"""app.py: FreshRoute Interactive Decision-Support Dashboard."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from engine.data_generator import get_standard_scenario, apply_disruption
from engine.baseline_solver import BaselineSolver
from engine.freshroute_solver import FreshRouteSolver
from engine.explainability import DecisionExplainer


def format_inr(number: float, prefix: str = "₹", decimals: int = 0) -> str:
    """Formats float into Indian Numbering System (Lakhs, Crores)."""
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


def render_metric_card(title: str, main_val: str, vs_val: str, delta_text: str, is_positive: bool, arrow: str):
    """Renders a modern metric card with side-by-side values, independent arrow direction, and colored badge."""
    badge_bg = "rgba(16, 185, 129, 0.15)" if is_positive else "rgba(239, 68, 68, 0.15)"
    badge_color = "#10b981" if is_positive else "#ef4444"
    badge_border = "1px solid rgba(16, 185, 129, 0.3)" if is_positive else "1px solid rgba(239, 68, 68, 0.3)"

    card_html = f"""
    <div style="background-color: #1e293b; padding: 18px 22px; border-radius: 10px; border: 1px solid #334155; margin-bottom: 16px;">
        <div style="color: #94a3b8; font-size: 0.95rem; font-weight: 500; margin-bottom: 8px;">{title}</div>
        <div style="display: flex; align-items: baseline; flex-wrap: wrap; gap: 12px; margin-bottom: 10px;">
            <span style="color: #ffffff; font-size: 1.75rem; font-weight: 700; letter-spacing: -0.02em;">{main_val}</span>
            <span style="color: #94a3b8; font-size: 1.35rem; font-weight: 500;">vs {vs_val}</span>
        </div>
        <div style="display: inline-flex; align-items: center; gap: 6px; background-color: {badge_bg}; color: {badge_color}; border: {badge_border}; font-size: 0.85rem; font-weight: 600; padding: 4px 10px; border-radius: 9999px;">
            <span>{arrow}</span>
            <span>{delta_text}</span>
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


st.set_page_config(
    page_title="FreshRoute | Decision Support System",
    layout="wide"
)

st.title("FreshRoute: Perishable Produce Distribution System")
st.caption("PS 07 - IEEE RAS VITC Buildathon - Decision Support for MoFPI Post-Harvest Loss Mitigation")

# Sidebar Controls
st.sidebar.header("Scenario and Policy Controls")

disruption_toggle = st.sidebar.toggle("Simulate Supply-Chain Shock (Disruption)", value=False)
if disruption_toggle:
    transit_delay = st.sidebar.slider("Highway Transit Delay (Hours)", 1.0, 12.0, 6.0, step=0.5)
    demand_shock = st.sidebar.slider("Destination Demand Drop (%)", 0, 50, 30, step=5) / 100.0
else:
    transit_delay = 0.0
    demand_shock = 0.0

st.sidebar.markdown("---")
st.sidebar.subheader("FreshRoute Parameters")
min_buffer = st.sidebar.slider("Minimum Safe Shelf Buffer (Hours)", min_value=1.0, max_value=8.0, value=2.0, step=0.5)
max_discount = st.sidebar.slider("Maximum Dynamic Discount (%)", min_value=5, max_value=40, value=25, step=5) / 100.0

# Load Data
batches, destinations, routes = get_standard_scenario()
if disruption_toggle:
    routes, destinations = apply_disruption(routes, destinations, delay_hours=transit_delay, demand_shock_pct=-demand_shock)

# Execute Solvers
baseline_solver = BaselineSolver()
fresh_solver = FreshRouteSolver(min_safe_buffer_hrs=min_buffer, max_discount_pct=max_discount)

base_res = baseline_solver.solve(batches, destinations, routes)
fresh_res = fresh_solver.solve(batches, destinations, routes)

# Calculations
profit_gain = fresh_res.net_profit - base_res.net_profit
profit_pct = (profit_gain / max(abs(base_res.net_profit), 1)) * 100

spoilage_delta = fresh_res.spoilage_rate_pct - base_res.spoilage_rate_pct
fulfill_delta = fresh_res.demand_fulfillment_pct - base_res.demand_fulfillment_pct

fresh_accepted_kg = sum(a.quantity_kg for a in fresh_res.allocations if a.shelf_life_buffer_hrs >= min_buffer)
base_accepted_kg = sum(a.quantity_kg for a in base_res.allocations if a.shelf_life_buffer_hrs >= 6.0)
vol_delta = fresh_accepted_kg - base_accepted_kg

st.markdown("### Operational and Financial Overview")

# 2-Row Layout (2x2 Grid)
row1_col1, row1_col2 = st.columns(2)
with row1_col1:
    render_metric_card(
        title="Net Profit",
        main_val=format_inr(fresh_res.net_profit),
        vs_val=format_inr(base_res.net_profit),
        delta_text=f"+{format_inr(profit_gain)} ({profit_pct:+.1f}%)" if profit_gain >= 0 else f"-{format_inr(abs(profit_gain))} ({profit_pct:.1f}%)",
        is_positive=profit_gain >= 0,
        arrow="↑" if profit_gain >= 0 else "↓"
    )

with row1_col2:
    render_metric_card(
        title="Spoilage Rate",
        main_val=f"{fresh_res.spoilage_rate_pct}%",
        vs_val=f"{base_res.spoilage_rate_pct}%",
        delta_text=f"{abs(spoilage_delta):.1f}% reduction" if spoilage_delta <= 0 else f"{spoilage_delta:+.1f}% increase",
        is_positive=spoilage_delta <= 0,
        arrow="↓" if spoilage_delta <= 0 else "↑"
    )

row2_col1, row2_col2 = st.columns(2)
with row2_col1:
    render_metric_card(
        title="Demand Fulfillment",
        main_val=f"{fresh_res.demand_fulfillment_pct}%",
        vs_val=f"{base_res.demand_fulfillment_pct:.1f}%",
        delta_text=f"{fulfill_delta:+.1f}% points" if fulfill_delta >= 0 else f"{fulfill_delta:.1f}% points",
        is_positive=fulfill_delta >= 0,
        arrow="↑" if fulfill_delta >= 0 else "↓"
    )

with row2_col2:
    render_metric_card(
        title="Usable Volume Delivered",
        main_val=f"{format_inr(fresh_accepted_kg, prefix='', decimals=0)} kg",
        vs_val=f"{format_inr(base_accepted_kg, prefix='', decimals=0)} kg",
        delta_text=f"+{format_inr(vol_delta, prefix='', decimals=0)} kg" if vol_delta >= 0 else f"-{format_inr(abs(vol_delta), prefix='', decimals=0)} kg",
        is_positive=vol_delta >= 0,
        arrow="↑" if vol_delta >= 0 else "↓"
    )

st.markdown("---")

# Visual Comparison Tabs
tab1, tab2, tab3 = st.tabs(["Side-by-Side Comparison", "Detailed Dispatch Plan and Audit", "Inventory Batches"])

with tab1:
    vcol1, vcol2 = st.columns(2)
    
    financial_df = pd.DataFrame({
        "Category": ["Gross Revenue", "Logistics Cost", "Procurement Cost", "Spoilage Penalties", "Net Profit"],
        "Baseline (FIFO)": [base_res.total_gross_revenue, base_res.total_transport_cost, base_res.total_procurement_cost, base_res.disposal_waste_cost, base_res.net_profit],
        "FreshRoute": [fresh_res.total_gross_revenue, fresh_res.total_transport_cost, fresh_res.total_procurement_cost, fresh_res.disposal_waste_cost, fresh_res.net_profit]
    })
    
    fig_fin = go.Figure(data=[
        go.Bar(name='Baseline (FIFO)', x=financial_df['Category'], y=financial_df['Baseline (FIFO)'], marker_color='#94a3b8'),
        go.Bar(name='FreshRoute', x=financial_df['Category'], y=financial_df['FreshRoute'], marker_color='#10b981')
    ])
    fig_fin.update_layout(title="Financial Comparison (INR)", barmode='group')
    vcol1.plotly_chart(fig_fin, use_container_width=True)

    fig_metrics = go.Figure(data=[
        go.Bar(name='Baseline (FIFO)', x=['Spoilage %', 'Fulfillment %'], y=[base_res.spoilage_rate_pct, base_res.demand_fulfillment_pct], marker_color='#ef4444'),
        go.Bar(name='FreshRoute', x=['Spoilage %', 'Fulfillment %'], y=[fresh_res.spoilage_rate_pct, fresh_res.demand_fulfillment_pct], marker_color='#06b6d4')
    ])
    fig_metrics.update_layout(title="Operational Efficiency Comparison (%)", barmode='group')
    vcol2.plotly_chart(fig_metrics, use_container_width=True)

    insights = DecisionExplainer.explain_comparison(base_res, fresh_res)
    st.info(f"Audit Summary: {insights['Key Driver']}")

with tab2:
    st.subheader("Traceable Dispatch Plan with Dynamic Discounting")
    audit_table = DecisionExplainer.generate_audit_table(fresh_res.allocations)
    st.dataframe(audit_table, use_container_width=True)

    csv_data = audit_table.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Export Evidence-Backed Distribution Plan (CSV)",
        data=csv_data,
        file_name='freshroute_distribution_plan.csv',
        mime='text/csv'
    )

with tab3:
    st.subheader("Current Warehouse Inventory Batches (Nashik Central Hub)")
    batch_df = pd.DataFrame([b.model_dump() for b in batches])
    st.dataframe(batch_df, use_container_width=True)