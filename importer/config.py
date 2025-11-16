"""
Configuration settings for Walmart Importer.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

# Outlook configuration
OUTLOOK_FOLDER_PATH = os.getenv(
    "OUTLOOK_FOLDER_PATH",
    "Inbox/Shopping/Supermarkets/Walmart"
)

EMAIL_SUBJECT_FILTER = os.getenv(
    "EMAIL_SUBJECT_FILTER",
    "Your Walmart order was delivered"
)

# Walmart configuration
WALMART_ORDER_URL_TEMPLATE = "https://www.walmart.ca/en/orders/{order_no}"

# Paths
BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "out"
LOGS_DIR = BASE_DIR / "logs"
PW_USER_DATA_DIR = BASE_DIR / ".pw-user-data"

# Timeouts (milliseconds)
PAGE_NAVIGATION_TIMEOUT = 120000  # 2 minutes
PAGE_CONTENT_TIMEOUT = 25000      # 25 seconds
ELEMENT_TIMEOUT = 4000            # 4 seconds

# Retry configuration
MAX_RETRIES = 2
RETRY_DELAY = 1.0  # seconds

# Ensure directories exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
