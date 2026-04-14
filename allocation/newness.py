"""
Like-for-like newness replacement.
For new SKUs without sales history, borrow ROS from the SKU they replace.
Falls back to category average if no replacement is mapped.
"""
import pandas as pd


def apply_newness(ros_df, sku_master_df, store_range_df):
    """
    Augment ROS data with estimates for new SKUs.

    For new SKUs (is_new == 1):
    1. If replaces_sku is set, use that SKU's ROS per store
    2. If replaces_sku also has no ROS (chained replacement), walk up to 2 levels
    3. Fall back to category average ROS per store

    Args:
        ros_df: Current ROS with columns [store_id, sku, ros, total_sold, active_weeks]
        sku_master_df: SKU master with [sku, category, is_new, replaces_sku]
        store_range_df: Range matrix with [store_id, sku]

    Returns:
        Updated ROS DataFrame with new SKUs included
    """
    new_skus = sku_master_df[sku_master_df["is_new"] == 1].copy()
    if new_skus.empty:
        return ros_df

    # Build replacement lookup: new_sku -> replaces_sku
    replacement_map = dict(
        zip(
            new_skus["sku"],
            new_skus["replaces_sku"],
        )
    )

    # Build category lookup
    sku_to_category = dict(zip(sku_master_df["sku"], sku_master_df["category"]))

    # Compute category average ROS per store (excluding new SKUs)
    existing_ros = ros_df[~ros_df["sku"].isin(new_skus["sku"])].copy()
    existing_ros["category"] = existing_ros["sku"].map(sku_to_category)

    cat_avg_ros = (
        existing_ros[existing_ros["ros"] > 0]
        .groupby(["store_id", "category"], as_index=False)["ros"]
        .mean()
        .rename(columns={"ros": "cat_avg_ros"})
    )

    # Get in-range pairs for new SKUs
    new_sku_set = set(new_skus["sku"])
    new_range = store_range_df[store_range_df["sku"].isin(new_sku_set)].copy()

    if new_range.empty:
        return ros_df

    new_rows = []

    for _, row in new_range.iterrows():
        store_id = row["store_id"]
        sku = row["sku"]
        ros_value = 0.0

        # Try to find replacement ROS (walk up to 2 levels)
        current_sku = sku
        for _ in range(2):
            replaces = replacement_map.get(current_sku, "")
            if not replaces:
                break
            # Look up the replacement SKU's ROS for this store
            match = existing_ros[
                (existing_ros["store_id"] == store_id) & (existing_ros["sku"] == replaces)
            ]
            if not match.empty and match.iloc[0]["ros"] > 0:
                ros_value = match.iloc[0]["ros"]
                break
            current_sku = replaces

        # Fall back to category average if no like-for-like found
        if ros_value == 0.0:
            category = sku_to_category.get(sku, "")
            cat_match = cat_avg_ros[
                (cat_avg_ros["store_id"] == store_id) & (cat_avg_ros["category"] == category)
            ]
            if not cat_match.empty:
                ros_value = round(cat_match.iloc[0]["cat_avg_ros"], 2)

        new_rows.append({
            "store_id": store_id,
            "sku": sku,
            "ros": ros_value,
            "total_sold": 0,
            "active_weeks": 0,
        })

    if new_rows:
        new_ros_df = pd.DataFrame(new_rows)
        # Remove any existing entries for new SKUs (they'd have 0 ROS)
        ros_df = ros_df[~ros_df["sku"].isin(new_sku_set)].copy()
        ros_df = pd.concat([ros_df, new_ros_df], ignore_index=True)

    return ros_df
