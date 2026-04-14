"""Tests for fair share allocation."""
import types
import pandas as pd
from allocation.fair_share import allocate_fair_share


def _make_config(**kwargs):
    cfg = types.SimpleNamespace()
    cfg.WAREHOUSE_RESERVE_PCT = kwargs.get("reserve_pct", 0.0)
    cfg.MIN_ALLOCATION_QTY = kwargs.get("min_alloc", 1)
    cfg.INCLUDE_INCOMING_STOCK = kwargs.get("include_incoming", False)
    cfg.REPLACED_SKU_ALLOCATION_FACTOR = kwargs.get("phase_down", 1.0)
    cfg.GRADE_PRIORITY_MULTIPLIER = kwargs.get("grade_priority", {"A": 1.0, "B": 1.0, "C": 1.0})
    cfg.DEFAULT_MAX_WEEKLY_INTAKE = kwargs.get("max_intake", 0)
    return cfg


def _make_need(rows):
    """Each row: (store_id, sku, need, store_grade)"""
    return pd.DataFrame([
        {"store_id": r[0], "sku": r[1], "ros": 5.0, "demand_std": 1.0,
         "store_soh": 0, "ideal_stock": r[2], "safety_stock": 0,
         "min_pres": 1, "raw_need": r[2], "need": r[2],
         "store_grade": r[3] if len(r) > 3 else "B"}
        for r in rows
    ])


def test_full_fill():
    """When warehouse has enough, all stores get full need."""
    need_df = _make_need([("S001", "SKU001", 20, "B"), ("S002", "SKU001", 12, "B")])
    warehouse = pd.DataFrame([{"sku": "SKU001", "warehouse_soh": 100, "incoming_stock": 0}])
    sku_master = pd.DataFrame([{"sku": "SKU001", "pack_size": 1, "is_new": 0, "replaces_sku": ""}])

    result = allocate_fair_share(need_df, warehouse, sku_master, _make_config())

    allocs = result[result["allocated_qty"] > 0]
    s001 = allocs[allocs["store_id"] == "S001"].iloc[0]
    s002 = allocs[allocs["store_id"] == "S002"].iloc[0]

    assert s001["allocated_qty"] == 20
    assert s002["allocated_qty"] == 12


def test_proportional_allocation():
    """When stock is short, allocation is proportional to need."""
    need_df = _make_need([
        ("S001", "SKU001", 10, "B"),
        ("S002", "SKU001", 20, "B"),
        ("S003", "SKU001", 30, "B"),
    ])
    warehouse = pd.DataFrame([{"sku": "SKU001", "warehouse_soh": 30, "incoming_stock": 0}])
    sku_master = pd.DataFrame([{"sku": "SKU001", "pack_size": 1, "is_new": 0, "replaces_sku": ""}])

    result = allocate_fair_share(need_df, warehouse, sku_master, _make_config())

    allocs = result[result["allocated_qty"] > 0].sort_values("store_id")
    total = allocs["allocated_qty"].sum()

    assert total <= 30
    s1 = allocs[allocs["store_id"] == "S001"]["allocated_qty"].iloc[0]
    s2 = allocs[allocs["store_id"] == "S002"]["allocated_qty"].iloc[0]
    s3 = allocs[allocs["store_id"] == "S003"]["allocated_qty"].iloc[0]
    assert s1 <= s2 <= s3


def test_grade_priority():
    """A-grade stores should get more allocation when constrained."""
    need_df = _make_need([
        ("S001", "SKU001", 30, "A"),
        ("S002", "SKU001", 30, "C"),
    ])
    warehouse = pd.DataFrame([{"sku": "SKU001", "warehouse_soh": 30, "incoming_stock": 0}])
    sku_master = pd.DataFrame([{"sku": "SKU001", "pack_size": 1, "is_new": 0, "replaces_sku": ""}])

    cfg = _make_config(grade_priority={"A": 1.5, "B": 1.0, "C": 0.5})
    result = allocate_fair_share(need_df, warehouse, sku_master, cfg)

    allocs = result[result["allocated_qty"] > 0]
    a_alloc = allocs[allocs["store_id"] == "S001"]["allocated_qty"].iloc[0]
    c_alloc = allocs[allocs["store_id"] == "S002"]["allocated_qty"].iloc[0]

    assert a_alloc > c_alloc


def test_incoming_stock():
    """Incoming stock should increase available inventory when enabled."""
    need_df = _make_need([("S001", "SKU001", 50, "B")])
    warehouse = pd.DataFrame([{"sku": "SKU001", "warehouse_soh": 20, "incoming_stock": 30}])
    sku_master = pd.DataFrame([{"sku": "SKU001", "pack_size": 1, "is_new": 0, "replaces_sku": ""}])

    # Without incoming: only 20 available
    result_no = allocate_fair_share(need_df, warehouse, sku_master, _make_config(include_incoming=False))
    alloc_no = result_no[result_no["allocated_qty"] > 0]["allocated_qty"].sum()

    # With incoming: 50 available
    result_yes = allocate_fair_share(need_df, warehouse, sku_master, _make_config(include_incoming=True))
    alloc_yes = result_yes[result_yes["allocated_qty"] > 0]["allocated_qty"].sum()

    assert alloc_yes > alloc_no


def test_phase_down_replaced_sku():
    """Replaced SKUs should get reduced allocation."""
    need_df = _make_need([("S001", "SKU_OLD", 100, "B")])
    warehouse = pd.DataFrame([{"sku": "SKU_OLD", "warehouse_soh": 100, "incoming_stock": 0}])
    sku_master = pd.DataFrame([
        {"sku": "SKU_OLD", "pack_size": 1, "is_new": 0, "replaces_sku": ""},
        {"sku": "SKU_NEW", "pack_size": 1, "is_new": 1, "replaces_sku": "SKU_OLD"},
    ])

    result = allocate_fair_share(need_df, warehouse, sku_master, _make_config(phase_down=0.25))
    alloc = result[result["allocated_qty"] > 0]["allocated_qty"].sum()

    # With 25% phase down, only 25 units available from the 100
    assert alloc <= 25


def test_never_over_allocate():
    """Sum of allocations must never exceed warehouse stock."""
    need_df = _make_need([
        (f"S{i:03d}", "SKU001", 50, "B")
        for i in range(1, 11)
    ])
    warehouse = pd.DataFrame([{"sku": "SKU001", "warehouse_soh": 47, "incoming_stock": 0}])
    sku_master = pd.DataFrame([{"sku": "SKU001", "pack_size": 1, "is_new": 0, "replaces_sku": ""}])

    result = allocate_fair_share(need_df, warehouse, sku_master, _make_config())
    total = result["allocated_qty"].sum()
    assert total <= 47


def test_warehouse_reserve():
    """Reserve holds back a percentage of warehouse stock."""
    need_df = _make_need([("S001", "SKU001", 100, "B")])
    warehouse = pd.DataFrame([{"sku": "SKU001", "warehouse_soh": 100, "incoming_stock": 0}])
    sku_master = pd.DataFrame([{"sku": "SKU001", "pack_size": 1, "is_new": 0, "replaces_sku": ""}])

    result = allocate_fair_share(need_df, warehouse, sku_master, _make_config(reserve_pct=0.10))

    alloc = result[result["allocated_qty"] > 0].iloc[0]["allocated_qty"]
    assert alloc <= 90


def test_zero_warehouse_stock():
    """SKU with no warehouse stock gets zero allocation."""
    need_df = _make_need([("S001", "SKU001", 20, "B")])
    warehouse = pd.DataFrame([{"sku": "SKU001", "warehouse_soh": 0, "incoming_stock": 0}])
    sku_master = pd.DataFrame([{"sku": "SKU001", "pack_size": 1, "is_new": 0, "replaces_sku": ""}])

    result = allocate_fair_share(need_df, warehouse, sku_master, _make_config())
    assert result.iloc[0]["allocated_qty"] == 0
