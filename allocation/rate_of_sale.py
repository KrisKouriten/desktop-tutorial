"""
Rate of Sale (ROS) calculation.
Computes average weekly sales per store per SKU, with optional
recency weighting so recent weeks count more than older weeks.
Also computes demand variability (std dev) for safety stock calculations.
"""
import numpy as np
import pandas as pd


def calculate_ros(sales_df, store_range_df, ros_weeks, ros_floor=0.0, use_weighted=False):
    """
    Calculate rate of sale for each in-range store/SKU combination.

    Args:
        sales_df: Sales history with columns [week_ending, store_id, sku, qty_sold]
        store_range_df: Range matrix with columns [store_id, sku, ...]
        ros_weeks: Number of recent weeks to include
        ros_floor: Minimum ROS threshold — below this is treated as zero
        use_weighted: If True, apply linear recency weighting (recent weeks count more)

    Returns:
        DataFrame with columns [store_id, sku, ros, demand_std, total_sold, active_weeks]
    """
    # Filter sales to the most recent N weeks
    max_date = sales_df["week_ending"].max()
    cutoff = max_date - pd.Timedelta(weeks=ros_weeks - 1)
    recent_sales = sales_df[sales_df["week_ending"] >= cutoff].copy()

    # Get ordered list of weeks for weighting
    weeks_sorted = sorted(recent_sales["week_ending"].unique())
    num_weeks = len(weeks_sorted)
    if num_weeks == 0:
        num_weeks = ros_weeks

    if use_weighted and num_weeks > 1:
        # Linear weights: oldest week gets 1, most recent gets num_weeks
        week_weights = {w: i + 1 for i, w in enumerate(weeks_sorted)}
        recent_sales["weight"] = recent_sales["week_ending"].map(week_weights)
    else:
        recent_sales["weight"] = 1.0

    # Pivot to get qty per store/SKU/week for std dev calculation
    range_keys = store_range_df[["store_id", "sku"]].drop_duplicates()

    # Aggregate: weighted ROS and demand std dev
    if use_weighted and num_weeks > 1:
        # Weighted average: sum(qty * weight) / sum(weight) per week
        weighted = (
            recent_sales
            .groupby(["store_id", "sku"], as_index=False)
            .apply(lambda g: pd.Series({
                "total_sold": g["qty_sold"].sum(),
                "weighted_avg": np.average(g["qty_sold"], weights=g["weight"]) if len(g) > 0 else 0.0,
                "demand_std": g["qty_sold"].std(ddof=0) if len(g) > 1 else 0.0,
                "active_weeks": g["week_ending"].nunique(),
            }), include_groups=False)
        )
        weighted["ros"] = weighted["weighted_avg"]
    else:
        weighted = (
            recent_sales
            .groupby(["store_id", "sku"], as_index=False)
            .agg(
                total_sold=("qty_sold", "sum"),
                demand_std=("qty_sold", "std"),
                active_weeks=("week_ending", "nunique"),
            )
        )
        weighted["demand_std"] = weighted["demand_std"].fillna(0.0)
        weighted["ros"] = weighted["total_sold"] / max(num_weeks, 1)

    # Join with store range to get all in-range pairs
    ros_df = range_keys.merge(weighted, on=["store_id", "sku"], how="left")
    ros_df["total_sold"] = ros_df["total_sold"].fillna(0).astype(int)
    ros_df["active_weeks"] = ros_df["active_weeks"].fillna(0).astype(int)
    ros_df["ros"] = ros_df["ros"].fillna(0.0)
    ros_df["demand_std"] = ros_df["demand_std"].fillna(0.0)

    # Apply floor: set ROS below threshold to 0
    if ros_floor > 0:
        ros_df.loc[ros_df["ros"] < ros_floor, "ros"] = 0.0

    # Round for readability
    ros_df["ros"] = ros_df["ros"].round(2)
    ros_df["demand_std"] = ros_df["demand_std"].round(2)

    return ros_df[["store_id", "sku", "ros", "demand_std", "total_sold", "active_weeks"]]
