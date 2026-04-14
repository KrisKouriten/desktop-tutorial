"""
Generate realistic sample data for the allocation model.
Run this once to produce the sample CSVs.

Usage: python data/samples/generate_sample_data.py
"""
import csv
import os
import random
from datetime import datetime, timedelta

random.seed(42)

SAMPLE_DIR = os.path.dirname(os.path.abspath(__file__))

NUM_STORES = 65
NUM_SKUS = 80  # Sample subset (real system handles 8000+)
NUM_KEY_SKUS = 50  # Subset that drives performance
NUM_WEEKS = 8
CATEGORIES = [
    "mens_shirts", "mens_trousers", "womens_tops", "womens_dresses",
    "accessories", "footwear", "outerwear", "knitwear"
]

# Generate store IDs
stores = [f"S{str(i).zfill(3)}" for i in range(1, NUM_STORES + 1)]

# Generate SKUs with categories
skus = []
for i in range(1, NUM_SKUS + 1):
    sku_id = f"SKU{str(i).zfill(5)}"
    category = CATEGORIES[(i - 1) % len(CATEGORIES)]
    skus.append((sku_id, category))

# Mark some SKUs as new with like-for-like replacements
new_skus = {}  # new_sku -> replaces_sku
for i in range(NUM_SKUS - 5, NUM_SKUS + 1):
    new_sku = f"SKU{str(i).zfill(5)}"
    old_sku = f"SKU{str(i - 20).zfill(5)}"
    new_skus[new_sku] = old_sku

# --- sku_master.csv ---
sku_master_path = os.path.join(SAMPLE_DIR, "sku_master.csv")
with open(sku_master_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["sku", "description", "category", "is_new", "replaces_sku", "pack_size"])
    for sku_id, category in skus:
        desc = f"{category.replace('_', ' ').title()} - {sku_id}"
        is_new = 1 if sku_id in new_skus else 0
        replaces = new_skus.get(sku_id, "")
        pack_size = random.choice([1, 1, 1, 2, 3])  # Most are pack_size 1
        writer.writerow([sku_id, desc, category, is_new, replaces, pack_size])

# --- store_range.csv ---
# Not all stores carry all SKUs. Larger stores carry more.
store_range_path = os.path.join(SAMPLE_DIR, "store_range.csv")
range_pairs = set()
store_grades = {}
with open(store_range_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["store_id", "sku", "in_range", "store_grade", "max_weekly_intake"])
    for store in stores:
        store_num = int(store[1:])
        # Store grading: A = flagship, B = mid-tier, C = smaller
        if store_num <= 20:
            range_pct = 0.90
            grade = "A"
            max_intake = 500  # Large receiving capacity
        elif store_num <= 45:
            range_pct = 0.65
            grade = "B"
            max_intake = 300
        else:
            range_pct = 0.40
            grade = "C"
            max_intake = 150

        store_grades[store] = grade
        for sku_id, _ in skus:
            if random.random() < range_pct:
                writer.writerow([store, sku_id, 1, grade, max_intake])
                range_pairs.add((store, sku_id))

# --- sales_history.csv ---
# Generate 8 weeks of sales for in-range store/SKU pairs
sales_path = os.path.join(SAMPLE_DIR, "sales_history.csv")
today = datetime(2026, 4, 12)  # Most recent Sunday
weeks = [(today - timedelta(weeks=w)).strftime("%Y-%m-%d") for w in range(NUM_WEEKS)]

with open(sales_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["week_ending", "store_id", "sku", "qty_sold"])
    for store, sku_id in range_pairs:
        # Skip new SKUs (they have no sales history)
        if sku_id in new_skus:
            continue
        # Base ROS varies by SKU (some are fast movers)
        sku_num = int(sku_id[3:])
        if sku_num <= NUM_KEY_SKUS:
            base_ros = random.uniform(2, 15)  # Key SKUs sell well
        else:
            base_ros = random.uniform(0.2, 3)  # Tail SKUs

        # Store size affects sales
        store_num = int(store[1:])
        if store_num <= 20:
            store_multiplier = random.uniform(1.2, 2.0)
        elif store_num <= 45:
            store_multiplier = random.uniform(0.7, 1.3)
        else:
            store_multiplier = random.uniform(0.3, 0.8)

        for week in weeks:
            qty = max(0, int(random.gauss(base_ros * store_multiplier, base_ros * 0.3)))
            if qty > 0:
                writer.writerow([week, store, sku_id, qty])

# --- warehouse_soh.csv ---
warehouse_path = os.path.join(SAMPLE_DIR, "warehouse_soh.csv")
with open(warehouse_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["sku", "warehouse_soh", "incoming_stock"])
    for sku_id, _ in skus:
        sku_num = int(sku_id[3:])
        if sku_num <= NUM_KEY_SKUS:
            wh_soh = random.randint(50, 500)
            incoming = random.choice([0, 0, 0, random.randint(50, 200)])
        else:
            wh_soh = random.randint(10, 150)
            incoming = random.choice([0, 0, random.randint(10, 50)])
        writer.writerow([sku_id, wh_soh, incoming])

# --- store_soh.csv ---
store_soh_path = os.path.join(SAMPLE_DIR, "store_soh.csv")
with open(store_soh_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["store_id", "sku", "store_soh"])
    for store, sku_id in range_pairs:
        # Some stock on hand, varies by store size
        store_num = int(store[1:])
        sku_num = int(sku_id[3:])
        if sku_num <= NUM_KEY_SKUS:
            base_soh = random.randint(0, 20)
        else:
            base_soh = random.randint(0, 8)

        if store_num <= 20:
            soh = int(base_soh * random.uniform(1.0, 1.5))
        else:
            soh = int(base_soh * random.uniform(0.5, 1.0))

        writer.writerow([store, sku_id, soh])

grade_counts = {}
for g in store_grades.values():
    grade_counts[g] = grade_counts.get(g, 0) + 1
grade_str = ", ".join(f"{g}={c}" for g, c in sorted(grade_counts.items()))

print(f"Sample data generated in {SAMPLE_DIR}/")
print(f"  Stores: {NUM_STORES} ({grade_str})")
print(f"  SKUs: {NUM_SKUS} ({NUM_KEY_SKUS} key)")
print(f"  New SKUs: {len(new_skus)}")
print(f"  Range pairs: {len(range_pairs)}")
print(f"  Weeks of history: {NUM_WEEKS}")
