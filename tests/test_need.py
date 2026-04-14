"""Tests for store need calculation."""
import pandas as pd
from allocation.need import calculate_need


def test_basic_need():
    """Store with ROS 5, SOH 8, target 4 weeks → ideal=20, need=12."""
    ros_df = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "ros": 5.0},
    ])
    store_soh = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "store_soh": 8},
    ])
    sku_master = pd.DataFrame([
        {"sku": "SKU001", "pack_size": 1},
    ])

    result = calculate_need(ros_df, store_soh, sku_master, target_weeks_of_cover=4)
    row = result.iloc[0]

    assert row["ideal_stock"] == 20
    assert row["need"] == 12


def test_overstocked_store():
    """Store with more SOH than ideal gets need = 0."""
    ros_df = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "ros": 2.0},
    ])
    store_soh = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "store_soh": 50},
    ])
    sku_master = pd.DataFrame([
        {"sku": "SKU001", "pack_size": 1},
    ])

    result = calculate_need(ros_df, store_soh, sku_master, target_weeks_of_cover=4)
    assert result.iloc[0]["need"] == 0


def test_pack_size_rounding():
    """Need rounds up to nearest pack_size."""
    ros_df = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "ros": 2.5},
    ])
    store_soh = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "store_soh": 5},
    ])
    sku_master = pd.DataFrame([
        {"sku": "SKU001", "pack_size": 3},
    ])

    result = calculate_need(ros_df, store_soh, sku_master, target_weeks_of_cover=4)
    # ideal = ceil(2.5*4) = 10, raw_need = 10-5 = 5, rounded to pack 3 → 6
    assert result.iloc[0]["need"] == 6


def test_zero_ros_zero_need():
    """SKU with zero ROS gets zero need."""
    ros_df = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "ros": 0.0},
    ])
    store_soh = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "store_soh": 0},
    ])
    sku_master = pd.DataFrame([
        {"sku": "SKU001", "pack_size": 1},
    ])

    result = calculate_need(ros_df, store_soh, sku_master, target_weeks_of_cover=4)
    assert result.iloc[0]["need"] == 0


def test_min_allocation_qty():
    """Need below minimum allocation is set to 0."""
    ros_df = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "ros": 0.5},
    ])
    store_soh = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "store_soh": 1},
    ])
    sku_master = pd.DataFrame([
        {"sku": "SKU001", "pack_size": 1},
    ])

    # ideal = ceil(0.5*4) = 2, raw_need = 2-1 = 1, need = 1
    # With min_alloc=3, need should be set to 0
    result = calculate_need(ros_df, store_soh, sku_master, target_weeks_of_cover=4, min_allocation_qty=3)
    assert result.iloc[0]["need"] == 0
