"""
FX conversion utilities.

The WAC model uses a *costing* FX rate (not the spot rate) so that
landed costs stay stable between revaluations. Rates are expressed
as "how many GBP you get for 1 unit of the source currency", i.e.
    amount_gbp = amount_ccy * rate_to_gbp

Rates are loaded from a small table (ccy -> rate_to_gbp) but can be
overridden at runtime from the Streamlit UI or CLI.
"""
import pandas as pd


# GBP is always 1.0 — it's the reporting currency.
GBP_RATE = 1.0


def build_fx_lookup(fx_rates_df, overrides=None):
    """
    Build a {ccy: rate_to_gbp} dict from an FX rates DataFrame.

    Args:
        fx_rates_df: DataFrame with columns [ccy, rate_to_gbp]
        overrides: optional dict of {ccy: rate_to_gbp} that wins
            over the DataFrame values (used for live UI overrides)

    Returns:
        dict mapping upper-cased currency code -> rate_to_gbp (float)
    """
    lookup = {"GBP": GBP_RATE}
    if fx_rates_df is not None and not fx_rates_df.empty:
        for _, row in fx_rates_df.iterrows():
            ccy = str(row["ccy"]).upper().strip()
            rate = float(row["rate_to_gbp"])
            if rate <= 0:
                raise ValueError(
                    f"FX rate for {ccy} must be positive, got {rate}"
                )
            lookup[ccy] = rate
    if overrides:
        for ccy, rate in overrides.items():
            ccy = str(ccy).upper().strip()
            rate = float(rate)
            if rate <= 0:
                raise ValueError(
                    f"FX override for {ccy} must be positive, got {rate}"
                )
            lookup[ccy] = rate
    # GBP always maps to 1.0 regardless of what's in the file
    lookup["GBP"] = GBP_RATE
    return lookup


def to_gbp(amount, ccy, fx_lookup):
    """
    Convert an amount in `ccy` to GBP using the costing rate.

    Missing currencies raise — silent fallback to 1.0 would hide bugs.
    """
    if amount is None or pd.isna(amount):
        return 0.0
    ccy = str(ccy).upper().strip() if ccy else "GBP"
    if ccy not in fx_lookup:
        raise KeyError(
            f"No costing FX rate defined for currency '{ccy}'. "
            f"Add it to fx_rates.csv or pass an override."
        )
    return float(amount) * fx_lookup[ccy]


def convert_series(amount_series, ccy_series, fx_lookup):
    """Vectorised version of `to_gbp` for pandas Series."""
    result = []
    for amt, ccy in zip(amount_series, ccy_series):
        result.append(to_gbp(amt, ccy, fx_lookup))
    return pd.Series(result, index=amount_series.index, dtype=float)
