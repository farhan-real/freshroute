"""engine/freshroute_solver.py: Intelligent Constrained Optimization Solver with Clearance Elasticity."""

from typing import List, Dict, Tuple
from .models import Batch, Destination, TransportRoute, AllocationDecision, OptimizationSummary


class FreshRouteSolver:
    """
    Intelligent Decision Engine:
    1. Feasibility: Ensures remaining_shelf_life >= travel_time + handling_time + min_safe_buffer (2h).
    2. Targeted Dynamic Clearance: Applies calibrated discounts (0-25%) when buffer is tight (< 12h)
       to guarantee mandi absorption and prevent spoilage.
    3. Clearance Elasticity: If discount is too low on tight-buffer produce, buyers do not absorb
       the stock fast enough, causing unsold produce to spoil.
    4. Profit Optimization: Balances margin retention vs. clearance velocity to find the optimal price.
    """

    def __init__(
        self,
        min_safe_buffer_hrs: float = 2.0,
        discount_threshold_hrs: float = 12.0,
        max_discount_pct: float = 0.25,
        spoilage_penalty_per_kg: float = 5.0
    ):
        self.min_safe_buffer_hrs = min_safe_buffer_hrs
        self.discount_threshold_hrs = discount_threshold_hrs
        self.max_discount_pct = max_discount_pct
        self.spoilage_penalty_per_kg = spoilage_penalty_per_kg

    def calculate_discount_and_clearance(self, buffer_hrs: float) -> Tuple[float, float, str]:
        """
        Calculates dynamic discount and expected market clearance rate.
        If buffer is tight (< 12h), the market requires a minimum incentive to clear inventory in time.
        """
        if buffer_hrs <= 0:
            return 0.0, 0.0, "EXPIRED"
        if buffer_hrs >= self.discount_threshold_hrs:
            # Full buffer: 100% clearance at full price
            return 0.0, 1.0, "Full Price (Adequate Buffer)"
        
        # Urgency factor (0.0 to 1.0)
        urgency = (self.discount_threshold_hrs - buffer_hrs) / self.discount_threshold_hrs
        
        # Minimum discount market expects to absorb near-expiry stock fast
        required_clearance_discount = urgency * 0.20
        
        # Actual discount applied by distributor's policy
        actual_discount = round(urgency * self.max_discount_pct, 2)
        
        # Clearance elasticity: If distributor under-discounts, market clearance drops
        if actual_discount >= required_clearance_discount:
            clearance_rate = 1.0
            reason = f"Dynamic clearance {int(actual_discount*100)}% applied: 100% inventory cleared in time"
        else:
            # Under-discounting penalty: produce sells too slowly and a fraction spoils
            shortfall = required_clearance_discount - actual_discount
            clearance_rate = max(0.50, round(1.0 - (shortfall * 2.5), 2))
            reason = f"Under-discounted ({int(actual_discount*100)}% vs {int(required_clearance_discount*100)}% req): only {int(clearance_rate*100)}% cleared before expiry"

        return actual_discount, clearance_rate, reason

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

                if buffer_hrs < self.min_safe_buffer_hrs:
                    continue

                discount_pct, clearance_rate, discount_reason = self.calculate_discount_and_clearance(buffer_hrs)
                effective_price = d.selling_price_per_kg * (1.0 - discount_pct)
                unit_margin = effective_price - route.cost_per_kg - b.base_cost_per_kg

                if unit_margin <= 0:
                    continue

                urgency_multiplier = 1.0 + (3.0 / max(b.remaining_shelf_life_hrs, 1.0))
                priority_index = unit_margin * urgency_multiplier

                candidates.append({
                    "batch": b,
                    "dest": d,
                    "route": route,
                    "buffer_hrs": buffer_hrs,
                    "discount_pct": discount_pct,
                    "clearance_rate": clearance_rate,
                    "discount_reason": discount_reason,
                    "effective_price": effective_price,
                    "unit_margin": unit_margin,
                    "priority_index": priority_index
                })

        candidates.sort(key=lambda x: x["priority_index"], reverse=True)

        batch_remaining_qty = {b.batch_id: b.quantity_kg for b in batches}
        allocations: List[AllocationDecision] = []
        dispatched_kg = 0.0
        spoiled_kg = 0.0

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

            clearance = cand["clearance_rate"]
            sold_qty = alloc_qty * clearance
            unsold_spoiled_qty = alloc_qty * (1.0 - clearance)

            spoiled_kg += unsold_spoiled_qty

            gross = sold_qty * cand["effective_price"]
            t_cost = alloc_qty * r.cost_per_kg
            p_cost = alloc_qty * b.base_cost_per_kg
            net = gross - t_cost - p_cost

            reason = (
                f"FreshRoute: Margin ₹{cand['unit_margin']:.1f}/kg. "
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

        # Unallocated inventory expiring in warehouse
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
        fulfilled_kg = sum(a.quantity_kg * cand["clearance_rate"] for a, cand in zip(allocations, candidates[:len(allocations)]))
        fulfillment_pct = (fulfilled_kg / total_demand * 100) if total_demand > 0 else 0
        spoilage_pct = (spoiled_kg / total_inventory_kg * 100) if total_inventory_kg > 0 else 0

        return OptimizationSummary(
            strategy_name="FreshRoute Intelligent Engine",
            total_inventory_kg=total_inventory_kg,
            dispatched_kg=dispatched_kg,
            spoiled_kg=round(spoiled_kg, 1),
            unsold_unspoiled_kg=round(unsold_unspoiled, 1),
            spoilage_rate_pct=round(spoilage_pct, 2),
            demand_fulfillment_pct=round(fulfillment_pct, 2),
            total_gross_revenue=round(tot_gross, 2),
            total_transport_cost=round(tot_trans, 2),
            total_procurement_cost=round(tot_proc, 2),
            disposal_waste_cost=round(waste_penalty, 2),
            net_profit=round(net_profit, 2),
            allocations=allocations
        )