"""app.py: FreshRoute Interactive Decision-Support Dashboard."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from engine.data_generator import get_standard_scenario, apply_disruption
from engine.baseline_solver import BaselineSolver
from engine.freshroute_solver import FreshRouteSolver
from engine.explainability import DecisionExplainer

st.set_page_config(
    page_title="FreshRoute | Decision Support System",
    page_icon="🥦",
    layout="wide"
)

st.title("🥦 FreshRoute: Perishable Produce Distribution System")
st.caption("PS 07 • IEEE RAS VITC Buildathon • Decision Support for MoFPI Post-Harvest Loss Mitigation")

# Sidebar Controls
st.sidebar.header("🕹️ Scenario & Policy Controls")

disruption_toggle = st.sidebar.toggle("Simulate Supply-Chain Shock (Disruption)", value=False)
if disruption_toggle:
    transit_delay = st.sidebar.slider("Highway Transit Delay (Hours)", 1.0, 12.0, 5.0)
    demand_shock = st.sidebar.slider("Destination Demand Drop (%)", 0, 50, 25) / 100.0
else:
    transit_delay = 0.0
    demand_shock = 0.0

st.sidebar.markdown("---")
st.sidebar.subheader("FreshRoute Parameters")
min_buffer = st.sidebar.slider("Minimum Safe Shelf Buffer (Hours)", 2.0, 12.0, 6.0)
max_discount = st.sidebar.slider("Maximum Dynamic Discount (%)", 10, 50, 35) / 100.0

# Load Data
batches, destinations, routes = get_standard_scenario()
if disruption_toggle:
    routes, destinations = apply_disruption(routes, destinations, delay_hours=transit_delay, demand_shock_pct=-demand_shock)

# Execute Solvers
baseline_solver = BaselineSolver()
fresh_solver = FreshRouteSolver(min_safe_buffer_hrs=min_buffer, max_discount_pct=max_discount)

base_res = baseline_solver.solve(batches, destinations, routes)
fresh_res = fresh_solver.solve(batches, destinations, routes)

# Top KPIs
col1, col2, col3, col4 = st.columns(4)

profit_gain = fresh_res.net_profit - base_res.net_profit
col1.metric("FreshRoute Net Profit", f"₹{fresh_res.net_profit:,.0f}", f"+₹{profit_gain:,.0f} vs Baseline")
col2.metric("Spoilage Rate", f"{fresh_res.spoilage_rate_pct}%", f"{fresh_res.spoilage_rate_pct - base_res.spoilage_rate_pct:.1f}% vs Baseline", delta_color="inverse")
col3.metric("Demand Fulfillment", f"{fresh_res.demand_fulfillment_pct}%", f"{fresh_res.demand_fulfillment_pct - base_res.demand_fulfillment_pct:.1f}% vs Baseline")
col4.metric("Dispatched Volume", f"{fresh_res.dispatched_kg:,.0f} kg", f"{fresh_res.dispatched_kg - base_res.dispatched_kg:+,.0f} kg")

st.markdown("---")

# Visual Comparison
tab1, tab2, tab3 = st.tabs(["📊 Side-by-Side Comparison", "📑 Detailed Dispatch Plan & Audit", "📦 Inventory Batches"])

with tab1:
    vcol1, vcol2 = st.columns(2)
    
    # Financial breakdown
    financial_df = pd.DataFrame({
        "Category": ["Gross Revenue", "Logistics Cost", "Procurement Cost", "Spoilage Penalties", "Net Profit"],
        "Baseline (FIFO)": [base_res.total_gross_revenue, base_res.total_transport_cost, base_res.total_procurement_cost, base_res.disposal_waste_cost, base_res.net_profit],
        "FreshRoute": [fresh_res.total_gross_revenue, fresh_res.total_transport_cost, fresh_res.total_procurement_cost, fresh_res.disposal_waste_cost, fresh_res.net_profit]
    })
    
    fig_fin = go.Figure(data=[
        go.Bar(name='Baseline (FIFO)', x=financial_df['Category'], y=financial_df['Baseline (FIFO)'], marker_color='#94a3b8'),
        go.Bar(name='FreshRoute', x=financial_df['Category'], y=financial_df['FreshRoute'], marker_color='#10b981')
    ])
    fig_fin.update_layout(title="Financial Comparison (₹ INR)", barmode='group')
    vcol1.plotly_chart(fig_fin, use_container_width=True)

    # Spoilage vs Fulfillment
    fig_metrics = go.Figure(data=[
        go.Bar(name='Baseline (FIFO)', x=['Spoilage %', 'Fulfillment %'], y=[base_res.spoilage_rate_pct, base_res.demand_fulfillment_pct], marker_color='#ef4444'),
        go.Bar(name='FreshRoute', x=['Spoilage %', 'Fulfillment %'], y=[fresh_res.spoilage_rate_pct, fresh_res.demand_fulfillment_pct], marker_color='#06b6d4')
    ])
    fig_metrics.update_layout(title="Operational Efficiency Comparison (%)", barmode='group')
    vcol2.plotly_chart(fig_metrics, use_container_width=True)

    # Explanatory Card
    insights = DecisionExplainer.explain_comparison(base_res, fresh_res)
    st.info(f"💡 **Audit Summary**: {insights['Key Driver']}")

with tab2:
    st.subheader("Traceable Dispatch Plan with Dynamic Discounting")
    audit_table = DecisionExplainer.generate_audit_table(fresh_res.allocations)
    st.dataframe(audit_table, use_container_width=True)

    # Download CSV button for judges
    csv_data = audit_table.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Export Evidence-Backed Distribution Plan (CSV)",
        data=csv_data,
        file_name='freshroute_distribution_plan.csv',
        mime='text/csv'
    )

with tab3:
    st.subheader("Current Warehouse Inventory Batches (Nashik Central Hub)")
    batch_df = pd.DataFrame([b.model_dump() for b in batches])
    st.dataframe(batch_df, use_container_width=True)