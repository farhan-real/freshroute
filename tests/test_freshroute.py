"""tests/test_freshroute.py: Comprehensive test suite covering constraints, LP, security, and edge cases."""

import pytest
from pydantic import ValidationError

from engine.baseline_solver import BaselineSolver
from engine.data_generator import (
    apply_disruption,
    apply_temperature_excursion,
    get_standard_scenario,
)
from engine.explainability import DecisionExplainer, format_inr, sanitize_csv_value
from engine.freshroute_solver import FreshRouteSolver
from engine.models import Batch, Destination, TransportRoute


def test_freshroute_outperforms_baseline():
    batches, dests, routes = get_standard_scenario()
    baseline = BaselineSolver().solve(batches, dests, routes)
    fresh = FreshRouteSolver().solve(batches, dests, routes)

    assert fresh.net_profit > baseline.net_profit, "FreshRoute should generate higher net profit"
    assert fresh.spoilage_rate_pct <= baseline.spoilage_rate_pct, "FreshRoute should reduce or match spoilage"
    assert fresh.net_profit == pytest.approx(502497.0, rel=1e-4)
    assert baseline.net_profit == pytest.approx(321690.0, rel=1e-4)


def test_zero_in_transit_spoilage_for_freshroute():
    batches, dests, routes = get_standard_scenario()
    solver = FreshRouteSolver()
    fresh = solver.solve(batches, dests, routes)

    for alloc in fresh.allocations:
        assert alloc.shelf_life_buffer_hrs >= solver.min_safe_buffer_hrs - 1e-5, (
            f"Batch {alloc.batch_id} violated minimum safe buffer upon arrival!"
        )


def test_capacity_and_demand_constraints_respected():
    batches, dests, routes = get_standard_scenario()
    fresh = FreshRouteSolver().solve(batches, dests, routes)

    dest_allocs = {}
    route_allocs = {}
    for a in fresh.allocations:
        dest_allocs[a.dest_id] = dest_allocs.get(a.dest_id, 0.0) + a.quantity_kg
        route_allocs[a.dest_id] = route_allocs.get(a.dest_id, 0.0) + a.quantity_kg

    for d in dests:
        allocated = dest_allocs.get(d.dest_id, 0.0)
        assert allocated <= d.demand_kg + 1e-4, f"Demand constraint violated for destination {d.dest_id}"

    for r in routes:
        allocated = route_allocs.get(r.dest_id, 0.0)
        assert allocated <= r.vehicle_capacity_kg + 1e-4, f"Vehicle capacity violated for route {r.dest_id}"


def test_disruption_handling_robustness():
    """Verify solver stays robust when a 6-hour delay occurs across all routes."""
    batches, dests, routes = get_standard_scenario()
    bad_routes, bad_dests = apply_disruption(routes, dests, delay_hours=6.0, demand_shock_pct=-0.25)

    fresh = FreshRouteSolver().solve(batches, bad_dests, bad_routes)
    assert fresh.net_profit > 0, "Engine should stay profitable or preserve capital even under severe delays"


def test_lp_highs_solver_mode():
    """Verify SciPy HiGHS Linear Programming mode satisfies all constraints and beats baseline."""
    batches, dests, routes = get_standard_scenario()
    baseline = BaselineSolver().solve(batches, dests, routes)
    lp_res = FreshRouteSolver(solver_mode="lp_highs").solve(batches, dests, routes)

    assert lp_res.net_profit >= baseline.net_profit
    assert lp_res.spoilage_rate_pct == 0.0
    assert lp_res.demand_fulfillment_pct > baseline.demand_fulfillment_pct


def test_max_reception_capacity_enforced():
    """Verify destination max_reception_capacity_kg constraint caps allocations below demand_kg."""
    batches = [
        Batch(
            batch_id="B-TOM-CAP",
            commodity="Tomato",
            quantity_kg=3000,
            remaining_shelf_life_hrs=24.0,
            base_cost_per_kg=10.0,
            origin="Hub-A",
        )
    ]
    dests = [
        Destination(
            dest_id="D-1",
            name="Capped Market",
            commodity="Tomato",
            demand_kg=2500,
            selling_price_per_kg=30.0,
            handling_time_hrs=1.0,
            max_reception_capacity_kg=1200.0,
        )
    ]
    routes = [
        TransportRoute(
            origin="Hub-A", dest_id="D-1", travel_time_hrs=2.0, cost_per_kg=2.0, vehicle_capacity_kg=5000.0
        )
    ]
    res = FreshRouteSolver().solve(batches, dests, routes)
    assert res.dispatched_kg == pytest.approx(1200.0)


def test_clearance_elasticity_and_fulfillment_alignment():
    """Verify fulfillment_pct accurately reflects sold_qty_kg when candidates are skipped."""
    batches, dests, routes = get_standard_scenario()
    solver = FreshRouteSolver(max_discount_pct=0.05)
    res = solver.solve(batches, dests, routes)

    total_demand = sum(d.demand_kg for d in dests)
    expected_fulfillment = round(sum(a.sold_qty_kg for a in res.allocations) / total_demand * 100.0, 2)
    assert res.demand_fulfillment_pct == pytest.approx(expected_fulfillment, abs=1e-2)


def test_temperature_excursion_decay():
    """Verify Q10 thermal excursion reduces shelf life of perishable produce."""
    batches, _, _ = get_standard_scenario()
    heated = apply_temperature_excursion(batches, ambient_temp_c=14.0, reference_temp_c=4.0, q10_factor=2.0)

    assert heated[0].remaining_shelf_life_hrs == pytest.approx(batches[0].remaining_shelf_life_hrs / 2.0, abs=0.1)


def test_monte_carlo_uncertainty_evaluation():
    """Verify Monte Carlo uncertainty simulator returns bounded statistical metrics."""
    batches, dests, routes = get_standard_scenario()
    report = FreshRouteSolver().evaluate_uncertainty(batches, dests, routes, runs=15, seed=123)

    assert report.runs == 15
    assert report.p5_net_profit <= report.mean_net_profit <= report.p95_net_profit
    assert 0.0 <= report.mean_spoilage_pct <= 100.0


def test_csv_injection_sanitization():
    """Verify formula payloads are neutralized during CSV export generation."""
    assert sanitize_csv_value("=cmd|' /C calc'!A0") == "'=cmd|' /C calc'!A0"
    assert sanitize_csv_value("+SUM(A1:A10)") == "'+SUM(A1:A10)"
    assert sanitize_csv_value("Safe Text") == "Safe Text"


def test_indian_number_formatting():
    """Verify format_inr accurately formats thousands, lakhs, crores, and negative values."""
    assert format_inr(502497, prefix="\u20b9", decimals=2) == "\u20b95,02,497.00"
    assert format_inr(-12345678, prefix="\u20b9", decimals=0) == "\u20b9-1,23,45,678"
    assert format_inr(950, prefix="", decimals=0) == "950"


def test_pydantic_constraint_validations():
    """Verify invalid negative quantities or out-of-range parameters raise errors."""
    with pytest.raises(ValidationError):
        Batch(
            batch_id="BAD",
            commodity="Tomato",
            quantity_kg=-100.0,
            remaining_shelf_life_hrs=10.0,
            base_cost_per_kg=10.0,
        )

    with pytest.raises(ValueError):
        FreshRouteSolver(max_discount_pct=1.5)