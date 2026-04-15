"""
Weighted Average Cost (WAC) model.

Computes new WAC per SKU from opening stock + inbound receipts.
Receipts are landed at Invoice + Amortised Freight + Amortised Duty
+ Amortised Goods-In, with all foreign-currency costs translated to
GBP via a dynamic costing FX rate.
"""
