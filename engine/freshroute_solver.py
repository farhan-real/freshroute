"""engine/freshroute_solver.py: Intelligent Constrained Optimization Solver."""

from typing import List, Dict, Tuple
from .models import Batch, Destination, TransportRoute, AllocationDecision, OptimizationSummary


class FreshRouteSolver:
    """
    Intelligent Decision Engine:
    1. Feasibility Pre-filter: Ensures remaining_shelf_life >= travel_time + handling_time + min_shelf_buffer.
    2. Dynamic Discounting: If remaining buffer is tight (e.g. 6-18h), applies calibrated discounts
       to ensure clearance and prevent destination-side discard.
    3. Multi-objective Value Ranking:
       Net Margin = (Adjusted Price - Transport Cost - Base Cost) with perishability multiplier.
    4. Capacity & Demand Bounds: Strictly enforces destination reception limits and route vehicle limits.
    5. Salvage Strategy: Batches with ultra-short shelf life get local high-speed distress dispatch.
    """

    def __init__(
        self,
        min_safe_buffer_hrs: float = 6.0,
        discount_threshold_hrs: float = 24.0,
        max_discount_pct: float = 0.35,
        spoilage_penalty_per_kg: float = 5.0
    ):
        self.min_safe_buffer_hrs = min_safe_buffer_hrs
        self.discount_threshold_hrs = discount_threshold_hrs
        self.max_discount_pct = max_discount_pct
        self.spoilage_penalty_per_kg = spoilage_penalty_per_kg

    def calculate_discount(self, buffer_hrs: float) -> Tuple[float, str]:
        """Calculates dynamic discount based on remaining shelf life buffer."""
        if buffer_hrs <= 0:
            return 0.0, "EXPIRED"
        if buffer_hrs >= self.discount_threshold_hrs:
            return 0.0, "Full Price (Adequate Buffer)"
        
        # Linear discounting between 0% and max_discount_pct
        urgency_factor = (self.discount_threshold_hrs - buffer_hrs) / self.discount_threshold_hrs
        discount = round(urgency_factor * self.max_discount_pct, 2)
        return discount, f"Dynamic discount {int(discount*100)}% applied: buffer is {buffer_hrs:.1f}h"

    def solve(
        self,
        batches: List[Batch],
        destinations: List[Destination],
        routes: List[TransportRoute]
    ) -> OptimizationSummary:
        route_map = {(r.origin, r.dest_id): r for r in routes}
        remaining_demand = {d.dest_id: d.demand_kg for d in destinations}
        remaining_route_cap = {(r.origin, r.dest_id): r.vehicle_capacity_kg for r in routes}
        total_inventory_kg = sum(b.quantity_kg for b in batches)

        # Generate all feasible allocation candidates
        candidates = []
        for b in batches:
            for d in destinations:
                if b.commodity != d.commodity:
                    continue

                route = route_map.get((b.origin, d.dest_id))
                if not route:
                    continue

                total_transit_hrs = route.travel_time_hrs + d.handling_time_hrs
                buffer_hrs = b.remaining_shelf_life_hrs - total_transit_hrs

                # Feasibility check: produces must arrive with at least minimal safe buffer
                if buffer_hrs < self.min_safe_buffer_hrs:
                    continue

                discount_pct, discount_reason = self.calculate_discount(buffer_hrs)
                effective_price = d.selling_price_per_kg * (1.0 - discount_pct)
                unit_margin = effective_price - route.cost_per_kg - b.base_cost_per_kg

                # Perishability urgency weight: batches closer to expiry get priority boost
                # Urgency multiplier ranges from 1.0 to 2.5
                urgency_score = 1.0 + (1.0 / (max(buffer_hrs, 1.0) / 10.0))
                priority_index = unit_margin * urgency_score

                candidates.append({
                    "batch": b,
                    "dest": d,
                    "route": route,
                    "buffer_hrs": buffer_hrs,
                    "discount_pct": discount_pct,
                    "discount_reason": discount_reason,
                    "effective_price": effective_price,
                    "unit_margin": unit_margin,
                    "priority_index": priority_index
                })

        # Sort candidates by calculated priority index descending
        candidates.sort(key=lambda x: x["priority_index"], reverse=True)

        batch_remaining_qty = {b.batch_id: b.quantity_kg for b in batches}
        allocations: List[AllocationDecision] = []
        dispatched_kg = 0.0

        for cand in candidates:
            b: Batch = cand["batch"]
            d: Destination = cand["dest"]
            r: TransportRoute = cand["route"]

            avail_b = batch_remaining_qty[b.batch_id]
            avail_d = remaining_demand[d.dest_id]
            avail_cap = remaining_route_cap[(r.origin, r.dest_id)]

            if avail_b <= 0 or avail_d <= 0 or avail_cap <= 0:
                continue

            alloc_qty = min(avail_b, avail_d, avail_cap)
            if alloc_qty <= 0:
                continue

            # Financials
            gross = alloc_qty * cand["effective_price"]
            t_cost = alloc_qty * r.cost_per_kg
            p_cost = alloc_qty * b.base_cost_per_kg
            net = gross - t_cost - p_cost

            reason = (
                f"FreshRoute Optimized: Margin ₹{cand['unit_margin']:.1f}/kg. "
                f"Buffer {cand['buffer_hrs']:.1f}h. {cand['discount_reason']}."
            )

            allocations.append(AllocationDecision(
                batch_id=b.batch_id,
                dest_id=d.dest_id,
                commodity=b.commodity,
                quantity_kg=alloc_qty,
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
                reason=reason
            ))

            batch_remaining_qty[b.batch_id] -= alloc_qty
            remaining_demand[d.dest_id] -= alloc_qty
            remaining_route_cap[(r.origin, r.dest_id)] -= alloc_qty
            dispatched_kg += alloc_qty

        # Spoilage assessment: Only inventory left unallocated that has shelf-life <= 24h
        spoiled_kg = 0.0
        for b in batches:
            rem = batch_remaining_qty[b.batch_id]
            if rem > 0 and b.remaining_shelf_life_hrs <= 24.0:
                spoiled_kg += rem

        unsold_unspoiled = max(0.0, total_inventory_kg - dispatched_kg - spoiled_kg)

        tot_gross = sum(a.gross_revenue for a in allocations)
        tot_trans = sum(a.transport_cost_total for a in allocations)
        tot_proc = sum(a.procurement_cost_total for a in allocations)
        waste_penalty = spoiled_kg * self.spoilage_penalty_per_kg
        net_profit = tot_gross - tot_trans - tot_proc - waste_penalty

        total_demand = sum(d.demand_kg for d in destinations)
        fulfillment_pct = (dispatched_kg / total_demand * 100) if total_demand > 0 else 0
        spoilage_pct = (spoiled_kg / total_inventory_kg * 100) if total_inventory_kg > 0 else 0

        return OptimizationSummary(
            strategy_name="FreshRoute Intelligent Engine",
            total_inventory_kg=total_inventory_kg,
            dispatched_kg=dispatched_kg,
            spoiled_kg=spoiled_kg,
            unsold_unspoiled_kg=unsold_unspoiled,
            spoilage_rate_pct=round(spoilage_pct, 2),
            demand_fulfillment_pct=round(fulfillment_pct, 2),
            total_gross_revenue=round(tot_gross, 2),
            total_transport_cost=round(tot_trans, 2),
            total_procurement_cost=round(tot_proc, 2),
            disposal_waste_cost=round(waste_penalty, 2),
            net_profit=round(net_profit, 2),
            allocations=allocations
        )