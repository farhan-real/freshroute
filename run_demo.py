"""run_demo.py: One-command benchmark evaluator and explainability showcase."""

from tabulate import tabulate
from engine.data_generator import get_standard_scenario, apply_disruption
from engine.baseline_solver import BaselineSolver
from engine.freshroute_solver import FreshRouteSolver
from engine.explainability import DecisionExplainer


def run_benchmark():
    print("=" * 80)
    print("  FRESHROUTE: PERISHABLE PRODUCE DECISION-SUPPORT BENCHMARK")
    print("=" * 80)

    batches, dests, routes = get_standard_scenario()

    baseline_solver = BaselineSolver()
    fresh_solver = FreshRouteSolver()

    # Normal Scenario
    base_res = baseline_solver.solve(batches, dests, routes)
    fresh_res = fresh_solver.solve(batches, dests, routes)

    comparison_data = [
        ["Total Inventory (kg)", f"{base_res.total_inventory_kg:,.0f}", f"{fresh_res.total_inventory_kg:,.0f}"],
        ["Dispatched Quantity (kg)", f"{base_res.dispatched_kg:,.0f}", f"{fresh_res.dispatched_kg:,.0f}"],
        ["Demand Fulfillment (%)", f"{base_res.demand_fulfillment_pct}%", f"{fresh_res.demand_fulfillment_pct}%"],
        ["Spoilage Loss (kg)", f"{base_res.spoiled_kg:,.0f}", f"{fresh_res.spoiled_kg:,.0f}"],
        ["Spoilage Rate (%)", f"{base_res.spoilage_rate_pct}%", f"{fresh_res.spoilage_rate_pct}%"],
        ["Gross Revenue", f"₹{base_res.total_gross_revenue:,.2f}", f"₹{fresh_res.total_gross_revenue:,.2f}"],
        ["Logistics Cost", f"₹{base_res.total_transport_cost:,.2f}", f"₹{fresh_res.total_transport_cost:,.2f}"],
        ["Spoilage Penalties", f"₹{base_res.disposal_waste_cost:,.2f}", f"₹{fresh_res.disposal_waste_cost:,.2f}"],
        ["NET PROFIT", f"₹{base_res.net_profit:,.2f}", f"₹{fresh_res.net_profit:,.2f}"],
    ]

    print("\n[SCENARIO 1: NORMAL CONDITIONS - NASHIK CORRIDOR]")
    print(tabulate(comparison_data, headers=["Metric", "Baseline (Naive FIFO)", "FreshRoute Intelligent"], tablefmt="fancy_grid"))

    insights = DecisionExplainer.explain_comparison(base_res, fresh_res)
    print("\n--- PERFORMANCE HIGHLIGHTS ---")
    for k, v in insights.items():
        print(f"• {k}: {v}")

    # Stress Test Disruption Scenario
    print("\n" + "=" * 80)
    print("  STRESS TEST: MONSOON DELAY (+6h Highway Blockade, -30% Demand Shock)")
    print("=" * 80)

    dis_routes, dis_dests = apply_disruption(routes, dests, delay_hours=6.0, demand_shock_pct=-0.30)
    base_dis = baseline_solver.solve(batches, dis_dests, dis_routes)
    fresh_dis = fresh_solver.solve(batches, dis_dests, dis_routes)

    stress_data = [
        ["Spoilage Loss (kg)", f"{base_dis.spoiled_kg:,.0f}", f"{fresh_dis.spoiled_kg:,.0f}"],
        ["Spoilage Rate (%)", f"{base_dis.spoilage_rate_pct}%", f"{fresh_dis.spoilage_rate_pct}%"],
        ["NET PROFIT", f"₹{base_dis.net_profit:,.2f}", f"₹{fresh_dis.net_profit:,.2f}"],
    ]
    print(tabulate(stress_data, headers=["Stress Metric", "Baseline (Naive FIFO)", "FreshRoute Resilient"], tablefmt="fancy_grid"))

    print("\n[SAMPLE AUDIT TRAIL - FIRST 5 ALLOCATIONS]")
    audit_df = DecisionExplainer.generate_audit_table(fresh_res.allocations)
    print(audit_df[["Batch", "Commodity", "Destination", "Quantity (kg)", "Buffer Upon Arrival (h)", "Discount %", "Net Margin (₹/kg)"]].head(5).to_string(index=False))
    print("\nBenchmark completed successfully.")


if __name__ == "__main__":
    run_benchmark()