"""Tests for like-for-like newness replacement."""
import pandas as pd
from allocation.newness import apply_newness


def test_like_for_like():
    """New SKU inherits ROS from the SKU it replaces."""
    ros_df = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU_OLD", "ros": 5.0, "demand_std": 1.5, "total_sold": 40, "active_weeks": 8},
        {"store_id": "S002", "sku": "SKU_OLD", "ros": 3.0, "demand_std": 0.8, "total_sold": 24, "active_weeks": 8},
    ])
    sku_master = pd.DataFrame([
        {"sku": "SKU_OLD", "category": "shirts", "is_new": 0, "replaces_sku": ""},
        {"sku": "SKU_NEW", "category": "shirts", "is_new": 1, "replaces_sku": "SKU_OLD"},
    ])
    store_range = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU_OLD"},
        {"store_id": "S002", "sku": "SKU_OLD"},
        {"store_id": "S001", "sku": "SKU_NEW"},
        {"store_id": "S002", "sku": "SKU_NEW"},
    ])

    result = apply_newness(ros_df, sku_master, store_range)

    new_s001 = result[(result["sku"] == "SKU_NEW") & (result["store_id"] == "S001")].iloc[0]
    new_s002 = result[(result["sku"] == "SKU_NEW") & (result["store_id"] == "S002")].iloc[0]

    assert new_s001["ros"] == 5.0
    assert new_s002["ros"] == 3.0
    assert new_s001["demand_std"] == 1.5  # Should inherit demand_std too


def test_category_fallback():
    """New SKU without replacement falls back to category average."""
    ros_df = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU_A", "ros": 4.0, "demand_std": 1.0, "total_sold": 32, "active_weeks": 8},
        {"store_id": "S001", "sku": "SKU_B", "ros": 6.0, "demand_std": 2.0, "total_sold": 48, "active_weeks": 8},
    ])
    sku_master = pd.DataFrame([
        {"sku": "SKU_A", "category": "shirts", "is_new": 0, "replaces_sku": ""},
        {"sku": "SKU_B", "category": "shirts", "is_new": 0, "replaces_sku": ""},
        {"sku": "SKU_NEW", "category": "shirts", "is_new": 1, "replaces_sku": ""},
    ])
    store_range = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU_A"},
        {"store_id": "S001", "sku": "SKU_B"},
        {"store_id": "S001", "sku": "SKU_NEW"},
    ])

    result = apply_newness(ros_df, sku_master, store_range)

    new_row = result[result["sku"] == "SKU_NEW"].iloc[0]
    assert new_row["ros"] == 5.0  # Category avg = (4+6)/2


def test_no_new_skus():
    """When there are no new SKUs, ROS DataFrame is unchanged."""
    ros_df = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU001", "ros": 5.0, "demand_std": 1.0, "total_sold": 40, "active_weeks": 8},
    ])
    sku_master = pd.DataFrame([
        {"sku": "SKU001", "category": "shirts", "is_new": 0, "replaces_sku": ""},
    ])
    store_range = pd.DataFrame([{"store_id": "S001", "sku": "SKU001"}])

    result = apply_newness(ros_df, sku_master, store_range)
    assert len(result) == 1
    assert result.iloc[0]["ros"] == 5.0


def test_new_sku_only_in_ranged_stores():
    """New SKU only gets ROS for stores where it's ranged."""
    ros_df = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU_OLD", "ros": 5.0, "demand_std": 1.0, "total_sold": 40, "active_weeks": 8},
        {"store_id": "S002", "sku": "SKU_OLD", "ros": 3.0, "demand_std": 0.5, "total_sold": 24, "active_weeks": 8},
    ])
    sku_master = pd.DataFrame([
        {"sku": "SKU_OLD", "category": "shirts", "is_new": 0, "replaces_sku": ""},
        {"sku": "SKU_NEW", "category": "shirts", "is_new": 1, "replaces_sku": "SKU_OLD"},
    ])
    store_range = pd.DataFrame([
        {"store_id": "S001", "sku": "SKU_OLD"},
        {"store_id": "S002", "sku": "SKU_OLD"},
        {"store_id": "S001", "sku": "SKU_NEW"},
    ])

    result = apply_newness(ros_df, sku_master, store_range)
    new_rows = result[result["sku"] == "SKU_NEW"]
    assert len(new_rows) == 1
    assert new_rows.iloc[0]["store_id"] == "S001"
