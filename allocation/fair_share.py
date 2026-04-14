"""
Fair share allocation engine.
When warehouse stock is insufficient to fill all store needs,
allocate proportionally with store-grade priority weighting.

Enhancements over basic proportional:
- Store grade priority multiplier (A-stores get filled first)
- Incoming/pipeline stock included in available inventory
- Store capacity constraints (max weekly intake)
- Replaced SKU phase-down (reduce allocation to SKUs being replaced)
"""
import math
import pandas as pd


def allocate_fair_share(need_df, warehouse_soh_df, sku_master_df, config):
    """
    Allocate warehouse stock to stores based on need, constrained by availability.

    Algorithm per SKU:
    1. Compute available stock (warehouse SOH + optional incoming - reserve)
    2. Apply replaced-SKU phase-down factor
    3. Weight store needs by grade priority multiplier
    4. If total need <= available: allocate full need
    5. If total need > available: priority-weighted proportional allocation
    6. Apply store capacity constraints, pack_size, and min_allocation
    7. Never over-allocate beyond warehouse stock

    Args:
        need_df: Store needs with columns [store_id, sku, store_grade, ros, ..., need]
        warehouse_soh_df: Warehouse stock with columns [sku, warehouse_soh, incoming_stock]
        sku_master_df: SKU master with columns [sku, pack_size, is_new, replaces_sku, ...]
        config: Configuration module

    Returns:
        DataFrame with columns [store_id, sku, need, allocated_qty,
                                warehouse_soh_before, warehouse_remaining]
    """
    reserve_pct = config.WAREHOUSE_RESERVE_PCT
    min_alloc = config.MIN_ALLOCATION_QTY
    include_incoming = getattr(config, "INCLUDE_INCOMING_STOCK", False)
    phase_down_factor = getattr(config, "REPLACED_SKU_ALLOCATION_FACTOR", 1.0)
    grade_priority = getattr(config, "GRADE_PRIORITY_MULTIPLIER", {"A": 1.0, "B": 1.0, "C": 1.0})
    default_max_intake = getattr(config, "DEFAULT_MAX_WEEKLY_INTAKE", 0)

    # Build lookups
    pack_sizes = dict(zip(sku_master_df["sku"], sku_master_df["pack_size"]))
    is_new = dict(zip(sku_master_df["sku"], sku_master_df["is_new"]))
    warehouse_stock = dict(zip(warehouse_soh_df["sku"], warehouse_soh_df["warehouse_soh"]))
    incoming_stock = dict(zip(warehouse_soh_df["sku"], warehouse_soh_df["incoming_stock"]))

    # Build set of SKUs being replaced (old SKUs that should phase down)
    replaced_skus = set(
        sku_master_df.loc[
            (sku_master_df["is_new"] == 1) & (sku_master_df["replaces_sku"] != ""),
            "replaces_sku"
        ]
    )

    # Build store max-intake lookup (per store, across all SKUs)
    store_max_intake = {}
    if "max_weekly_intake" in need_df.columns:
        # Use the value from the need_df if present (came from store_range)
        pass
    # We'll enforce capacity per-store across all SKUs at the end

    # Track cumulative allocation per store for capacity limits
    store_cumulative = {}

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
        wh_incoming = incoming_stock.get(sku, 0) if include_incoming else 0

        # Total available = on hand + incoming - reserve
        total_pool = wh_soh + wh_incoming
        available = max(0, int(total_pool * (1 - reserve_pct)))

        # Phase-down: reduce available for SKUs being replaced by new ones
        if sku in replaced_skus and phase_down_factor < 1.0:
            available = max(0, int(available * phase_down_factor))

        if available <= 0:
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

        # Add grade priority weight
        stores_for_sku["priority_weight"] = stores_for_sku["store_grade"].map(grade_priority).fillna(1.0)
        stores_for_sku["weighted_need"] = stores_for_sku["need"] * stores_for_sku["priority_weight"]

        if total_need <= available:
            # Enough stock: allocate full need
            for _, store_row in stores_for_sku.iterrows():
                alloc = int(store_row["need"])
                alloc = _apply_capacity_limit(
                    store_row["store_id"], alloc, store_cumulative,
                    need_df, default_max_intake,
                )
                store_cumulative[store_row["store_id"]] = (
                    store_cumulative.get(store_row["store_id"], 0) + alloc
                )
                results.append({
                    "store_id": store_row["store_id"],
                    "sku": sku,
                    "need": store_row["need"],
                    "allocated_qty": alloc,
                    "warehouse_soh_before": wh_soh,
                    "warehouse_remaining": wh_soh - total_need,
                })
        else:
            # Constrained: priority-weighted proportional allocation
            total_weighted_need = stores_for_sku["weighted_need"].sum()
            if total_weighted_need > 0:
                ratio = available / total_weighted_need
            else:
                ratio = 0

            stores_for_sku = stores_for_sku.copy()
            stores_for_sku["exact_alloc"] = stores_for_sku["weighted_need"] * ratio

            # Round down to pack_size multiples
            stores_for_sku["floor_alloc"] = stores_for_sku["exact_alloc"].apply(
                lambda x: int(math.floor(x / pack_size) * pack_size)
            )

            # Enforce minimum allocation
            stores_for_sku.loc[
                (stores_for_sku["floor_alloc"] > 0) & (stores_for_sku["floor_alloc"] < min_alloc),
                "floor_alloc"
            ] = 0

            # Calculate remainder for each store
            stores_for_sku["remainder"] = stores_for_sku["exact_alloc"] - stores_for_sku["floor_alloc"]

            # Distribute remaining stock to stores with largest remainders
            # Prioritize higher-grade stores when remainders are equal
            total_floored = stores_for_sku["floor_alloc"].sum()
            leftover = available - total_floored

            if leftover > 0:
                grade_sort_order = {"A": 0, "B": 1, "C": 2}
                sorted_stores = stores_for_sku.copy()
                sorted_stores["grade_sort"] = sorted_stores["store_grade"].map(grade_sort_order).fillna(1)
                sorted_stores = sorted_stores.sort_values(
                    ["remainder", "grade_sort"], ascending=[False, True]
                )
                for idx in sorted_stores.index:
                    if leftover < pack_size:
                        break
                    stores_for_sku.loc[idx, "floor_alloc"] += pack_size
                    leftover -= pack_size

            total_allocated = stores_for_sku["floor_alloc"].sum()
            wh_remaining = wh_soh - total_allocated

            for _, store_row in stores_for_sku.iterrows():
                alloc = int(store_row["floor_alloc"])
                alloc = _apply_capacity_limit(
                    store_row["store_id"], alloc, store_cumulative,
                    need_df, default_max_intake,
                )
                store_cumulative[store_row["store_id"]] = (
                    store_cumulative.get(store_row["store_id"], 0) + alloc
                )
                results.append({
                    "store_id": store_row["store_id"],
                    "sku": sku,
                    "need": store_row["need"],
                    "allocated_qty": alloc,
                    "warehouse_soh_before": wh_soh,
                    "warehouse_remaining": wh_remaining,
                })

    result_df = pd.DataFrame(results)

    # Include stores/SKUs with zero need
    zero_need = need_df[need_df["need"] == 0][["store_id", "sku", "need"]].copy()
    if not zero_need.empty:
        zero_need["allocated_qty"] = 0
        zero_need["warehouse_soh_before"] = zero_need["sku"].map(warehouse_stock).fillna(0).astype(int)
        zero_need["warehouse_remaining"] = zero_need["warehouse_soh_before"]
        result_df = pd.concat([result_df, zero_need], ignore_index=True)

    return result_df


def _apply_capacity_limit(store_id, alloc, store_cumulative, need_df, default_max_intake):
    """Cap allocation to store's max weekly intake if configured."""
    # Get store's max intake from need_df (inherited from store_range)
    store_rows = need_df[need_df["store_id"] == store_id]
    if "max_weekly_intake" in need_df.columns and not store_rows.empty:
        max_intake = store_rows.iloc[0].get("max_weekly_intake", default_max_intake)
    else:
        max_intake = default_max_intake

    if max_intake <= 0:
        return alloc  # No limit

    current = store_cumulative.get(store_id, 0)
    remaining_capacity = max(0, max_intake - current)
    return min(alloc, remaining_capacity)
