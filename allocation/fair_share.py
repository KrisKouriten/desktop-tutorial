"""
Fair share allocation engine.
When warehouse stock is insufficient to fill all store needs,
allocate proportionally using the largest-remainder method.
"""
import math
import pandas as pd


def allocate_fair_share(need_df, warehouse_soh_df, sku_master_df, config):
    """
    Allocate warehouse stock to stores based on need, constrained by availability.

    Algorithm per SKU:
    1. Compute available stock = warehouse_soh - reserve
    2. If total need <= available: allocate full need to each store
    3. If total need > available: proportional allocation with largest-remainder rounding
    4. Enforce pack_size and min_allocation constraints
    5. Never over-allocate beyond warehouse stock

    Args:
        need_df: Store needs with columns [store_id, sku, ros, store_soh, ideal_stock, raw_need, need]
        warehouse_soh_df: Warehouse stock with columns [sku, warehouse_soh, incoming_stock]
        sku_master_df: SKU master with columns [sku, pack_size, is_new, ...]
        config: Configuration module with WAREHOUSE_RESERVE_PCT, MIN_ALLOCATION_QTY

    Returns:
        DataFrame with columns [store_id, sku, need, allocated_qty, warehouse_soh_before, warehouse_remaining]
    """
    reserve_pct = config.WAREHOUSE_RESERVE_PCT
    min_alloc = config.MIN_ALLOCATION_QTY

    # Build lookups
    pack_sizes = dict(zip(sku_master_df["sku"], sku_master_df["pack_size"]))
    is_new = dict(zip(sku_master_df["sku"], sku_master_df["is_new"]))
    warehouse_stock = dict(zip(warehouse_soh_df["sku"], warehouse_soh_df["warehouse_soh"]))

    # Only allocate for SKUs with positive need
    active_need = need_df[need_df["need"] > 0].copy()

    # Priority: new SKUs first, then by total need descending
    sku_priority = (
        active_need
        .groupby("sku", as_index=False)["need"]
        .sum()
        .rename(columns={"need": "total_need"})
    )
    sku_priority["is_new"] = sku_priority["sku"].map(is_new).fillna(0).astype(int)
    sku_priority = sku_priority.sort_values(
        ["is_new", "total_need"], ascending=[False, False]
    )

    results = []

    for _, sku_row in sku_priority.iterrows():
        sku = sku_row["sku"]
        wh_soh = warehouse_stock.get(sku, 0)

        # Available stock after reserve
        available = max(0, int(wh_soh * (1 - reserve_pct)))
        if available <= 0:
            # No stock to allocate — still record zeros
            stores_for_sku = active_need[active_need["sku"] == sku]
            for _, store_row in stores_for_sku.iterrows():
                results.append({
                    "store_id": store_row["store_id"],
                    "sku": sku,
                    "need": store_row["need"],
                    "allocated_qty": 0,
                    "warehouse_soh_before": wh_soh,
                    "warehouse_remaining": wh_soh,
                })
            continue

        stores_for_sku = active_need[active_need["sku"] == sku].copy()
        total_need = stores_for_sku["need"].sum()
        pack_size = pack_sizes.get(sku, 1)

        if total_need <= available:
            # Enough stock: allocate full need
            for _, store_row in stores_for_sku.iterrows():
                alloc = int(store_row["need"])
                results.append({
                    "store_id": store_row["store_id"],
                    "sku": sku,
                    "need": store_row["need"],
                    "allocated_qty": alloc,
                    "warehouse_soh_before": wh_soh,
                    "warehouse_remaining": wh_soh - total_need,
                })
        else:
            # Constrained: proportional allocation with largest-remainder
            ratio = available / total_need
            stores_for_sku = stores_for_sku.copy()
            stores_for_sku["exact_alloc"] = stores_for_sku["need"] * ratio

            # Round down to pack_size multiples
            stores_for_sku["floor_alloc"] = stores_for_sku["exact_alloc"].apply(
                lambda x: int(math.floor(x / pack_size) * pack_size)
            )

            # Enforce minimum allocation
            stores_for_sku.loc[
                (stores_for_sku["floor_alloc"] > 0) & (stores_for_sku["floor_alloc"] < min_alloc),
                "floor_alloc"
            ] = 0

            # Calculate remainder for each store (fractional part in pack units)
            stores_for_sku["remainder"] = stores_for_sku["exact_alloc"] - stores_for_sku["floor_alloc"]

            # Distribute remaining stock
            total_floored = stores_for_sku["floor_alloc"].sum()
            leftover = available - total_floored

            # Give extra packs to stores with largest remainders
            if leftover > 0:
                sorted_stores = stores_for_sku.sort_values("remainder", ascending=False)
                for idx in sorted_stores.index:
                    if leftover < pack_size:
                        break
                    stores_for_sku.loc[idx, "floor_alloc"] += pack_size
                    leftover -= pack_size

            total_allocated = stores_for_sku["floor_alloc"].sum()
            wh_remaining = wh_soh - total_allocated

            for _, store_row in stores_for_sku.iterrows():
                results.append({
                    "store_id": store_row["store_id"],
                    "sku": sku,
                    "need": store_row["need"],
                    "allocated_qty": int(store_row["floor_alloc"]),
                    "warehouse_soh_before": wh_soh,
                    "warehouse_remaining": wh_remaining,
                })

    result_df = pd.DataFrame(results)

    # Include stores with zero need for completeness (they get 0 allocation)
    zero_need = need_df[need_df["need"] == 0][["store_id", "sku", "need"]].copy()
    if not zero_need.empty:
        zero_need["allocated_qty"] = 0
        zero_need["warehouse_soh_before"] = zero_need["sku"].map(warehouse_stock).fillna(0).astype(int)
        zero_need["warehouse_remaining"] = zero_need["warehouse_soh_before"]
        result_df = pd.concat([result_df, zero_need], ignore_index=True)

    return result_df
