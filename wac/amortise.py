"""
Amortise per-shipment cost pools (freight, duty, goods-in) across
the receipt lines that belong to each shipment.

Two amortisation bases are supported:

- `qty`   — split the cost pool proportionally by units received.
            Use this for costs that scale with volume (e.g. freight
            billed per carton, goods-in labour).
- `value` — split proportionally by GBP invoice value of each line.
            Use this for ad-valorem costs (e.g. customs duty).

All cost pools are first translated to GBP with the costing FX rate
before being spread, so downstream calcs are single-currency.
"""
import pandas as pd

from wac.fx import to_gbp


def _split_pool(receipts_shipment, pool_total_gbp, basis):
    """
    Return a Series aligned to receipts_shipment.index with the GBP
    cost-pool share allocated to each line.

    basis: 'qty' | 'value'. For 'value', `invoice_line_gbp` must already
    be present on the receipts frame.
    """
    if pool_total_gbp <= 0 or receipts_shipment.empty:
        return pd.Series(0.0, index=receipts_shipment.index, dtype=float)

    if basis == "qty":
        weights = receipts_shipment["qty"].astype(float)
    elif basis == "value":
        weights = receipts_shipment["invoice_line_gbp"].astype(float)
    else:
        raise ValueError(f"Unknown amortise_basis: {basis!r}")

    total_weight = weights.sum()
    if total_weight <= 0:
        # Degenerate pool (e.g. all qty zero) — fall back to equal split
        equal = pool_total_gbp / len(receipts_shipment)
        return pd.Series(equal, index=receipts_shipment.index, dtype=float)

    return (weights / total_weight) * pool_total_gbp


def amortise_cost_pools(receipts_df, cost_pools_df, fx_lookup):
    """
    Spread freight, duty, and goods-in cost pools across each shipment's
    receipt lines and return an enriched DataFrame.

    Added columns (all GBP):
        invoice_unit_gbp          per-unit invoice cost translated to GBP
        invoice_line_gbp          invoice_unit_gbp * qty
        amort_freight_line_gbp    this line's share of freight
        amort_duty_line_gbp       this line's share of duty
        amort_goods_in_line_gbp   this line's share of goods-in
        amort_freight_unit_gbp    per-unit freight share
        amort_duty_unit_gbp       per-unit duty share
        amort_goods_in_unit_gbp   per-unit goods-in share

    Args:
        receipts_df: output of load_receipts()
        cost_pools_df: output of load_cost_pools()
        fx_lookup: dict from wac.fx.build_fx_lookup()
    """
    if receipts_df.empty:
        return receipts_df.copy()

    df = receipts_df.copy()

    # Step 1: translate per-unit invoice cost into GBP
    df["invoice_unit_gbp"] = [
        to_gbp(c, ccy, fx_lookup)
        for c, ccy in zip(df["invoice_unit_cost"], df["invoice_ccy"])
    ]
    df["invoice_line_gbp"] = (df["invoice_unit_gbp"] * df["qty"]).astype(float)

    # Initialise amortised columns — zero by default
    for col in [
        "amort_freight_line_gbp",
        "amort_duty_line_gbp",
        "amort_goods_in_line_gbp",
    ]:
        df[col] = 0.0

    # Step 2: walk each shipment's cost pool and apportion across its lines
    pools = cost_pools_df.set_index("shipment_id")

    for shipment_id, group in df.groupby("shipment_id", sort=False):
        if shipment_id not in pools.index:
            # No cost pool = all charges stay at zero (warning logged in loader)
            continue
        pool = pools.loc[shipment_id]
        basis = pool["amortise_basis"]

        freight_gbp = to_gbp(pool["freight_cost"], pool["freight_ccy"], fx_lookup)
        duty_gbp = to_gbp(pool["duty_cost"], pool["duty_ccy"], fx_lookup)
        goods_in_gbp = to_gbp(pool["goods_in_cost"], pool["goods_in_ccy"], fx_lookup)

        df.loc[group.index, "amort_freight_line_gbp"] = _split_pool(group, freight_gbp, basis).values
        df.loc[group.index, "amort_duty_line_gbp"] = _split_pool(group, duty_gbp, basis).values
        df.loc[group.index, "amort_goods_in_line_gbp"] = _split_pool(group, goods_in_gbp, basis).values

    # Step 3: derive per-unit equivalents (guarded against qty == 0)
    safe_qty = df["qty"].replace(0, pd.NA)
    df["amort_freight_unit_gbp"] = (df["amort_freight_line_gbp"] / safe_qty).fillna(0.0).astype(float)
    df["amort_duty_unit_gbp"] = (df["amort_duty_line_gbp"] / safe_qty).fillna(0.0).astype(float)
    df["amort_goods_in_unit_gbp"] = (df["amort_goods_in_line_gbp"] / safe_qty).fillna(0.0).astype(float)

    return df
