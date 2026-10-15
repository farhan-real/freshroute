"""engine/freshroute_solver.py: Constrained Optimization Solver with Clearance Elasticity & LP Support."""

from collections import defaultdict
import time
from typing import Any, Dict, List, Literal, Tuple

import numpy as np
from scipy.optimize import linprog

from .models import (
    AllocationDecision,
    Batch,
    Destination,
    OptimizationSummary,
    TransportRoute,
    UncertaintyReport,
)


class FreshRouteSolver:
    """
    Intelligent Decision Engine:
    1. Feasibility: Enforces remaining_shelf_life >= travel_time + handling_time + min_safe_buffer.
    2. Targeted Dynamic Clearance: Applies calibrated discounts (0-25%) when arrival buffer < 12h
       to stimulate rapid mandi absorption and prevent commercial dock rejection.
    3. Clearance Elasticity: Models buyer absorption velocity when discounts are constrained.
    4. Dual Solver Support:
       - 'urgency_margin': Priority-Index greedy dispatch (fast, deterministic explainability).
       - 'lp_highs': Exact Linear Programming via SciPy HiGHS simplex/interior-point solver.
    """

    def __init__(
        self,
        min_safe_buffer_hrs: float = 2.0,
        discount_threshold_hrs: float = 12.0,
        max_discount_pct: float = 0.25,
        spoilage_penalty_per_kg: float = 5.0,
        solver_mode: Literal["urgency_margin", "lp_highs"] = "urgency_margin",
    ):
        if min_safe_buffer_hrs < 0:
            raise ValueError("min_safe_buffer_hrs must be non-negative.")
        if discount_threshold_hrs <= 0:
            raise ValueError("discount_threshold_hrs must be positive.")
        if not 0.0 <= max_discount_pct <= 1.0:
            raise ValueError("max_discount_pct must be between 0.0 and 1.0.")
        if spoilage_penalty_per_kg < 0:
            raise ValueError("spoilage_penalty_per_kg must be non-negative.")

        self.min_safe_buffer_hrs = min_safe_buffer_hrs
        self.discount_threshold_hrs = discount_threshold_hrs
        self.max_discount_pct = max_discount_pct
        self.spoilage_penalty_per_kg = spoilage_penalty_per_kg
        self.solver_mode = solver_mode

    def calculate_discount_and_clearance(self, buffer_hrs: float) -> Tuple[float, float, str]:
        """
        Calculates dynamic discount and expected market clearance rate.
        Disclosed Rule:
        - When arrival buffer >= 12.0h, 0% discount is required (100% clearance).
        - When 2.0h <= arrival buffer < 12.0h, urgency scales linearly:
          urgency = (12.0 - buffer) / 12.0.
        - Market requires at least `urgency * 20%` discount for 100% immediate absorption.
        """
        if buffer_hrs <= 0:
            return 0.0, 0.0, "EXPIRED"
        if buffer_hrs >= self.discount_threshold_hrs:
            return 0.0, 1.0, "Full Price (Adequate Buffer)"

        urgency = (self.discount_threshold_hrs - buffer_hrs) / self.discount_threshold_hrs
        required_clearance_discount = urgency * 0.20
        actual_discount = round(urgency * self.max_discount_pct, 2)

        if actual_discount >= required_clearance_discount:
            clearance_rate = 1.0
            reason = (
                f"Dynamic clearance {int(actual_discount * 100)}% applied: "
                "100% inventory cleared in time"
            )
        else:
            shortfall = required_clearance_discount - actual_discount
            clearance_rate = max(0.50, round(1.0 - (shortfall * 2.5), 2))
            reason = (
                f"Under-discounted ({int(actual_discount * 100)}% vs "
                f"{int(required_clearance_discount * 100)}% req): "
                f"only {int(clearance_rate * 100)}% cleared before expiry"
            )

        return actual_discount, clearance_rate, reason

    def _build_candidates(
        self,
        batches: List[Batch],
        destinations: List[Destination],
        route_map: Dict[Tuple[str, str], TransportRoute],
    ) -> List[Dict[str, Any]]:
        """Builds feasible (batch, destination) candidate arcs using O(B + D) commodity indexing."""
        dests_by_commodity: Dict[str, List[Destination]] = defaultdict(list)
        for d in destinations:
            dests_by_commodity[d.commodity].append(d)

        candidates: List[Dict[str, Any]] = []
        for b in batches:
            for d in dests_by_commodity.get(b.commodity, []):
                route = route_map.get((b.origin, d.dest_id))
                if not route:
                    continue

                total_transit_hrs = route.travel_time_hrs + d.handling_time_hrs
                buffer_hrs = b.remaining_shelf_life_hrs - total_transit_hrs
                if buffer_hrs < self.min_safe_buffer_hrs:
                    continue

                discount_pct, clearance_rate, discount_reason = (
                    self.calculate_discount_and_clearance(buffer_hrs)
                )
                effective_price = d.selling_price_per_kg * (1.0 - discount_pct)
                unit_margin = (
                    (effective_price * clearance_rate)
                    - route.cost_per_kg
                    - b.base_cost_per_kg
                    - ((1.0 - clearance_rate) * self.spoilage_penalty_per_kg)
                )

                if unit_margin <= 0:
                    continue

                urgency_multiplier = 1.0 + (3.0 / max(b.remaining_shelf_life_hrs, 1.0))
                priority_index = unit_margin * urgency_multiplier

                candidates.append(
                    {
                        "batch": b,
                        "dest": d,
                        "route": route,
                        "buffer_hrs": buffer_hrs,
                        "discount_pct": discount_pct,
                        "clearance_rate": clearance_rate,
                        "discount_reason": discount_reason,
                        "effective_price": effective_price,
                        "unit_margin": effective_price - route.cost_per_kg - b.base_cost_per_kg,
                        "net_unit_contribution": unit_margin,
                        "priority_index": priority_index,
                    }
                )

        candidates.sort(key=lambda x: x["priority_index"], reverse=True)
        return candidates

    def _allocate_lp(
        self,
        candidates: List[Dict[str, Any]],
        batches: List[Batch],
        destinations: List[Destination],
        routes: List[TransportRoute],
    ) -> List[Tuple[Dict[str, Any], float]]:
        """Solves exact global allocation using SciPy HiGHS Linear Programming."""
        if not candidates:
            return []

        n_vars = len(candidates)
        # Maximize priority-weighted net contribution (avoiding perishable warehouse expiration penalties)
        c = np.array(
            [
                -(
                    cand["net_unit_contribution"]
                    + (self.spoilage_penalty_per_kg if cand["batch"].remaining_shelf_life_hrs <= 24.0 else 0.0)
                    + 1e-3 * cand["priority_index"]
                )
                for cand in candidates
            ],
            dtype=float,
        )

        rows: List[np.ndarray] = []
        rhs: List[float] = []

        # 1. Batch supply constraints
        for b in batches:
            row = np.zeros(n_vars, dtype=float)
            has_arc = False
            for idx, cand in enumerate(candidates):
                if cand["batch"].batch_id == b.batch_id:
                    row[idx] = 1.0
                    has_arc = True
            if has_arc:
                rows.append(row)
                rhs.append(b.quantity_kg)

        # 2. Destination demand & reception capacity constraints
        for d in destinations:
            row = np.zeros(n_vars, dtype=float)
            has_arc = False
            for idx, cand in enumerate(candidates):
                if cand["dest"].dest_id == d.dest_id:
                    row[idx] = 1.0
                    has_arc = True
            if has_arc:
                cap_limit = (
                    min(d.demand_kg, d.max_reception_capacity_kg)
                    if d.max_reception_capacity_kg is not None
                    else d.demand_kg
                )
                rows.append(row)
                rhs.append(cap_limit)

        # 3. Route vehicle capacity constraints
        for r in routes:
            row = np.zeros(n_vars, dtype=float)
            has_arc = False
            for idx, cand in enumerate(candidates):
                if (cand["route"].origin, cand["route"].dest_id) == (r.origin, r.dest_id):
                    row[idx] = 1.0
                    has_arc = True
            if has_arc:
                rows.append(row)
                rhs.append(r.vehicle_capacity_kg)

        a_ub = np.vstack(rows) if rows else None
        b_ub = np.array(rhs, dtype=float) if rhs else None

        res = linprog(c, A_ub=a_ub, b_ub=b_ub, bounds=(0, None), method="highs")
        if not res.success or res.x is None:
            return []

        return [
            (cand, round(float(qty), 2))
            for cand, qty in zip(candidates, res.x)
            if qty > 1e-4
        ]

    def solve(
        self,
        batches: List[Batch],
        destinations: List[Destination],
        routes: List[TransportRoute],
    ) -> OptimizationSummary:
        start_ns = time.perf_counter_ns()

        route_map = {(r.origin, r.dest_id): r for r in routes}
        remaining_demand = {
            d.dest_id: (
                min(d.demand_kg, d.max_reception_capacity_kg)
                if d.max_reception_capacity_kg is not None
                else d.demand_kg
            )
            for d in destinations
        }
        remaining_route_cap = {(r.origin, r.dest_id): r.vehicle_capacity_kg for r in routes}
        total_inventory_kg = sum(b.quantity_kg for b in batches)

        candidates = self._build_candidates(batches, destinations, route_map)
        batch_remaining_qty = {b.batch_id: b.quantity_kg for b in batches}
        allocations: List[AllocationDecision] = []
        dispatched_kg = 0.0
        spoiled_kg = 0.0
        fulfilled_kg = 0.0

        if self.solver_mode == "lp_highs":
            planned_dispatch = self._allocate_lp(candidates, batches, destinations, routes)
        else:
            planned_dispatch = []
            for cand in candidates:
                b: Batch = cand["batch"]
                d: Destination = cand["dest"]
                r: TransportRoute = cand["route"]

                avail_b = batch_remaining_qty[b.batch_id]
                avail_d = remaining_demand[d.dest_id]
                avail_cap = remaining_route_cap[(r.origin, r.dest_id)]

                alloc_qty = min(avail_b, avail_d, avail_cap)
                if alloc_qty <= 0:
                    continue

                batch_remaining_qty[b.batch_id] -= alloc_qty
                remaining_demand[d.dest_id] -= alloc_qty
                remaining_route_cap[(r.origin, r.dest_id)] -= alloc_qty
                planned_dispatch.append((cand, alloc_qty))

        if self.solver_mode == "lp_highs":
            for cand, alloc_qty in planned_dispatch:
                batch_remaining_qty[cand["batch"].batch_id] -= alloc_qty

        for cand, alloc_qty in planned_dispatch:
            b = cand["batch"]
            d = cand["dest"]
            r = cand["route"]

            clearance = cand["clearance_rate"]
            sold_qty = alloc_qty * clearance
            unsold_spoiled_qty = alloc_qty * (1.0 - clearance)

            spoiled_kg += unsold_spoiled_qty
            fulfilled_kg += sold_qty
            dispatched_kg += alloc_qty

            gross = sold_qty * cand["effective_price"]
            t_cost = alloc_qty * r.cost_per_kg
            p_cost = alloc_qty * b.base_cost_per_kg
            net = gross - t_cost - p_cost

            reason = (
                f"FreshRoute: Margin \u20b9{cand['unit_margin']:.1f}/kg. "
                f"Buffer {cand['buffer_hrs']:.1f}h. {cand['discount_reason']}."
            )

            allocations.append(
                AllocationDecision(
                    batch_id=b.batch_id,
                    dest_id=d.dest_id,
                    commodity=b.commodity,
                    quantity_kg=alloc_qty,
                    sold_qty_kg=round(sold_qty, 2),
                    clearance_rate=clearance,
                    travel_time_hrs=r.travel_time_hrs,
                    remaining_shelf_life_hrs=b.remaining_shelf_life_hrs,
                    shelf_life_buffer_hrs=round(cand["buffer_hrs"], 1),
                    base_price_per_kg=d.selling_price_per_kg,
                    discount_pct=cand["discount_pct"],
                    final_price_per_kg=round(cand["effective_price"], 2),
                    transport_cost_per_kg=r.cost_per_kg,
                    base_cost_per_kg=b.base_cost_per_kg,
                    gross_revenue=round(gross, 2),
                    transport_cost_total=round(t_cost, 2),
                    procurement_cost_total=round(p_cost, 2),
                    net_profit=round(net, 2),
                    reason=reason,
                )
            )

        # Unallocated inventory expiring in warehouse within 24h planning horizon
        for b in batches:
            rem = max(0.0, batch_remaining_qty[b.batch_id])
            if rem > 0 and b.remaining_shelf_life_hrs <= 24.0:
                spoiled_kg += rem

        unsold_unspoiled = max(0.0, total_inventory_kg - dispatched_kg - spoiled_kg)

        tot_gross = sum(a.gross_revenue for a in allocations)
        tot_trans = sum(a.transport_cost_total for a in allocations)
        tot_proc = sum(a.procurement_cost_total for a in allocations)
        waste_penalty = spoiled_kg * self.spoilage_penalty_per_kg
        net_profit = tot_gross - tot_trans - tot_proc - waste_penalty

        total_demand = sum(d.demand_kg for d in destinations)
        fulfillment_pct = (fulfilled_kg / total_demand * 100.0) if total_demand > 0 else 0.0
        spoilage_pct = (spoiled_kg / total_inventory_kg * 100.0) if total_inventory_kg > 0 else 0.0
        elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0

        return OptimizationSummary(
            strategy_name="FreshRoute Intelligent Engine",
            total_inventory_kg=total_inventory_kg,
            dispatched_kg=round(dispatched_kg, 1),
            spoiled_kg=round(spoiled_kg, 1),
            unsold_unspoiled_kg=round(unsold_unspoiled, 1),
            spoilage_rate_pct=round(spoilage_pct, 2),
            demand_fulfillment_pct=round(fulfillment_pct, 2),
            total_gross_revenue=round(tot_gross, 2),
            total_transport_cost=round(tot_trans, 2),
            total_procurement_cost=round(tot_proc, 2),
            disposal_waste_cost=round(waste_penalty, 2),
            net_profit=round(net_profit, 2),
            solve_time_ms=round(elapsed_ms, 3),
            allocations=allocations,
        )

    def evaluate_uncertainty(
        self,
        batches: List[Batch],
        destinations: List[Destination],
        routes: List[TransportRoute],
        runs: int = 50,
        shelf_life_noise_pct: float = 0.10,
        transit_noise_pct: float = 0.15,
        demand_noise_pct: float = 0.10,
        seed: int = 42,
    ) -> UncertaintyReport:
        """
        PS 07 Optional Extension: Monte Carlo sensitivity evaluation across uncertainty ranges
        in remaining shelf life, highway travel times, and destination demand.
        """
        rng = np.random.default_rng(seed)
        profits: List[float] = []
        spoilages: List[float] = []
        fulfillments: List[float] = []

        for _ in range(runs):
            sim_batches = [
                b.model_copy(
                    update={
                        "remaining_shelf_life_hrs": max(
                            1.0,
                            round(
                                b.remaining_shelf_life_hrs
                                * float(rng.uniform(1.0 - shelf_life_noise_pct, 1.0 + shelf_life_noise_pct)),
                                2,
                            ),
                        )
                    }
                )
                for b in batches
            ]
            sim_routes = [
                r.model_copy(
                    update={
                        "travel_time_hrs": max(
                            0.5,
                            round(
                                r.travel_time_hrs
                                * float(rng.uniform(1.0 - transit_noise_pct, 1.0 + transit_noise_pct)),
                                2,
                            ),
                        )
                    }
                )
                for r in routes
            ]
            sim_dests = [
                d.model_copy(
                    update={
                        "demand_kg": max(
                            0.0,
                            round(
                                d.demand_kg
                                * float(rng.uniform(1.0 - demand_noise_pct, 1.0 + demand_noise_pct)),
                                2,
                            ),
                        )
                    }
                )
                for d in destinations
            ]

            res = self.solve(sim_batches, sim_dests, sim_routes)
            profits.append(res.net_profit)
            spoilages.append(res.spoilage_rate_pct)
            fulfillments.append(res.demand_fulfillment_pct)

        arr_p = np.array(profits, dtype=float)
        return UncertaintyReport(
            runs=runs,
            mean_net_profit=round(float(np.mean(arr_p)), 2),
            std_net_profit=round(float(np.std(arr_p)), 2),
            p5_net_profit=round(float(np.percentile(arr_p, 5)), 2),
            p95_net_profit=round(float(np.percentile(arr_p, 95)), 2),
            mean_spoilage_pct=round(float(np.mean(spoilages)), 2),
            mean_fulfillment_pct=round(float(np.mean(fulfillments)), 2),
        )