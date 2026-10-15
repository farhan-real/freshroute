"""engine/explainability.py: Evidence-backed decision explanation, counterfactual logs, and CSV safety."""

from typing import Any, Dict, List
import pandas as pd
from .models import AllocationDecision, OptimizationSummary, RejectedRoute


def format_inr(number: float, prefix: str = "\u20b9", decimals: int = 0) -> str:
    """Formats a float into the Indian Numbering System (Lakhs, Crores) without code duplication."""
    neg = "-" if number < 0 else ""
    num_abs = abs(float(number))
    formatted_float = f"{num_abs:.{decimals}f}"
    parts = formatted_float.split(".")
    integer_part = parts[0]
    decimal_part = f".{parts[1]}" if decimals > 0 else ""

    if len(integer_part) <= 3:
        res = integer_part
    else:
        last3 = integer_part[-3:]
        remaining = integer_part[:-3]
        groups: List[str] = []
        while len(remaining) > 2:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            groups.insert(0, remaining)
        res = ",".join(groups) + "," + last3

    return f"{prefix}{neg}{res}{decimal_part}" if prefix else f"{neg}{res}{decimal_part}"


def sanitize_csv_value(val: Any) -> Any:
    """
    Security safeguard: Neutralizes spreadsheet formula injection (CSV Injection)
    by prefixing strings starting with '=', '+', '-', '@', tab, or CR with a single quote.
    """
    if isinstance(val, str) and val.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{val}"
    return val


class DecisionExplainer:
    """Generates transparent, auditable explanations for logistics and procurement teams."""

    @staticmethod
    def generate_audit_table(
        allocations: List[AllocationDecision], sanitize_for_export: bool = False
    ) -> pd.DataFrame:
        records = []
        for a in allocations:
            status = "APPROVED" if a.shelf_life_buffer_hrs > 0 else "REJECTED/SPOILED"
            row = {
                "Batch": a.batch_id,
                "Commodity": a.commodity,
                "Destination": a.dest_id,
                "Quantity (kg)": a.quantity_kg,
                "Cleared (kg)": a.sold_qty_kg,
                "Shelf Life (h)": a.remaining_shelf_life_hrs,
                "Transit (h)": a.travel_time_hrs,
                "Buffer Upon Arrival (h)": a.shelf_life_buffer_hrs,
                "Discount %": f"{int(round(a.discount_pct * 100))}%",
                "Net Margin (\u20b9/kg)": round(a.net_profit / a.quantity_kg, 2) if a.quantity_kg > 0 else 0.0,
                "Status": status,
                "Audit Reason": a.reason,
            }
            if sanitize_for_export:
                row = {k: sanitize_csv_value(v) for k, v in row.items()}
            records.append(row)
        return pd.DataFrame(records)

    @staticmethod
    def generate_rejection_table(
        rejected_routes: List[RejectedRoute], sanitize_for_export: bool = False
    ) -> pd.DataFrame:
        """Generates a counterfactual audit table explaining why specific routes were blocked."""
        records = []
        for r in rejected_routes:
            row = {
                "Batch": r.batch_id,
                "Commodity": r.commodity,
                "Destination": f"{r.destination_name} ({r.dest_id})",
                "Shelf Life (h)": r.remaining_shelf_life_hrs,
                "Req Transit+Handling (h)": r.required_transit_and_handling_hrs,
                "Projected Buffer (h)": r.projected_buffer_hrs,
                "Guardrail Triggered": r.rejection_category,
                "Counterfactual Explanation": r.reason,
            }
            if sanitize_for_export:
                row = {k: sanitize_csv_value(v) for k, v in row.items()}
            records.append(row)
        return pd.DataFrame(records)

    @staticmethod
    def explain_comparison(baseline: OptimizationSummary, fresh: OptimizationSummary) -> Dict[str, str]:
        profit_diff = fresh.net_profit - baseline.net_profit
        spoilage_reduction = baseline.spoilage_rate_pct - fresh.spoilage_rate_pct
        fulfillment_gain = fresh.demand_fulfillment_pct - baseline.demand_fulfillment_pct

        return {
            "Profit Delta": (
                f"+{format_inr(profit_diff, decimals=2)} "
                f"({((profit_diff / max(abs(baseline.net_profit), 1.0)) * 100.0):+.1f}%)"
            ),
            "Spoilage Reduction": f"{spoilage_reduction:+.1f}% points lower spoilage",
            "Fulfillment Delta": f"{fulfillment_gain:+.1f}% points higher demand fulfillment",
            "Key Driver": (
                "FreshRoute prevented in-transit spoilage by enforcing arrival buffer thresholds, "
                "routed high-perishability stock to high-margin close hubs, and liquidated aging batches "
                "via dynamic discounting before expiration."
            ),
        }