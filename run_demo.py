"""run_demo.py: One-command benchmark evaluator with Indian Numbering System."""

from tabulate import tabulate
from engine.data_generator import get_standard_scenario, apply_disruption
from engine.baseline_solver import BaselineSolver
from engine.freshroute_solver import FreshRouteSolver
from engine.explainability import DecisionExplainer


def format_inr(number: float, prefix: str = "₹", decimals: int = 2) -> str:
    """Formats any float into Indian Numbering System (Lakhs, Crores)."""
    neg = "-" if number < 0 else ""
    num_abs = abs(number)
    formatted_float = f"{num_abs:.{decimals}f}"
    parts = formatted_float.split(".")
    integer_part = parts[0]
    decimal_part = f".{parts[1]}" if decimals > 0 else ""

    if len(integer_part) <= 3:
        res = integer_part
    else:
        last3 = integer_part[-3:]
        remaining = integer_part[:-3]
        groups = []
        while len(remaining) > 2:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            groups.insert(0, remaining)
        res = ",".join(groups) + "," + last3

    return f"{prefix}{neg}{res}{decimal_part}" if prefix else f"{neg}{res}{decimal_part}"


def run_benchmark():
    print("=" * 80)
    print("  FRESHROUTE: PERISHABLE PRODUCE DECISION-SUPPORT BENCHMARK")
    print("=" * 80)

    batches, dests, routes = get_standard_scenario()

    baseline_solver = BaselineSolver()
    fresh_solver = FreshRouteSolver()

    base_res = baseline_solver.solve(batches, dests, routes)
    fresh_res = fresh_solver.solve(batches, dests, routes)

    comparison_data = [
        ["Total Inventory (kg)", f"{format_inr(base_res.total_inventory_kg, prefix='', decimals=0)}", f"{format_inr(fresh_res.total_inventory_kg, prefix='', decimals=0)}"],
        ["Dispatched Quantity (kg)", f"{format_inr(base_res.dispatched_kg, prefix='', decimals=0)}", f"{format_inr(fresh_res.dispatched_kg, prefix='', decimals=0)}"],
        ["Demand Fulfillment (%)", f"{base_res.demand_fulfillment_pct}%", f"{fresh_res.demand_fulfillment_pct}%"],
        ["Spoilage Loss (kg)", f"{format_inr(base_res.spoiled_kg, prefix='', decimals=0)}", f"{format_inr(fresh_res.spoiled_kg, prefix='', decimals=0)}"],
        ["Spoilage Rate (%)", f"{base_res.spoilage_rate_pct}%", f"{fresh_res.spoilage_rate_pct}%"],
        ["Gross Revenue", f"{format_inr(base_res.total_gross_revenue)}", f"{format_inr(fresh_res.total_gross_revenue)}"],
        ["Logistics Cost", f"{format_inr(base_res.total_transport_cost)}", f"{format_inr(fresh_res.total_transport_cost)}"],
        ["Spoilage Penalties", f"{format_inr(base_res.disposal_waste_cost)}", f"{format_inr(fresh_res.disposal_waste_cost)}"],
        ["NET PROFIT", f"{format_inr(base_res.net_profit)}", f"{format_inr(fresh_res.net_profit)}"],
    ]

    print("\n[SCENARIO 1: NORMAL CONDITIONS - NASHIK CORRIDOR]")
    print(tabulate(comparison_data, headers=["Metric", "Baseline (Naive FIFO)", "FreshRoute Intelligent"], tablefmt="fancy_grid"))

    profit_diff = fresh_res.net_profit - base_res.net_profit
    pct_gain = ((profit_diff / max(abs(base_res.net_profit), 1)) * 100)

    print("\n--- PERFORMANCE HIGHLIGHTS ---")
    print(f"• Profit Delta: +{format_inr(profit_diff)} (+{pct_gain:.1f}%)")
    print(f"• Spoilage Reduction: +{base_res.spoilage_rate_pct - fresh_res.spoilage_rate_pct:.1f}% points lower spoilage")
    print(f"• Fulfillment Delta: +{fresh_res.demand_fulfillment_pct - base_res.demand_fulfillment_pct:.1f}% points higher demand fulfillment")
    print("• Key Driver: FreshRoute eliminated in-transit spoilage via arrival buffer enforcement and liquidated tight-buffer produce via targeted dynamic discounting.")

    # Stress Test
    print("\n" + "=" * 80)
    print("  STRESS TEST: MONSOON DELAY (+6h Highway Blockade, -30% Demand Shock)")
    print("=" * 80)

    dis_routes, dis_dests = apply_disruption(routes, dests, delay_hours=6.0, demand_shock_pct=-0.30)
    base_dis = baseline_solver.solve(batches, dis_dests, dis_routes)
    fresh_dis = fresh_solver.solve(batches, dis_dests, dis_routes)

    stress_data = [
        ["Spoilage Loss (kg)", f"{format_inr(base_dis.spoiled_kg, prefix='', decimals=0)}", f"{format_inr(fresh_dis.spoiled_kg, prefix='', decimals=0)}"],
        ["Spoilage Rate (%)", f"{base_dis.spoilage_rate_pct}%", f"{fresh_dis.spoilage_rate_pct}%"],
        ["NET PROFIT", f"{format_inr(base_dis.net_profit)}", f"{format_inr(fresh_dis.net_profit)}"],
    ]
    print(tabulate(stress_data, headers=["Stress Metric", "Baseline (Naive FIFO)", "FreshRoute Resilient"], tablefmt="fancy_grid"))

    print("\n[SAMPLE AUDIT TRAIL - FIRST 5 ALLOCATIONS]")
    audit_df = DecisionExplainer.generate_audit_table(fresh_res.allocations)
    print(audit_df[["Batch", "Commodity", "Destination", "Quantity (kg)", "Buffer Upon Arrival (h)", "Discount %", "Net Margin (₹/kg)"]].head(5).to_string(index=False))
    print("\nBenchmark completed successfully.")


if __name__ == "__main__":
    run_benchmark()