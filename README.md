# Weekly Store Allocation Model

Allocation model for a 60+ store retail business with 8000+ SKUs. Calculates weekly stock allocations from warehouse to stores based on rate of sale, store grading, safety stock, and fair share logic.

## Key Features

- **Store Grading (A/B/C)**: Flagship stores get more weeks of cover and priority when stock is constrained
- **Weighted Rate of Sale**: Recent weeks count more than older weeks — catches trending products faster
- **Safety Stock**: Buffer based on demand variability (configurable service level: 90%, 95%, 98%)
- **Minimum Presentation Qty**: Ensures stores have enough units for visual merchandising (by grade)
- **Incoming Stock**: Pipeline/incoming warehouse stock factored into available inventory
- **Fair Share with Priority**: Proportional allocation using largest-remainder method, weighted by store grade
- **Newness / Like-for-Like**: New SKUs inherit ROS from the SKU they replace, or fall back to category averages
- **Replaced SKU Phase-Down**: Old SKUs being replaced get reduced allocation to clear space for newness
- **Store Capacity Limits**: Max weekly intake per store prevents overloading receiving docks
- **Transparent Output**: Every allocation includes ROS, SOH, ideal stock, safety stock, and post-allocation weeks of cover

## Quick Start

```bash
pip install -r requirements.txt

# Generate sample data
python data/samples/generate_sample_data.py

# Option 1: Web app (recommended)
streamlit run streamlit_app.py

# Option 2: Command line
python run_allocation.py --data-dir data/samples
```

## Web App

The Streamlit app provides a full interactive interface:

```bash
streamlit run streamlit_app.py
```

**Features:**
- Upload CSVs or use sample data with one click
- Adjust all parameters with sliders (weeks of cover, safety stock, reserve %, priority weights)
- Data preview with validation
- KPI dashboard (fill rate, total allocated, units by grade)
- Filterable allocation detail table (by store, category, grade)
- SKU summary, store summary, and constrained SKU views
- Charts showing allocation distribution by grade and store
- Download allocation detail and summary as CSV

## Input Files

Place these CSVs in your data directory (see `data/samples/` for examples):

| File | Columns | Description |
|------|---------|-------------|
| `sales_history.csv` | `week_ending, store_id, sku, qty_sold` | Weekly sales (8+ weeks) |
| `warehouse_soh.csv` | `sku, warehouse_soh, incoming_stock` | Warehouse stock + pipeline |
| `store_soh.csv` | `store_id, sku, store_soh` | Current store stock |
| `store_range.csv` | `store_id, sku, in_range, store_grade*, max_weekly_intake*` | Range matrix with optional grade and capacity |
| `sku_master.csv` | `sku, description, category, is_new, replaces_sku, pack_size` | SKU metadata + newness mapping |

*Optional columns — defaults to grade "B" and unlimited intake if not provided.

### Store Grades

Add a `store_grade` column to `store_range.csv`:

| Grade | Description | Default Cover | Priority | Min Presentation |
|-------|-------------|---------------|----------|-----------------|
| **A** | Flagship / high volume | 5 weeks | 1.3x | 3 units |
| **B** | Mid-tier | 4 weeks | 1.0x | 2 units |
| **C** | Smaller / lower volume | 3 weeks | 0.8x | 1 unit |

## Output

Generates two files in the output directory:

- **`allocation_YYYY-MM-DD.csv`** — Detail: one row per store/SKU with store grade, ROS, SOH, ideal stock, safety stock, allocated qty, and **weeks of cover after allocation**
- **`allocation_summary_YYYY-MM-DD.csv`** — Summary: one row per SKU with total allocated, fill rate, average weeks of cover after allocation

## Configuration

Edit `config.py` or use command-line arguments:

```bash
# Adjust weeks of cover and safety level
python run_allocation.py --data-dir data --weeks-of-cover 3 --safety-z 1.65

# Change warehouse reserve and disable weighted ROS
python run_allocation.py --data-dir data --reserve-pct 0.10 --no-weighted-ros

# Adjust replaced SKU phase-down (0.0 = stop entirely, 1.0 = no change)
python run_allocation.py --data-dir data --phase-down 0.50

# Exclude incoming/pipeline stock from available inventory
python run_allocation.py --data-dir data --no-incoming
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ROS_WEEKS` | 8 | Weeks of sales history for ROS calculation |
| `ROS_USE_WEIGHTED` | True | Weight recent weeks more heavily |
| `WEEKS_OF_COVER_BY_GRADE` | A=5, B=4, C=3 | Target cover by store grade |
| `GRADE_PRIORITY_MULTIPLIER` | A=1.3, B=1.0, C=0.8 | Allocation priority when constrained |
| `SAFETY_STOCK_Z` | 1.28 | Safety stock Z-score (1.28=90%, 1.65=95%) |
| `WAREHOUSE_RESERVE_PCT` | 0.05 | Hold back 5% for emergencies |
| `INCLUDE_INCOMING_STOCK` | True | Include pipeline stock in available inventory |
| `REPLACED_SKU_ALLOCATION_FACTOR` | 0.25 | Reduce old SKU allocation to 25% |
| `MIN_PRESENTATION_QTY` | A=3, B=2, C=1 | Minimum display units by grade |
| `DEFAULT_MAX_WEEKLY_INTAKE` | 0 | Max units per store per week (0=unlimited) |
| `MIN_ALLOCATION_QTY` | 1 | Don't send fewer than this |

## How It Works

1. **Load & Validate** — Reads all CSVs, validates schemas, cross-references SKUs and stores
2. **Rate of Sale** — Computes weekly ROS per store/SKU (weighted or simple average) plus demand variability
3. **Newness** — New SKUs get ROS + demand_std from their like-for-like replacement or category average
4. **Need** — `ideal_stock = (ROS x weeks_of_cover_for_grade) + safety_stock`; `need = max(0, ideal - SOH)`, rounded to pack size. Enforces minimum presentation quantity.
5. **Fair Share** — Allocates warehouse stock per SKU. Includes incoming stock. Applies grade priority weighting. Phases down replaced SKUs. Respects store capacity limits. Full fill if enough stock; priority-weighted proportional with largest-remainder rounding if constrained.
6. **Output** — Writes detail and summary CSVs with post-allocation weeks of cover, prints console summary with grade breakdown.

## For New Products (Like-for-Like)

In `sku_master.csv`, set:
- `is_new = 1` for new SKUs
- `replaces_sku = SKU_OLD_CODE` to map the old SKU it replaces

The model will:
1. Use the old SKU's per-store ROS and demand variability to allocate the new product
2. Automatically phase down the old SKU's allocation (default: 25% of normal)
3. If no replacement is mapped, fall back to category average ROS

## Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

43 tests covering: ROS (simple + weighted + demand std), need (grade-based cover, safety stock, min presentation, pack size), fair share (proportional, grade priority, incoming stock, phase-down, capacity, reserve), newness (like-for-like, category fallback, range filtering), and WAC (FX conversion, cost-pool amortisation by qty/value, mixed-currency pools, landed cost, opening+receipts blend).

---

## Weighted Average Cost (WAC) Model

Companion model that computes a new WAC per SKU from **opening stock on hand + inbound receipts**. Each receipt is landed at:

```
Landed unit cost = Invoice price
                 + Amortised Freight
                 + Amortised Duty
                 + Amortised Goods-In
```

All foreign-currency costs are translated to GBP via a **dynamic costing FX rate**, overridable at runtime for what-if analysis.

### Quick Start

```bash
# Generate sample WAC data
python data/samples/wac/generate_sample_wac_data.py

# CLI run
python run_wac.py --data-dir data/samples/wac

# With FX overrides (USD 0.82 and EUR 0.86 instead of file values)
python run_wac.py --data-dir data/samples/wac --fx USD=0.82 --fx EUR=0.86

# Interactive Streamlit app
streamlit run streamlit_wac.py
```

### Input Files

| File | Columns | Description |
|------|---------|-------------|
| `opening_stock.csv` | `sku, opening_qty, opening_wac_gbp` | Existing stock + its current GBP WAC |
| `receipts.csv` | `receipt_id, shipment_id, sku, receipt_date, qty, invoice_ccy, invoice_unit_cost` | Inbound receipt lines |
| `cost_pools.csv` | `shipment_id, freight_cost, freight_ccy, duty_cost, duty_ccy, goods_in_cost, goods_in_ccy, amortise_basis` | Per-shipment cost pools. `amortise_basis` is `qty` or `value` |
| `fx_rates.csv` | `ccy, rate_to_gbp` | Costing rates (GBP per 1 unit of CCY) |

### How It Works

1. **Load & validate** — All four CSVs, with cross-reference checks (orphan shipments warned).
2. **FX** — Build a `{ccy -> rate_to_gbp}` lookup. GBP is always 1.0. CLI `--fx CCY=RATE` or the Streamlit FX editor override rates live.
3. **Amortise cost pools** — For each shipment, convert freight/duty/goods-in totals to GBP, then split across the shipment's receipt lines. Two bases:
   - `qty` — proportional to units received (use for volume-driven costs like freight-per-carton, goods-in labour).
   - `value` — proportional to GBP invoice value (use for ad-valorem costs like customs duty).
4. **Landed cost** — Per line: `landed_unit_gbp = invoice_unit_gbp + amort_freight_unit_gbp + amort_duty_unit_gbp + amort_goods_in_unit_gbp`.
5. **WAC roll-up** — Per SKU: `new_wac = (opening_value + Σ landed_line) / (opening_qty + Σ receipt_qty)`. Zero-qty SKUs get WAC 0.
6. **Output** — `wac_summary_YYYY-MM-DD.csv` (one row per SKU) and `wac_receipt_detail_YYYY-MM-DD.csv` (per-line landed cost).

### WAC Project Layout

```
├── run_wac.py                      # CLI entry point
├── streamlit_wac.py                # Streamlit app (dynamic FX editor)
├── wac/
│   ├── loader.py                   # Load & validate the 4 CSVs
│   ├── fx.py                       # Costing-rate lookup + USD->GBP helper
│   ├── amortise.py                 # Split freight/duty/goods-in across lines
│   ├── landed.py                   # Invoice + amortised uplifts = landed cost
│   ├── wac.py                      # Roll opening + receipts into new WAC
│   ├── engine.py                   # Pipeline orchestrator
│   └── output.py                   # CSV writer + console summary
├── data/samples/wac/               # Sample data (20 SKUs, 40 receipts, 6 shipments)
└── tests/test_wac.py               # 18 WAC unit tests
```

## Project Structure

```
├── streamlit_app.py           # Streamlit web app
├── run_allocation.py          # CLI entry point
├── config.py                  # All configurable parameters
├── allocation/
│   ├── loader.py              # CSV loading & validation (incl. store grade)
│   ├── rate_of_sale.py        # Weighted ROS + demand variability
│   ├── need.py                # Grade-based cover + safety stock + min presentation
│   ├── fair_share.py          # Priority-weighted allocation + phase-down + capacity
│   ├── newness.py             # Like-for-like replacement (ROS + demand_std)
│   ├── engine.py              # Pipeline orchestrator
│   └── output.py              # Output with post-allocation weeks of cover
├── data/samples/              # Sample data (65 stores, 80 SKUs, 3 grades)
├── output/                    # Generated allocation files
└── tests/                     # 25 unit tests
```
