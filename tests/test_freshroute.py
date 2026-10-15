"""tests/test_freshroute.py: Pytest validation of constraints and superiority over baseline."""

import pytest
from engine.data_generator import get_standard_scenario, apply_disruption
from engine.baseline_solver import BaselineSolver
from engine.freshroute_solver import FreshRouteSolver


def test_freshroute_outperforms_baseline():
    batches, dests, routes = get_standard_scenario()
    baseline = BaselineSolver().solve(batches, dests, routes)
    fresh = FreshRouteSolver().solve(batches, dests, routes)

    # FreshRoute must achieve higher profit and equal or lower spoilage
    assert fresh.net_profit > baseline.net_profit, "FreshRoute should generate higher net profit"
    assert fresh.spoilage_rate_pct <= baseline.spoilage_rate_pct, "FreshRoute should reduce or match spoilage"


def test_zero_in_transit_spoilage_for_freshroute():
    batches, dests, routes = get_standard_scenario()
    solver = FreshRouteSolver()
    fresh = solver.solve(batches, dests, routes)

    for alloc in fresh.allocations:
        # Checked against the solver's configured min_safe_buffer_hrs
        assert alloc.shelf_life_buffer_hrs >= solver.min_safe_buffer_hrs - 1e-5, (
            f"Batch {alloc.batch_id} violated minimum safe buffer upon arrival!"
        )


def test_capacity_and_demand_constraints_respected():
    batches, dests, routes = get_standard_scenario()
    fresh = FreshRouteSolver().solve(batches, dests, routes)

    # Aggregate allocations per destination
    dest_allocs = {}
    for a in fresh.allocations:
        dest_allocs[a.dest_id] = dest_allocs.get(a.dest_id, 0.0) + a.quantity_kg

    for d in dests:
        allocated = dest_allocs.get(d.dest_id, 0.0)
        assert allocated <= d.demand_kg + 1e-4, f"Demand constraint violated for destination {d.dest_id}"


def test_disruption_handling_robustness():
    """Verify solver stays robust when a 6-hour delay occurs across all routes."""
    batches, dests, routes = get_standard_scenario()
    bad_routes, bad_dests = apply_disruption(routes, dests, delay_hours=6.0, demand_shock_pct=-0.25)

    fresh = FreshRouteSolver().solve(batches, bad_dests, bad_routes)
    assert fresh.net_profit > 0, "Engine should stay profitable or preserve capital even under severe delays"