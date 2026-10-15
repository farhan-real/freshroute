"""engine/baseline_solver.py: Realistic Naive FIFO Dispatcher with O(B + D) pre-indexed lookup."""

from collections import defaultdict
import time
from typing import Dict, List

from .models import (
    AllocationDecision,
    Batch,
    Destination,
    OptimizationSummary,
    TransportRoute,
)


class BaselineSolver:
    """
    Standard naive baseline:
    - Dispatches oldest batches first (FIFO) to fulfill orders in order of destination appearance.
    - Respects physical vehicle capacity and dock reception constraints.
    - Zero dynamic discounting.
    - Retail dock inspection: Shipments arriving with < 6.0h shelf-life buffer without clearance
      discounting fail commercial inspection and are rejected at the dock as spoiled.
    """

    def __init__(self, min_retail_buffer_hrs: float = 6.0, spoilage_penalty_per_kg: float = 5.0):
        if min_retail_buffer_hrs < 0:
            raise ValueError("min_retail_buffer_hrs must be non-negative.")
        if spoilage_penalty_per_kg < 0:
            raise ValueError("spoilage_penalty_per_kg must be non-negative.")
        self.min_retail_buffer_hrs = min_retail_buffer_hrs
        self.spoilage_penalty_per_kg = spoilage_penalty_per_kg

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

        dests_by_commodity: Dict[str, List[Destination]] = defaultdict(list)
        for d in destinations:
            dests_by_commodity[d.commodity].append(d)

        sorted_batches = sorted(batches, key=lambda b: b.remaining_shelf_life_hrs)
        allocations: List[AllocationDecision] = []
        dispatched_kg = 0.0
        spoiled_kg = 0.0

        for batch in sorted_batches:
            batch_qty = batch.quantity_kg
            candidate_dests = dests_by_commodity.get(batch.commodity, [])

            for dest in candidate_dests:
                if batch_qty <= 0:
                    break

                avail_demand = remaining_demand[dest.dest_id]
                if avail_demand <= 0:
                    continue

                route = route_map.get((batch.origin, dest.dest_id))
                if not route:
                    continue

                avail_cap = remaining_route_cap[(batch.origin, dest.dest_id)]
                if avail_cap <= 0:
                    continue

                alloc_qty = min(batch_qty, avail_demand, avail_cap)
                if alloc_qty <= 0:
                    continue

                travel_time = route.travel_time_hrs
                total_time_to_shelf = travel_time + dest.handling_time_hrs
                buffer = batch.remaining_shelf_life_hrs - total_time_to_shelf

                discount = 0.0
                final_price = dest.selling_price_per_kg

                if buffer < self.min_retail_buffer_hrs:
                    spoiled_kg += alloc_qty
                    sold_qty = 0.0
                    clearance_rate = 0.0
                    reason = (
                        f"REJECTED/SPOILED: Arrived with insufficient buffer "
                        f"({buffer:.1f}h < {self.min_retail_buffer_hrs}h contracted window)."
                    )
                    gross_rev = 0.0
                else:
                    sold_qty = alloc_qty
                    clearance_rate = 1.0
                    gross_rev = alloc_qty * final_price
                    reason = f"Dispatched via naive FIFO to {dest.name}."

                t_cost = alloc_qty * route.cost_per_kg
                p_cost = alloc_qty * batch.base_cost_per_kg
                net = gross_rev - t_cost - p_cost

                allocations.append(
                    AllocationDecision(
                        batch_id=batch.batch_id,
                        dest_id=dest.dest_id,
                        commodity=batch.commodity,
                        quantity_kg=alloc_qty,
                        sold_qty_kg=sold_qty,
                        clearance_rate=clearance_rate,
                        travel_time_hrs=travel_time,
                        remaining_shelf_life_hrs=batch.remaining_shelf_life_hrs,
                        shelf_life_buffer_hrs=round(buffer, 1),
                        base_price_per_kg=dest.selling_price_per_kg,
                        discount_pct=discount,
                        final_price_per_kg=final_price,
                        transport_cost_per_kg=route.cost_per_kg,
                        base_cost_per_kg=batch.base_cost_per_kg,
                        gross_revenue=round(gross_rev, 2),
                        transport_cost_total=round(t_cost, 2),
                        procurement_cost_total=round(p_cost, 2),
                        net_profit=round(net, 2),
                        reason=reason,
                    )
                )

                remaining_demand[dest.dest_id] -= alloc_qty
                remaining_route_cap[(batch.origin, dest.dest_id)] -= alloc_qty
                batch_qty -= alloc_qty
                dispatched_kg += alloc_qty

            if batch_qty > 0 and batch.remaining_shelf_life_hrs <= 24.0:
                spoiled_kg += batch_qty

        unsold_unspoiled = max(0.0, total_inventory_kg - dispatched_kg)
        tot_gross = sum(a.gross_revenue for a in allocations)
        tot_trans = sum(a.transport_cost_total for a in allocations)
        tot_proc = sum(a.procurement_cost_total for a in allocations)
        waste_penalty = spoiled_kg * self.spoilage_penalty_per_kg
        net_profit = tot_gross - tot_trans - tot_proc - waste_penalty

        total_demand = sum(d.demand_kg for d in destinations)
        fulfilled = sum(a.sold_qty_kg for a in allocations)
        fulfillment_pct = (fulfilled / total_demand * 100.0) if total_demand > 0 else 0.0
        spoilage_pct = (spoiled_kg / total_inventory_kg * 100.0) if total_inventory_kg > 0 else 0.0
        elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0

        return OptimizationSummary(
            strategy_name="Baseline (Naive FIFO)",
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
            rejected_routes=[],
        )