"""
Compute landed cost per receipt line from the amortised receipts frame.

    landed_unit_gbp  = invoice_unit_gbp
                     + amort_freight_unit_gbp
                     + amort_duty_unit_gbp
                     + amort_goods_in_unit_gbp

    landed_line_gbp  = landed_unit_gbp * qty
"""
import pandas as pd


LANDED_COMPONENTS = [
    "invoice_unit_gbp",
    "amort_freight_unit_gbp",
    "amort_duty_unit_gbp",
    "amort_goods_in_unit_gbp",
]


def calculate_landed_cost(amortised_df):
    """
    Add `landed_unit_gbp` and `landed_line_gbp` columns to the receipts frame.

    Args:
        amortised_df: output of amortise_cost_pools()

    Returns:
        DataFrame (copy) with two extra columns, rounded to 4 dp for unit cost
        and 2 dp for line value.
    """
    if amortised_df.empty:
        df = amortised_df.copy()
        df["landed_unit_gbp"] = pd.Series(dtype=float)
        df["landed_line_gbp"] = pd.Series(dtype=float)
        return df

    df = amortised_df.copy()
    df["landed_unit_gbp"] = sum(df[c] for c in LANDED_COMPONENTS).astype(float).round(4)
    df["landed_line_gbp"] = (df["landed_unit_gbp"] * df["qty"]).round(2)
    return df
