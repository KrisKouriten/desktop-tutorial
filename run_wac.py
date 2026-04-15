"""
Weighted Average Cost (WAC) Model — CLI runner
===============================================
Computes a new WAC per SKU from opening stock on hand plus inbound
receipts. Receipts are landed at:

    Invoice + Amortised Freight + Amortised Duty + Amortised Goods-In

All foreign-currency costs are converted to GBP using a dynamic
costing FX rate loaded from fx_rates.csv (with optional CLI overrides).

Usage:
    python run_wac.py
    python run_wac.py --data-dir data/samples/wac --output-dir output
    python run_wac.py --fx USD=0.82 --fx EUR=0.86

Input files expected in data directory:
    - opening_stock.csv   (sku, opening_qty, opening_wac_gbp)
    - receipts.csv        (receipt_id, shipment_id, sku, receipt_date,
                           qty, invoice_ccy, invoice_unit_cost)
    - cost_pools.csv      (shipment_id,
                           freight_cost, freight_ccy,
                           duty_cost, duty_ccy,
                           goods_in_cost, goods_in_ccy,
                           amortise_basis)
    - fx_rates.csv        (ccy, rate_to_gbp)

See data/samples/wac/ for example file formats.
"""
import argparse
import sys

import config
from wac.engine import run


def _parse_fx_overrides(fx_args):
    """Parse --fx USD=0.82 into {'USD': 0.82}."""
    overrides = {}
    if not fx_args:
        return overrides
    for entry in fx_args:
        if "=" not in entry:
            raise ValueError(f"--fx expects CCY=RATE, got '{entry}'")
        ccy, rate = entry.split("=", 1)
        ccy = ccy.strip().upper()
        try:
            rate_f = float(rate)
        except ValueError as e:
            raise ValueError(f"--fx rate for {ccy} must be numeric, got '{rate}'") from e
        if rate_f <= 0:
            raise ValueError(f"--fx rate for {ccy} must be positive, got {rate_f}")
        overrides[ccy] = rate_f
    return overrides


def main():
    parser = argparse.ArgumentParser(
        description="Weighted average cost model (landed cost + dynamic FX)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  python run_wac.py --data-dir data/samples/wac\n"
            "  python run_wac.py --fx USD=0.82 --fx EUR=0.86"
        ),
    )
    parser.add_argument(
        "--data-dir",
        default=f"{config.DATA_DIR}/samples/wac",
        help="Directory containing WAC input CSVs",
    )
    parser.add_argument(
        "--output-dir",
        default=config.OUTPUT_DIR,
        help=f"Directory for output files (default: {config.OUTPUT_DIR})",
    )
    parser.add_argument(
        "--fx",
        action="append",
        metavar="CCY=RATE",
        help="Override a costing FX rate (GBP per 1 unit of CCY). "
             "Repeat for multiple currencies, e.g. --fx USD=0.82 --fx EUR=0.86",
    )
    args = parser.parse_args()

    try:
        fx_overrides = _parse_fx_overrides(args.fx)
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(2)

    print("=" * 60)
    print("WEIGHTED AVERAGE COST MODEL")
    print("=" * 60)
    print(f"  Data directory:   {args.data_dir}")
    print(f"  Output directory: {args.output_dir}")
    if fx_overrides:
        ov_str = ", ".join(f"{c}={r}" for c, r in sorted(fx_overrides.items()))
        print(f"  FX overrides:     {ov_str}")
    print("=" * 60 + "\n")

    try:
        run(
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            fx_overrides=fx_overrides,
        )
    except FileNotFoundError as e:
        print(f"\nERROR: Input file not found: {e}")
        print("Make sure all required CSVs exist in your data directory.")
        print("Run with --data-dir data/samples/wac to test with sample data.")
        sys.exit(1)
    except ValueError as e:
        print(f"\nERROR: Data validation failed: {e}")
        sys.exit(1)
    except KeyError as e:
        print(f"\nERROR: Missing FX rate: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
