"""
WAC engine orchestrator.
Wires the full pipeline: load → FX → amortise → landed → WAC → output.
"""
from wac.loader import load_all
from wac.fx import build_fx_lookup
from wac.amortise import amortise_cost_pools
from wac.landed import calculate_landed_cost
from wac.wac import calculate_wac
from wac.output import write_wac_output, print_summary_stats


def run(data_dir, output_dir, fx_overrides=None):
    """
    Execute the WAC pipeline.

    Steps:
      1. Load opening stock, receipts, cost pools, FX rates
      2. Build FX lookup (applying any runtime overrides)
      3. Amortise freight / duty / goods-in across receipt lines
      4. Compute landed cost per line
      5. Roll into new WAC per SKU
      6. Write CSV output and print console summary

    Args:
        data_dir: directory with opening_stock.csv, receipts.csv,
                  cost_pools.csv, fx_rates.csv
        output_dir: where to write summary + detail CSVs
        fx_overrides: optional dict of {ccy: rate_to_gbp} that overrides
                      the values in fx_rates.csv (used for what-if analysis)

    Returns:
        (wac_df, landed_df) — final per-SKU WAC frame and the enriched
        per-line landed-cost frame.
    """
    # Step 1: Load
    data = load_all(data_dir)

    # Step 2: FX
    fx_lookup = build_fx_lookup(data["fx_rates"], overrides=fx_overrides)
    ccy_str = ", ".join(f"{c}={r:.4f}" for c, r in sorted(fx_lookup.items()))
    print(f"Costing FX rates (to GBP): {ccy_str}")
    if fx_overrides:
        ov_str = ", ".join(f"{c}={r:.4f}" for c, r in sorted(fx_overrides.items()))
        print(f"  (overrides applied: {ov_str})")

    # Step 3: Amortise cost pools
    print("Amortising freight, duty, and goods-in cost pools...")
    amortised = amortise_cost_pools(data["receipts"], data["cost_pools"], fx_lookup)
    print(f"  Amortised across {len(amortised):,} receipt lines "
          f"({amortised['shipment_id'].nunique()} shipments)\n")

    # Step 4: Landed cost per line
    print("Calculating landed cost per receipt...")
    landed = calculate_landed_cost(amortised)
    print(f"  Landed cost range: "
          f"£{landed['landed_unit_gbp'].min():.4f} - "
          f"£{landed['landed_unit_gbp'].max():.4f} per unit\n")

    # Step 5: Roll into WAC per SKU
    print("Computing weighted average cost per SKU...")
    wac_df = calculate_wac(data["opening"], landed)
    print(f"  New WAC computed for {len(wac_df):,} SKUs\n")

    # Step 6: Output
    print("Writing output...")
    write_wac_output(wac_df, landed, output_dir)
    print_summary_stats(wac_df, landed)

    return wac_df, landed
