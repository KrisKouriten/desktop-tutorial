"""
Allocation engine orchestrator.
Wires the full pipeline: load → ROS → newness → need → fair share → output.
"""
from allocation.loader import load_all
from allocation.rate_of_sale import calculate_ros
from allocation.newness import apply_newness
from allocation.need import calculate_need
from allocation.fair_share import allocate_fair_share
from allocation.output import write_allocation_output, print_summary_stats


def run(data_dir, output_dir, config):
    """
    Execute the weekly allocation pipeline.

    Steps:
    1. Load and validate all input data
    2. Calculate rate of sale (with optional recency weighting)
    3. Apply newness overlays for new SKUs
    4. Calculate store need (with safety stock, grade-based cover, min presentation)
    5. Allocate warehouse stock using priority-weighted fair share
    6. Write output and print summary

    Args:
        data_dir: Directory containing input CSVs
        output_dir: Directory for output files
        config: Configuration module

    Returns:
        Final allocation DataFrame
    """
    # Step 1: Load data
    data = load_all(data_dir)

    # Step 2: Calculate rate of sale
    use_weighted = getattr(config, "ROS_USE_WEIGHTED", False)
    print(f"Calculating rate of sale ({'weighted' if use_weighted else 'simple average'})...")
    ros_df = calculate_ros(
        sales_df=data["sales"],
        store_range_df=data["store_range"],
        ros_weeks=config.ROS_WEEKS,
        ros_floor=config.ROS_FLOOR,
        use_weighted=use_weighted,
    )
    active_ros = ros_df[ros_df["ros"] > 0]
    print(f"  {len(active_ros):,} store/SKU pairs with active ROS\n")

    # Step 3: Apply newness (like-for-like replacement)
    print("Applying newness overlays...")
    new_skus = data["sku_master"][data["sku_master"]["is_new"] == 1]
    if not new_skus.empty:
        ros_df = apply_newness(
            ros_df=ros_df,
            sku_master_df=data["sku_master"],
            store_range_df=data["store_range"],
        )
        new_with_ros = ros_df[ros_df["sku"].isin(new_skus["sku"]) & (ros_df["ros"] > 0)]
        print(f"  {len(new_with_ros):,} new SKU/store pairs assigned ROS via like-for-like\n")
    else:
        print("  No new SKUs to process.\n")

    # Step 4: Calculate store need
    woc_by_grade = getattr(config, "WEEKS_OF_COVER_BY_GRADE", {})
    safety_z = getattr(config, "SAFETY_STOCK_Z", 0)
    print(f"Calculating store needs (cover by grade: {woc_by_grade}, safety Z={safety_z})...")
    need_df = calculate_need(
        ros_df=ros_df,
        store_soh_df=data["store_soh"],
        sku_master_df=data["sku_master"],
        store_range_df=data["store_range"],
        config=config,
    )
    active_need = need_df[need_df["need"] > 0]
    print(f"  {len(active_need):,} store/SKU pairs with positive need\n")

    # Step 5: Fair share allocation
    include_incoming = getattr(config, "INCLUDE_INCOMING_STOCK", False)
    phase_factor = getattr(config, "REPLACED_SKU_ALLOCATION_FACTOR", 1.0)
    print(f"Running fair share allocation (incoming={'yes' if include_incoming else 'no'}, "
          f"phase-down={phase_factor})...")
    allocation_df = allocate_fair_share(
        need_df=need_df,
        warehouse_soh_df=data["warehouse"],
        sku_master_df=data["sku_master"],
        config=config,
    )
    allocated = allocation_df[allocation_df["allocated_qty"] > 0]
    print(f"  {len(allocated):,} allocations generated\n")

    # Step 6: Output
    print("Writing output...")
    write_allocation_output(
        allocation_df=allocation_df,
        need_df=need_df,
        sku_master_df=data["sku_master"],
        warehouse_soh_df=data["warehouse"],
        output_dir=output_dir,
    )

    # Summary
    print_summary_stats(allocation_df, need_df, data["sku_master"])

    return allocation_df
