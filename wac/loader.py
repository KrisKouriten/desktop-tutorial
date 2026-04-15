"""
Data loading and validation for the WAC model.
"""
import os
import pandas as pd


def _check_columns(df, required_cols, filename):
    missing = set(required_cols) - set(df.columns)
    if missing:
        raise ValueError(
            f"{filename}: missing required columns: {sorted(missing)}. "
            f"Found columns: {sorted(df.columns)}"
        )


def _check_no_blanks(df, columns, filename):
    for col in columns:
        blank_count = df[col].isna().sum()
        if blank_count > 0:
            raise ValueError(
                f"{filename}: {blank_count} rows have blank '{col}' — fix your data"
            )


def load_opening_stock(path):
    """
    Load opening stock on hand with existing WAC.

    Expected columns:
        sku                 — SKU identifier
        opening_qty         — units on hand at period start
        opening_wac_gbp     — existing weighted average cost per unit (GBP)

    A derived `opening_value_gbp` column is added (qty x wac).
    """
    df = pd.read_csv(path)
    _check_columns(df, ["sku", "opening_qty", "opening_wac_gbp"], path)
    _check_no_blanks(df, ["sku"], path)

    df["opening_qty"] = pd.to_numeric(df["opening_qty"], errors="coerce").fillna(0).astype(int)
    df["opening_wac_gbp"] = pd.to_numeric(df["opening_wac_gbp"], errors="coerce").fillna(0.0).astype(float)
    df.loc[df["opening_qty"] < 0, "opening_qty"] = 0
    df.loc[df["opening_wac_gbp"] < 0, "opening_wac_gbp"] = 0.0

    df["opening_value_gbp"] = (df["opening_qty"] * df["opening_wac_gbp"]).round(2)

    print(f"  Opening stock: {len(df):,} SKUs, "
          f"{df['opening_qty'].sum():,} units, "
          f"£{df['opening_value_gbp'].sum():,.2f} value")
    return df


def load_receipts(path):
    """
    Load inbound receipts (purchase order lines).

    Expected columns:
        receipt_id          — unique line identifier
        shipment_id         — groups receipts that share a cost pool
        sku                 — SKU identifier
        receipt_date        — date the stock arrived
        qty                 — units received
        invoice_ccy         — currency of the invoice (e.g. USD, GBP, EUR)
        invoice_unit_cost   — unit cost on the supplier invoice, in invoice_ccy
    """
    df = pd.read_csv(path)
    required = [
        "receipt_id", "shipment_id", "sku", "receipt_date",
        "qty", "invoice_ccy", "invoice_unit_cost",
    ]
    _check_columns(df, required, path)
    _check_no_blanks(df, ["receipt_id", "shipment_id", "sku"], path)

    df["receipt_date"] = pd.to_datetime(df["receipt_date"], errors="coerce")
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0).astype(int)
    df["invoice_unit_cost"] = pd.to_numeric(df["invoice_unit_cost"], errors="coerce").fillna(0.0).astype(float)
    df["invoice_ccy"] = df["invoice_ccy"].fillna("GBP").astype(str).str.upper().str.strip()
    df.loc[df["qty"] < 0, "qty"] = 0
    df.loc[df["invoice_unit_cost"] < 0, "invoice_unit_cost"] = 0.0

    print(f"  Receipts: {len(df):,} lines, "
          f"{df['shipment_id'].nunique()} shipments, "
          f"{df['sku'].nunique()} SKUs, "
          f"{df['qty'].sum():,} units")
    return df


def load_cost_pools(path):
    """
    Load per-shipment cost pools for freight, duty, and goods-in charges.

    Expected columns:
        shipment_id         — matches receipts.shipment_id
        freight_cost        — total freight for the shipment
        freight_ccy         — currency of freight_cost
        duty_cost           — total duty for the shipment
        duty_ccy            — currency of duty_cost
        goods_in_cost       — total goods-in handling for the shipment
        goods_in_ccy        — currency of goods_in_cost
        amortise_basis      — 'qty' or 'value' (how to split cost across lines)
    """
    df = pd.read_csv(path)
    required = [
        "shipment_id",
        "freight_cost", "freight_ccy",
        "duty_cost", "duty_ccy",
        "goods_in_cost", "goods_in_ccy",
        "amortise_basis",
    ]
    _check_columns(df, required, path)
    _check_no_blanks(df, ["shipment_id"], path)

    for col in ["freight_cost", "duty_cost", "goods_in_cost"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)
        df.loc[df[col] < 0, col] = 0.0

    for col in ["freight_ccy", "duty_ccy", "goods_in_ccy"]:
        df[col] = df[col].fillna("GBP").astype(str).str.upper().str.strip()

    df["amortise_basis"] = df["amortise_basis"].fillna("value").astype(str).str.lower().str.strip()
    invalid_basis = ~df["amortise_basis"].isin({"qty", "value"})
    if invalid_basis.any():
        bad = df.loc[invalid_basis, "shipment_id"].tolist()
        raise ValueError(
            f"cost_pools: invalid amortise_basis for shipments {bad}. "
            f"Must be 'qty' or 'value'."
        )

    print(f"  Cost pools: {len(df):,} shipments, "
          f"freight={df['freight_cost'].sum():,.2f}, "
          f"duty={df['duty_cost'].sum():,.2f}, "
          f"goods_in={df['goods_in_cost'].sum():,.2f} (mixed ccy)")
    return df


def load_fx_rates(path):
    """
    Load costing FX rates.

    Expected columns:
        ccy              — ISO currency code (USD, EUR, GBP, ...)
        rate_to_gbp      — GBP received per 1 unit of ccy
    """
    df = pd.read_csv(path)
    _check_columns(df, ["ccy", "rate_to_gbp"], path)
    _check_no_blanks(df, ["ccy", "rate_to_gbp"], path)

    df["ccy"] = df["ccy"].astype(str).str.upper().str.strip()
    df["rate_to_gbp"] = pd.to_numeric(df["rate_to_gbp"], errors="coerce")
    if df["rate_to_gbp"].isna().any():
        raise ValueError(f"{path}: non-numeric rate_to_gbp values found")
    if (df["rate_to_gbp"] <= 0).any():
        raise ValueError(f"{path}: non-positive rate_to_gbp values found")

    print(f"  FX rates: {len(df)} currencies ({', '.join(sorted(df['ccy'].unique()))})")
    return df


def load_all(data_dir):
    """Load all WAC input files from the data directory."""
    print("Loading WAC data...")
    opening = load_opening_stock(os.path.join(data_dir, "opening_stock.csv"))
    receipts = load_receipts(os.path.join(data_dir, "receipts.csv"))
    cost_pools = load_cost_pools(os.path.join(data_dir, "cost_pools.csv"))
    fx_rates = load_fx_rates(os.path.join(data_dir, "fx_rates.csv"))

    # Cross-reference: every receipt must have a matching cost pool
    receipt_shipments = set(receipts["shipment_id"].unique())
    pool_shipments = set(cost_pools["shipment_id"].unique())
    orphans = receipt_shipments - pool_shipments
    if orphans:
        print(f"  WARNING: {len(orphans)} shipments on receipts have no cost pool "
              f"(freight/duty/GI will be 0): {sorted(orphans)[:5]}...")
    empty_pools = pool_shipments - receipt_shipments
    if empty_pools:
        print(f"  WARNING: {len(empty_pools)} cost pools have no receipts "
              f"(cost will not be amortised): {sorted(empty_pools)[:5]}...")

    print("Data loaded successfully.\n")
    return {
        "opening": opening,
        "receipts": receipts,
        "cost_pools": cost_pools,
        "fx_rates": fx_rates,
    }
