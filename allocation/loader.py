"""
Data loading and validation for the allocation model.
Each loader validates schema, data types, and flags problems early.
"""
import os
import pandas as pd


def _check_columns(df, required_cols, filename):
    """Validate that required columns exist in the DataFrame."""
    missing = set(required_cols) - set(df.columns)
    if missing:
        raise ValueError(
            f"{filename}: missing required columns: {sorted(missing)}. "
            f"Found columns: {sorted(df.columns)}"
        )


def _check_no_blanks(df, columns, filename):
    """Validate that key columns have no blank/null values."""
    for col in columns:
        blank_count = df[col].isna().sum()
        if blank_count > 0:
            raise ValueError(
                f"{filename}: found {blank_count} rows with blank '{col}' — fix your data"
            )


def load_sales_history(path):
    """
    Load weekly sales history.
    Expected columns: week_ending, store_id, sku, qty_sold
    """
    df = pd.read_csv(path)
    _check_columns(df, ["week_ending", "store_id", "sku", "qty_sold"], path)
    _check_no_blanks(df, ["store_id", "sku"], path)

    df["week_ending"] = pd.to_datetime(df["week_ending"])
    df["qty_sold"] = pd.to_numeric(df["qty_sold"], errors="coerce").fillna(0).astype(int)
    df.loc[df["qty_sold"] < 0, "qty_sold"] = 0

    print(f"  Sales history: {len(df):,} rows, "
          f"{df['store_id'].nunique()} stores, "
          f"{df['sku'].nunique()} SKUs, "
          f"{df['week_ending'].nunique()} weeks")
    return df


def load_warehouse_soh(path):
    """
    Load warehouse stock on hand.
    Expected columns: sku, warehouse_soh
    Optional: incoming_stock
    """
    df = pd.read_csv(path)
    _check_columns(df, ["sku", "warehouse_soh"], path)
    _check_no_blanks(df, ["sku"], path)

    df["warehouse_soh"] = pd.to_numeric(df["warehouse_soh"], errors="coerce").fillna(0).astype(int)
    df.loc[df["warehouse_soh"] < 0, "warehouse_soh"] = 0

    if "incoming_stock" in df.columns:
        df["incoming_stock"] = pd.to_numeric(df["incoming_stock"], errors="coerce").fillna(0).astype(int)
    else:
        df["incoming_stock"] = 0

    print(f"  Warehouse SOH: {len(df):,} SKUs, "
          f"{df['warehouse_soh'].sum():,} total units")
    return df


def load_store_soh(path):
    """
    Load store stock on hand.
    Expected columns: store_id, sku, store_soh
    """
    df = pd.read_csv(path)
    _check_columns(df, ["store_id", "sku", "store_soh"], path)
    _check_no_blanks(df, ["store_id", "sku"], path)

    df["store_soh"] = pd.to_numeric(df["store_soh"], errors="coerce").fillna(0).astype(int)
    df.loc[df["store_soh"] < 0, "store_soh"] = 0

    print(f"  Store SOH: {len(df):,} rows, "
          f"{df['store_id'].nunique()} stores, "
          f"{df['store_soh'].sum():,} total units")
    return df


def load_store_range(path):
    """
    Load store range matrix (which stores carry which SKUs).
    Expected columns: store_id, sku, in_range
    Only returns rows where in_range == 1.
    """
    df = pd.read_csv(path)
    _check_columns(df, ["store_id", "sku", "in_range"], path)
    _check_no_blanks(df, ["store_id", "sku"], path)

    df["in_range"] = pd.to_numeric(df["in_range"], errors="coerce").fillna(0).astype(int)
    df = df[df["in_range"] == 1][["store_id", "sku"]].copy()

    print(f"  Store range: {len(df):,} active pairs, "
          f"{df['store_id'].nunique()} stores, "
          f"{df['sku'].nunique()} SKUs")
    return df


def load_sku_master(path):
    """
    Load SKU master data.
    Expected columns: sku, description, category, is_new, replaces_sku, pack_size
    """
    df = pd.read_csv(path)
    _check_columns(df, ["sku", "description", "category", "is_new", "replaces_sku", "pack_size"], path)
    _check_no_blanks(df, ["sku"], path)

    df["is_new"] = pd.to_numeric(df["is_new"], errors="coerce").fillna(0).astype(int)
    df["replaces_sku"] = df["replaces_sku"].fillna("").astype(str).str.strip()
    df["pack_size"] = pd.to_numeric(df["pack_size"], errors="coerce").fillna(1).astype(int)
    df.loc[df["pack_size"] < 1, "pack_size"] = 1

    new_count = (df["is_new"] == 1).sum()
    with_replacement = (df["replaces_sku"] != "").sum()
    print(f"  SKU master: {len(df):,} SKUs, "
          f"{new_count} new ({with_replacement} with like-for-like mapping)")
    return df


def load_all(data_dir):
    """Load all input files from the data directory."""
    print("Loading data...")
    sales = load_sales_history(os.path.join(data_dir, "sales_history.csv"))
    warehouse = load_warehouse_soh(os.path.join(data_dir, "warehouse_soh.csv"))
    store_soh = load_store_soh(os.path.join(data_dir, "store_soh.csv"))
    store_range = load_store_range(os.path.join(data_dir, "store_range.csv"))
    sku_master = load_sku_master(os.path.join(data_dir, "sku_master.csv"))

    # Cross-reference warnings
    range_skus = set(store_range["sku"].unique())
    master_skus = set(sku_master["sku"].unique())
    sales_skus = set(sales["sku"].unique())

    orphan_range = range_skus - master_skus
    if orphan_range:
        print(f"  WARNING: {len(orphan_range)} SKUs in store_range not found in sku_master")

    orphan_sales = sales_skus - master_skus
    if orphan_sales:
        print(f"  WARNING: {len(orphan_sales)} SKUs in sales_history not found in sku_master")

    print("Data loaded successfully.\n")
    return {
        "sales": sales,
        "warehouse": warehouse,
        "store_soh": store_soh,
        "store_range": store_range,
        "sku_master": sku_master,
    }
