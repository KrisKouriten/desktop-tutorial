"""
Tests for the Weighted Average Cost (WAC) model.
Covers FX conversion, cost-pool amortisation, landed cost, and WAC roll-up.
"""
import pandas as pd
import pytest

from wac.fx import build_fx_lookup, to_gbp
from wac.amortise import amortise_cost_pools
from wac.landed import calculate_landed_cost
from wac.wac import calculate_wac


# ---------------------------------------------------------------------------
# FX
# ---------------------------------------------------------------------------

def test_fx_gbp_always_one():
    lookup = build_fx_lookup(pd.DataFrame(columns=["ccy", "rate_to_gbp"]))
    assert lookup["GBP"] == 1.0
    assert to_gbp(100.0, "GBP", lookup) == 100.0


def test_fx_usd_to_gbp():
    fx = pd.DataFrame([{"ccy": "USD", "rate_to_gbp": 0.80}])
    lookup = build_fx_lookup(fx)
    assert to_gbp(100.0, "USD", lookup) == pytest.approx(80.0)


def test_fx_overrides_take_precedence():
    fx = pd.DataFrame([{"ccy": "USD", "rate_to_gbp": 0.80}])
    lookup = build_fx_lookup(fx, overrides={"USD": 0.85})
    assert lookup["USD"] == 0.85


def test_fx_override_for_gbp_is_ignored():
    """GBP is the reporting ccy — it should always be 1.0 no matter what."""
    fx = pd.DataFrame([{"ccy": "USD", "rate_to_gbp": 0.80}])
    lookup = build_fx_lookup(fx, overrides={"GBP": 2.0})
    assert lookup["GBP"] == 1.0


def test_fx_missing_currency_raises():
    lookup = build_fx_lookup(pd.DataFrame([{"ccy": "USD", "rate_to_gbp": 0.80}]))
    with pytest.raises(KeyError):
        to_gbp(100.0, "JPY", lookup)


def test_fx_negative_rate_rejected():
    with pytest.raises(ValueError):
        build_fx_lookup(pd.DataFrame([{"ccy": "USD", "rate_to_gbp": -0.5}]))


# ---------------------------------------------------------------------------
# Amortisation: basis = value
# ---------------------------------------------------------------------------

def test_amortise_by_value_equal_split_when_values_equal():
    """Two lines with equal GBP invoice value should split the pool 50/50."""
    receipts = pd.DataFrame([
        {"receipt_id": "R1", "shipment_id": "S1", "sku": "A",
         "receipt_date": "2026-01-01", "qty": 10, "invoice_ccy": "GBP",
         "invoice_unit_cost": 5.0},
        {"receipt_id": "R2", "shipment_id": "S1", "sku": "B",
         "receipt_date": "2026-01-01", "qty": 10, "invoice_ccy": "GBP",
         "invoice_unit_cost": 5.0},
    ])
    pools = pd.DataFrame([{
        "shipment_id": "S1",
        "freight_cost": 100.0, "freight_ccy": "GBP",
        "duty_cost": 0.0, "duty_ccy": "GBP",
        "goods_in_cost": 0.0, "goods_in_ccy": "GBP",
        "amortise_basis": "value",
    }])
    lookup = build_fx_lookup(pd.DataFrame(columns=["ccy", "rate_to_gbp"]))
    out = amortise_cost_pools(receipts, pools, lookup)

    assert out["amort_freight_line_gbp"].tolist() == [50.0, 50.0]


def test_amortise_by_value_weighted_by_invoice_value():
    """Line with 3x the value gets 3x the freight share."""
    receipts = pd.DataFrame([
        {"receipt_id": "R1", "shipment_id": "S1", "sku": "A",
         "receipt_date": "2026-01-01", "qty": 10, "invoice_ccy": "GBP",
         "invoice_unit_cost": 3.0},
        {"receipt_id": "R2", "shipment_id": "S1", "sku": "B",
         "receipt_date": "2026-01-01", "qty": 10, "invoice_ccy": "GBP",
         "invoice_unit_cost": 9.0},
    ])
    pools = pd.DataFrame([{
        "shipment_id": "S1",
        "freight_cost": 120.0, "freight_ccy": "GBP",
        "duty_cost": 0.0, "duty_ccy": "GBP",
        "goods_in_cost": 0.0, "goods_in_ccy": "GBP",
        "amortise_basis": "value",
    }])
    lookup = build_fx_lookup(pd.DataFrame(columns=["ccy", "rate_to_gbp"]))
    out = amortise_cost_pools(receipts, pools, lookup)

    # Invoice values: 30 and 90 -> 25% / 75% -> 30 and 90 of the 120 freight pool
    assert out["amort_freight_line_gbp"].tolist() == [pytest.approx(30.0), pytest.approx(90.0)]


# ---------------------------------------------------------------------------
# Amortisation: basis = qty
# ---------------------------------------------------------------------------

def test_amortise_by_qty_ignores_invoice_value():
    """With qty basis, a high-price line pays the same per-unit share as low-price."""
    receipts = pd.DataFrame([
        {"receipt_id": "R1", "shipment_id": "S1", "sku": "A",
         "receipt_date": "2026-01-01", "qty": 10, "invoice_ccy": "GBP",
         "invoice_unit_cost": 100.0},
        {"receipt_id": "R2", "shipment_id": "S1", "sku": "B",
         "receipt_date": "2026-01-01", "qty": 30, "invoice_ccy": "GBP",
         "invoice_unit_cost": 1.0},
    ])
    pools = pd.DataFrame([{
        "shipment_id": "S1",
        "freight_cost": 200.0, "freight_ccy": "GBP",
        "duty_cost": 0.0, "duty_ccy": "GBP",
        "goods_in_cost": 0.0, "goods_in_ccy": "GBP",
        "amortise_basis": "qty",
    }])
    lookup = build_fx_lookup(pd.DataFrame(columns=["ccy", "rate_to_gbp"]))
    out = amortise_cost_pools(receipts, pools, lookup)

    # 10 and 30 units -> 25% and 75% -> 50 and 150
    assert out["amort_freight_line_gbp"].tolist() == [pytest.approx(50.0), pytest.approx(150.0)]


# ---------------------------------------------------------------------------
# Amortisation: FX integration
# ---------------------------------------------------------------------------

def test_amortise_converts_pool_currency_to_gbp():
    """Freight pool in USD gets translated via FX rate before being amortised."""
    receipts = pd.DataFrame([
        {"receipt_id": "R1", "shipment_id": "S1", "sku": "A",
         "receipt_date": "2026-01-01", "qty": 10, "invoice_ccy": "USD",
         "invoice_unit_cost": 10.0},
    ])
    pools = pd.DataFrame([{
        "shipment_id": "S1",
        "freight_cost": 100.0, "freight_ccy": "USD",
        "duty_cost": 0.0, "duty_ccy": "GBP",
        "goods_in_cost": 0.0, "goods_in_ccy": "GBP",
        "amortise_basis": "qty",
    }])
    fx = pd.DataFrame([{"ccy": "USD", "rate_to_gbp": 0.80}])
    lookup = build_fx_lookup(fx)

    out = amortise_cost_pools(receipts, pools, lookup)

    # Invoice: 10 units * 10 USD * 0.80 = 80 GBP
    assert out["invoice_line_gbp"].iloc[0] == pytest.approx(80.0)
    # Freight: 100 USD * 0.80 = 80 GBP, all to one line
    assert out["amort_freight_line_gbp"].iloc[0] == pytest.approx(80.0)


def test_amortise_mixed_currency_pool_components():
    """Each component (freight / duty / goods-in) uses its own currency."""
    receipts = pd.DataFrame([
        {"receipt_id": "R1", "shipment_id": "S1", "sku": "A",
         "receipt_date": "2026-01-01", "qty": 10, "invoice_ccy": "GBP",
         "invoice_unit_cost": 10.0},
    ])
    pools = pd.DataFrame([{
        "shipment_id": "S1",
        "freight_cost": 100.0, "freight_ccy": "USD",    # -> 80 GBP
        "duty_cost":    50.0,  "duty_ccy":    "EUR",    # -> 42.5 GBP
        "goods_in_cost": 20.0, "goods_in_ccy": "GBP",   # -> 20 GBP
        "amortise_basis": "qty",
    }])
    lookup = build_fx_lookup(pd.DataFrame([
        {"ccy": "USD", "rate_to_gbp": 0.80},
        {"ccy": "EUR", "rate_to_gbp": 0.85},
    ]))

    out = amortise_cost_pools(receipts, pools, lookup)
    assert out["amort_freight_line_gbp"].iloc[0] == pytest.approx(80.0)
    assert out["amort_duty_line_gbp"].iloc[0] == pytest.approx(42.5)
    assert out["amort_goods_in_line_gbp"].iloc[0] == pytest.approx(20.0)


def test_amortise_missing_cost_pool_leaves_zero_uplift():
    """Receipts without a matching shipment cost pool get no amortised charges."""
    receipts = pd.DataFrame([
        {"receipt_id": "R1", "shipment_id": "UNKNOWN", "sku": "A",
         "receipt_date": "2026-01-01", "qty": 10, "invoice_ccy": "GBP",
         "invoice_unit_cost": 5.0},
    ])
    pools = pd.DataFrame(columns=[
        "shipment_id", "freight_cost", "freight_ccy",
        "duty_cost", "duty_ccy", "goods_in_cost", "goods_in_ccy",
        "amortise_basis",
    ])
    lookup = build_fx_lookup(pd.DataFrame(columns=["ccy", "rate_to_gbp"]))
    out = amortise_cost_pools(receipts, pools, lookup)

    assert out["amort_freight_line_gbp"].iloc[0] == 0.0
    assert out["amort_duty_line_gbp"].iloc[0] == 0.0
    assert out["amort_goods_in_line_gbp"].iloc[0] == 0.0


# ---------------------------------------------------------------------------
# Landed cost
# ---------------------------------------------------------------------------

def test_landed_cost_is_sum_of_components():
    receipts = pd.DataFrame([
        {"receipt_id": "R1", "shipment_id": "S1", "sku": "A",
         "receipt_date": "2026-01-01", "qty": 10, "invoice_ccy": "GBP",
         "invoice_unit_cost": 10.0},
    ])
    pools = pd.DataFrame([{
        "shipment_id": "S1",
        "freight_cost": 20.0, "freight_ccy": "GBP",
        "duty_cost": 5.0, "duty_ccy": "GBP",
        "goods_in_cost": 5.0, "goods_in_ccy": "GBP",
        "amortise_basis": "qty",
    }])
    lookup = build_fx_lookup(pd.DataFrame(columns=["ccy", "rate_to_gbp"]))
    amortised = amortise_cost_pools(receipts, pools, lookup)
    landed = calculate_landed_cost(amortised)

    # invoice 10 + freight 2 + duty 0.5 + goods_in 0.5 = 13
    assert landed["landed_unit_gbp"].iloc[0] == pytest.approx(13.0)
    assert landed["landed_line_gbp"].iloc[0] == pytest.approx(130.0)


# ---------------------------------------------------------------------------
# WAC roll-up
# ---------------------------------------------------------------------------

def test_wac_blends_opening_and_receipts():
    """New WAC = (opening_value + landed_value) / (opening_qty + receipt_qty)."""
    opening = pd.DataFrame([{
        "sku": "A", "opening_qty": 100, "opening_wac_gbp": 10.0,
        "opening_value_gbp": 1000.0,
    }])
    landed = pd.DataFrame([{
        "sku": "A", "qty": 100,
        "invoice_line_gbp": 1500.0,
        "amort_freight_line_gbp": 200.0,
        "amort_duty_line_gbp": 100.0,
        "amort_goods_in_line_gbp": 50.0,
        "landed_line_gbp": 1850.0,
    }])
    wac_df = calculate_wac(opening, landed)
    row = wac_df.iloc[0]
    # closing: 200 units, value 1000 + 1850 = 2850, WAC = 14.25
    assert row["closing_qty"] == 200
    assert row["closing_value_gbp"] == pytest.approx(2850.0)
    assert row["new_wac_gbp"] == pytest.approx(14.25)


def test_wac_sku_with_no_receipts_keeps_opening_wac():
    opening = pd.DataFrame([{
        "sku": "A", "opening_qty": 50, "opening_wac_gbp": 4.0,
        "opening_value_gbp": 200.0,
    }])
    landed = pd.DataFrame(columns=[
        "sku", "qty", "invoice_line_gbp",
        "amort_freight_line_gbp", "amort_duty_line_gbp",
        "amort_goods_in_line_gbp", "landed_line_gbp",
    ])
    wac_df = calculate_wac(opening, landed)
    row = wac_df.iloc[0]
    assert row["receipt_qty"] == 0
    assert row["closing_qty"] == 50
    assert row["new_wac_gbp"] == pytest.approx(4.0)


def test_wac_new_sku_no_opening_stock():
    """A SKU with receipts but no opening stock gets WAC from receipts alone."""
    opening = pd.DataFrame(columns=[
        "sku", "opening_qty", "opening_wac_gbp", "opening_value_gbp",
    ])
    landed = pd.DataFrame([{
        "sku": "NEW1", "qty": 100,
        "invoice_line_gbp": 500.0,
        "amort_freight_line_gbp": 80.0,
        "amort_duty_line_gbp": 15.0,
        "amort_goods_in_line_gbp": 5.0,
        "landed_line_gbp": 600.0,
    }])
    wac_df = calculate_wac(opening, landed)
    row = wac_df.iloc[0]
    assert row["opening_qty"] == 0
    assert row["receipt_qty"] == 100
    assert row["closing_qty"] == 100
    assert row["new_wac_gbp"] == pytest.approx(6.0)


def test_wac_zero_total_qty_yields_zero_wac():
    opening = pd.DataFrame([{
        "sku": "DEAD", "opening_qty": 0, "opening_wac_gbp": 0.0,
        "opening_value_gbp": 0.0,
    }])
    landed = pd.DataFrame(columns=[
        "sku", "qty", "invoice_line_gbp",
        "amort_freight_line_gbp", "amort_duty_line_gbp",
        "amort_goods_in_line_gbp", "landed_line_gbp",
    ])
    wac_df = calculate_wac(opening, landed)
    assert wac_df.iloc[0]["new_wac_gbp"] == 0.0


# ---------------------------------------------------------------------------
# End-to-end round trip
# ---------------------------------------------------------------------------

def test_end_to_end_single_shipment():
    """
    Stakeholder-level check: a USD shipment, value-based amortisation.
    Walk through every step and assert the final WAC.
    """
    opening = pd.DataFrame([{
        "sku": "A", "opening_qty": 100, "opening_wac_gbp": 8.0,
        "opening_value_gbp": 800.0,
    }])
    receipts = pd.DataFrame([
        {"receipt_id": "R1", "shipment_id": "S1", "sku": "A",
         "receipt_date": "2026-01-01", "qty": 100, "invoice_ccy": "USD",
         "invoice_unit_cost": 10.0},   # 10 USD * 0.80 = 8.00 GBP per unit -> line 800
    ])
    pools = pd.DataFrame([{
        "shipment_id": "S1",
        "freight_cost": 125.0, "freight_ccy": "USD",   # -> 100 GBP
        "duty_cost":    62.5,  "duty_ccy":    "USD",   # -> 50 GBP
        "goods_in_cost": 50.0, "goods_in_ccy": "GBP",  # -> 50 GBP
        "amortise_basis": "value",
    }])
    fx = pd.DataFrame([{"ccy": "USD", "rate_to_gbp": 0.80}])
    lookup = build_fx_lookup(fx)

    amort = amortise_cost_pools(receipts, pools, lookup)
    landed = calculate_landed_cost(amort)
    wac_df = calculate_wac(opening, landed)

    row = wac_df.iloc[0]
    # Invoice GBP 800 + freight 100 + duty 50 + goods-in 50 = landed 1000
    assert row["receipt_invoice_gbp"] == pytest.approx(800.0)
    assert row["receipt_landed_gbp"] == pytest.approx(1000.0)
    # Closing: opening 800 + landed 1000 = 1800 over 200 units -> 9.00
    assert row["new_wac_gbp"] == pytest.approx(9.0)
