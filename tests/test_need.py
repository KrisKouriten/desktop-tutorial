"""Tests for store need calculation."""
import types
import pandas as pd
from allocation.need import calculate_need


def _make_config(**kwargs):
    cfg = types.SimpleNamespace()
    cfg.TARGET_WEEKS_OF_COVER = kwargs.get("woc", 4)
    cfg.MIN_ALLOCATION_QTY = kwargs.get("min_alloc", 1)
    cfg.WEEKS_OF_COVER_BY_GRADE = kwargs.get("woc_by_grade", {"A": 5, "B": 4, "C": 3})
    cfg.SAFETY_STOCK_Z = kwargs.get("safety_z", 0.0)
    cfg.MIN_PRESENTATION_QTY = kwargs.get("min_pres", {"A": 3, "B": 2, "C": 1})
    return cfg


def _make_range(pairs):
    """pairs: list of (store_id, sku, grade)"""
    return pd.DataFrame(pairs, columns=["store_id", "sku", "store_grade"])


def test_basic_need():
    """Store with ROS 5, SOH 8, grade B (4 weeks cover) → ideal=20, need=12."""
    ros_df = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "ros": 5.0, "demand_std": 1.0},
    ])
    store_soh = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "store_soh": 8},
    ])
    sku_master = pd.DataFrame([{"sku": "SKU001", "pack_size": 1}])
    store_range = _make_range([("S001", "SKU001", "B")])

    result = calculate_need(ros_df, store_soh, sku_master, store_range, _make_config())
    row = result.iloc[0]

    assert row["ideal_stock"] == 20  # 5*4 + 0 safety (z=0)
    assert row["need"] == 12


def test_grade_based_cover():
    """A-grade store gets 5 weeks cover, C-grade gets 3."""
    ros_df = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "ros": 10.0, "demand_std": 0.0},
        {"store_id": "S002", "sku": "SKU001", "ros": 10.0, "demand_std": 0.0},
    ])
    store_soh = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "store_soh": 0},
        {"store_id": "S002", "sku": "SKU001", "store_soh": 0},
    ])
    sku_master = pd.DataFrame([{"sku": "SKU001", "pack_size": 1}])
    store_range = _make_range([("S001", "SKU001", "A"), ("S002", "SKU001", "C")])

    result = calculate_need(ros_df, store_soh, sku_master, store_range, _make_config())
    a_store = result[result["store_id"] == "S001"].iloc[0]
    c_store = result[result["store_id"] == "S002"].iloc[0]

    assert a_store["ideal_stock"] == 50  # 10 * 5
    assert c_store["ideal_stock"] == 30  # 10 * 3


def test_safety_stock():
    """Safety stock buffer should increase ideal stock."""
    ros_df = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "ros": 5.0, "demand_std": 3.0},
    ])
    store_soh = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "store_soh": 0},
    ])
    sku_master = pd.DataFrame([{"sku": "SKU001", "pack_size": 1}])
    store_range = _make_range([("S001", "SKU001", "B")])

    # Z=1.28, std=3 → safety stock = ceil(1.28*3) = ceil(3.84) = 4
    cfg = _make_config(safety_z=1.28)
    result = calculate_need(ros_df, store_soh, sku_master, store_range, cfg)
    row = result.iloc[0]

    assert row["safety_stock"] == 4
    assert row["ideal_stock"] == 24  # ceil(5*4) + 4


def test_min_presentation_qty():
    """Even with low ROS, A-grade store gets at least 3 units ideal."""
    ros_df = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "ros": 0.2, "demand_std": 0.0},
    ])
    store_soh = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "store_soh": 0},
    ])
    sku_master = pd.DataFrame([{"sku": "SKU001", "pack_size": 1}])
    store_range = _make_range([("S001", "SKU001", "A")])

    result = calculate_need(ros_df, store_soh, sku_master, store_range, _make_config())
    row = result.iloc[0]

    # ROS 0.2 * 5 weeks = 1 → but min presentation for A = 3
    assert row["ideal_stock"] >= 3


def test_overstocked_store():
    """Store with more SOH than ideal gets need = 0."""
    ros_df = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "ros": 2.0, "demand_std": 0.0},
    ])
    store_soh = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "store_soh": 50},
    ])
    sku_master = pd.DataFrame([{"sku": "SKU001", "pack_size": 1}])
    store_range = _make_range([("S001", "SKU001", "B")])

    result = calculate_need(ros_df, store_soh, sku_master, store_range, _make_config())
    assert result.iloc[0]["need"] == 0


def test_pack_size_rounding():
    """Need rounds up to nearest pack_size."""
    ros_df = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "ros": 2.5, "demand_std": 0.0},
    ])
    store_soh = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "store_soh": 5},
    ])
    sku_master = pd.DataFrame([{"sku": "SKU001", "pack_size": 3}])
    store_range = _make_range([("S001", "SKU001", "B")])

    result = calculate_need(ros_df, store_soh, sku_master, store_range, _make_config())
    # ideal = ceil(2.5*4) = 10, raw_need = 10-5 = 5, rounded to pack 3 → 6
    assert result.iloc[0]["need"] == 6


def test_zero_ros_zero_need():
    """SKU with zero ROS gets zero need."""
    ros_df = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "ros": 0.0, "demand_std": 0.0},
    ])
    store_soh = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "store_soh": 0},
    ])
    sku_master = pd.DataFrame([{"sku": "SKU001", "pack_size": 1}])
    store_range = _make_range([("S001", "SKU001", "B")])

    result = calculate_need(ros_df, store_soh, sku_master, store_range, _make_config())
    assert result.iloc[0]["need"] == 0
