"""
Roll opening stock and landed receipts into a new Weighted Average Cost
per SKU.

    new_wac_gbp = (opening_value_gbp + sum(landed_line_gbp across receipts))
                / (opening_qty + sum(qty across receipts))

When the total closing qty is zero the WAC is reported as 0.00.
"""
import pandas as pd


def calculate_wac(opening_df, landed_df):
    """
    Combine opening stock with landed receipts and compute new WAC per SKU.

    Args:
        opening_df: DataFrame with columns
            [sku, opening_qty, opening_wac_gbp, opening_value_gbp]
        landed_df: DataFrame with columns
            [sku, qty, invoice_line_gbp,
             amort_freight_line_gbp, amort_duty_line_gbp,
             amort_goods_in_line_gbp, landed_line_gbp]

    Returns:
        DataFrame with one row per SKU containing:
            sku
            opening_qty
            opening_wac_gbp
            opening_value_gbp
            receipt_qty
            receipt_invoice_gbp
            receipt_freight_gbp
            receipt_duty_gbp
            receipt_goods_in_gbp
            receipt_landed_gbp
            closing_qty
            closing_value_gbp
            new_wac_gbp
    """
    # Aggregate receipts per SKU (build typed columns explicitly so an empty
    # landed frame still merges cleanly)
    agg_cols = {
        "receipt_qty": ("qty", "sum"),
        "receipt_invoice_gbp": ("invoice_line_gbp", "sum"),
        "receipt_freight_gbp": ("amort_freight_line_gbp", "sum"),
        "receipt_duty_gbp": ("amort_duty_line_gbp", "sum"),
        "receipt_goods_in_gbp": ("amort_goods_in_line_gbp", "sum"),
        "receipt_landed_gbp": ("landed_line_gbp", "sum"),
    }
    if not landed_df.empty:
        agg = landed_df.groupby("sku", as_index=False).agg(**agg_cols)
    else:
        agg = pd.DataFrame({
            "sku": pd.Series(dtype=object),
            "receipt_qty": pd.Series(dtype=int),
            "receipt_invoice_gbp": pd.Series(dtype=float),
            "receipt_freight_gbp": pd.Series(dtype=float),
            "receipt_duty_gbp": pd.Series(dtype=float),
            "receipt_goods_in_gbp": pd.Series(dtype=float),
            "receipt_landed_gbp": pd.Series(dtype=float),
        })

    # Outer-join to include SKUs with opening stock but no receipts AND vice versa
    merged = opening_df.merge(agg, on="sku", how="outer")

    # Fill numeric NaNs introduced by the outer join
    fill_zero_cols = [
        "opening_qty", "opening_wac_gbp", "opening_value_gbp",
        "receipt_qty",
        "receipt_invoice_gbp", "receipt_freight_gbp",
        "receipt_duty_gbp", "receipt_goods_in_gbp",
        "receipt_landed_gbp",
    ]
    for col in fill_zero_cols:
        if col in merged.columns:
            merged[col] = merged[col].fillna(0)

    merged["opening_qty"] = merged["opening_qty"].astype(int)
    merged["receipt_qty"] = merged["receipt_qty"].astype(int)

    merged["closing_qty"] = merged["opening_qty"] + merged["receipt_qty"]
    merged["closing_value_gbp"] = (merged["opening_value_gbp"] + merged["receipt_landed_gbp"]).round(2)

    # Safe divide: qty == 0 -> WAC 0
    merged["new_wac_gbp"] = (
        merged["closing_value_gbp"].astype(float)
        / merged["closing_qty"].replace(0, pd.NA)
    ).fillna(0.0).astype(float).round(4)

    # Stable column order
    cols = [
        "sku",
        "opening_qty", "opening_wac_gbp", "opening_value_gbp",
        "receipt_qty",
        "receipt_invoice_gbp", "receipt_freight_gbp",
        "receipt_duty_gbp", "receipt_goods_in_gbp",
        "receipt_landed_gbp",
        "closing_qty", "closing_value_gbp", "new_wac_gbp",
    ]
    return merged[cols].sort_values("sku").reset_index(drop=True)
