"""engine/baseline_solver.py: Realistic Naive FIFO Dispatcher."""

from typing import List, Dict
from .models import Batch, Destination, TransportRoute, AllocationDecision, OptimizationSummary


class BaselineSolver:
    """
    Standard naive baseline:
    - Dispatches oldest batches first (FIFO) to fulfill orders in order of destination demand.
    - Zero dynamic discounting.
    - Retail inspection: Shipments arriving with < 6.0h shelf-life buffer without discounting
      fail commercial inspection and are rejected at the dock as spoiled.
    """

    def __init__(self, min_retail_buffer_hrs: float = 6.0, spoilage_penalty_per_kg: float = 5.0):
        self.min_retail_buffer_hrs = min_retail_buffer_hrs
        self.spoilage_penalty_per_kg = spoilage_penalty_per_kg

    def solve(
        self,
        batches: List[Batch],
        destinations: List[Destination],
        routes: List[TransportRoute]
    ) -> OptimizationSummary:
        route_map = {(r.origin, r.dest_id): r for r in routes}
        remaining_demand = {d.dest_id: d.demand_kg for d in destinations}
        total_inventory_kg = sum(b.quantity_kg for b in batches)

        # FIFO: oldest batches dispatched first
        sorted_batches = sorted(batches, key=lambda b: b.remaining_shelf_life_hrs)
        allocations: List[AllocationDecision] = []
        dispatched_kg = 0.0
        spoiled_kg = 0.0

        for batch in sorted_batches:
            batch_qty = batch.quantity_kg

            candidate_dests = [
                d for d in destinations
                if d.commodity == batch.commodity and remaining_demand[d.dest_id] > 0
            ]

            for dest in candidate_dests:
                if batch_qty <= 0:
                    break

                route = route_map.get((batch.origin, dest.dest_id))
                if not route:
                    continue

                alloc_qty = min(batch_qty, remaining_demand[dest.dest_id])
                if alloc_qty <= 0:
                    continue

                travel_time = route.travel_time_hrs
                total_time_to_shelf = travel_time + dest.handling_time_hrs
                buffer = batch.remaining_shelf_life_hrs - total_time_to_shelf

                discount = 0.0
                final_price = dest.selling_price_per_kg

                # Retail quality check: In real logistics, if buffer < 6.0h and no clearance discount,
                # the shipment is rejected at the dock and dumped as spoilage.
                if buffer < self.min_retail_buffer_hrs:
                    spoiled_kg += alloc_qty
                    reason = f"REJECTED/SPOILED: Arrived with insufficient buffer ({buffer:.1f}h < {self.min_retail_buffer_hrs}h contracted window)."
                    gross_rev = 0.0
                else:
                    gross_rev = alloc_qty * final_price
                    reason = f"Dispatched via naive FIFO to {dest.name}."

                t_cost = alloc_qty * route.cost_per_kg
                p_cost = alloc_qty * batch.base_cost_per_kg
                net = gross_rev - t_cost - p_cost

                allocations.append(AllocationDecision(
                    batch_id=batch.batch_id,
                    dest_id=dest.dest_id,
                    commodity=batch.commodity,
                    quantity_kg=alloc_qty,
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
                    reason=reason
                ))

                remaining_demand[dest.dest_id] -= alloc_qty
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
        fulfilled = sum(a.quantity_kg for a in allocations if a.shelf_life_buffer_hrs >= self.min_retail_buffer_hrs)
        fulfillment_pct = (fulfilled / total_demand * 100) if total_demand > 0 else 0
        spoilage_pct = (spoiled_kg / total_inventory_kg * 100) if total_inventory_kg > 0 else 0

        return OptimizationSummary(
            strategy_name="Baseline (Naive FIFO)",
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