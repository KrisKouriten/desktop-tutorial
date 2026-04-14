"""
Store need calculation.
Determines how many units each store needs per SKU based on:
- ROS and target weeks of cover (by store grade)
- Safety stock buffer (based on demand variability)
- Minimum presentation quantity (by store grade)
- Current store SOH
"""
import math
import pandas as pd


def calculate_need(ros_df, store_soh_df, sku_master_df, store_range_df, config):
    """
    Calculate store need for each store/SKU combination.

    Args:
        ros_df: Rate of sale with columns [store_id, sku, ros, demand_std]
        store_soh_df: Store stock with columns [store_id, sku, store_soh]
        sku_master_df: SKU master with columns [sku, pack_size, ...]
        store_range_df: Range with columns [store_id, sku, store_grade, ...]
        config: Configuration module

    Returns:
        DataFrame with columns [store_id, sku, store_grade, ros, demand_std,
                                store_soh, ideal_stock, safety_stock, min_pres,
                                raw_need, need]
    """
    # Build grade lookup per store
    store_grades = (
        store_range_df[["store_id", "store_grade"]]
        .drop_duplicates(subset="store_id")
        .set_index("store_id")["store_grade"]
        .to_dict()
    )

    # Merge ROS with store SOH
    need_df = ros_df[["store_id", "sku", "ros", "demand_std"]].merge(
        store_soh_df[["store_id", "sku", "store_soh"]],
        on=["store_id", "sku"],
        how="left",
    )
    need_df["store_soh"] = need_df["store_soh"].fillna(0).astype(int)

    # Merge pack_size from SKU master
    need_df = need_df.merge(
        sku_master_df[["sku", "pack_size"]],
        on="sku",
        how="left",
    )
    need_df["pack_size"] = need_df["pack_size"].fillna(1).astype(int)

    # Add store grade
    need_df["store_grade"] = need_df["store_id"].map(store_grades).fillna("B")

    # Look up weeks of cover target by grade
    woc_by_grade = getattr(config, "WEEKS_OF_COVER_BY_GRADE", {})
    default_woc = config.TARGET_WEEKS_OF_COVER
    need_df["target_woc"] = need_df["store_grade"].map(woc_by_grade).fillna(default_woc)

    # Safety stock: Z * std_dev of weekly demand
    safety_z = getattr(config, "SAFETY_STOCK_Z", 0.0)
    need_df["safety_stock"] = (safety_z * need_df["demand_std"]).apply(math.ceil)

    # Minimum presentation quantity by grade
    min_pres_by_grade = getattr(config, "MIN_PRESENTATION_QTY", {})
    need_df["min_pres"] = need_df["store_grade"].map(min_pres_by_grade).fillna(1).astype(int)

    # Calculate ideal stock: (ROS * weeks_of_cover) + safety_stock
    need_df["ideal_stock"] = (
        (need_df["ros"] * need_df["target_woc"]) + need_df["safety_stock"]
    ).apply(math.ceil)

    # Ensure ideal stock is at least min presentation qty (for ranged SKUs with any ROS)
    has_ros = need_df["ros"] > 0
    below_min = need_df["ideal_stock"] < need_df["min_pres"]
    need_df.loc[has_ros & below_min, "ideal_stock"] = need_df.loc[has_ros & below_min, "min_pres"]

    # Raw need
    need_df["raw_need"] = (need_df["ideal_stock"] - need_df["store_soh"]).clip(lower=0)

    # Round up to nearest pack_size
    def round_to_pack(row):
        if row["raw_need"] <= 0:
            return 0
        pack = row["pack_size"]
        return int(math.ceil(row["raw_need"] / pack) * pack)

    need_df["need"] = need_df.apply(round_to_pack, axis=1)

    # Apply minimum allocation quantity
    min_alloc = config.MIN_ALLOCATION_QTY
    need_df.loc[(need_df["need"] > 0) & (need_df["need"] < min_alloc), "need"] = 0

    return need_df[[
        "store_id", "sku", "store_grade", "ros", "demand_std",
        "store_soh", "ideal_stock", "safety_stock", "min_pres",
        "raw_need", "need",
    ]]
