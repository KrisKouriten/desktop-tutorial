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

# File paths
DATA_DIR = "data"
OUTPUT_DIR = "output"
