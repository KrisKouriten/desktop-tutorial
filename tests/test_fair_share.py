"""Tests for fair share allocation."""
import types
import pandas as pd
from allocation.fair_share import allocate_fair_share


def _make_config(**kwargs):
    cfg = types.SimpleNamespace()
    cfg.WAREHOUSE_RESERVE_PCT = kwargs.get("reserve_pct", 0.0)
    cfg.MIN_ALLOCATION_QTY = kwargs.get("min_alloc", 1)
    return cfg


def test_full_fill():
    """When warehouse has enough, all stores get full need."""
    need_df = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "ros": 5.0, "store_soh": 0, "ideal_stock": 20, "raw_need": 20, "need": 20},
        {"store_id": "S002", "sku": "SKU001", "ros": 3.0, "store_soh": 0, "ideal_stock": 12, "raw_need": 12, "need": 12},
    ])
    warehouse = pd.DataFrame([{"sku": "SKU001", "warehouse_soh": 100, "incoming_stock": 0}])
    sku_master = pd.DataFrame([{"sku": "SKU001", "pack_size": 1, "is_new": 0}])

    result = allocate_fair_share(need_df, warehouse, sku_master, _make_config())

    allocs = result[result["allocated_qty"] > 0]
    s001 = allocs[allocs["store_id"] == "S001"].iloc[0]
    s002 = allocs[allocs["store_id"] == "S002"].iloc[0]

    assert s001["allocated_qty"] == 20
    assert s002["allocated_qty"] == 12


def test_proportional_allocation():
    """When stock is short, allocation is proportional to need."""
    need_df = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "ros": 5.0, "store_soh": 0, "ideal_stock": 10, "raw_need": 10, "need": 10},
        {"store_id": "S002", "sku": "SKU001", "ros": 5.0, "store_soh": 0, "ideal_stock": 20, "raw_need": 20, "need": 20},
        {"store_id": "S003", "sku": "SKU001", "ros": 5.0, "store_soh": 0, "ideal_stock": 30, "raw_need": 30, "need": 30},
    ])
    warehouse = pd.DataFrame([{"sku": "SKU001", "warehouse_soh": 30, "incoming_stock": 0}])
    sku_master = pd.DataFrame([{"sku": "SKU001", "pack_size": 1, "is_new": 0}])

    result = allocate_fair_share(need_df, warehouse, sku_master, _make_config())

    allocs = result[result["allocated_qty"] > 0].sort_values("store_id")
    total = allocs["allocated_qty"].sum()

    # Total should not exceed warehouse stock
    assert total <= 30

    # Proportions should roughly match need proportions (10:20:30 = 1:2:3)
    s1 = allocs[allocs["store_id"] == "S001"]["allocated_qty"].iloc[0]
    s2 = allocs[allocs["store_id"] == "S002"]["allocated_qty"].iloc[0]
    s3 = allocs[allocs["store_id"] == "S003"]["allocated_qty"].iloc[0]
    assert s1 <= s2 <= s3


def test_never_over_allocate():
    """Sum of allocations must never exceed warehouse stock."""
    need_df = pd.DataFrame([
        {"store_id": f"S{i:03d}", "sku": "SKU001", "ros": 5.0, "store_soh": 0,
         "ideal_stock": 50, "raw_need": 50, "need": 50}
        for i in range(1, 11)
    ])
    warehouse = pd.DataFrame([{"sku": "SKU001", "warehouse_soh": 47, "incoming_stock": 0}])
    sku_master = pd.DataFrame([{"sku": "SKU001", "pack_size": 1, "is_new": 0}])

    result = allocate_fair_share(need_df, warehouse, sku_master, _make_config())
    total = result["allocated_qty"].sum()
    assert total <= 47


def test_warehouse_reserve():
    """Reserve holds back a percentage of warehouse stock."""
    need_df = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "ros": 5.0, "store_soh": 0, "ideal_stock": 100, "raw_need": 100, "need": 100},
    ])
    warehouse = pd.DataFrame([{"sku": "SKU001", "warehouse_soh": 100, "incoming_stock": 0}])
    sku_master = pd.DataFrame([{"sku": "SKU001", "pack_size": 1, "is_new": 0}])

    result = allocate_fair_share(need_df, warehouse, sku_master, _make_config(reserve_pct=0.10))

    alloc = result[result["allocated_qty"] > 0].iloc[0]["allocated_qty"]
    # With 10% reserve, only 90 available
    assert alloc <= 90


def test_zero_warehouse_stock():
    """SKU with no warehouse stock gets zero allocation."""
    need_df = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "ros": 5.0, "store_soh": 0, "ideal_stock": 20, "raw_need": 20, "need": 20},
    ])
    warehouse = pd.DataFrame([{"sku": "SKU001", "warehouse_soh": 0, "incoming_stock": 0}])
    sku_master = pd.DataFrame([{"sku": "SKU001", "pack_size": 1, "is_new": 0}])

    result = allocate_fair_share(need_df, warehouse, sku_master, _make_config())
    assert result.iloc[0]["allocated_qty"] == 0
