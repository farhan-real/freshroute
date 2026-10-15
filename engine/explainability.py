"""engine/explainability.py: Evidence-backed decision explanation and audit reporting."""

from typing import List, Dict
import pandas as pd
from .models import AllocationDecision, OptimizationSummary


class DecisionExplainer:
    """Generates transparent, auditable explanations for logistics and procurement teams."""

    @staticmethod
    def generate_audit_table(allocations: List[AllocationDecision]) -> pd.DataFrame:
        records = []
        for a in allocations:
            status = "APPROVED" if a.shelf_life_buffer_hrs > 0 else "REJECTED/SPOILED"
            records.append({
                "Batch": a.batch_id,
                "Commodity": a.commodity,
                "Destination": a.dest_id,
                "Quantity (kg)": a.quantity_kg,
                "Shelf Life (h)": a.remaining_shelf_life_hrs,
                "Transit (h)": a.travel_time_hrs,
                "Buffer Upon Arrival (h)": a.shelf_life_buffer_hrs,
                "Discount %": f"{int(a.discount_pct * 100)}%",
                "Net Margin (₹/kg)": round(a.net_profit / a.quantity_kg, 2) if a.quantity_kg > 0 else 0,
                "Status": status,
                "Audit Reason": a.reason
            })
        return pd.DataFrame(records)

    @staticmethod
    def explain_comparison(baseline: OptimizationSummary, fresh: OptimizationSummary) -> Dict[str, str]:
        profit_diff = fresh.net_profit - baseline.net_profit
        spoilage_reduction = baseline.spoilage_rate_pct - fresh.spoilage_rate_pct
        fulfillment_gain = fresh.demand_fulfillment_pct - baseline.demand_fulfillment_pct

        return {
            "Profit Delta": f"+₹{profit_diff:,.2f} ({((profit_diff / max(abs(baseline.net_profit), 1)) * 100):+.1f}%)",
            "Spoilage Reduction": f"{spoilage_reduction:+.1f}% points lower spoilage",
            "Fulfillment Delta": f"{fulfillment_gain:+.1f}% points higher demand fulfillment",
            "Key Driver": (
                "FreshRoute prevented in-transit spoilage by enforcing arrival buffer thresholds, "
                "routed high-perishability stock to high-margin close hubs, and liquidated aging batches "
                "via dynamic discounting before expiration."
            )
        }