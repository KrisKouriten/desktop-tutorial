"""
Weekly Allocation Model — Streamlit App
========================================
Interactive web interface for running store allocations.

Usage:
    streamlit run app.py
"""
import io
import os
import math
import types
from datetime import date

import pandas as pd
import streamlit as st

from allocation.rate_of_sale import calculate_ros
from allocation.newness import apply_newness
from allocation.need import calculate_need
from allocation.fair_share import allocate_fair_share

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Store Allocation Model",
    page_icon="📦",
    layout="wide",
)

st.title("Weekly Store Allocation Model")
st.markdown("Upload your data, adjust parameters, and generate weekly allocations.")

# ---------------------------------------------------------------------------
# Sidebar — Parameters
# ---------------------------------------------------------------------------
st.sidebar.header("Allocation Parameters")

ros_weeks = st.sidebar.slider("ROS lookback (weeks)", 4, 16, 8)
use_weighted = st.sidebar.checkbox("Weighted ROS (recent weeks count more)", value=True)

st.sidebar.subheader("Weeks of Cover by Grade")
col_a, col_b, col_c = st.sidebar.columns(3)
woc_a = col_a.number_input("A", min_value=1, max_value=12, value=5)
woc_b = col_b.number_input("B", min_value=1, max_value=12, value=4)
woc_c = col_c.number_input("C", min_value=1, max_value=12, value=3)

st.sidebar.subheader("Grade Priority (constrained stock)")
prio_a = st.sidebar.slider("A-grade priority", 0.5, 2.0, 1.3, 0.1)
prio_b = st.sidebar.slider("B-grade priority", 0.5, 2.0, 1.0, 0.1)
prio_c = st.sidebar.slider("C-grade priority", 0.5, 2.0, 0.8, 0.1)

st.sidebar.subheader("Safety & Reserve")
safety_z = st.sidebar.slider(
    "Safety stock Z-score",
    0.0, 2.5, 1.28, 0.01,
    help="0=none, 1.28=90%, 1.65=95%, 2.05=98% service level",
)
reserve_pct = st.sidebar.slider("Warehouse reserve %", 0, 20, 5) / 100.0
include_incoming = st.sidebar.checkbox("Include incoming/pipeline stock", value=True)

st.sidebar.subheader("Newness")
phase_down = st.sidebar.slider(
    "Replaced SKU phase-down",
    0.0, 1.0, 0.25, 0.05,
    help="0.0=stop old SKU entirely, 1.0=no reduction",
)

st.sidebar.subheader("Minimums")
min_alloc = st.sidebar.number_input("Min allocation qty", min_value=1, max_value=10, value=1)
st.sidebar.markdown("**Min presentation qty**")
mp_a, mp_b, mp_c = st.sidebar.columns(3)
min_pres_a = mp_a.number_input("A", min_value=0, max_value=10, value=3, key="mp_a")
min_pres_b = mp_b.number_input("B", min_value=0, max_value=10, value=2, key="mp_b")
min_pres_c = mp_c.number_input("C", min_value=0, max_value=10, value=1, key="mp_c")

ros_floor = st.sidebar.number_input("ROS floor", min_value=0.0, max_value=1.0, value=0.1, step=0.05)


def build_config():
    """Build a config namespace from sidebar values."""
    cfg = types.SimpleNamespace()
    cfg.ROS_WEEKS = ros_weeks
    cfg.ROS_USE_WEIGHTED = use_weighted
    cfg.ROS_FLOOR = ros_floor
    cfg.TARGET_WEEKS_OF_COVER = woc_b
    cfg.WEEKS_OF_COVER_BY_GRADE = {"A": woc_a, "B": woc_b, "C": woc_c}
    cfg.GRADE_PRIORITY_MULTIPLIER = {"A": prio_a, "B": prio_b, "C": prio_c}
    cfg.SAFETY_STOCK_Z = safety_z
    cfg.WAREHOUSE_RESERVE_PCT = reserve_pct
    cfg.INCLUDE_INCOMING_STOCK = include_incoming
    cfg.REPLACED_SKU_ALLOCATION_FACTOR = phase_down
    cfg.MIN_ALLOCATION_QTY = min_alloc
    cfg.MIN_PRESENTATION_QTY = {"A": min_pres_a, "B": min_pres_b, "C": min_pres_c}
    cfg.DEFAULT_MAX_WEEKLY_INTAKE = 0
    return cfg


# ---------------------------------------------------------------------------
# File upload
# ---------------------------------------------------------------------------
st.header("1. Upload Data")

use_sample = st.checkbox("Use sample data (65 stores, 80 SKUs)", value=False)

if use_sample:
    sample_dir = os.path.join(os.path.dirname(__file__), "data", "samples")
    try:
        sales_df = pd.read_csv(os.path.join(sample_dir, "sales_history.csv"))
        warehouse_df = pd.read_csv(os.path.join(sample_dir, "warehouse_soh.csv"))
        store_soh_df = pd.read_csv(os.path.join(sample_dir, "store_soh.csv"))
        store_range_df = pd.read_csv(os.path.join(sample_dir, "store_range.csv"))
        sku_master_df = pd.read_csv(os.path.join(sample_dir, "sku_master.csv"))
        st.success("Sample data loaded.")
    except FileNotFoundError:
        st.error("Sample data not found. Run `python data/samples/generate_sample_data.py` first.")
        st.stop()
else:
    col1, col2 = st.columns(2)
    with col1:
        sales_file = st.file_uploader("Sales History", type="csv", key="sales")
        warehouse_file = st.file_uploader("Warehouse SOH", type="csv", key="warehouse")
        store_soh_file = st.file_uploader("Store SOH", type="csv", key="store_soh")
    with col2:
        store_range_file = st.file_uploader("Store Range", type="csv", key="range")
        sku_master_file = st.file_uploader("SKU Master", type="csv", key="sku")

    if not all([sales_file, warehouse_file, store_soh_file, store_range_file, sku_master_file]):
        st.info("Upload all 5 CSV files to proceed, or check **Use sample data** above.")
        st.stop()

    sales_df = pd.read_csv(sales_file)
    warehouse_df = pd.read_csv(warehouse_file)
    store_soh_df = pd.read_csv(store_soh_file)
    store_range_df = pd.read_csv(store_range_file)
    sku_master_df = pd.read_csv(sku_master_file)


# ---------------------------------------------------------------------------
# Data preparation (same validation as loader.py but inline for the app)
# ---------------------------------------------------------------------------
def prepare_data(sales_df, warehouse_df, store_soh_df, store_range_df, sku_master_df):
    """Validate and prepare uploaded data."""
    errors = []

    # Sales
    for col in ["week_ending", "store_id", "sku", "qty_sold"]:
        if col not in sales_df.columns:
            errors.append(f"sales_history: missing column '{col}'")
    if not errors:
        sales_df["week_ending"] = pd.to_datetime(sales_df["week_ending"], errors="coerce")
        sales_df["qty_sold"] = pd.to_numeric(sales_df["qty_sold"], errors="coerce").fillna(0).astype(int)
        sales_df.loc[sales_df["qty_sold"] < 0, "qty_sold"] = 0

    # Warehouse
    for col in ["sku", "warehouse_soh"]:
        if col not in warehouse_df.columns:
            errors.append(f"warehouse_soh: missing column '{col}'")
    if not errors:
        warehouse_df["warehouse_soh"] = pd.to_numeric(warehouse_df["warehouse_soh"], errors="coerce").fillna(0).astype(int)
        if "incoming_stock" not in warehouse_df.columns:
            warehouse_df["incoming_stock"] = 0
        else:
            warehouse_df["incoming_stock"] = pd.to_numeric(warehouse_df["incoming_stock"], errors="coerce").fillna(0).astype(int)

    # Store SOH
    for col in ["store_id", "sku", "store_soh"]:
        if col not in store_soh_df.columns:
            errors.append(f"store_soh: missing column '{col}'")
    if not errors:
        store_soh_df["store_soh"] = pd.to_numeric(store_soh_df["store_soh"], errors="coerce").fillna(0).astype(int)

    # Store Range
    for col in ["store_id", "sku", "in_range"]:
        if col not in store_range_df.columns:
            errors.append(f"store_range: missing column '{col}'")
    if not errors:
        store_range_df["in_range"] = pd.to_numeric(store_range_df["in_range"], errors="coerce").fillna(0).astype(int)
        store_range_df = store_range_df[store_range_df["in_range"] == 1].copy()
        if "store_grade" not in store_range_df.columns:
            store_range_df["store_grade"] = "B"
        store_range_df["store_grade"] = store_range_df["store_grade"].fillna("B").astype(str).str.upper().str.strip()
        valid_grades = {"A", "B", "C"}
        store_range_df.loc[~store_range_df["store_grade"].isin(valid_grades), "store_grade"] = "B"
        if "max_weekly_intake" not in store_range_df.columns:
            store_range_df["max_weekly_intake"] = 0
        else:
            store_range_df["max_weekly_intake"] = pd.to_numeric(store_range_df["max_weekly_intake"], errors="coerce").fillna(0).astype(int)

    # SKU Master
    for col in ["sku", "description", "category", "is_new", "replaces_sku", "pack_size"]:
        if col not in sku_master_df.columns:
            errors.append(f"sku_master: missing column '{col}'")
    if not errors:
        sku_master_df["is_new"] = pd.to_numeric(sku_master_df["is_new"], errors="coerce").fillna(0).astype(int)
        sku_master_df["replaces_sku"] = sku_master_df["replaces_sku"].fillna("").astype(str).str.strip()
        sku_master_df["pack_size"] = pd.to_numeric(sku_master_df["pack_size"], errors="coerce").fillna(1).astype(int)
        sku_master_df.loc[sku_master_df["pack_size"] < 1, "pack_size"] = 1

    return errors, sales_df, warehouse_df, store_soh_df, store_range_df, sku_master_df


errors, sales_df, warehouse_df, store_soh_df, store_range_df, sku_master_df = prepare_data(
    sales_df, warehouse_df, store_soh_df, store_range_df, sku_master_df
)

if errors:
    for err in errors:
        st.error(err)
    st.stop()


# ---------------------------------------------------------------------------
# Data preview
# ---------------------------------------------------------------------------
st.header("2. Data Preview")

with st.expander("View uploaded data", expanded=False):
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Sales History", "Warehouse SOH", "Store SOH", "Store Range", "SKU Master"
    ])
    with tab1:
        st.write(f"{len(sales_df):,} rows, {sales_df['store_id'].nunique()} stores, "
                 f"{sales_df['sku'].nunique()} SKUs, {sales_df['week_ending'].nunique()} weeks")
        st.dataframe(sales_df.head(100), use_container_width=True)
    with tab2:
        total_avail = warehouse_df["warehouse_soh"].sum() + warehouse_df["incoming_stock"].sum()
        st.write(f"{len(warehouse_df):,} SKUs — "
                 f"{warehouse_df['warehouse_soh'].sum():,} on hand + "
                 f"{warehouse_df['incoming_stock'].sum():,} incoming = {total_avail:,} total")
        st.dataframe(warehouse_df, use_container_width=True)
    with tab3:
        st.write(f"{len(store_soh_df):,} rows, {store_soh_df['store_id'].nunique()} stores, "
                 f"{store_soh_df['store_soh'].sum():,} total units")
        st.dataframe(store_soh_df.head(100), use_container_width=True)
    with tab4:
        grade_counts = store_range_df.groupby("store_grade")["store_id"].nunique()
        grade_str = ", ".join(f"{g}={c}" for g, c in sorted(grade_counts.items()))
        st.write(f"{len(store_range_df):,} active pairs, "
                 f"{store_range_df['store_id'].nunique()} stores ({grade_str})")
        st.dataframe(store_range_df.head(100), use_container_width=True)
    with tab5:
        new_count = (sku_master_df["is_new"] == 1).sum()
        st.write(f"{len(sku_master_df):,} SKUs, {new_count} new")
        st.dataframe(sku_master_df, use_container_width=True)


# ---------------------------------------------------------------------------
# Run allocation
# ---------------------------------------------------------------------------
st.header("3. Run Allocation")

if st.button("Run Weekly Allocation", type="primary", use_container_width=True):
    cfg = build_config()

    with st.spinner("Calculating rate of sale..."):
        ros_df = calculate_ros(
            sales_df=sales_df,
            store_range_df=store_range_df,
            ros_weeks=cfg.ROS_WEEKS,
            ros_floor=cfg.ROS_FLOOR,
            use_weighted=cfg.ROS_USE_WEIGHTED,
        )

    with st.spinner("Applying newness overlays..."):
        new_skus = sku_master_df[sku_master_df["is_new"] == 1]
        if not new_skus.empty:
            ros_df = apply_newness(ros_df, sku_master_df, store_range_df)

    with st.spinner("Calculating store needs..."):
        need_df = calculate_need(ros_df, store_soh_df, sku_master_df, store_range_df, cfg)

    with st.spinner("Running fair share allocation..."):
        allocation_df = allocate_fair_share(need_df, warehouse_df, sku_master_df, cfg)

    # Build detail output
    allocated = allocation_df[allocation_df["allocated_qty"] > 0].copy()

    if allocated.empty:
        st.warning("No allocations generated. Check your data and parameters.")
        st.stop()

    # Merge enrichment data
    need_cols = [c for c in ["store_id", "sku", "store_grade", "ros", "demand_std",
                              "store_soh", "ideal_stock", "safety_stock"] if c in need_df.columns]
    detail = allocated.merge(
        need_df[need_cols].drop_duplicates(subset=["store_id", "sku"]),
        on=["store_id", "sku"], how="left",
    )
    detail = detail.merge(
        sku_master_df[["sku", "description", "category", "is_new", "replaces_sku"]],
        on="sku", how="left",
    )
    detail["stock_after"] = detail["store_soh"].fillna(0).astype(int) + detail["allocated_qty"]
    detail["woc_after"] = detail.apply(
        lambda r: round(r["stock_after"] / r["ros"], 1) if r["ros"] > 0 else 0.0, axis=1
    )
    detail["is_new_sku"] = detail["is_new"].map({1: "Yes", 0: "No"}).fillna("No")

    # Store in session state for display
    st.session_state["detail"] = detail
    st.session_state["need_df"] = need_df
    st.session_state["allocation_df"] = allocation_df
    st.session_state["sku_master_df"] = sku_master_df
    st.session_state["run_complete"] = True

# ---------------------------------------------------------------------------
# Results display
# ---------------------------------------------------------------------------
if st.session_state.get("run_complete"):
    detail = st.session_state["detail"]
    need_df = st.session_state["need_df"]
    allocation_df = st.session_state["allocation_df"]
    sku_master_df_result = st.session_state["sku_master_df"]

    total_units = detail["allocated_qty"].sum()
    total_need = need_df["need"].sum()
    fill_rate = (total_units / total_need * 100) if total_need > 0 else 0

    st.header("4. Results")

    # KPI cards
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total Allocated", f"{total_units:,}")
    k2.metric("Total Need", f"{total_need:,}")
    k3.metric("Fill Rate", f"{fill_rate:.1f}%")
    k4.metric("SKUs", f"{detail['sku'].nunique():,}")
    k5.metric("Stores", f"{detail['store_id'].nunique():,}")

    # Grade breakdown
    st.subheader("Allocation by Store Grade")
    grade_summary = (
        detail.groupby("store_grade")
        .agg(
            stores=("store_id", "nunique"),
            units_allocated=("allocated_qty", "sum"),
            avg_woc=("woc_after", "mean"),
        )
        .reset_index()
    )
    grade_summary["avg_woc"] = grade_summary["avg_woc"].round(1)
    grade_summary["pct_of_total"] = (grade_summary["units_allocated"] / total_units * 100).round(1)
    st.dataframe(grade_summary, use_container_width=True, hide_index=True)

    # Bar chart - units by grade
    st.bar_chart(grade_summary.set_index("store_grade")["units_allocated"])

    # Tabs for detail views
    tab_detail, tab_summary, tab_store, tab_constrained = st.tabs([
        "Allocation Detail", "SKU Summary", "Store View", "Constrained SKUs"
    ])

    with tab_detail:
        st.subheader("Full Allocation Detail")

        # Filters
        f1, f2, f3 = st.columns(3)
        with f1:
            filter_store = st.multiselect(
                "Filter by store",
                sorted(detail["store_id"].unique()),
                key="filter_store",
            )
        with f2:
            filter_category = st.multiselect(
                "Filter by category",
                sorted(detail["category"].dropna().unique()),
                key="filter_cat",
            )
        with f3:
            filter_grade = st.multiselect(
                "Filter by grade",
                sorted(detail["store_grade"].dropna().unique()),
                key="filter_grade",
            )

        filtered = detail.copy()
        if filter_store:
            filtered = filtered[filtered["store_id"].isin(filter_store)]
        if filter_category:
            filtered = filtered[filtered["category"].isin(filter_category)]
        if filter_grade:
            filtered = filtered[filtered["store_grade"].isin(filter_grade)]

        display_cols = [
            "store_id", "store_grade", "sku", "description", "category",
            "ros", "store_soh", "ideal_stock", "safety_stock",
            "need", "allocated_qty", "stock_after", "woc_after", "is_new_sku",
        ]
        display_cols = [c for c in display_cols if c in filtered.columns]
        st.dataframe(
            filtered[display_cols].sort_values(["sku", "store_id"]),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(f"Showing {len(filtered):,} of {len(detail):,} allocations")

    with tab_summary:
        st.subheader("SKU Summary")
        sku_summary = (
            detail.groupby("sku")
            .agg(
                description=("description", "first"),
                category=("category", "first"),
                total_need=("need", "sum"),
                total_allocated=("allocated_qty", "sum"),
                stores_receiving=("store_id", "nunique"),
                avg_ros=("ros", "mean"),
                avg_woc_after=("woc_after", "mean"),
                is_new=("is_new_sku", "first"),
            )
            .reset_index()
        )
        sku_summary["fill_rate"] = (sku_summary["total_allocated"] / sku_summary["total_need"].clip(lower=1) * 100).round(1)
        sku_summary["avg_ros"] = sku_summary["avg_ros"].round(2)
        sku_summary["avg_woc_after"] = sku_summary["avg_woc_after"].round(1)
        sku_summary = sku_summary.sort_values("total_allocated", ascending=False)
        st.dataframe(sku_summary, use_container_width=True, hide_index=True)

    with tab_store:
        st.subheader("Store-Level Summary")
        store_summary = (
            detail.groupby(["store_id", "store_grade"])
            .agg(
                skus_receiving=("sku", "nunique"),
                total_allocated=("allocated_qty", "sum"),
                avg_woc_after=("woc_after", "mean"),
            )
            .reset_index()
        )
        store_summary["avg_woc_after"] = store_summary["avg_woc_after"].round(1)
        store_summary = store_summary.sort_values("total_allocated", ascending=False)
        st.dataframe(store_summary, use_container_width=True, hide_index=True)

        # Chart
        st.bar_chart(store_summary.set_index("store_id")["total_allocated"])

    with tab_constrained:
        st.subheader("Constrained SKUs (need > allocated)")
        sku_totals = detail.groupby("sku").agg(
            total_allocated=("allocated_qty", "sum"),
            total_need=("need", "sum"),
            description=("description", "first"),
            category=("category", "first"),
            warehouse_soh=("warehouse_soh_before", "first"),
        ).reset_index()
        constrained = sku_totals[sku_totals["total_need"] > sku_totals["total_allocated"]].copy()
        constrained["shortfall"] = constrained["total_need"] - constrained["total_allocated"]
        constrained["fill_rate"] = (constrained["total_allocated"] / constrained["total_need"] * 100).round(1)
        constrained = constrained.sort_values("shortfall", ascending=False)
        st.dataframe(constrained, use_container_width=True, hide_index=True)
        st.caption(f"{len(constrained)} SKUs where warehouse stock was insufficient")

    # ---------------------------------------------------------------------------
    # Download
    # ---------------------------------------------------------------------------
    st.header("5. Download")

    col_dl1, col_dl2 = st.columns(2)

    with col_dl1:
        csv_detail = detail.to_csv(index=False)
        st.download_button(
            label="Download Allocation Detail (CSV)",
            data=csv_detail,
            file_name=f"allocation_{date.today().isoformat()}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with col_dl2:
        sku_summary_for_dl = (
            detail.groupby("sku")
            .agg(
                description=("description", "first"),
                category=("category", "first"),
                total_need=("need", "sum"),
                total_allocated=("allocated_qty", "sum"),
                stores_receiving=("store_id", "nunique"),
                avg_ros=("ros", "mean"),
                warehouse_soh_before=("warehouse_soh_before", "first"),
                avg_woc_after=("woc_after", "mean"),
                is_new=("is_new_sku", "first"),
            )
            .reset_index()
        )
        sku_summary_for_dl["fill_rate_pct"] = (
            sku_summary_for_dl["total_allocated"] / sku_summary_for_dl["total_need"].clip(lower=1) * 100
        ).round(1)
        csv_summary = sku_summary_for_dl.to_csv(index=False)
        st.download_button(
            label="Download SKU Summary (CSV)",
            data=csv_summary,
            file_name=f"allocation_summary_{date.today().isoformat()}.csv",
            mime="text/csv",
            use_container_width=True,
        )
