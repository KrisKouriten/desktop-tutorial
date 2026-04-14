"""
Store need calculation.
Determines how many units each store needs per SKU based on ROS, target cover, and current SOH.
"""
import math
import pandas as pd


def calculate_need(ros_df, store_soh_df, sku_master_df, target_weeks_of_cover, min_allocation_qty=1):
    """
    Calculate store need for each store/SKU combination.

    Args:
        ros_df: Rate of sale with columns [store_id, sku, ros]
        store_soh_df: Store stock with columns [store_id, sku, store_soh]
        sku_master_df: SKU master with columns [sku, pack_size, ...]
        target_weeks_of_cover: How many weeks of stock each store should hold
        min_allocation_qty: Minimum units to bother allocating

    Returns:
        DataFrame with columns [store_id, sku, ros, store_soh, ideal_stock, raw_need, need]
    """
    # Merge ROS with store SOH
    need_df = ros_df[["store_id", "sku", "ros"]].merge(
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

    # Calculate ideal stock and raw need
    need_df["ideal_stock"] = (need_df["ros"] * target_weeks_of_cover).apply(math.ceil)
    need_df["raw_need"] = (need_df["ideal_stock"] - need_df["store_soh"]).clip(lower=0)

    # Round up to nearest pack_size
    def round_to_pack(row):
        if row["raw_need"] <= 0:
            return 0
        pack = row["pack_size"]
        return int(math.ceil(row["raw_need"] / pack) * pack)

    need_df["need"] = need_df.apply(round_to_pack, axis=1)

    # Apply minimum allocation quantity: if need is positive but below minimum, set to 0
    need_df.loc[(need_df["need"] > 0) & (need_df["need"] < min_allocation_qty), "need"] = 0

    return need_df[["store_id", "sku", "ros", "store_soh", "ideal_stock", "raw_need", "need"]]
