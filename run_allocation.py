"""
Weekly Retail Allocation Model
===============================
Allocates warehouse stock to 60+ stores based on rate of sale,
current stock levels, range availability, store grading, and fair share logic.

Usage:
    python run_allocation.py
    python run_allocation.py --data-dir data/samples --output-dir output
    python run_allocation.py --weeks-of-cover 3 --reserve-pct 0.10 --safety-z 1.65

Input files expected in data directory:
    - sales_history.csv
    - warehouse_soh.csv
    - store_soh.csv
    - store_range.csv  (with optional store_grade and max_weekly_intake columns)
    - sku_master.csv

See data/samples/ for example file formats.
"""
import argparse
import sys
import config
from allocation.engine import run


def main():
    parser = argparse.ArgumentParser(
        description="Weekly store allocation model",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example: python run_allocation.py --data-dir data/samples",
    )
    parser.add_argument(
        "--data-dir",
        default=config.DATA_DIR,
        help=f"Directory containing input CSVs (default: {config.DATA_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        default=config.OUTPUT_DIR,
        help=f"Directory for output files (default: {config.OUTPUT_DIR})",
    )
    parser.add_argument(
        "--weeks-of-cover",
        type=int,
        default=None,
        help=f"Target weeks of cover — overrides all grades (default: {config.TARGET_WEEKS_OF_COVER})",
    )
    parser.add_argument(
        "--ros-weeks",
        type=int,
        default=None,
        help=f"Weeks of sales history for ROS (default: {config.ROS_WEEKS})",
    )
    parser.add_argument(
        "--reserve-pct",
        type=float,
        default=None,
        help=f"Warehouse reserve percentage 0.0-1.0 (default: {config.WAREHOUSE_RESERVE_PCT})",
    )
    parser.add_argument(
        "--safety-z",
        type=float,
        default=None,
        help=f"Safety stock Z-score (1.28=90%%, 1.65=95%%, 2.05=98%%) (default: {config.SAFETY_STOCK_Z})",
    )
    parser.add_argument(
        "--no-weighted-ros",
        action="store_true",
        help="Use simple average ROS instead of recency-weighted",
    )
    parser.add_argument(
        "--no-incoming",
        action="store_true",
        help="Exclude incoming/pipeline stock from available inventory",
    )
    parser.add_argument(
        "--phase-down",
        type=float,
        default=None,
        help=f"Replaced SKU allocation factor 0.0-1.0 (default: {config.REPLACED_SKU_ALLOCATION_FACTOR})",
    )
    args = parser.parse_args()

    # Override config with CLI arguments
    if args.weeks_of_cover is not None:
        config.TARGET_WEEKS_OF_COVER = args.weeks_of_cover
        # Also override grade-specific targets to this value
        config.WEEKS_OF_COVER_BY_GRADE = {
            g: args.weeks_of_cover for g in config.WEEKS_OF_COVER_BY_GRADE
        }
    if args.ros_weeks is not None:
        config.ROS_WEEKS = args.ros_weeks
    if args.reserve_pct is not None:
        config.WAREHOUSE_RESERVE_PCT = args.reserve_pct
    if args.safety_z is not None:
        config.SAFETY_STOCK_Z = args.safety_z
    if args.no_weighted_ros:
        config.ROS_USE_WEIGHTED = False
    if args.no_incoming:
        config.INCLUDE_INCOMING_STOCK = False
    if args.phase_down is not None:
        config.REPLACED_SKU_ALLOCATION_FACTOR = args.phase_down

    woc_str = ", ".join(f"{g}={v}" for g, v in sorted(config.WEEKS_OF_COVER_BY_GRADE.items()))
    grade_prio = ", ".join(f"{g}={v}" for g, v in sorted(config.GRADE_PRIORITY_MULTIPLIER.items()))

    print("=" * 60)
    print("WEEKLY ALLOCATION MODEL")
    print("=" * 60)
    print(f"  Data directory:      {args.data_dir}")
    print(f"  Output directory:    {args.output_dir}")
    print(f"  ROS lookback weeks:  {config.ROS_WEEKS} ({'weighted' if config.ROS_USE_WEIGHTED else 'simple avg'})")
    print(f"  Weeks of cover:      {woc_str}")
    print(f"  Store grade priority:{grade_prio}")
    print(f"  Safety stock Z:      {config.SAFETY_STOCK_Z} (service level)")
    print(f"  Warehouse reserve:   {config.WAREHOUSE_RESERVE_PCT:.0%}")
    print(f"  Include incoming:    {'Yes' if config.INCLUDE_INCOMING_STOCK else 'No'}")
    print(f"  Phase-down factor:   {config.REPLACED_SKU_ALLOCATION_FACTOR}")
    print(f"  Min allocation qty:  {config.MIN_ALLOCATION_QTY}")
    print(f"  Min presentation:    {config.MIN_PRESENTATION_QTY}")
    print("=" * 60 + "\n")

    try:
        run(data_dir=args.data_dir, output_dir=args.output_dir, config=config)
    except FileNotFoundError as e:
        print(f"\nERROR: Input file not found: {e}")
        print("Make sure all required CSVs exist in your data directory.")
        print("Run with --data-dir data/samples to test with sample data.")
        sys.exit(1)
    except ValueError as e:
        print(f"\nERROR: Data validation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
