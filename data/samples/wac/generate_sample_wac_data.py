"""
Generate sample data for the Weighted Average Cost (WAC) model.

Produces:
    opening_stock.csv   — 20 SKUs with existing WAC in GBP
    receipts.csv        — 40 receipt lines across 6 shipments, mixed currencies
    cost_pools.csv      — freight / duty / goods-in per shipment (mixed ccy + basis)
    fx_rates.csv        — GBP, USD, EUR costing rates

Run:
    python data/samples/wac/generate_sample_wac_data.py
"""
import os
import random

import pandas as pd


OUT_DIR = os.path.dirname(os.path.abspath(__file__))
random.seed(42)


# ---------------------------------------------------------------------------
# 1. Opening stock: 20 SKUs
# ---------------------------------------------------------------------------
skus = [f"SKU{i:03d}" for i in range(1, 21)]
opening_rows = []
for sku in skus:
    qty = random.randint(0, 500)
    wac = round(random.uniform(3.00, 25.00), 2)
    opening_rows.append({
        "sku": sku,
        "opening_qty": qty,
        "opening_wac_gbp": wac,
    })
opening_df = pd.DataFrame(opening_rows)

# ---------------------------------------------------------------------------
# 2. Cost pools: 6 shipments, mixed currency + amortisation basis
# ---------------------------------------------------------------------------
shipments = [
    # Asia-origin USD freight, USD duty, GBP local handling
    {"shipment_id": "SHP-2026-001", "freight_cost": 4800.00, "freight_ccy": "USD",
     "duty_cost":    3200.00, "duty_ccy": "USD",
     "goods_in_cost": 450.00, "goods_in_ccy": "GBP",
     "amortise_basis": "value"},
    {"shipment_id": "SHP-2026-002", "freight_cost": 3200.00, "freight_ccy": "USD",
     "duty_cost":    1900.00, "duty_ccy": "USD",
     "goods_in_cost": 320.00, "goods_in_ccy": "GBP",
     "amortise_basis": "qty"},
    # Europe-origin EUR freight, GBP duty
    {"shipment_id": "SHP-2026-003", "freight_cost": 1600.00, "freight_ccy": "EUR",
     "duty_cost":     800.00, "duty_ccy": "GBP",
     "goods_in_cost": 210.00, "goods_in_ccy": "GBP",
     "amortise_basis": "value"},
    {"shipment_id": "SHP-2026-004", "freight_cost": 2100.00, "freight_ccy": "EUR",
     "duty_cost":    1100.00, "duty_ccy": "EUR",
     "goods_in_cost": 280.00, "goods_in_ccy": "GBP",
     "amortise_basis": "value"},
    # Domestic GBP
    {"shipment_id": "SHP-2026-005", "freight_cost":  550.00, "freight_ccy": "GBP",
     "duty_cost":       0.00, "duty_ccy": "GBP",
     "goods_in_cost": 140.00, "goods_in_ccy": "GBP",
     "amortise_basis": "qty"},
    # Mixed USD, high-duty apparel shipment
    {"shipment_id": "SHP-2026-006", "freight_cost": 5900.00, "freight_ccy": "USD",
     "duty_cost":    4600.00, "duty_ccy": "USD",
     "goods_in_cost": 600.00, "goods_in_ccy": "GBP",
     "amortise_basis": "value"},
]
cost_pools_df = pd.DataFrame(shipments)

# ---------------------------------------------------------------------------
# 3. Receipts: allocate each SKU to a shipment, sometimes multiple lines
# ---------------------------------------------------------------------------
receipts_rows = []
receipt_counter = 1
shipment_ccy_map = {
    "SHP-2026-001": "USD",
    "SHP-2026-002": "USD",
    "SHP-2026-003": "EUR",
    "SHP-2026-004": "EUR",
    "SHP-2026-005": "GBP",
    "SHP-2026-006": "USD",
}
shipment_date_map = {
    "SHP-2026-001": "2026-03-10",
    "SHP-2026-002": "2026-03-18",
    "SHP-2026-003": "2026-03-22",
    "SHP-2026-004": "2026-04-02",
    "SHP-2026-005": "2026-04-05",
    "SHP-2026-006": "2026-04-11",
}

# Make sure every shipment gets at least 2 lines, then fill out 40 total
lines_per_shipment = {s["shipment_id"]: [] for s in shipments}
sku_pool = list(skus)
for s in shipments:
    # seed with 2 random SKUs
    seeded = random.sample(sku_pool, 2)
    for sku in seeded:
        lines_per_shipment[s["shipment_id"]].append(sku)

# top up to 40 total lines
target_lines = 40
current = sum(len(v) for v in lines_per_shipment.values())
while current < target_lines:
    sid = random.choice(list(lines_per_shipment.keys()))
    lines_per_shipment[sid].append(random.choice(skus))
    current += 1

for sid, sku_list in lines_per_shipment.items():
    ccy = shipment_ccy_map[sid]
    recv_date = shipment_date_map[sid]
    for sku in sku_list:
        qty = random.randint(50, 400)
        if ccy == "USD":
            unit_cost = round(random.uniform(4.00, 20.00), 2)
        elif ccy == "EUR":
            unit_cost = round(random.uniform(4.50, 22.00), 2)
        else:
            unit_cost = round(random.uniform(3.50, 18.00), 2)
        receipts_rows.append({
            "receipt_id": f"RCV-{receipt_counter:04d}",
            "shipment_id": sid,
            "sku": sku,
            "receipt_date": recv_date,
            "qty": qty,
            "invoice_ccy": ccy,
            "invoice_unit_cost": unit_cost,
        })
        receipt_counter += 1

receipts_df = pd.DataFrame(receipts_rows)

# ---------------------------------------------------------------------------
# 4. FX rates
# ---------------------------------------------------------------------------
fx_df = pd.DataFrame([
    {"ccy": "GBP", "rate_to_gbp": 1.0},
    {"ccy": "USD", "rate_to_gbp": 0.79},   # ≈ $1 -> £0.79 costing rate
    {"ccy": "EUR", "rate_to_gbp": 0.85},   # ≈ €1 -> £0.85 costing rate
])

# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------
opening_df.to_csv(os.path.join(OUT_DIR, "opening_stock.csv"), index=False)
receipts_df.to_csv(os.path.join(OUT_DIR, "receipts.csv"), index=False)
cost_pools_df.to_csv(os.path.join(OUT_DIR, "cost_pools.csv"), index=False)
fx_df.to_csv(os.path.join(OUT_DIR, "fx_rates.csv"), index=False)

print(f"Wrote sample WAC data to {OUT_DIR}")
print(f"  opening_stock.csv : {len(opening_df)} SKUs")
print(f"  receipts.csv      : {len(receipts_df)} lines, "
      f"{receipts_df['shipment_id'].nunique()} shipments")
print(f"  cost_pools.csv    : {len(cost_pools_df)} shipments")
print(f"  fx_rates.csv      : {len(fx_df)} currencies")
