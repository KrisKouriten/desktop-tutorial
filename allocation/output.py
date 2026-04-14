"""
Output formatting for allocation results.
Writes detailed allocation CSV and summary CSV.
"""
import os
from datetime import date
import pandas as pd


def write_allocation_output(allocation_df, need_df, sku_master_df, warehouse_soh_df, output_dir):
    """
    Write allocation results to CSV files.

    Produces:
    - allocation_YYYY-MM-DD.csv: Detail file with one row per store/SKU
    - allocation_summary_YYYY-MM-DD.csv: Summary file with one row per SKU

    Args:
        allocation_df: Allocation results [store_id, sku, need, allocated_qty, warehouse_soh_before, warehouse_remaining]
        need_df: Need data [store_id, sku, ros, store_soh, ideal_stock, raw_need, need]
        sku_master_df: SKU metadata
        warehouse_soh_df: Warehouse stock data

    Returns:
        Tuple of (detail_path, summary_path)
    """
    os.makedirs(output_dir, exist_ok=True)
    today = date.today().isoformat()

    # --- Detail output ---
    detail = allocation_df[allocation_df["allocated_qty"] > 0].copy()

    if detail.empty:
        print("  No allocations to write (all needs met or no warehouse stock).")
        return None, None

    # Merge in need details (ROS, store SOH, ideal stock)
    detail = detail.merge(
        need_df[["store_id", "sku", "ros", "store_soh", "ideal_stock"]],
        on=["store_id", "sku"],
        how="left",
    )

    # Merge SKU master details
    detail = detail.merge(
        sku_master_df[["sku", "description", "category", "is_new", "replaces_sku"]],
        on="sku",
        how="left",
    )

    # Compute warehouse SOH after allocation per SKU
    sku_total_alloc = detail.groupby("sku", as_index=False)["allocated_qty"].sum().rename(
        columns={"allocated_qty": "total_sku_alloc"}
    )
    detail = detail.merge(sku_total_alloc, on="sku", how="left")
    detail["warehouse_soh_after"] = detail["warehouse_soh_before"] - detail["total_sku_alloc"]

    # Rename for clarity
    detail["is_new_sku"] = detail["is_new"].map({1: "Yes", 0: "No"}).fillna("No")
    detail["like_for_like_sku"] = detail["replaces_sku"].fillna("")

    # Select and order output columns
    output_cols = [
        "store_id", "sku", "description", "category",
        "ros", "store_soh", "ideal_stock", "need", "allocated_qty",
        "warehouse_soh_before", "warehouse_soh_after",
        "is_new_sku", "like_for_like_sku",
    ]
    detail = detail[output_cols].sort_values(["sku", "store_id"])

    detail_path = os.path.join(output_dir, f"allocation_{today}.csv")
    detail.to_csv(detail_path, index=False)
    print(f"  Detail: {detail_path} ({len(detail):,} rows)")

    # --- Summary output ---
    summary = (
        detail
        .groupby("sku", as_index=False)
        .agg(
            description=("description", "first"),
            category=("category", "first"),
            total_need=("need", "sum"),
            total_allocated=("allocated_qty", "sum"),
            stores_receiving=("store_id", "nunique"),
            avg_ros=("ros", "mean"),
            warehouse_soh_before=("warehouse_soh_before", "first"),
            warehouse_soh_after=("warehouse_soh_after", "first"),
            is_new_sku=("is_new_sku", "first"),
        )
    )
    summary["fill_rate_pct"] = (
        (summary["total_allocated"] / summary["total_need"].clip(lower=1) * 100).round(1)
    )
    summary["avg_ros"] = summary["avg_ros"].round(2)
    summary = summary.sort_values("total_allocated", ascending=False)

    summary_path = os.path.join(output_dir, f"allocation_summary_{today}.csv")
    summary.to_csv(summary_path, index=False)
    print(f"  Summary: {summary_path} ({len(summary):,} SKUs)")

    return detail_path, summary_path


def print_summary_stats(allocation_df, need_df, sku_master_df):
    """Print a console summary of the allocation run."""
    allocated = allocation_df[allocation_df["allocated_qty"] > 0]

    total_units = allocated["allocated_qty"].sum()
    total_skus = allocated["sku"].nunique()
    total_stores = allocated["store_id"].nunique()

    new_sku_list = set(sku_master_df[sku_master_df["is_new"] == 1]["sku"])
    new_alloc = allocated[allocated["sku"].isin(new_sku_list)]
    new_sku_count = new_alloc["sku"].nunique()

    total_need = need_df["need"].sum()
    fill_rate = (total_units / total_need * 100) if total_need > 0 else 0

    # Constrained SKUs (where total allocated < total need)
    sku_summary = allocated.groupby("sku")["allocated_qty"].sum()
    sku_need = need_df[need_df["need"] > 0].groupby("sku")["need"].sum()
    constrained = sku_need.index[sku_need > sku_summary.reindex(sku_need.index, fill_value=0)]

    print("\n" + "=" * 60)
    print("ALLOCATION SUMMARY")
    print("=" * 60)
    print(f"  SKUs allocated:          {total_skus:,} ({new_sku_count} new)")
    print(f"  Stores receiving stock:  {total_stores:,}")
    print(f"  Total units allocated:   {total_units:,}")
    print(f"  Total need:              {total_need:,}")
    print(f"  Overall fill rate:       {fill_rate:.1f}%")
    print(f"  Constrained SKUs:        {len(constrained):,}")

    # Top 10 by allocation
    if not allocated.empty:
        top10 = (
            allocated
            .groupby("sku", as_index=False)["allocated_qty"]
            .sum()
            .sort_values("allocated_qty", ascending=False)
            .head(10)
        )
        print(f"\n  Top 10 SKUs by allocation:")
        for _, row in top10.iterrows():
            print(f"    {row['sku']}: {int(row['allocated_qty']):,} units")

    print("=" * 60 + "\n")
