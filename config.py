"""
Allocation Model Configuration
Adjust these parameters to match your business requirements.
"""

# How many weeks of sales history to use for rate-of-sale calculation
ROS_WEEKS = 8

# Target weeks of cover each store should hold
TARGET_WEEKS_OF_COVER = 4

# Minimum units to allocate to a store (avoid sending trivial quantities)
MIN_ALLOCATION_QTY = 1

# Warehouse reserve - hold back this percentage for ad-hoc / emergency needs
WAREHOUSE_RESERVE_PCT = 0.05  # 5%

# Rate of sale floor - ignore ROS below this (noise from very slow movers)
ROS_FLOOR = 0.1  # units per week

# --- Weighted ROS ---
# Weight recent weeks more heavily. Linear decay: most recent week gets
# weight ROS_WEEKS, next gets ROS_WEEKS-1, etc. Set False for simple average.
ROS_USE_WEIGHTED = True

# --- Store Grading ---
# Weeks of cover target per store grade (flagship stores hold more stock)
WEEKS_OF_COVER_BY_GRADE = {
    "A": 5,  # Flagship / high volume
    "B": 4,  # Mid-tier
    "C": 3,  # Smaller / lower volume
}

# Allocation priority multiplier per grade when stock is constrained.
# Higher = gets filled first. A-grade stores' needs are scaled up in priority.
GRADE_PRIORITY_MULTIPLIER = {
    "A": 1.3,
    "B": 1.0,
    "C": 0.8,
}

# --- Minimum Presentation Quantity ---
# Minimum units on hand for visual merchandising (by store grade).
# If a store is in-range for a SKU, it should have at least this many units.
MIN_PRESENTATION_QTY = {
    "A": 3,
    "B": 2,
    "C": 1,
}

# --- Safety Stock ---
# Safety stock multiplier on demand standard deviation.
# safety_stock = SAFETY_STOCK_Z * std_dev(weekly_sales)
# Z=1.28 ≈ 90% service level, Z=1.65 ≈ 95%, Z=2.05 ≈ 98%
SAFETY_STOCK_Z = 1.28

# --- Incoming Stock ---
# Whether to include incoming/pipeline stock in available warehouse inventory
INCLUDE_INCOMING_STOCK = True

# --- Replaced SKU Phase-Down ---
# When a new SKU replaces an old one, reduce the old SKU's allocation by this factor.
# 0.0 = stop allocating old SKU entirely, 0.5 = halve it, 1.0 = no change
REPLACED_SKU_ALLOCATION_FACTOR = 0.25

# --- Store Capacity ---
# Default maximum units a store can receive per week (0 = unlimited).
# Can be overridden per store in store_range.csv via max_weekly_intake column.
DEFAULT_MAX_WEEKLY_INTAKE = 0

# File paths
DATA_DIR = "data"
OUTPUT_DIR = "output"
