"""app.py: FreshRoute Interactive Decision-Support Dashboard (WCAG Accessible & XSS-Hardened)."""

import html
from typing import Dict, List, Literal, Optional, Tuple

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from pydantic import ValidationError

from engine.baseline_solver import BaselineSolver
from engine.data_generator import (
    SeasonalityMode,
    apply_disruption,
    apply_temperature_excursion,
    export_scenario_to_json,
    forecast_destination_demand,
    get_standard_scenario,
    inject_replanning_event,
    load_scenario_from_json,
)
from engine.explainability import DecisionExplainer, format_inr
from engine.freshroute_solver import FreshRouteSolver
from engine.models import OptimizationSummary, UncertaintyReport


@st.cache_data(show_spinner=False)
def run_cached_simulation(
    custom_json_bytes: Optional[bytes],
    seasonality_mode: SeasonalityMode,
    add_spot_order: bool,
    fleet_breakdown_pct: float,
    disruption_active: bool,
    transit_delay: float,
    demand_shock: float,
    ambient_temp_c: float,
    min_buffer: float,
    max_discount: float,
    solver_mode: Literal["urgency_margin", "lp_highs"],
) -> Tuple[OptimizationSummary, OptimizationSummary, UncertaintyReport, pd.DataFrame, str]:
    """Cached simulation pipeline for O(1) UI responsiveness across widget interactions."""
    if custom_json_bytes is not None:
        batches, destinations, routes = load_scenario_from_json(custom_json_bytes)
    else:
        batches, destinations, routes = get_standard_scenario()

    if seasonality_mode != "normal":
        destinations = forecast_destination_demand(destinations, seasonality=seasonality_mode)

    if add_spot_order or fleet_breakdown_pct > 0.0:
        batches, destinations, routes = inject_replanning_event(
            batches,
            destinations,
            routes,
            add_spot_order=add_spot_order,
            fleet_breakdown_pct=fleet_breakdown_pct,
        )

    if ambient_temp_c > 4.0:
        batches = apply_temperature_excursion(batches, ambient_temp_c=ambient_temp_c)

    if disruption_active:
        routes, destinations = apply_disruption(
            routes,
            destinations,
            delay_hours=transit_delay,
            demand_shock_pct=-demand_shock,
        )

    baseline_solver = BaselineSolver()
    fresh_solver = FreshRouteSolver(
        min_safe_buffer_hrs=min_buffer,
        max_discount_pct=max_discount,
        solver_mode=solver_mode,
    )

    base_res = baseline_solver.solve(batches, destinations, routes)
    fresh_res = fresh_solver.solve(batches, destinations, routes)
    mc_report = fresh_solver.evaluate_uncertainty(batches, destinations, routes, runs=40)
    batch_df = pd.DataFrame([b.model_dump() for b in batches])
    scenario_json = export_scenario_to_json(batches, destinations, routes)
    return base_res, fresh_res, mc_report, batch_df, scenario_json


def build_sankey_figure(batches_df: pd.DataFrame, summary: OptimizationSummary) -> go.Figure:
    """Builds a collision-safe, dark-theme Sankey diagram showing Batch -> Mandi -> Market Outcomes."""
    batch_ids: List[str] = [str(x) for x in batches_df["batch_id"].tolist()]
    dest_ids: List[str] = sorted({a.dest_id for a in summary.allocations})

    node_keys = [f"b_{b}" for b in batch_ids] + [f"d_{d}" for d in dest_ids] + ["t_cleared", "t_spoiled", "t_reserve"]
    labels = batch_ids + dest_ids + ["Cleared at Mandi", "Spoiled / Expired", "Storable Reserve (Unallocated)"]
    node_idx = {k: i for i, k in enumerate(node_keys)}

    sources: List[int] = []
    targets: List[int] = []
    values: List[float] = []
    link_colors: List[str] = []

    dispatched_by_batch: Dict[str, float] = {b_id: 0.0 for b_id in batch_ids}
    cleared_by_dest: Dict[str, float] = {d_id: 0.0 for d_id in dest_ids}
    spoiled_by_dest: Dict[str, float] = {d_id: 0.0 for d_id in dest_ids}

    for alloc in summary.allocations:
        b_key = f"b_{alloc.batch_id}"
        d_key = f"d_{alloc.dest_id}"
        if b_key in node_idx and d_key in node_idx and alloc.quantity_kg > 0:
            sources.append(node_idx[b_key])
            targets.append(node_idx[d_key])
            values.append(alloc.quantity_kg)
            link_colors.append("rgba(56, 189, 248, 0.40)")
            dispatched_by_batch[alloc.batch_id] = (
                dispatched_by_batch.get(alloc.batch_id, 0.0) + alloc.quantity_kg
            )
            cleared_by_dest[alloc.dest_id] += alloc.sold_qty_kg
            spoiled_by_dest[alloc.dest_id] += max(0.0, alloc.quantity_kg - alloc.sold_qty_kg)

    for d_id in dest_ids:
        d_key = f"d_{d_id}"
        if cleared_by_dest[d_id] > 0 and d_key in node_idx:
            sources.append(node_idx[d_key])
            targets.append(node_idx["t_cleared"])
            values.append(cleared_by_dest[d_id])
            link_colors.append("rgba(2, 132, 199, 0.55)")
        if spoiled_by_dest[d_id] > 0 and d_key in node_idx:
            sources.append(node_idx[d_key])
            targets.append(node_idx["t_spoiled"])
            values.append(spoiled_by_dest[d_id])
            link_colors.append("rgba(217, 119, 6, 0.65)")

    # Iterating over dict records avoids Pylance Series-to-float conversion warnings
    for row in batches_df.to_dict(orient="records"):
        b_id = str(row["batch_id"])
        b_key = f"b_{b_id}"
        qty = float(row["quantity_kg"])
        shelf_life = float(row["remaining_shelf_life_hrs"])

        rem_qty = max(0.0, qty - dispatched_by_batch.get(b_id, 0.0))
        if rem_qty > 0 and b_key in node_idx:
            sources.append(node_idx[b_key])
            if shelf_life <= 24.0:
                targets.append(node_idx["t_spoiled"])
                link_colors.append("rgba(217, 119, 6, 0.65)")
            else:
                targets.append(node_idx["t_reserve"])
                link_colors.append("rgba(148, 163, 184, 0.45)")
            values.append(rem_qty)

    if not values or not sources or not targets:
        empty_fig = go.Figure()
        empty_fig.update_layout(
            title="Supply-Chain Mass Flow: No active allocations to display",
            height=300,
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#cbd5e1"),
        )
        return empty_fig

    node_colors = (
        ["#38bdf8"] * len(batch_ids)
        + ["#818cf8"] * len(dest_ids)
        + ["#0284c7", "#d97706", "#64748b"]
    )

    fig = go.Figure(
        data=[
            go.Sankey(
                node=dict(
                    pad=16,
                    thickness=18,
                    line=dict(color="#0f172a", width=1),
                    label=labels,
                    color=node_colors,
                ),
                link=dict(source=sources, target=targets, value=values, color=link_colors),
            )
        ]
    )
    fig.update_layout(
        title="Supply-Chain Mass Flow: Inventory Batches → Destination Mandis → Outcome (kg)",
        height=420,
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#cbd5e1", size=12),
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig


def render_metric_card(
    title: str,
    main_val: str,
    vs_val: str,
    delta_text: str,
    is_positive: bool,
    arrow: str,
) -> None:
    """Renders an accessible, XSS-sanitized metric card with ARIA semantics."""
    safe_title = html.escape(str(title))
    safe_main = html.escape(str(main_val))
    safe_vs = html.escape(str(vs_val))
    safe_delta = html.escape(str(delta_text))
    safe_arrow = html.escape(str(arrow))
    sr_status = "Favorable change" if is_positive else "Unfavorable change"

    badge_bg = "rgba(14, 165, 233, 0.18)" if is_positive else "rgba(245, 158, 11, 0.18)"
    badge_color = "#38bdf8" if is_positive else "#fbbf24"
    badge_border = (
        "1px solid rgba(56, 189, 248, 0.45)"
        if is_positive
        else "1px solid rgba(251, 191, 36, 0.45)"
    )

    card_html = f"""
    <div role="region" aria-label="{safe_title}: {safe_main} compared to baseline {safe_vs}, {sr_status} {safe_delta}"
         style="background-color: #1e293b; padding: 18px 22px; border-radius: 10px; border: 1px solid #334155; margin-bottom: 16px;">
        <div style="color: #cbd5e1; font-size: 0.95rem; font-weight: 600; margin-bottom: 8px;">{safe_title}</div>
        <div style="display: flex; align-items: baseline; flex-wrap: wrap; gap: 12px; margin-bottom: 10px;">
            <span style="color: #ffffff; font-size: 1.75rem; font-weight: 700; letter-spacing: -0.02em;">{safe_main}</span>
            <span style="color: #94a3b8; font-size: 1.25rem; font-weight: 500;">vs {safe_vs}</span>
        </div>
        <div style="display: inline-flex; align-items: center; gap: 6px; background-color: {badge_bg}; color: {badge_color}; border: {badge_border}; font-size: 0.85rem; font-weight: 600; padding: 4px 10px; border-radius: 9999px;">
            <span aria-hidden="true">{safe_arrow}</span>
            <span>{safe_delta}</span>
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


st.set_page_config(
    page_title="FreshRoute | Decision Support System",
    layout="wide",
)

# ----------------- SIDEBAR: CONTROL CONSOLE -----------------

custom_json_bytes: Optional[bytes] = None

with st.sidebar:
    st.markdown(
        """
        <div style="padding-bottom: 12px; border-bottom: 1px solid #334155; margin-bottom: 16px;">
            <div style="font-size: 0.72rem; font-weight: 800; color: #38bdf8; letter-spacing: 0.15em; text-transform: uppercase;">
                Control Console
            </div>
            <div style="font-size: 1.25rem; font-weight: 700; color: #f8fafc; margin-top: 2px;">
                Policy &amp; Simulation
            </div>
            <div style="font-size: 0.8rem; color: #cbd5e1; margin-top: 2px;">
                Origin Hub: Nashik Central Corridor
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div style="font-size: 0.72rem; font-weight: 700; color: #f59e0b; letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 6px;">
            Environment Shock Testing
        </div>
        """,
        unsafe_allow_html=True,
    )

    disruption_toggle = st.toggle(
        "Simulate Supply-Chain Disruption",
        value=False,
        help="Inject highway transit delays and destination market demand shocks.",
    )

    if disruption_toggle:
        st.markdown(
            """
            <div role="status" style="display: inline-block; font-size: 0.72rem; font-weight: 700; padding: 2px 8px; border-radius: 4px; background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.45); margin-bottom: 10px;">
                DISRUPTION ACTIVE // MONSOON DELAYS
            </div>
            """,
            unsafe_allow_html=True,
        )
        transit_delay = st.slider(
            "Highway Transit Delay (Hours)",
            1.0,
            12.0,
            6.0,
            step=0.5,
            help="Simulates road blockages, landslide detours, or toll delays.",
        )
        demand_shock = (
            st.slider(
                "Destination Demand Drop (%)",
                0,
                50,
                30,
                step=5,
                help="Simulates mandi shutdowns or purchasing cutbacks.",
            )
            / 100.0
        )
    else:
        st.markdown(
            """
            <div role="status" style="display: inline-block; font-size: 0.72rem; font-weight: 700; padding: 2px 8px; border-radius: 4px; background: rgba(14, 165, 233, 0.18); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.35); margin-bottom: 10px;">
                NORMAL TRANSIT CONDITIONS
            </div>
            """,
            unsafe_allow_html=True,
        )
        transit_delay = 0.0
        demand_shock = 0.0

    ambient_temp_c = st.slider(
        "Cold-Chain Storage Temp (°C)",
        min_value=4.0,
        max_value=24.0,
        value=4.0,
        step=2.0,
        help="Simulates reefer cooling excursions using Q10 biological respiration decay (4°C = nominal).",
    )

    st.markdown("<div style='margin: 16px 0; border-top: 1px solid #334155;'></div>", unsafe_allow_html=True)

    st.markdown(
        """
        <div style="font-size: 0.72rem; font-weight: 700; color: #38bdf8; letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 6px;">
            Forecasting &amp; Dynamic Replanning
        </div>
        """,
        unsafe_allow_html=True,
    )

    seasonality_label = st.selectbox(
        "Demand Forecast Profile",
        options=[
            "Normal Baseline (Default)",
            "Festival Surge (+10% to +30%)",
            "Weekend Mandi Rush (+5% to +25%)",
            "Monsoon Hospitality Dip (-5% to -25%)",
        ],
        index=0,
        help="Forecasts destination mandi demand from event and seasonality indicators.",
    )
    seasonality_map: Dict[str, SeasonalityMode] = {
        "Normal Baseline (Default)": "normal",
        "Festival Surge (+10% to +30%)": "festival_surge",
        "Weekend Mandi Rush (+5% to +25%)": "weekend_rush",
        "Monsoon Hospitality Dip (-5% to -25%)": "monsoon_dip",
    }
    seasonality_mode: SeasonalityMode = seasonality_map[seasonality_label]

    add_spot_order = st.checkbox(
        "Inject Mid-Day Spot Order",
        value=False,
        help="Simulates an urgent 1,800 kg Tomato order from Mumbai Dark Stores at ₹42/kg.",
    )
    fleet_breakdown_pct = (
        st.slider(
            "Fleet Breakdown Capacity Loss (%)",
            min_value=0,
            max_value=50,
            value=0,
            step=10,
            help="Simulates mid-day truck unavailability requiring dynamic route reallocation.",
        )
        / 100.0
    )

    st.markdown("<div style='margin: 16px 0; border-top: 1px solid #334155;'></div>", unsafe_allow_html=True)

    st.markdown(
        """
        <div style="font-size: 0.72rem; font-weight: 700; color: #a78bfa; letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 6px;">
            Optimization Hyperparameters
        </div>
        """,
        unsafe_allow_html=True,
    )

    min_buffer = st.slider(
        "Safe Shelf Buffer Threshold (Hours)",
        min_value=1.0,
        max_value=8.0,
        value=2.0,
        step=0.5,
        help="Minimum remaining shelf life upon arrival. Routes below this are marked infeasible.",
    )

    max_discount = (
        st.slider(
            "Dynamic Discount Ceiling (%)",
            min_value=5,
            max_value=40,
            value=25,
            step=5,
            help="Maximum allowable price reduction to stimulate clearance of near-expiry inventory.",
        )
        / 100.0
    )

    solver_label = st.selectbox(
        "Optimization Engine Mode",
        options=["Urgency-Margin Heuristic (Ultra-Fast)", "SciPy HiGHS Linear Program (Very Accurate)"],
        index=0,
        help="Switch between Priority-Index heuristic and SciPy HiGHS Linear Programming.",
    )
    solver_mode: Literal["urgency_margin", "lp_highs"] = (
        "lp_highs" if "HiGHS" in solver_label else "urgency_margin"
    )

    with st.expander("Custom Scenario JSON"):
        uploaded_file = st.file_uploader(
            "Upload Custom Scenario (.json)",
            type=["json"],
            help="Upload a custom dataset with 'batches', 'destinations', and 'routes'.",
        )
        if uploaded_file is not None:
            try:
                raw_bytes = uploaded_file.getvalue()
                load_scenario_from_json(raw_bytes)
                custom_json_bytes = raw_bytes
                st.success("Custom scenario validated & loaded!")
            except (ValidationError, ValueError, KeyError) as exc:
                st.error(f"Invalid scenario schema: {exc}")

    st.markdown("<div style='margin: 18px 0; border-top: 1px solid #334155;'></div>", unsafe_allow_html=True)

    st.markdown(
        """
        <div style="background-color: #0f172a; padding: 14px; border-radius: 8px; border: 1px solid #334155;">
            <div style="font-size: 0.68rem; font-weight: 800; color: #94a3b8; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 8px;">
                Engine Architecture
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.78rem; color: #cbd5e1; margin-bottom: 5px;">
                <span>Active Batches</span>
                <span style="color: #f8fafc; font-weight: 600;">9 Batches (27.8T)</span>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.78rem; color: #cbd5e1; margin-bottom: 5px;">
                <span>Target Mandis</span>
                <span style="color: #f8fafc; font-weight: 600;">10 Market Lines</span>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.78rem; color: #cbd5e1; margin-bottom: 5px;">
                <span>Accessibility</span>
                <span style="color: #38bdf8; font-weight: 600;">WCAG AA + Patterns</span>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.78rem; color: #cbd5e1;">
                <span>Constraints State</span>
                <span style="color: #38bdf8; font-weight: 600;">Strictly Enforced</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ----------------- MAIN DASHBOARD CONTENT -----------------

st.title("FreshRoute: Perishable Produce Distribution System")
st.caption("PS 07 — IEEE RAS VITC Buildathon — Decision Support for MoFPI Post-Harvest Loss Mitigation")

base_res, fresh_res, mc_report, batch_df, scenario_json = run_cached_simulation(
    custom_json_bytes=custom_json_bytes,
    seasonality_mode=seasonality_mode,
    add_spot_order=add_spot_order,
    fleet_breakdown_pct=fleet_breakdown_pct,
    disruption_active=disruption_toggle,
    transit_delay=transit_delay,
    demand_shock=demand_shock,
    ambient_temp_c=ambient_temp_c,
    min_buffer=min_buffer,
    max_discount=max_discount,
    solver_mode=solver_mode,
)

profit_gain = fresh_res.net_profit - base_res.net_profit
profit_pct = (profit_gain / max(abs(base_res.net_profit), 1.0)) * 100.0

spoilage_delta = fresh_res.spoilage_rate_pct - base_res.spoilage_rate_pct
fulfill_delta = fresh_res.demand_fulfillment_pct - base_res.demand_fulfillment_pct

fresh_accepted_kg = sum(a.sold_qty_kg for a in fresh_res.allocations)
base_accepted_kg = sum(a.sold_qty_kg for a in base_res.allocations)
vol_delta = fresh_accepted_kg - base_accepted_kg

st.markdown("### Operational and Financial Overview")

row1_col1, row1_col2 = st.columns(2)
with row1_col1:
    render_metric_card(
        title="Net Profit",
        main_val=format_inr(fresh_res.net_profit),
        vs_val=format_inr(base_res.net_profit),
        delta_text=(
            f"+{format_inr(profit_gain)} ({profit_pct:+.1f}%)"
            if profit_gain >= 0
            else f"-{format_inr(abs(profit_gain))} ({profit_pct:.1f}%)"
        ),
        is_positive=profit_gain >= 0,
        arrow="↑" if profit_gain >= 0 else "↓",
    )

with row1_col2:
    render_metric_card(
        title="Spoilage Rate",
        main_val=f"{fresh_res.spoilage_rate_pct}%",
        vs_val=f"{base_res.spoilage_rate_pct}%",
        delta_text=(
            f"{abs(spoilage_delta):.2f}% pts reduction"
            if spoilage_delta <= 0
            else f"{spoilage_delta:+.2f}% pts increase"
        ),
        is_positive=spoilage_delta <= 0,
        arrow="↓" if spoilage_delta <= 0 else "↑",
    )

row2_col1, row2_col2 = st.columns(2)
with row2_col1:
    render_metric_card(
        title="Demand Fulfillment",
        main_val=f"{fresh_res.demand_fulfillment_pct}%",
        vs_val=f"{base_res.demand_fulfillment_pct:.2f}%",
        delta_text=f"{fulfill_delta:+.2f}% points",
        is_positive=fulfill_delta >= 0,
        arrow="↑" if fulfill_delta >= 0 else "↓",
    )

with row2_col2:
    render_metric_card(
        title="Usable Volume Cleared",
        main_val=f"{format_inr(fresh_accepted_kg, prefix='', decimals=0)} kg",
        vs_val=f"{format_inr(base_accepted_kg, prefix='', decimals=0)} kg",
        delta_text=(
            f"+{format_inr(vol_delta, prefix='', decimals=0)} kg"
            if vol_delta >= 0
            else f"-{format_inr(abs(vol_delta), prefix='', decimals=0)} kg"
        ),
        is_positive=vol_delta >= 0,
        arrow="↑" if vol_delta >= 0 else "↓",
    )

st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "Side-by-Side Comparison & Flow",
        "Dispatch Plan & Counterfactual Audit",
        "Uncertainty & Risk Analysis",
        "Inventory & Scenario Export",
    ]
)

with tab1:
    vcol1, vcol2 = st.columns(2)

    financial_df = pd.DataFrame(
        {
            "Category": [
                "Gross Revenue",
                "Logistics Cost",
                "Procurement Cost",
                "Spoilage Penalties",
                "Net Profit",
            ],
            "Baseline (FIFO)": [
                base_res.total_gross_revenue,
                base_res.total_transport_cost,
                base_res.total_procurement_cost,
                base_res.disposal_waste_cost,
                base_res.net_profit,
            ],
            "FreshRoute": [
                fresh_res.total_gross_revenue,
                fresh_res.total_transport_cost,
                fresh_res.total_procurement_cost,
                fresh_res.disposal_waste_cost,
                fresh_res.net_profit,
            ],
        }
    )

    fig_fin = go.Figure(
        data=[
            go.Bar(
                name="Baseline (FIFO)",
                x=financial_df["Category"],
                y=financial_df["Baseline (FIFO)"],
                marker_color="#64748b",
                marker_pattern_shape="/",
            ),
            go.Bar(
                name="FreshRoute",
                x=financial_df["Category"],
                y=financial_df["FreshRoute"],
                marker_color="#0284c7",
            ),
        ]
    )
    fig_fin.update_layout(
        title="Financial Comparison (INR)",
        barmode="group",
        legend_title_text="Strategy",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#cbd5e1"),
    )
    vcol1.plotly_chart(fig_fin, use_container_width=True)

    fig_metrics = go.Figure(
        data=[
            go.Bar(
                name="Baseline (FIFO)",
                x=["Spoilage %", "Fulfillment %"],
                y=[base_res.spoilage_rate_pct, base_res.demand_fulfillment_pct],
                marker_color="#d97706",
                marker_pattern_shape="x",
            ),
            go.Bar(
                name="FreshRoute",
                x=["Spoilage %", "Fulfillment %"],
                y=[fresh_res.spoilage_rate_pct, fresh_res.demand_fulfillment_pct],
                marker_color="#0284c7",
            ),
        ]
    )
    fig_metrics.update_layout(
        title="Operational Efficiency Comparison (%)",
        barmode="group",
        legend_title_text="Strategy",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#cbd5e1"),
    )
    vcol2.plotly_chart(fig_metrics, use_container_width=True)

    fig_sankey = build_sankey_figure(batch_df, fresh_res)
    st.plotly_chart(fig_sankey, use_container_width=True)

    insights = DecisionExplainer.explain_comparison(base_res, fresh_res)
    st.info(
        f"Audit Summary ({fresh_res.solve_time_ms:.2f} ms execution): {insights['Key Driver']}"
    )

with tab2:
    st.subheader("Traceable Dispatch Plan with Dynamic Discounting")
    audit_table = DecisionExplainer.generate_audit_table(fresh_res.allocations)
    st.dataframe(audit_table, use_container_width=True)

    safe_export_df = DecisionExplainer.generate_audit_table(
        fresh_res.allocations, sanitize_for_export=True
    )
    csv_data = safe_export_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Export Evidence-Backed Distribution Plan (CSV)",
        data=csv_data,
        file_name="freshroute_distribution_plan.csv",
        mime="text/csv",
    )

    st.markdown("---")
    st.subheader(
        f"Counterfactual Guardrail Log: Why Specific Routes Were Blocked ({len(fresh_res.rejected_routes)} Prevented)"
    )
    if fresh_res.rejected_routes:
        rej_table = DecisionExplainer.generate_rejection_table(fresh_res.rejected_routes)
        st.dataframe(rej_table, use_container_width=True)
    else:
        st.success("All candidate commodity corridors satisfied shelf-life and margin constraints.")

with tab3:
    st.subheader("Monte Carlo Sensitivity Analysis (±10% Shelf-Life/Demand, ±15% Transit Uncertainty)")
    ucol1, ucol2, ucol3 = st.columns(3)
    ucol1.metric("Expected Net Profit (Mean)", format_inr(mc_report.mean_net_profit))
    ucol2.metric("5th Percentile (Downside Risk)", format_inr(mc_report.p5_net_profit))
    ucol3.metric("95th Percentile (Upside Case)", format_inr(mc_report.p95_net_profit))

    fig_mc = go.Figure()
    fig_mc.add_trace(
        go.Bar(
            name="Profit Risk Bounds",
            x=[mc_report.p5_net_profit, mc_report.mean_net_profit, mc_report.p95_net_profit],
            y=["5th Percentile (P5)", "Expected Mean", "95th Percentile (P95)"],
            orientation="h",
            marker=dict(color=["#d97706", "#0284c7", "#38bdf8"]),
            text=[format_inr(mc_report.p5_net_profit), format_inr(mc_report.mean_net_profit), format_inr(mc_report.p95_net_profit)],
            textposition="auto",
        )
    )
    fig_mc.update_layout(
        title="Stochastic Profit Confidence Distribution (INR)",
        xaxis_title="Net Profit (INR)",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#cbd5e1"),
        height=260,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    st.plotly_chart(fig_mc, use_container_width=True)

    st.caption(
        f"Evaluated across {mc_report.runs} stochastic scenarios: "
        f"Mean Spoilage = {mc_report.mean_spoilage_pct:.2f}%, "
        f"Mean Fulfillment = {mc_report.mean_fulfillment_pct:.2f}%, "
        f"Profit Std Dev = {format_inr(mc_report.std_net_profit)}."
    )

with tab4:
    st.subheader("Current Warehouse Inventory Batches (Nashik Central Hub)")
    st.dataframe(batch_df, use_container_width=True)
    st.download_button(
        label="Download Active Scenario Template (.json)",
        data=scenario_json.encode("utf-8"),
        file_name="freshroute_scenario.json",
        mime="application/json",
    )