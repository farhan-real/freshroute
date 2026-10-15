# FreshRoute: Intelligent Decision Support for Perishable Produce Distribution

> Problem Statement PS 07 — Bugged Out! 8-Hour Buildathon | IEEE RAS VITC & VIT Chennai Office of Students' Welfare  
> Domain: Post-Harvest Supply Chain Optimization & Agri-Tech Decision Support  
> Target Alignment: India Ministry of Food Processing Industries (MoFPI) Post-Harvest Loss Mitigation

---

## 1. Executive Summary & Problem Context

India's Ministry of Food Processing Industries (MoFPI) reported severe post-harvest losses across 54 commodities in 15 agro-climatic zones, with fruits and vegetables suffering 15% to 25% waste between farm gates and retail markets. 

Traditional agricultural distributors rely on naive FIFO (First-In, First-Out) dispatching the oldest inventory to the first available destination order. This causes three critical supply chain failures:
1. In-Transit & Dock Spoilage: Batches with short shelf life are sent on long transit corridors and arrive with insufficient commercial shelf life (< 6.0h), causing retailers to reject and dump consignments at the loading dock.
2. Suboptimal Revenue Realization: High-perishability produce is dumped into low-price local markets instead of high-margin transit corridors.
3. Binary Pricing (Spoil or Sell): Produce is priced at 100% until it spoils, instead of applying dynamic clearance discounting to salvage near-expiry batches.

FreshRoute is a constrained decision-support engine that unifies remaining shelf-life estimates, transport matrices, dynamic pricing, and destination demand to produce a mathematically optimal, 100% explainable, and zero-in-transit-spoilage dispatch schedule.

---

## 2. Verified Benchmark Evaluation

Evaluated on the Maharashtra-Gujarat Agricultural Corridor (Nashik Central Hub distributing Tomatoes, Leafy Greens/Spinach, Alphonso Mangoes, and Onions across Mumbai, Pune, Surat, and Goa).

### Benchmark 1: Normal Operating Conditions
| Metric | Baseline (Naive FIFO) | FreshRoute Intelligent | Performance Delta |
| :--- | :---: | :---: | :---: |
| Total Inventory | 27,800 kg | 27,800 kg | — |
| Dispatched Quantity | 27,800 kg | 27,800 kg | — |
| Demand Fulfillment (%) | 74.68% | 89.10% | +14.4% points |
| Spoilage Loss (kg) | 4,500 kg | 0 kg | -100% Spoilage |
| Spoilage Rate (%) | 16.19% | 0.00% | -16.19% points |
| Gross Realized Revenue | ₹10,67,400.00 | ₹12,36,807.00 | +₹1,69,407.00 (+15.9%) |
| Logistics & Freight Cost | ₹81,110.00 | ₹92,210.00 | Route optimization trade-off |
| Spoilage Penalties | ₹22,500.00 | ₹0.00 | Saved ₹22,500.00 |
| NET PROFIT | ₹3,21,690.00 (3.21 L) | ₹5,02,497.00 (5.02 L) | +₹1,80,807.00 (+56.2%) |

---

### Benchmark 2: Robustness Stress-Test (Monsoon Disruption)
Scenario: Simulated Monsoon Highway Blockade (+6.0h Transit Delays across all corridors) + Market Demand Shock (-30% drop).

| Stress Metric under Severe Shock | Baseline (Naive FIFO) | FreshRoute Resilient | Performance Delta |
| :--- | :---: | :---: | :---: |
| Spoiled Produce (kg) | 6,550 kg | 4,500 kg | 2,050 kg saved from dump |
| Spoilage Rate (%) | 23.56% | 16.19% | -7.37% points lower waste |
| NET PROFIT PRESERVED | ₹1,68,525.00 (1.68 L) | ₹3,31,568.00 (3.31 L) | +₹1,63,043.00 (+96.7%) |

---

## 3. Core Technical Architecture

FreshRoute is engineered across three decoupled layers:

```
[ Raw Inputs: Batches, Mandi Demands, Routes ]
                       |
                       v
+-------------------------------------------------------------+
| 1. Constraint & Feasibility Layer (models.py)               |
|    - Hard Bounds: S_i >= T_ij + H_j + Buffer (2.0h)         |
|    - Transport Vehicle Capacity & Mandi Demand Caps         |
+-------------------------------------------------------------+
                       |
                       v
+-------------------------------------------------------------+
| 2. Intelligent Optimization Engine (freshroute_solver.py)   |
|    - Multi-Objective Priority Index (Margin x Urgency)      |
|    - Dynamic Salvage Discounting (0% - 25% Decay Curve)     |
+-------------------------------------------------------------+
                       |
                       v
+-------------------------------------------------------------+
| 3. Audit & Explainability Layer (explainability.py)         |
|    - Line-item trace: Base cost, Freight, Net Margin/kg     |
|    - Evidence-backed reasoning for every single kilogram    |
+-------------------------------------------------------------+
                       |
         +-------------+-------------+
         v                           v
[ CLI Benchmark (run_demo.py) ]  [ Interactive Dashboard (app.py) ]
```

### Key Engineering Safeguards:
1. Zero In-Transit Spoilage Guarantee: Enforces strict inequality S_i >= T_ij + H_j + safe_buffer, where S_i is batch shelf life, T_ij is route transit time, H_j is destination handling time, and safe_buffer is 2.0h minimum arrival buffer.
2. Targeted Dynamic Clearance Discounting: When arrival buffer is between 2h and 12h, the engine dynamically applies a calibrated clearance discount (up to 25%) to ensure immediate mandi turnover and prevent commercial rejection.
3. Traceable Decision Audit: Every dispatch includes a transparent mathematical proof showing gross revenue, freight cost per kg, applied discount, and exact business justification.

---

## 4. Repository Structure

```
freshroute/
|-- README.md                  # Documentation and verified benchmark metrics
|-- pytest.ini                 # Pytest root configuration
|-- requirements.txt           # Deterministic Python dependencies
|-- run_demo.py                # 1-Command CLI benchmark evaluator (Indian numbering)
|-- app.py                     # Streamlit executive dashboard & interactive simulator
|-- engine/
|   |-- __init__.py
|   |-- models.py              # Pydantic data schemas & constraint validations
|   |-- baseline_solver.py     # Naive FIFO baseline with commercial dock inspection
|   |-- freshroute_solver.py   # Multi-objective optimization & dynamic discounting
|   |-- explainability.py      # Line-by-line financial audit & narrative generator
|   `-- data_generator.py      # Indian agro-corridor datasets & disruption simulator
`-- tests/
    `-- test_freshroute.py     # Pytest verification suite (4/4 passed)
```

---

## 5. Quickstart & Reproducibility Guide

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

---

## 6. Verification Commands

### 1. Run the Terminal Benchmark
Executes side-by-side comparison tables against the baseline under normal and disrupted conditions:
```bash
python run_demo.py
```

### 2. Run the Automated Test Suite
Verifies that all constraints and arrival buffers are respected:
```bash
pytest tests/test_freshroute.py -v
```

### 3. Launch the Interactive Dashboard
Opens the Streamlit control panel with interactive policy sliders, disruption toggles, and CSV export:
```bash
streamlit run app.py
```

---

## 7. Sample Traceable Audit Record

Excerpt from the automated dispatch table generated by explainability.py:

| Batch ID | Commodity | Destination | Quantity (kg) | Buffer at Arrival | Discount % | Net Margin (₹/kg) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| B-MNG-01 | Mango | Goa Supermarkets (DEST-GOA-M) | 1,500.0 | 56.0 h | 0% | ₹72.50 / kg |
| B-MNG-01 | Mango | Mumbai Export (DEST-MUM-M) | 500.0 | 64.0 h | 0% | ₹56.00 / kg |
| B-MNG-02 | Mango | Mumbai Export (DEST-MUM-M) | 1,800.0 | 40.0 h | 0% | ₹54.00 / kg |
| B-TOM-02 | Tomato | Goa Hospitality (DEST-GOA-T) | 2,000.0 | 20.0 h | 0% | ₹19.00 / kg |
| B-SPN-01 | Spinach | Mumbai Retail Hub (DEST-MUM-S) | 1,500.0 | 8.0 h | 8% | ₹16.40 / kg |

---

## 8. Real-World Relevance & Commercial Model

* Target Users: Agricultural Produce Distributors, Farmer Producer Organizations (FPOs), APMC Commission Agents, Cold-Storage Hub Operators.
* Commercial Model: SaaS decision-support subscription for wholesale agri-distributors and 3PL cold-chain operators.
* Economic Value: Reduces post-harvest losses by >16%, increases distributor net margins by over 56%, and preserves grower capital during road disruptions.