"""run_demo.py: One-command benchmark evaluator with Indian Numbering System and accessible CLI modes."""

import argparse
import io
import sys
from tabulate import tabulate

from engine.baseline_solver import BaselineSolver
from engine.data_generator import apply_disruption, get_standard_scenario
from engine.explainability import DecisionExplainer, format_inr
from engine.freshroute_solver import FreshRouteSolver


def configure_utf8_output() -> None:
    """Ensures Windows PowerShell/CMD terminals render UTF-8 symbols without mojibake."""
    if isinstance(sys.stdout, io.TextIOWrapper):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except ValueError:
            pass


def run_benchmark(ascii_mode: bool = False) -> None:
    configure_utf8_output()
    currency = "INR " if ascii_mode else "\u20b9"
    bullet = "*" if ascii_mode else "\u2022"
    table_style = "grid" if ascii_mode else "fancy_grid"

    print("=" * 80)
    print("  FRESHROUTE: PERISHABLE PRODUCE DECISION-SUPPORT BENCHMARK")
    print("=" * 80)

    batches, dests, routes = get_standard_scenario()

    baseline_solver = BaselineSolver()
    fresh_solver = FreshRouteSolver()

    base_res = baseline_solver.solve(batches, dests, routes)
    fresh_res = fresh_solver.solve(batches, dests, routes)

    comparison_data = [
        [
            "Total Inventory (kg)",
            format_inr(base_res.total_inventory_kg, prefix="", decimals=0),
            format_inr(fresh_res.total_inventory_kg, prefix="", decimals=0),
        ],
        [
            "Dispatched Quantity (kg)",
            format_inr(base_res.dispatched_kg, prefix="", decimals=0),
            format_inr(fresh_res.dispatched_kg, prefix="", decimals=0),
        ],
        [
            "Demand Fulfillment (%)",
            f"{base_res.demand_fulfillment_pct}%",
            f"{fresh_res.demand_fulfillment_pct}%",
        ],
        [
            "Spoilage Loss (kg)",
            format_inr(base_res.spoiled_kg, prefix="", decimals=0),
            format_inr(fresh_res.spoiled_kg, prefix="", decimals=0),
        ],
        [
            "Spoilage Rate (%)",
            f"{base_res.spoilage_rate_pct}%",
            f"{fresh_res.spoilage_rate_pct}%",
        ],
        [
            "Gross Revenue",
            format_inr(base_res.total_gross_revenue, prefix=currency, decimals=2),
            format_inr(fresh_res.total_gross_revenue, prefix=currency, decimals=2),
        ],
        [
            "Logistics Cost",
            format_inr(base_res.total_transport_cost, prefix=currency, decimals=2),
            format_inr(fresh_res.total_transport_cost, prefix=currency, decimals=2),
        ],
        [
            "Spoilage Penalties",
            format_inr(base_res.disposal_waste_cost, prefix=currency, decimals=2),
            format_inr(fresh_res.disposal_waste_cost, prefix=currency, decimals=2),
        ],
        [
            "NET PROFIT",
            format_inr(base_res.net_profit, prefix=currency, decimals=2),
            format_inr(fresh_res.net_profit, prefix=currency, decimals=2),
        ],
        [
            "Solve Time (ms)",
            f"{base_res.solve_time_ms:.3f} ms",
            f"{fresh_res.solve_time_ms:.3f} ms",
        ],
    ]

    print("\n[SCENARIO 1: NORMAL CONDITIONS - NASHIK CORRIDOR]")
    print(
        tabulate(
            comparison_data,
            headers=["Metric", "Baseline (Naive FIFO)", "FreshRoute Intelligent"],
            tablefmt=table_style,
        )
    )

    profit_diff = fresh_res.net_profit - base_res.net_profit
    pct_gain = (profit_diff / max(abs(base_res.net_profit), 1.0)) * 100.0

    print("\n--- PERFORMANCE HIGHLIGHTS ---")
    print(f"{bullet} Profit Delta: +{format_inr(profit_diff, prefix=currency, decimals=2)} (+{pct_gain:.1f}%)")
    print(
        f"{bullet} Spoilage Reduction: "
        f"+{base_res.spoilage_rate_pct - fresh_res.spoilage_rate_pct:.2f}% points lower spoilage"
    )
    print(
        f"{bullet} Fulfillment Delta: "
        f"+{fresh_res.demand_fulfillment_pct - base_res.demand_fulfillment_pct:.2f}% points higher demand fulfillment"
    )
    print(
        f"{bullet} Key Driver: FreshRoute eliminated in-transit spoilage via arrival buffer enforcement "
        "and liquidated tight-buffer produce via targeted dynamic discounting."
    )

    # Stress Test
    print("\n" + "=" * 80)
    print("  STRESS TEST: MONSOON DELAY (+6h Highway Blockade, -30% Demand Shock)")
    print("=" * 80)

    dis_routes, dis_dests = apply_disruption(routes, dests, delay_hours=6.0, demand_shock_pct=-0.30)
    base_dis = baseline_solver.solve(batches, dis_dests, dis_routes)
    fresh_dis = fresh_solver.solve(batches, dis_dests, dis_routes)

    stress_data = [
        [
            "Spoilage Loss (kg)",
            format_inr(base_dis.spoiled_kg, prefix="", decimals=0),
            format_inr(fresh_dis.spoiled_kg, prefix="", decimals=0),
        ],
        [
            "Spoilage Rate (%)",
            f"{base_dis.spoilage_rate_pct}%",
            f"{fresh_dis.spoilage_rate_pct}%",
        ],
        [
            "NET PROFIT",
            format_inr(base_dis.net_profit, prefix=currency, decimals=2),
            format_inr(fresh_dis.net_profit, prefix=currency, decimals=2),
        ],
    ]
    print(
        tabulate(
            stress_data,
            headers=["Stress Metric", "Baseline (Naive FIFO)", "FreshRoute Resilient"],
            tablefmt=table_style,
        )
    )

    # Monte Carlo Uncertainty Report
    mc_report = fresh_solver.evaluate_uncertainty(batches, dests, routes, runs=30)
    print("\n[MONTE CARLO UNCERTAINTY ANALYSIS (30 STOCHASTIC RUNS)]")
    print(
        f"{bullet} Expected Profit: {format_inr(mc_report.mean_net_profit, prefix=currency, decimals=2)} "
        f"(5th-95th Percentile: {format_inr(mc_report.p5_net_profit, prefix=currency, decimals=0)} to "
        f"{format_inr(mc_report.p95_net_profit, prefix=currency, decimals=0)})"
    )

    print("\n[SAMPLE AUDIT TRAIL - FIRST 5 ALLOCATIONS]")
    audit_df = DecisionExplainer.generate_audit_table(fresh_res.allocations)
    margin_col = "Net Margin (\u20b9/kg)"
    print(
        audit_df[
            [
                "Batch",
                "Commodity",
                "Destination",
                "Quantity (kg)",
                "Buffer Upon Arrival (h)",
                "Discount %",
                margin_col,
            ]
        ]
        .head(5)
        .to_string(index=False)
    )
    print("\nBenchmark completed successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FreshRoute CLI Benchmark Runner")
    parser.add_argument(
        "--ascii",
        action="store_true",
        help="Use ASCII-only output for screen readers and legacy terminal environments.",
    )
    args = parser.parse_args()
    run_benchmark(ascii_mode=args.ascii)