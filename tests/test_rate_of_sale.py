"""Tests for rate of sale calculation."""
import pandas as pd
from allocation.rate_of_sale import calculate_ros


def _make_sales(rows):
    return pd.DataFrame(rows, columns=["week_ending", "store_id", "sku", "qty_sold"])


def _make_range(pairs):
    return pd.DataFrame(pairs, columns=["store_id", "sku"])


def test_basic_ros():
    """Simple ROS: 2 stores, 1 SKU, 4 weeks."""
    sales = _make_sales([
        ("2026-04-05", "S001", "SKU001", 10),
        ("2026-03-29", "S001", "SKU001", 8),
        ("2026-03-22", "S001", "SKU001", 12),
        ("2026-03-15", "S001", "SKU001", 10),
        ("2026-04-05", "S002", "SKU001", 4),
        ("2026-03-29", "S002", "SKU001", 6),
        ("2026-03-22", "S002", "SKU001", 2),
        ("2026-03-15", "S002", "SKU001", 4),
    ])
    sales["week_ending"] = pd.to_datetime(sales["week_ending"])
    store_range = _make_range([("S001", "SKU001"), ("S002", "SKU001")])

    result = calculate_ros(sales, store_range, ros_weeks=4, ros_floor=0.0)

    s001 = result[result["store_id"] == "S001"].iloc[0]
    s002 = result[result["store_id"] == "S002"].iloc[0]

    assert s001["ros"] == 10.0  # (10+8+12+10)/4
    assert s002["ros"] == 4.0   # (4+6+2+4)/4
    assert s001["total_sold"] == 40
    assert s002["total_sold"] == 16


def test_ros_floor():
    """SKU with very low sales gets ROS set to 0 when below floor."""
    sales = _make_sales([
        ("2026-04-05", "S001", "SKU001", 0),
        ("2026-03-29", "S001", "SKU001", 0),
        ("2026-03-22", "S001", "SKU001", 0),
        ("2026-03-15", "S001", "SKU001", 0),
    ])
    sales["week_ending"] = pd.to_datetime(sales["week_ending"])
    store_range = _make_range([("S001", "SKU001")])

    result = calculate_ros(sales, store_range, ros_weeks=4, ros_floor=0.1)
    assert result.iloc[0]["ros"] == 0.0


def test_unranged_store_excluded():
    """A store not in range should not get ROS even if it has sales."""
    sales = _make_sales([
        ("2026-04-05", "S001", "SKU001", 10),
        ("2026-04-05", "S002", "SKU001", 5),  # S002 not in range
    ])
    sales["week_ending"] = pd.to_datetime(sales["week_ending"])
    store_range = _make_range([("S001", "SKU001")])  # Only S001 ranged

    result = calculate_ros(sales, store_range, ros_weeks=4, ros_floor=0.0)
    assert len(result) == 1
    assert result.iloc[0]["store_id"] == "S001"


def test_ranged_but_no_sales():
    """Store in range but with no sales gets ROS = 0."""
    sales = _make_sales([
        ("2026-04-05", "S001", "SKU001", 10),
    ])
    sales["week_ending"] = pd.to_datetime(sales["week_ending"])
    store_range = _make_range([("S001", "SKU001"), ("S002", "SKU001")])

    result = calculate_ros(sales, store_range, ros_weeks=4, ros_floor=0.0)
    s002 = result[result["store_id"] == "S002"].iloc[0]
    assert s002["ros"] == 0.0
    assert s002["total_sold"] == 0
