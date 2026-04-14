# Weekly Store Allocation Model

Allocation model for a 60+ store retail business with 8000+ SKUs. Calculates weekly stock allocations from warehouse to stores based on rate of sale, current stock levels, store range availability, and fair share logic.

## Key Features

- **Rate of Sale (ROS)**: Calculates average weekly sales per store/SKU over a configurable lookback window
- **Range-Aware**: Only allocates to stores that carry each SKU — respects range availability
- **Fair Share**: When warehouse stock is limited, allocates proportionally using the largest-remainder method
- **Newness / Like-for-Like**: New SKUs with no sales history inherit ROS from the SKU they replace, or fall back to category averages
- **Configurable**: Target weeks of cover, warehouse reserve %, minimum allocation qty, ROS lookback period
- **Transparent Output**: Every allocation includes the ROS, SOH, ideal stock, and need — no black-box decisions

## Quick Start

```bash
pip install -r requirements.txt

# Generate sample data and run
python data/samples/generate_sample_data.py
python run_allocation.py --data-dir data/samples
```

## Input Files

Place these CSVs in your data directory (see `data/samples/` for examples):

| File | Description |
|------|-------------|
| `sales_history.csv` | Weekly sales: `week_ending, store_id, sku, qty_sold` |
| `warehouse_soh.csv` | Warehouse stock: `sku, warehouse_soh, incoming_stock` |
| `store_soh.csv` | Store stock: `store_id, sku, store_soh` |
| `store_range.csv` | Range matrix: `store_id, sku, in_range` (1=carries, 0=doesn't) |
| `sku_master.csv` | SKU metadata: `sku, description, category, is_new, replaces_sku, pack_size` |

## Output

Generates two files in the output directory:

- **`allocation_YYYY-MM-DD.csv`** — Detail: one row per store/SKU allocation with full transparency (ROS, SOH, ideal stock, need, allocated qty)
- **`allocation_summary_YYYY-MM-DD.csv`** — Summary: one row per SKU with total allocated, fill rate, stores receiving

## Configuration

Edit `config.py` or use command-line arguments:

```bash
python run_allocation.py --data-dir data --weeks-of-cover 3 --reserve-pct 0.10 --ros-weeks 6
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ROS_WEEKS` | 8 | Weeks of sales history for ROS calculation |
| `TARGET_WEEKS_OF_COVER` | 4 | Target weeks of stock each store should hold |
| `WAREHOUSE_RESERVE_PCT` | 0.05 | Hold back 5% of warehouse stock for emergencies |
| `MIN_ALLOCATION_QTY` | 1 | Minimum units to allocate (avoid trivial shipments) |
| `ROS_FLOOR` | 0.1 | Ignore ROS below this threshold |

## How It Works

1. **Load & Validate** — Reads all CSVs, validates schemas, cross-references SKUs
2. **Rate of Sale** — Computes average weekly sales per store/SKU over the lookback window
3. **Newness** — New SKUs get ROS from their like-for-like replacement or category average
4. **Need** — `ideal_stock = ROS x weeks_of_cover`; `need = max(0, ideal - current_SOH)`, rounded to pack size
5. **Fair Share** — Allocates warehouse stock per SKU. Full fill if enough stock; proportional with largest-remainder rounding if constrained
6. **Output** — Writes detail and summary CSVs, prints console summary

## For New Products (Like-for-Like)

In `sku_master.csv`, set:
- `is_new = 1` for new SKUs
- `replaces_sku = SKU_OLD_CODE` to map the old SKU it replaces

The model will use the old SKU's per-store ROS to allocate the new product. If no replacement is mapped, it falls back to the category average ROS.

## Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

## Project Structure

```
├── run_allocation.py          # Entry point
├── config.py                  # Configuration parameters
├── allocation/
│   ├── loader.py              # CSV loading & validation
│   ├── rate_of_sale.py        # ROS calculation
│   ├── need.py                # Store need calculation
│   ├── fair_share.py          # Proportional allocation engine
│   ├── newness.py             # Like-for-like replacement
│   ├── engine.py              # Pipeline orchestrator
│   └── output.py              # Output formatting
├── data/samples/              # Sample data for testing
├── output/                    # Generated allocation files
└── tests/                     # Unit tests
```
