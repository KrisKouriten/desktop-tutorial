"""
Rate of Sale (ROS) calculation.
Computes average weekly sales per store per SKU over the configured lookback window.
"""
import pandas as pd


def calculate_ros(sales_df, store_range_df, ros_weeks, ros_floor=0.0):
    """
    Calculate rate of sale for each in-range store/SKU combination.

    Args:
        sales_df: Sales history with columns [week_ending, store_id, sku, qty_sold]
        store_range_df: Range matrix with columns [store_id, sku] (only in-range pairs)
        ros_weeks: Number of recent weeks to include
        ros_floor: Minimum ROS threshold — below this is treated as zero

    Returns:
        DataFrame with columns [store_id, sku, ros, total_sold, active_weeks]
    """
    # Filter sales to the most recent N weeks
    max_date = sales_df["week_ending"].max()
    cutoff = max_date - pd.Timedelta(weeks=ros_weeks - 1)
    recent_sales = sales_df[sales_df["week_ending"] >= cutoff].copy()

    # Count distinct weeks in the data (for denominator)
    available_weeks = recent_sales["week_ending"].nunique()
    if available_weeks == 0:
        available_weeks = ros_weeks

    # Aggregate sales by store/SKU
    agg = (
        recent_sales
        .groupby(["store_id", "sku"], as_index=False)
        .agg(
            total_sold=("qty_sold", "sum"),
            active_weeks=("week_ending", "nunique"),
        )
    )

    # Join with store range to get all in-range pairs
    ros_df = store_range_df.merge(agg, on=["store_id", "sku"], how="left")
    ros_df["total_sold"] = ros_df["total_sold"].fillna(0).astype(int)
    ros_df["active_weeks"] = ros_df["active_weeks"].fillna(0).astype(int)

    # Calculate ROS: total sold / number of weeks available in the data
    # Use the full available_weeks as denominator for consistency
    # (a store ranged for all weeks but selling zero still has ROS = 0)
    ros_df["ros"] = ros_df["total_sold"] / max(available_weeks, 1)

    # Apply floor: set ROS below threshold to 0
    if ros_floor > 0:
        ros_df.loc[ros_df["ros"] < ros_floor, "ros"] = 0.0

    # Round for readability
    ros_df["ros"] = ros_df["ros"].round(2)

    return ros_df[["store_id", "sku", "ros", "total_sold", "active_weeks"]]
