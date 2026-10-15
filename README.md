# FreshRoute: Intelligent Decision Support for Perishable Produce Distribution

> Problem Statement PS 07 | Bugged Out! 8-Hour Solo Software Buildathon  
> Organized by IEEE Robotics & Automation Society (RAS), VITC Student Chapter & VIT Chennai Office of Students' Welfare  
> Reference Domain: Post-Harvest Supply Chain Optimization & Agri-Tech Decision Support  
> Government Alignment: Ministry of Food Processing Industries (MoFPI) Post-Harvest Loss Mitigation Study

---

## 1. Executive Summary & Root Challenge

India's Ministry of Food Processing Industries (MoFPI) documented post-harvest losses across 54 commodities in 15 agro-climatic zones, showing that 15% to 25% of harvested fruits and vegetables spoil before reaching retail consumers.

Traditional agricultural distributors rely on naive First-In, First-Out (FIFO) rules, dispatching the oldest inventory to incoming destination queues. This results in three critical operational breakdowns:
1. In-Transit and Dock Spoilage: Batches with tight shelf life are dispatched on long transit routes, arriving with less than the contracted commercial retail window (< 6.0h). Mandi dock inspectors reject and dump whole truckloads.
2. Suboptimal Margin Realization: High-perishability produce is dumped in saturated local markets instead of distant, high-margin consumption corridors.
3. Binary Pricing: Distributors demand full price until produce rots, rather than applying dynamic clearance discounting to salvage near-expiry batches.

FreshRoute is a constrained decision-support engine that unifies remaining shelf-life estimates, cold-chain thermal telemetry, transport matrices, dynamic pricing, and destination demand to produce a mathematically optimal, 100% explainable, and zero-in-transit-spoilage dispatch plan.

---

## 2. Core Platform Capabilities & Technical Features

### Advanced Constrained Optimization & Dual-Solver Engine
* Dual-Mode Solvers: Seamlessly toggle between an ultra-low-latency Urgency-Margin heuristic (0.259 ms execution) for real-time dispatch and an exact SciPy HiGHS Linear Programming (simplex/interior-point) solver for global mathematical optimality.
* Zero In-Transit Spoilage: Hard physical constraint validation ensures no batch is allocated unless Remaining Shelf Life >= Transit Time + Handling Time + Safety Buffer (2.0h default).
* Dynamic Clearance Discounting: Automatically calculates a calibrated 0% to 25% price reduction for batches arriving with tight shelf-life windows (< 12.0h), clearing stock to secondary processors before commercial dock rejection occurs.
* Market Clearance Elasticity: Models realistic buyer price-sensitivity to prevent clearance paradoxes; if discounts on near-expiry goods are restricted, the engine reflects the resulting destination spoilage.
* Counterfactual Guardrail Log: Automatically audits and records every infeasible (Batch, Destination) pair, explaining why specific corridors were rejected (insufficient buffer, negative contribution, or missing route).

### Supply Chain Risk & IoT Cold-Chain Simulation
* Biological Q10 Thermal Respiration Decay: Models refrigerated container failures. When transit temperatures rise from 4°C to 14°C, produce shelf life degrades twice as fast, automatically triggering dynamic rerouting to closer hubs.
* Monte Carlo Stochastic Risk Engine: Evaluates 30+ simultaneous perturbation runs across ±10% shelf-life variance, ±15% transit delays, and ±10% demand fluctuations to establish 5th to 95th percentile confidence intervals.
* Resilient Disruption Replanning: Instantly recalculates viable corridors during highway blockades (+6.0h delays) or market demand contractions (-30%).
* Dynamic Event Injection: Supports mid-day quick-commerce spot orders (e.g., 1,800 kg dark store Tomato orders at ₹42/kg) and sudden fleet breakdown capacity reductions.
* Seasonality Demand Forecasting: Four pre-configured demand profiles (Normal, Festival Surge +10% to +30%, Weekend Mandi Rush +5% to +25%, Monsoon Dip -5% to -25%).

### Defensive Engineering & Enterprise Security
* Strict Schema Boundaries: Pydantic v2 enforces non-negative procurement costs, bounded quantities, positive transit hours, and valid string identifiers.
* XSS-Sanitized Presentation: All dynamic parameters injected into custom dashboard components pass through HTML escaping to prevent cross-site scripting vulnerabilities.
* CSV Formula Injection Neutralization: Exported audit manifests automatically prefix spreadsheet formula triggers (`=`, `+`, `-`, `@`, tab) with a single quote to block remote command execution in Microsoft Excel and LibreOffice Calc.
* Custom Scenario Ingestion Guardrails: JSON file uploader enforces strict byte-size limits and schema validation for hidden judge evaluations.

### Universal Accessibility & Low-Resource Environments
* WCAG AA High Contrast: Dashboard typography exceeds the 4.5:1 contrast ratio using pure white (`#ffffff`) and slate (`#cbd5e1`) against a `#1e293b` container background.
* Colorblind-Safe Visualization: Visual charts use an Okabe-Ito inspired palette (Slate `#64748b`, Sky Blue `#0284c7`, Amber `#d97706`) completely independent of red-green reliance.
* Monochrome Pattern Fills: Plotly bar charts integrate distinct geometric patterns (`/` diagonal stripes, `x` crosshatch) ensuring readability in grayscale printouts.
* Supply-Chain Mass Flow (Sankey): Full visual flow tracing produce from initial harvest batches through intermediary mandis into cleared sales, reserve stock, or expired discard.
* Headless ASCII CLI: Built-in `--ascii` flag provides a terminal interface stripped of ANSI escape codes and Unicode box characters for screen readers and low-bandwidth remote SSH sessions.

---

## 3. Verified Benchmark Results

Evaluated on the Maharashtra-Gujarat Agricultural Corridor (Nashik Central Hub distributing Tomatoes, Leafy Greens/Spinach, Alphonso Mangoes, and Onions across Mumbai, Pune, Surat, and Goa).

### Benchmark 1: Normal Operating Conditions
| Metric | Baseline (Naive FIFO) | FreshRoute Intelligent | Performance Delta |
| :--- | :---: | :---: | :---: |
| Total Inventory | 27,800 kg | 27,800 kg | Identical input |
| Dispatched Quantity | 27,800 kg | 27,800 kg | 100% fleet utilization |
| Demand Fulfillment (%) | 74.68% | 89.10% | +14.42% points gain |
| Spoilage Loss (kg) | 4,500 kg | 0 kg | -100% spoilage eliminated |
| Spoilage Rate (%) | 16.19% | 0.00% | -16.19% points reduction |
| Gross Realized Revenue | ₹10,67,400.00 | ₹12,36,807.00 | +₹1,69,407.00 (+15.9%) |
| Logistics & Freight Cost | ₹81,110.00 | ₹92,210.00 | Optimal routing trade-off |
| Spoilage Penalties | ₹22,500.00 | ₹0.00 | Saved ₹22,500.00 |
| NET PROFIT | ₹3,21,690.00 (3.21 L) | ₹5,02,497.00 (5.02 L) | +₹1,80,807.00 (+56.2% boost) |
| Computational Solve Time | 0.115 ms | 0.259 ms | Sub-millisecond execution |

### Benchmark 2: Stress-Test under Severe Disruption
Scenario: Simulated Monsoon Highway Blockade (+6.0h Transit Delays across all corridors) + Market Demand Shock (-30% drop).

| Stress Metric under Severe Shock | Baseline (Naive FIFO) | FreshRoute Resilient | Performance Delta |
| :--- | :---: | :---: | :---: |
| Spoiled Produce (kg) | 6,550 kg | 4,500 kg | 2,050 kg saved from dump |
| Spoilage Rate (%) | 23.56% | 16.19% | -7.37% points lower waste |
| NET PROFIT PRESERVED | ₹1,68,525.00 (1.68 L) | ₹3,31,568.00 (3.31 L) | +₹1,63,043.00 (+96.7% gain) |

### Benchmark 3: Monte Carlo Uncertainty Analysis (30 Stochastic Runs)
Evaluated across simultaneous noise variations: ±10% in remaining shelf life, ±15% in highway transit times, and ±10% in mandi demand:
* Expected Net Profit (Mean): ₹4,99,410.62
* 5th Percentile (Downside Risk): ₹4,90,668.00
* 95th Percentile (Upside Case): ₹5,09,229.00
* Mean Spoilage Rate: 0.21%
* Mean Demand Fulfillment: 88.94%

---

## 4. Technical Architecture

FreshRoute operates across three decoupled modules:

```
[ Inputs: Harvest Batches, Cold-Chain Temp, Mandi Demands, Freight Corridors ]
                                      |
                                      v
+--------------------------------------------------------------------------+
| 1. Constraint & Security Validation Layer (engine/models.py)             |
|    - Hard Bounds: Shelf Life >= Transit Time + Handling Time + Buffer    |
|    - Enforces Vehicle Capacity, Mandi Demands & Dock Reception Limits    |
|    - Pydantic V2 Type Enforcement, Range Bounds & XSS/JSON Guards        |
+--------------------------------------------------------------------------+
                                      |
                                      v
+--------------------------------------------------------------------------+
| 2. Optimization & Analytics Engine (engine/freshroute_solver.py)         |
|    - Dual Solver Modes:                                                  |
|        a) Urgency-Margin Priority Heuristic (Sub-millisecond latency)    |
|        b) SciPy HiGHS Exact Linear Programming (Simplex / Interior Pt)   |
|    - Targeted Clearance Discounting (0% - 25% curve on < 12h buffer)     |
|    - Clearance Elasticity: Models market absorption to prevent paradoxes |
|    - Counterfactual Audit Logger: Tracks and explains rejected corridors |
|    - Q10 Biological Respiration Law for Cold-Chain Thermal Excursions    |
|    - Monte Carlo Stochastic Uncertainty & Sensitivity Analysis           |
+--------------------------------------------------------------------------+
                                      |
                                      v
+--------------------------------------------------------------------------+
| 3. Explainability, Accessibility & Delivery (engine/explainability.py)   |
|    - Full Line-Item Audit Trail: Gross, Freight, Margin/kg, Rationale    |
|    - CSV Formula Injection Sanitization (Neutralizes Excel DDE Payloads) |
|    - WCAG AA Accessible Web UI (app.py) + Colorblind-Safe Okabe-Ito Fills|
|    - Sankey Mass-Flow Chart: Batch -> Mandi -> Market Outcome            |
|    - Screen-Reader Semantic ARIA Regions & Headless ASCII CLI Mode       |
+--------------------------------------------------------------------------+
```

---

## 5. Automated Test Suite (18/18 Tests Passing)

The project includes 18 automated unit and integration tests executed via Pytest:

```text
tests/test_freshroute.py::test_freshroute_outperforms_baseline PASSED
tests/test_freshroute.py::test_zero_in_transit_spoilage_for_freshroute PASSED
tests/test_freshroute.py::test_capacity_and_demand_constraints_respected PASSED
tests/test_freshroute.py::test_disruption_handling_robustness PASSED
tests/test_freshroute.py::test_lp_highs_solver_mode PASSED
tests/test_freshroute.py::test_max_reception_capacity_and_vehicle_cap_in_both_solvers PASSED
tests/test_freshroute.py::test_discount_ceiling_does_not_over_discount PASSED
tests/test_freshroute.py::test_counterfactual_rejected_routes_logged PASSED
tests/test_freshroute.py::test_seasonality_demand_forecasting PASSED
tests/test_freshroute.py::test_dynamic_replanning_spot_order_and_breakdown PASSED
tests/test_freshroute.py::test_json_scenario_roundtrip_and_size_guard PASSED
tests/test_freshroute.py::test_boundary_empty_and_100pct_infeasible_network PASSED
tests/test_freshroute.py::test_clearance_elasticity_and_fulfillment_alignment PASSED
tests/test_freshroute.py::test_temperature_excursion_decay PASSED
tests/test_freshroute.py::test_monte_carlo_uncertainty_evaluation PASSED
tests/test_freshroute.py::test_csv_injection_sanitization PASSED
tests/test_freshroute.py::test_indian_number_formatting PASSED
tests/test_freshroute.py::test_pydantic_constraint_validations PASSED

======================== 18 passed in 0.73s ========================
```

---

## 6. Sample Traceable Audit Record (Real Output)

Excerpt from the automated dispatch table generated by `explainability.py`:

| Batch ID | Commodity | Destination | Quantity (kg) | Buffer at Arrival | Discount % | Net Margin (₹/kg) | Audit Reason |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| B-MNG-01 | Mango | Goa Supermarkets (DEST-GOA-M) | 1,500.0 | 56.0 h | 0% | ₹72.50 / kg | FreshRoute: Margin ₹72.5/kg. Buffer 56.0h. Full Price: Adequate commercial buffer. |
| B-MNG-01 | Mango | Mumbai Export (DEST-MUM-M) | 500.0 | 64.0 h | 0% | ₹56.00 / kg | FreshRoute: Margin ₹56.0/kg. Buffer 64.0h. Full Price: Adequate commercial buffer. |
| B-MNG-02 | Mango | Mumbai Export (DEST-MUM-M) | 1,800.0 | 40.0 h | 0% | ₹54.00 / kg | FreshRoute: Margin ₹54.0/kg. Buffer 40.0h. Full Price: Adequate commercial buffer. |
| B-TOM-02 | Tomato | Goa Hospitality (DEST-GOA-T) | 2,000.0 | 20.0 h | 0% | ₹19.00 / kg | FreshRoute: Margin ₹19.0/kg. Buffer 20.0h. Full Price: Adequate commercial buffer. |
| B-SPN-01 | Spinach | Mumbai Retail Hub (DEST-MUM-S) | 1,500.0 | 8.0 h | 8% | ₹16.40 / kg | FreshRoute: Margin ₹16.4/kg. Buffer 8.0h. Dynamic clearance 8% applied: 100% inventory cleared in time. |

## Example Custom Scenario Schema (JSON)

You can upload a custom dataset via the sidebar expander in the web dashboard or pass it to `python run_demo.py --scenario <path>.json`. The payload must adhere to the following schema:

```json
{
  "batches": [
    {
      "batch_id": "B-TOM-TEST-01",
      "commodity": "Tomato",
      "quantity_kg": 2000.0,
      "remaining_shelf_life_hrs": 20.0,
      "base_cost_per_kg": 14.0,
      "origin": "Hub-Nashik",
      "storage_temp_c": 4.0
    },
    {
      "batch_id": "B-SPN-TEST-01",
      "commodity": "Spinach",
      "quantity_kg": 1500.0,
      "remaining_shelf_life_hrs": 9.0,
      "base_cost_per_kg": 20.0,
      "origin": "Hub-Nashik",
      "storage_temp_c": 4.0
    }
  ],
  "destinations": [
    {
      "dest_id": "DEST-MUM-TEST",
      "name": "Mumbai Vashi APMC Mandi",
      "commodity": "Tomato",
      "demand_kg": 2500.0,
      "selling_price_per_kg": 32.0,
      "handling_time_hrs": 2.0,
      "max_reception_capacity_kg": 3000.0
    },
    {
      "dest_id": "DEST-PUN-TEST",
      "name": "Pune Local Wholesale Outlets",
      "commodity": "Spinach",
      "demand_kg": 1500.0,
      "selling_price_per_kg": 36.0,
      "handling_time_hrs": 1.0,
      "max_reception_capacity_kg": 2000.0
    }
  ],
  "routes": [
    {
      "origin": "Hub-Nashik",
      "dest_id": "DEST-MUM-TEST",
      "travel_time_hrs": 4.5,
      "cost_per_kg": 2.5,
      "vehicle_capacity_kg": 5000.0
    },
    {
      "origin": "Hub-Nashik",
      "dest_id": "DEST-PUN-TEST",
      "travel_time_hrs": 3.0,
      "cost_per_kg": 1.8,
      "vehicle_capacity_kg": 4000.0
    }
  ]
}
```

---

## 7. Quickstart & Verification Commands

### Step 1: Set Up Virtual Environment

Windows (PowerShell):
```powershell
py -3.12 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Linux / macOS:
```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

### Step 2: Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Run the Terminal Benchmark
Standard mode:
```bash
python run_demo.py
```

Accessible ASCII mode (for screen readers and low-bandwidth terminals):
```bash
python run_demo.py --ascii
```

Custom scenario evaluation mode (for judge datasets):
```bash
python run_demo.py --scenario ./tests/custom_scenario.json
```

### Step 4: Run the Complete Automated Test Suite
```bash
pytest tests/test_freshroute.py -v
```

### Step 5: Launch the Interactive Dashboard
```bash
streamlit run app.py
```

---

## 8. Commercial Relevance & Future Integration

* Primary Beneficiaries: Farmer Producer Organizations (FPOs), APMC Commission Agents, Cold-Storage Warehouse Operators, and Wholesale Produce Aggregators.
* Economic Value Proposition: Reduces distributor spoilage losses by over 16 percentage points, increases net profits by 56.2%, and prevents capital wipeout during seasonal road blockages.
* National Systems Integration: Architecture is structured for direct API ingestion from e-NAM (National Agriculture Market) electronic price tickers, ONDC logistics networks, and IoT container temperature loggers.