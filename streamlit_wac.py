"""
Weighted Average Cost (WAC) Model — Streamlit App
===================================================
Interactive WAC calculator with dynamic FX.

    Landed unit cost = Invoice + Amortised Freight + Amortised Duty
                       + Amortised Goods-In    (all GBP)

    New WAC = (Opening Value + Landed Value of Receipts)
            / (Opening Qty   + Receipt Qty)

Usage:
    streamlit run streamlit_wac.py
"""
import os
from datetime import date

import pandas as pd
import streamlit as st

from wac.fx import build_fx_lookup
from wac.amortise import amortise_cost_pools
from wac.landed import calculate_landed_cost
from wac.wac import calculate_wac


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Weighted Average Cost Model",
    page_icon="💷",
    layout="wide",
)

st.title("Weighted Average Cost Model")
st.markdown(
    "Compute a new WAC per SKU from **opening stock** + **inbound receipts**. "
    "Receipts are landed at `Invoice + Amortised Freight + Amortised Duty + "
    "Amortised Goods-In`, with all foreign costs translated to GBP via the "
    "costing FX rate."
)


# ---------------------------------------------------------------------------
# 1. Data source
# ---------------------------------------------------------------------------
st.header("1. Load Data")

use_sample = st.checkbox("Use sample data", value=True)

sample_dir = os.path.join(os.path.dirname(__file__), "data", "samples", "wac")


def _read(uploaded, sample_name):
    """Read CSV from uploader or fall back to sample file."""
    if use_sample:
        path = os.path.join(sample_dir, sample_name)
        if not os.path.exists(path):
            st.error(
                f"Sample file {path} not found. Run "
                "`python data/samples/wac/generate_sample_wac_data.py` first."
            )
            st.stop()
        return pd.read_csv(path)
    if uploaded is None:
        st.stop()
    return pd.read_csv(uploaded)


if not use_sample:
    col1, col2 = st.columns(2)
    with col1:
        opening_file = st.file_uploader("Opening Stock", type="csv", key="open")
        receipts_file = st.file_uploader("Receipts", type="csv", key="rcpt")
    with col2:
        pools_file = st.file_uploader("Cost Pools", type="csv", key="pool")
        fx_file = st.file_uploader("FX Rates", type="csv", key="fx")

    if not all([opening_file, receipts_file, pools_file, fx_file]):
        st.info("Upload all 4 CSVs, or tick **Use sample data** above.")
        st.stop()

    opening_df = _read(opening_file, "opening_stock.csv")
    receipts_df = _read(receipts_file, "receipts.csv")
    cost_pools_df = _read(pools_file, "cost_pools.csv")
    fx_df = _read(fx_file, "fx_rates.csv")
else:
    opening_df = _read(None, "opening_stock.csv")
    receipts_df = _read(None, "receipts.csv")
    cost_pools_df = _read(None, "cost_pools.csv")
    fx_df = _read(None, "fx_rates.csv")


# ---------------------------------------------------------------------------
# Prep: validate + coerce types inline (mirrors loader.py)
# ---------------------------------------------------------------------------
def _prepare(opening, receipts, pools, fx):
    errors = []

    req_open = {"sku", "opening_qty", "opening_wac_gbp"}
    req_recv = {"receipt_id", "shipment_id", "sku", "receipt_date",
                "qty", "invoice_ccy", "invoice_unit_cost"}
    req_pool = {"shipment_id",
                "freight_cost", "freight_ccy",
                "duty_cost", "duty_ccy",
                "goods_in_cost", "goods_in_ccy",
                "amortise_basis"}
    req_fx = {"ccy", "rate_to_gbp"}

    if not req_open.issubset(opening.columns):
        errors.append(f"opening_stock missing columns: {sorted(req_open - set(opening.columns))}")
    if not req_recv.issubset(receipts.columns):
        errors.append(f"receipts missing columns: {sorted(req_recv - set(receipts.columns))}")
    if not req_pool.issubset(pools.columns):
        errors.append(f"cost_pools missing columns: {sorted(req_pool - set(pools.columns))}")
    if not req_fx.issubset(fx.columns):
        errors.append(f"fx_rates missing columns: {sorted(req_fx - set(fx.columns))}")

    if errors:
        return errors, opening, receipts, pools, fx

    opening = opening.copy()
    opening["opening_qty"] = pd.to_numeric(opening["opening_qty"], errors="coerce").fillna(0).astype(int)
    opening["opening_wac_gbp"] = pd.to_numeric(opening["opening_wac_gbp"], errors="coerce").fillna(0.0)
    opening["opening_value_gbp"] = (opening["opening_qty"] * opening["opening_wac_gbp"]).round(2)

    receipts = receipts.copy()
    receipts["qty"] = pd.to_numeric(receipts["qty"], errors="coerce").fillna(0).astype(int)
    receipts["invoice_unit_cost"] = pd.to_numeric(receipts["invoice_unit_cost"], errors="coerce").fillna(0.0)
    receipts["invoice_ccy"] = receipts["invoice_ccy"].fillna("GBP").astype(str).str.upper().str.strip()
    receipts["receipt_date"] = pd.to_datetime(receipts["receipt_date"], errors="coerce")

    pools = pools.copy()
    for c in ["freight_cost", "duty_cost", "goods_in_cost"]:
        pools[c] = pd.to_numeric(pools[c], errors="coerce").fillna(0.0)
    for c in ["freight_ccy", "duty_ccy", "goods_in_ccy"]:
        pools[c] = pools[c].fillna("GBP").astype(str).str.upper().str.strip()
    pools["amortise_basis"] = pools["amortise_basis"].fillna("value").astype(str).str.lower().str.strip()

    fx = fx.copy()
    fx["ccy"] = fx["ccy"].astype(str).str.upper().str.strip()
    fx["rate_to_gbp"] = pd.to_numeric(fx["rate_to_gbp"], errors="coerce")

    return errors, opening, receipts, pools, fx


errors, opening_df, receipts_df, cost_pools_df, fx_df = _prepare(
    opening_df, receipts_df, cost_pools_df, fx_df
)
if errors:
    for e in errors:
        st.error(e)
    st.stop()


# ---------------------------------------------------------------------------
# 2. FX Calculator
# ---------------------------------------------------------------------------
st.header("2. Costing FX Rates")
st.markdown(
    "Rates are `GBP per 1 unit of CCY`. Edit the table below to run what-if "
    "scenarios — all amounts in the receipts and cost pools will be re-translated "
    "in real time."
)

# Combine the loaded rates with any currency seen in the data so nothing goes missing
needed_ccy = set(receipts_df["invoice_ccy"].unique()) | set(cost_pools_df["freight_ccy"].unique()) \
    | set(cost_pools_df["duty_ccy"].unique()) | set(cost_pools_df["goods_in_ccy"].unique())
needed_ccy.add("GBP")
existing_ccy = set(fx_df["ccy"].unique())
missing_ccy = needed_ccy - existing_ccy
if missing_ccy:
    add_rows = pd.DataFrame({"ccy": sorted(missing_ccy), "rate_to_gbp": 1.0})
    fx_df = pd.concat([fx_df, add_rows], ignore_index=True)
# Always force GBP = 1.0
fx_df.loc[fx_df["ccy"] == "GBP", "rate_to_gbp"] = 1.0

edited_fx = st.data_editor(
    fx_df.sort_values("ccy").reset_index(drop=True),
    use_container_width=True,
    num_rows="dynamic",
    column_config={
        "ccy": st.column_config.TextColumn("Currency", help="ISO code"),
        "rate_to_gbp": st.column_config.NumberColumn(
            "Rate to GBP",
            format="%.6f",
            min_value=0.000001,
            step=0.0001,
            help="GBP received per 1 unit of currency",
        ),
    },
    key="fx_editor",
)
edited_fx = edited_fx.dropna(subset=["ccy"]).copy()
edited_fx["ccy"] = edited_fx["ccy"].astype(str).str.upper().str.strip()
edited_fx["rate_to_gbp"] = pd.to_numeric(edited_fx["rate_to_gbp"], errors="coerce")
edited_fx = edited_fx[edited_fx["rate_to_gbp"] > 0]
edited_fx.loc[edited_fx["ccy"] == "GBP", "rate_to_gbp"] = 1.0

try:
    fx_lookup = build_fx_lookup(edited_fx)
except (ValueError, KeyError) as e:
    st.error(f"FX rates error: {e}")
    st.stop()


# ---------------------------------------------------------------------------
# 3. Data preview
# ---------------------------------------------------------------------------
with st.expander("Preview input data", expanded=False):
    t1, t2, t3 = st.tabs(["Opening Stock", "Receipts", "Cost Pools"])
    with t1:
        st.write(f"{len(opening_df):,} SKUs, {opening_df['opening_qty'].sum():,} units, "
                 f"£{opening_df['opening_value_gbp'].sum():,.2f} value")
        st.dataframe(opening_df, use_container_width=True, hide_index=True)
    with t2:
        st.write(f"{len(receipts_df):,} lines across "
                 f"{receipts_df['shipment_id'].nunique()} shipments, "
                 f"{receipts_df['qty'].sum():,} units")
        st.dataframe(receipts_df, use_container_width=True, hide_index=True)
    with t3:
        st.write(f"{len(cost_pools_df):,} shipments — native-currency totals: "
                 f"freight {cost_pools_df['freight_cost'].sum():,.2f}, "
                 f"duty {cost_pools_df['duty_cost'].sum():,.2f}, "
                 f"goods-in {cost_pools_df['goods_in_cost'].sum():,.2f}")
        st.dataframe(cost_pools_df, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# 4. Run model
# ---------------------------------------------------------------------------
st.header("3. WAC Results")

try:
    amortised = amortise_cost_pools(receipts_df, cost_pools_df, fx_lookup)
    landed = calculate_landed_cost(amortised)
    wac_df = calculate_wac(opening_df, landed)
except (KeyError, ValueError) as e:
    st.error(f"Calculation failed: {e}")
    st.stop()


# KPIs
total_open_qty = int(wac_df["opening_qty"].sum())
total_open_val = float(wac_df["opening_value_gbp"].sum())
total_recv_qty = int(wac_df["receipt_qty"].sum())
total_recv_inv = float(wac_df["receipt_invoice_gbp"].sum())
total_recv_lnd = float(wac_df["receipt_landed_gbp"].sum())
total_close_qty = int(wac_df["closing_qty"].sum())
total_close_val = float(wac_df["closing_value_gbp"].sum())
blended_wac = total_close_val / total_close_qty if total_close_qty > 0 else 0.0

k1, k2, k3, k4 = st.columns(4)
k1.metric("Opening Value", f"£{total_open_val:,.2f}", f"{total_open_qty:,} u")
k2.metric("Receipt Invoice (GBP)", f"£{total_recv_inv:,.2f}", f"{total_recv_qty:,} u")
k3.metric("Receipt Landed (GBP)", f"£{total_recv_lnd:,.2f}",
          f"+£{total_recv_lnd - total_recv_inv:,.2f} uplift")
k4.metric("Blended Closing WAC", f"£{blended_wac:,.4f}",
          f"£{total_close_val:,.2f} / {total_close_qty:,} u")

# Uplift breakdown
uplift = {
    "Freight": float(wac_df["receipt_freight_gbp"].sum()),
    "Duty": float(wac_df["receipt_duty_gbp"].sum()),
    "Goods-In": float(wac_df["receipt_goods_in_gbp"].sum()),
}
uplift_df = pd.DataFrame({
    "Cost Component": list(uplift.keys()),
    "Amortised GBP": list(uplift.values()),
})
uplift_df["% of Invoice"] = (uplift_df["Amortised GBP"] / max(total_recv_inv, 1) * 100).round(2)

st.subheader("Amortised Cost Uplift (over invoice)")
c1, c2 = st.columns([1, 2])
with c1:
    st.dataframe(uplift_df, use_container_width=True, hide_index=True)
with c2:
    st.bar_chart(uplift_df.set_index("Cost Component")["Amortised GBP"])


# ---------------------------------------------------------------------------
# 5. Detail tabs
# ---------------------------------------------------------------------------
tab_wac, tab_landed, tab_shipment = st.tabs([
    "WAC by SKU", "Landed Cost per Receipt", "Shipment Summary"
])

with tab_wac:
    st.subheader("Weighted Average Cost by SKU")
    filter_sku = st.text_input("Filter by SKU contains", key="wac_sku_filter")
    view = wac_df.copy()
    if filter_sku:
        view = view[view["sku"].astype(str).str.contains(filter_sku, case=False, na=False)]
    # Show WAC movement
    view["wac_delta_gbp"] = (view["new_wac_gbp"] - view["opening_wac_gbp"]).round(4)
    display = view[[
        "sku",
        "opening_qty", "opening_wac_gbp",
        "receipt_qty", "receipt_invoice_gbp",
        "receipt_freight_gbp", "receipt_duty_gbp", "receipt_goods_in_gbp",
        "receipt_landed_gbp",
        "closing_qty", "closing_value_gbp",
        "new_wac_gbp", "wac_delta_gbp",
    ]]
    st.dataframe(display, use_container_width=True, hide_index=True)
    st.caption(f"Showing {len(display):,} of {len(wac_df):,} SKUs")

with tab_landed:
    st.subheader("Landed Cost per Receipt Line")
    cols = [
        "receipt_id", "shipment_id", "sku", "receipt_date",
        "qty", "invoice_ccy", "invoice_unit_cost",
        "invoice_unit_gbp",
        "amort_freight_unit_gbp", "amort_duty_unit_gbp", "amort_goods_in_unit_gbp",
        "landed_unit_gbp", "landed_line_gbp",
    ]
    cols = [c for c in cols if c in landed.columns]
    st.dataframe(landed[cols], use_container_width=True, hide_index=True)

with tab_shipment:
    st.subheader("Shipment-Level Summary")
    if landed.empty:
        st.info("No receipts to summarise.")
    else:
        ship = (
            landed.groupby("shipment_id")
            .agg(
                lines=("receipt_id", "nunique"),
                units=("qty", "sum"),
                invoice_gbp=("invoice_line_gbp", "sum"),
                freight_gbp=("amort_freight_line_gbp", "sum"),
                duty_gbp=("amort_duty_line_gbp", "sum"),
                goods_in_gbp=("amort_goods_in_line_gbp", "sum"),
                landed_gbp=("landed_line_gbp", "sum"),
            )
            .reset_index()
        )
        ship["uplift_pct"] = ((ship["landed_gbp"] - ship["invoice_gbp"])
                              / ship["invoice_gbp"].clip(lower=0.01) * 100).round(2)
        ship = ship.merge(
            cost_pools_df[["shipment_id", "amortise_basis"]],
            on="shipment_id", how="left",
        )
        st.dataframe(ship, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# 6. Download
# ---------------------------------------------------------------------------
st.header("4. Download")
today = date.today().isoformat()

d1, d2 = st.columns(2)
with d1:
    st.download_button(
        "Download WAC Summary (CSV)",
        data=wac_df.to_csv(index=False),
        file_name=f"wac_summary_{today}.csv",
        mime="text/csv",
        use_container_width=True,
    )
with d2:
    st.download_button(
        "Download Landed Cost Detail (CSV)",
        data=landed.to_csv(index=False),
        file_name=f"wac_receipt_detail_{today}.csv",
        mime="text/csv",
        use_container_width=True,
    )
