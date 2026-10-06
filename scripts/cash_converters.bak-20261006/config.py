"""Configuration for Cash Converters scraper."""

import os
import json
from pathlib import Path

# Base paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
RESULTS_DIR = DATA_DIR / "results"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)

# Website configuration
BASE_URL = "https://www.cashconverters.co.za/shop/products"
SEARCH_INPUT_SELECTOR = "input[name='search']"
PRODUCT_CONTAINER_SELECTOR = "main"
PRODUCT_ARTICLE_SELECTOR = "article"

# Browser configuration
HEADLESS = True
TIMEOUT_MS = 30000  # 30 seconds
WAIT_FOR_LOAD_MS = 5000  # 5 seconds
PLAYWRIGHT_CHANNEL = "chromium"  # lightweight

# Search criteria storage
SEARCH_CRITERIA_FILE = DATA_DIR / "search_criteria.json"

# Default search criteria structure
DEFAULT_SEARCH_CRITERIA = [
    {
        "search_term": "laptop",
        "context": "Looking for functional second-hand laptops suitable for daily work"
    },
    {
        "search_term": "headphones",
        "context": "Seeking affordable second-hand headphones in good working condition"
    }
]

def load_search_criteria():
    """Load search criteria from file or create default."""
    if SEARCH_CRITERIA_FILE.exists():
        with open(SEARCH_CRITERIA_FILE, 'r') as f:
            return json.load(f)
    else:
        # Create default if none exists
        with open(SEARCH_CRITERIA_FILE, 'w') as f:
            json.dump(DEFAULT_SEARCH_CRITERIA, f, indent=2)
        return DEFAULT_SEARCH_CRITERIA

def save_search_criteria(criteria):
    """Save search criteria to file."""
    with open(SEARCH_CRITERIA_FILE, 'w') as f:
        json.dump(criteria, f, indent=2)

# Hermes handles Telegram delivery automatically.
# No TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID needed.
# No ANTHROPIC_API_KEY needed - Hermes provides Claude access.

# Results are delivered via Hermes gateway (stdout captured by cron)

# Session storage
LAST_RUN_FILE = DATA_DIR / "last_run.json"
