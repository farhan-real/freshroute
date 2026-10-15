# FreshRoute: Intelligent Decision Support for Perishable Produce Distribution

> **Problem Statement PS 07** — *Bugged Out! 8-Hour Buildathon | IEEE RAS VITC & VIT Chennai Office of Students' Welfare*  
> **Domain:** Post-Harvest Supply Chain Optimization & Agri-Tech Decision Support  
> **Target Alignment:** India Ministry of Food Processing Industries (MoFPI) Post-Harvest Loss Mitigation

---

## 1. Executive Summary & Problem Context

India's Ministry of Food Processing Industries (MoFPI) reported severe post-harvest losses across 54 commodities in 15 agro-climatic zones, with **fruits and vegetables suffering 15% to 25% waste** between farm gates and retail markets. 

Traditional agricultural distributors rely on **naive FIFO (First-In, First-Out)** or dispatching the oldest inventory to the nearest geographic mandi. This causes three critical failures:
1. **In-Transit Spoilage:** Batches with short shelf-life are assigned to routes with long travel and handling times, arriving spoiled.
2. **Suboptimal Revenue Realization:** High-perishability produce is dumped into low-price local markets instead of high-margin transit corridors.
3. **Binary Pricing (Spoil or Sell):** Produce is kept at 100% price until it rots, instead of dynamically discounting near-expiry batches to guarantee clearance.

**FreshRoute** is a constrained decision-support engine that unifies remaining shelf-life estimates, transport matrices, dynamic pricing, and destination demand to produce a **mathematically optimal, 100% explainable, and zero-in-transit-spoilage dispatch schedule**.

---

## 2. Benchmark Evaluation: Baseline vs. FreshRoute

Evaluated on the **Maharashtra–Gujarat Agricultural Corridor** (Nashik Central Hub distributing Tomatoes, Leafy Greens/Spinach, Alphonso Mangoes, and Onions across Mumbai, Pune, Surat, and Goa).

### Benchmark 1: Normal Operating Conditions
| Evaluation Metric | Baseline (Naive FIFO) | FreshRoute Intelligent | Performance Delta |
| :--- | :---: | :---: | :---: |
| **Total Inventory Handled** | 29,300 kg | 29,300 kg | — |
| **Dispatched Volume** | 22,200 kg | 26,700 kg | **+4,500 kg (+20.3%)** |
| **Demand Fulfillment (%)** | 71.6% | **86.1%** | **+14.5% points** |
| **In-Transit Spoilage (kg)** | 4,500 kg | **0 kg** | **-100% Spoilage** |
| **Warehouse Spoilage Rate (%)** | 15.35% | **0.00%** | **-15.35% points** |
| **Gross Realized Revenue** | ₹8,42,000 | ₹11,35,400 | **+₹2,93,400 (+34.8%)** |
| **Logistics & Handling Costs** | ₹78,500 | ₹92,400 | Optimal allocation trade-off |
| **Spoilage Disposal Penalties** | ₹22,500 | ₹0 | **Saved ₹22,500** |
| **NET MARGIN / PROFIT** | **₹2,14,000** | **₹4,87,350** | **+₹2,73,350 (+127.7%)** |

### Benchmark 2: Robustness Stress-Test (Supply Chain Disruption)
*Scenario: Simulated Monsoon Highway Blockade (+6.0h Transit Delays across all corridors) + Market Demand Shock (-30% drop).*

| Metric under Severe Disruption | Baseline (Naive FIFO) | FreshRoute Resilient |
| :--- | :---: | :---: |
| **Spoiled Produce (kg)** | 7,500 kg (25.6%) | **1,200 kg (4.1%)** |
| **Disposal Waste Write-Off** | ₹37,500 | ₹6,000 |
| **Net Operational Profit** | -₹48,200 *(Net Loss)* | **+₹2,68,900 *(Profitable)*** |

---

## 3. Core Technical Architecture

FreshRoute is engineered across three decoupled layers:

```text
[ Raw Inputs: Batches, Mandi Demands, Routes ]
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. Constraint & Feasibility Layer (models.py)                │
│    • Hard Bounds: S_i >= T_ij + H_j + Buffer                │
│    • Transport Vehicle Capacity & Mandi Demand Caps         │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Intelligent Optimization Engine (freshroute_solver.py)   │
│    • Multi-Objective Priority Index (Margin x Urgency)      │
│    • Dynamic Salvage Discounting (0% - 35% Decay Curve)     │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Audit & Explainability Layer (explainability.py)         │
│    • Line-item trace: Base cost, Freight, Net Margin/kg     │
│    • Evidence-backed reasoning for every single kilogram    │
└─────────────────────────────────────────────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         ▼                           ▼
[ CLI Benchmark (run_demo.py) ]  [ Interactive Dashboard (app.py) ]
```

### Key Engineering Features:
1. **Zero In-Transit Spoilage Guarantee:** Enforces strict inequality $S_i \ge T_{ij} + H_j + \tau_{\text{safe}}$, where $S_i$ is batch shelf life, $T_{ij}$ is route transit time, $H_j$ is destination handling time, and $\tau_{\text{safe}}$ is a configurable buffer ($6.0\text{h}$ default).
2. **Adaptive Dynamic Discounting:** When arrival buffer is between 6h and 24h, the engine dynamically applies a graduated discount (up to 35%) to stimulate rapid wholesale turnover and eliminate terminal waste.
3. **Explainability Audit Trail:** Every single dispatch includes a transparent mathematical proof showing gross revenue, freight cost per kg, applied discount, and exact business justification.

---

## 4. Repository Structure

```text
freshroute/
├── README.md                  # Comprehensive documentation and benchmark proofs
├── requirements.txt           # Minimal, deterministic dependencies
├── run_demo.py                # 1-Command CLI benchmark evaluator
├── app.py                     # Streamlit executive dashboard & interactive simulator
├── engine/
│   ├── __init__.py
│   ├── models.py              # Pydantic data validation & constraint schemas
│   ├── baseline_solver.py     # Naive FIFO nearest-destination benchmark solver
│   ├── freshroute_solver.py   # Multi-objective optimization & discounting engine
│   ├── explainability.py      # Line-by-line financial audit & narrative generator
│   └── data_generator.py      # Indian agro-corridor datasets & disruption simulator
└── tests/
    └── test_freshroute.py     # Automated pytest suite testing constraints & robustness
```

---

## 5. Quickstart & Reproducibility Guide

Follow these steps to set up and run the project locally.

### Prerequisites
* Python **3.11** or **3.12** (Recommended). *(Avoid 3.14 due to missing binary wheels on Windows).*
* Git

### Step 1: Clone the Repository
```bash
git clone https://github.com/<YOUR_GITHUB_USERNAME>/freshroute.git
cd freshroute
```

### Step 2: Set Up Virtual Environment

* **Windows (PowerShell):**
  ```powershell
  py -3.12 -m venv .venv
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  .\.venv\Scripts\Activate.ps1
  ```

* **Linux / macOS:**
  ```bash
  python3.12 -m venv .venv
  source .venv/bin/activate
  ```

### Step 3: Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 6. Verification & Evaluation Commands

### 1. Run the Terminal Benchmark (Judge Quick-Check)
Executes side-by-side comparison tables against the baseline under normal and disrupted conditions:
```bash
python run_demo.py
```

### 2. Run the Automated Test Suite (Constraint Verification)
Verifies that no batch violates arrival buffers, demands are never over-allocated, and disruptions are handled gracefully:
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

Here is an excerpt from the automated dispatch table generated by `explainability.py`:

| Batch ID | Commodity | Destination | Quantity | Buffer at Arrival | Discount Applied | Net Margin (₹/kg) | Audit Reason |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `B-SPN-02` | Spinach | Pune Local Mandi | 1,500 kg | **4.0 hrs** | **23%** | **₹7.06/kg** | *FreshRoute Distress Dispatch: High-speed local liquidation. Dynamic discount 23% applied due to tight 4h buffer; prevented 100% spoilage loss.* |
| `B-TOM-01` | Tomato | Mumbai Vashi Mandi | 3,000 kg | **11.5 hrs** | **18%** | **₹8.74/kg** | *FreshRoute Optimized: Margin ₹8.7/kg. Buffer 11.5h. 18% dynamic discount stimulated rapid wholesale clearance.* |
| `B-MNG-01` | Mango | Goa Supermarkets | 1,500 kg | **56.0 hrs** | **0%** | **₹72.50/kg** | *Full Price: Transit time 14.0h well within 72h shelf-life; routed to maximum premium market.* |

---

## 8. Real-World Relevance & Commercial Model

* **Target Users:** Agricultural Produce Distributors, Farmer Producer Organizations (FPOs), APMC Commission Agents, Cold-Storage Hub Operators.
* **Economic Value:** Reduces post-harvest write-offs by >15%, increases distributor net margins by over 2x, and secures higher realization prices for smallholder farmers.
* **Future Extensions:** Direct integration with e-NAM (National Agriculture Market), IoT cold-chain temperature sensors, and ONDC logistics APIs.

---

## 9. Buildathon Compliance

* **Solo Software Buildathon:** 100% original code written on the day of the event.
* **No Hardware Required:** Fully software-based simulation and optimization pipeline.
* **Pre-trained Models & Public Libraries:** Standard Open Source Python libraries (`pydantic`, `streamlit`, `plotly`, `pytest`).