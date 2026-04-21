"""
Finance Director search criteria.

Tune the values here to shape what counts as a "match". The scorer in
job_search.scorer reads this module directly. Defaults are a reasonable
starting point for a senior Finance Director targeting London and the
South West of England — edit to taste.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Title matching
# ---------------------------------------------------------------------------
# Any of these phrases in the job title counts as a title match. Case
# insensitive, substring match.
TITLE_INCLUDE = [
    "finance director",
    "group finance director",
    "divisional finance director",
    "fd",
    "cfo",
    "chief financial officer",
    "head of finance",
    "finance lead",
]

# Exclude junior / adjacent roles that often pollute "FD" searches.
TITLE_EXCLUDE = [
    "assistant",
    "trainee",
    "graduate",
    "intern",
    "analyst",
    "part qualified",
    "studier",
    "apprentice",
    "bookkeeper",
]

# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------
# Free-text locations sent to each API. We search each one and union the
# results. Tune the radius per location in MILES_RADIUS below.
LOCATIONS = [
    "London",
    "Bristol",
    "Bath",
    "Exeter",
    "Plymouth",
    "Bournemouth",
    "Cheltenham",
    "Swindon",
    "Taunton",
    "Truro",
]

# How wide to search around each location (miles).
MILES_RADIUS = 15

# Region keywords — if a listing's location string contains any of these we
# treat it as in-scope even when the city isn't in LOCATIONS (catches
# "South West England", "Greater London", etc).
REGION_KEYWORDS = [
    "london",
    "south west",
    "south-west",
    "southwest",
    "bristol",
    "bath",
    "somerset",
    "devon",
    "cornwall",
    "dorset",
    "wiltshire",
    "gloucestershire",
    "hampshire",
]

# ---------------------------------------------------------------------------
# Compensation
# ---------------------------------------------------------------------------
SALARY_MIN = 120_000       # £ per annum — floor for permanent roles
SALARY_CURRENCY = "GBP"

# Day rate floor for interim / contract roles.
DAY_RATE_MIN = 700

# ---------------------------------------------------------------------------
# Role type
# ---------------------------------------------------------------------------
INCLUDE_PERMANENT = True
INCLUDE_CONTRACT = True          # interim FD roles

# Remote tolerance: "onsite" | "hybrid" | "remote" | "any"
REMOTE_PREFERENCE = "hybrid"

# ---------------------------------------------------------------------------
# Industry preferences (optional — leave empty to not weight by sector)
# ---------------------------------------------------------------------------
INDUSTRY_PREFERRED = []          # e.g. ["retail", "consumer", "saas"]
INDUSTRY_EXCLUDED = []            # e.g. ["gambling", "tobacco"]

# ---------------------------------------------------------------------------
# Scoring thresholds
# ---------------------------------------------------------------------------
# Listings scoring below this are hidden from the dashboard by default.
MIN_SCORE_TO_SHOW = 50

# Weights used by job_search.scorer (sum need not equal 100).
WEIGHTS = {
    "title": 40,
    "location": 25,
    "salary": 20,
    "role_type": 10,
    "industry": 5,
}

# ---------------------------------------------------------------------------
# Polling
# ---------------------------------------------------------------------------
POLL_INTERVAL_MINUTES = 15        # how often poller.py re-checks sources
LOOKBACK_DAYS = 7                 # on first run, fetch jobs from the past N days

# ---------------------------------------------------------------------------
# RSS feeds — add any recruiter / aggregator feed URLs here.
# These are fetched as an additional source (see job_search.sources.rss).
# ---------------------------------------------------------------------------
RSS_FEEDS: list[str] = [
    # Examples — uncomment / add your own:
    # "https://www.cv-library.co.uk/search-jobs/finance-director-jobs/london/rss",
    # "https://www.jobserve.com/gb/en/JobSearch.aspx?shid=...&rss=1",
]
