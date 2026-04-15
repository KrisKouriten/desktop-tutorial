"""
Output writer and console summary for the WAC model.
"""
import os
from datetime import date

import pandas as pd


def write_wac_output(wac_df, landed_df, output_dir):
    """
    Write two CSVs:
      - wac_summary_YYYY-MM-DD.csv  — one row per SKU with new WAC
      - wac_receipt_detail_YYYY-MM-DD.csv — landed cost detail per receipt line
    """
    os.makedirs(output_dir, exist_ok=True)
    today = date.today().isoformat()

    summary_path = os.path.join(output_dir, f"wac_summary_{today}.csv")
    wac_df.to_csv(summary_path, index=False)
    print(f"  Wrote {summary_path} ({len(wac_df):,} SKUs)")

    detail_cols = [
        "receipt_id", "shipment_id", "sku", "receipt_date",
        "qty", "invoice_ccy", "invoice_unit_cost",
        "invoice_unit_gbp", "invoice_line_gbp",
        "amort_freight_line_gbp", "amort_duty_line_gbp",
        "amort_goods_in_line_gbp",
        "amort_freight_unit_gbp", "amort_duty_unit_gbp",
        "amort_goods_in_unit_gbp",
        "landed_unit_gbp", "landed_line_gbp",
    ]
    detail_cols = [c for c in detail_cols if c in landed_df.columns]
    detail_path = os.path.join(output_dir, f"wac_receipt_detail_{today}.csv")
    landed_df[detail_cols].to_csv(detail_path, index=False)
    print(f"  Wrote {detail_path} ({len(landed_df):,} receipt lines)")


def print_summary_stats(wac_df, landed_df):
    """Print a compact console summary of the WAC run."""
    total_open_qty = int(wac_df["opening_qty"].sum())
    total_open_val = float(wac_df["opening_value_gbp"].sum())
    total_recv_qty = int(wac_df["receipt_qty"].sum())
    total_recv_inv = float(wac_df["receipt_invoice_gbp"].sum())
    total_recv_frt = float(wac_df["receipt_freight_gbp"].sum())
    total_recv_dty = float(wac_df["receipt_duty_gbp"].sum())
    total_recv_gin = float(wac_df["receipt_goods_in_gbp"].sum())
    total_recv_lnd = float(wac_df["receipt_landed_gbp"].sum())
    total_close_qty = int(wac_df["closing_qty"].sum())
    total_close_val = float(wac_df["closing_value_gbp"].sum())
    blended_wac = total_close_val / total_close_qty if total_close_qty > 0 else 0.0

    print()
    print("=" * 72)
    print("WAC Run Summary")
    print("=" * 72)
    print(f"  SKUs processed          : {len(wac_df):,}")
    print(f"  Receipt lines           : {len(landed_df):,}")
    print()
    print(f"  Opening qty / value     : {total_open_qty:>10,}  £{total_open_val:>14,.2f}")
    print(f"  Receipt qty / invoice   : {total_recv_qty:>10,}  £{total_recv_inv:>14,.2f}")
    print(f"    + freight amortised   : {'':>10}   £{total_recv_frt:>14,.2f}")
    print(f"    + duty amortised      : {'':>10}   £{total_recv_dty:>14,.2f}")
    print(f"    + goods-in amortised  : {'':>10}   £{total_recv_gin:>14,.2f}")
    print(f"  Receipt landed value    : {'':>10}   £{total_recv_lnd:>14,.2f}")
    print()
    print(f"  Closing qty / value     : {total_close_qty:>10,}  £{total_close_val:>14,.2f}")
    print(f"  Blended WAC across all  : £{blended_wac:,.4f}")
    print("=" * 72)
