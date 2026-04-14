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

25 tests covering: ROS (simple + weighted + demand std), need (grade-based cover, safety stock, min presentation, pack size), fair share (proportional, grade priority, incoming stock, phase-down, capacity, reserve), and newness (like-for-like, category fallback, range filtering).

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
