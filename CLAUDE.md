# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Walmart Outlook Importer is a Windows Python application that automates order data extraction from Outlook emails and Walmart.ca order pages. The pipeline connects to Outlook desktop via MAPI, extracts order numbers from delivery confirmation emails, then uses Playwright to scrape order details from Walmart.ca.

**Key constraint**: This is a Windows-only application requiring Outlook Desktop and MAPI access.

## Running and Testing

### Install and Run
```cmd
# One-time setup
install.cmd

# Run the pipeline (prompts for period like "2025-10")
run_all.cmd

# Manual run with specific period
.venv\Scripts\activate
python -m importer.main --period 2025-10
```

### Testing
```cmd
# Run parser unit tests (validates critical bug fixes)
.venv\Scripts\activate
python -m importer.parsing

# Test Outlook connection
python -c "from importer.outlook_fetcher import connect_outlook; ns = connect_outlook(); print('OK' if ns else 'FAIL')"
```

## Architecture

### Pipeline Flow
1. **Outlook Connection** (`outlook_fetcher.py`) → Connects via win32com MAPI
2. **Email Filtering** → Filters by ReceivedTime (period) and Subject (exact match)
3. **Order Extraction** → Parses email bodies for Walmart order URLs, unwraps SafeLinks
4. **Web Scraping** (`walmart_fetcher.py`) → Launches Chromium via Playwright (non-headless)
5. **Gate Detection** → Pauses for manual intervention on robot/login pages
6. **HTML Parsing** (`parsing.py`) → Extracts order details using BeautifulSoup + regex
7. **File Export** → Saves `.txt` summary and `.html` raw page to `out/` directory

### Module Responsibilities

**`config.py`**: Central configuration via environment variables
- Outlook folder path and email subject filter
- Walmart URL template
- Timeouts and retry settings
- Directory paths (OUTPUT_DIR, LOGS_DIR, PW_USER_DATA_DIR)

**`outlook_fetcher.py`**: Outlook MAPI integration
- `connect_outlook()`: Establishes MAPI connection
- `get_folder_by_path()`: Navigates folder hierarchy by path string
- `get_items_for_period()`: Filters emails by ReceivedTime using Outlook date filters
- `extract_order_numbers_from_items()`: Parses HTML/text bodies for order URLs, handles SafeLinks unwrapping and URL decoding

**`walmart_fetcher.py`**: Playwright browser automation
- `_launch_context()`: Launches Chromium with persistent user data (for login sessions)
- `_check_robot_page()` / `_check_login_page()`: Detects gates requiring manual intervention
- `_parse_items_from_dom()`: Extracts order items using DOM selectors with fallbacks
- `fetch_orders()`: Main orchestrator - navigates pages, detects gates, parses, saves files

**`parsing.py`**: HTML parsing and data models
- Dataclasses: `OrderItem`, `OrderSummary`
- Regex patterns: `RE_TOTAL`, `RE_SUBTOTAL`, `RE_DISCOUNT`, `RE_DELIVERY`, `RE_TAXES`
- `parse_order_page()`: Main parser using BeautifulSoup + regex on visible text
- Built-in unit tests: `_test_discount_parsing()`, `_test_delivery_parsing()`

**`utils.py`**: Shared utilities
- `money_to_float()`: Strips currency symbols, commas, NBSP; handles parentheses as negative

**`main.py`**: Pipeline orchestrator
- Prints banner, prompts for period, runs full pipeline
- Ensures output directory exists, connects to Outlook, fetches orders

## Critical Parsing Rules

The parser has **specific bug fixes** from a reference implementation. Do NOT revert these patterns:

### Discount Parsing (CRITICAL)
```python
# CORRECT: Finds ALL discount labels, sums them, returns negative
RE_DISCOUNT = re.compile(
    r"\b(?:Savings|Multisave\s*Discount|[\w\s]*Discount)\b\s*[-]?\s*\$?\s*([0-9]+(?:\.[0-9]{2})?)",
    re.IGNORECASE
)
# Uses finditer() to find ALL matches
for m in RE_DISCOUNT.finditer(text_norm):
    discount_total += abs(discount_value)
discount = -discount_total  # ALWAYS negative
```
**Why**: Orders can have multiple discounts (Multisave Discount, Member Discount, etc.). All must be summed and returned as negative.

### Delivery Parsing (CRITICAL)
```python
# CORRECT: Requires $ immediately after "Delivery"/"Shipping"
RE_DELIVERY = re.compile(
    r"\b(?:Delivery|Shipping)\s*(?:fee)?\s*[:\-]?\s*\$\s*([0-9]+\.[0-9]{2})\b",
    re.IGNORECASE
)
# Defaults to 0.00 if not found
delivery = 0.0
m = RE_DELIVERY.search(text_norm)
if m:
    delivery = money_to_float(m.group(1))
```
**Why**: The previous pattern was too greedy - it matched "Delivered on" or "Delivery from store" followed by ANY price on the page (including item prices). This pattern requires the dollar sign immediately after the delivery label to avoid false positives.

**Real-world bug**: Order 600000046848554 showed `Delivery: 1.97` (first item price) instead of `0.00` because the old pattern matched "Delivery from store" followed by "Item: Pasta $1.97".

## DOM Selectors and Fallbacks

When Walmart changes their page structure, the parser uses layered fallbacks:
1. **Primary**: Data attributes (`data-testid="itemtile-stack"`, `data-testid="productName"`)
2. **Fallback 1**: CSS classes (`.bill-item-quantity`)
3. **Fallback 2**: XPath with text contains
4. **Fallback 3**: Regex on visible text (`page.evaluate("document.body.innerText")`)

If parsing fails after a Walmart update, check `walmart_fetcher.py` selectors first.

## Configuration Customization

Default Outlook folder: `Inbox/Shopping/Supermarkets/Walmart`
Default email subject: `Your Walmart order was delivered`

To customize, create `.env` file:
```env
OUTLOOK_FOLDER_PATH=your.email@outlook.com/Inbox/Shopping/Supermarkets/Walmart
EMAIL_SUBJECT_FILTER=Your Walmart order was delivered
```

## Human-in-the-Loop Gates

The browser runs **non-headless** to allow manual intervention:
- **Robot page**: Detects "We like real shoppers, not robots!" or "PRESS & HOLD" button
- **Login page**: Detects sign-in forms with email/password inputs

When detected, script prints message and waits for `input()` (user presses Enter after solving).

## Browser and User Data

- Uses **Playwright's bundled Chromium** (not Edge/Chrome)
- Persistent user data stored in `.pw-user-data/` (preserves login sessions between runs)
- Launch configured with anti-detection flags (`--disable-blink-features=AutomationControlled`)

## Output Files

For each order number (e.g., `600000046846089`):
- `out/600000046846089.txt`: Text summary with order details
- `out/600000046846089.html`: Raw HTML page source

Text format is strictly formatted (used for downstream processing):
```
Order: {order_no}
URL: {url}
Date: {date_str}
Payment: {payment_last4}
Name: {name}
Subtotal: {subtotal with 2dp}
Discount: {discount with minus sign}
Delivery: {delivery with 2dp}
Taxes: {taxes with 2dp}
Total: {total with 2dp}
Items:
- {title} | Qty: {qty} | Price: {price_each with 2dp}
```

## Modifying the Pipeline

- **Change Outlook logic**: Edit `outlook_fetcher.py`
- **Change Walmart scraping**: Edit `walmart_fetcher.py` (DOM selectors, gate detection)
- **Change parsing rules**: Edit `parsing.py` (regex patterns, extraction logic)
- **Change configuration**: Edit `config.py` (timeouts, paths, defaults)
- **Change pipeline flow**: Edit `main.py` (orchestration, logging)

## Important Notes

- **Windows-only**: Requires `pywin32` for Outlook MAPI
- **Outlook Desktop required**: Cannot use Outlook Web Access (OWA)
- **Period format**: Always `YYYY-MM` (e.g., `2025-10`)
- **Order numbers**: 15-digit numeric strings from Walmart.ca URLs
- **Browser state**: Login sessions persist across runs via `.pw-user-data/`
- **Error handling**: Individual order failures don't stop the pipeline (continues with next order)
