# Walmart Outlook Importer

A Windows Python application that imports Walmart orders from Outlook emails and scrapes order details from Walmart.ca using Playwright.

## Features

- **Outlook Integration**: Connects to Outlook desktop (MAPI) to find delivery confirmation emails
- **Order Extraction**: Extracts order numbers from email links and filters by date period
- **Web Scraping**: Uses Playwright to navigate to Walmart.ca order pages and extract details
- **Human-in-the-Loop**: Pauses when robot/login gates are detected for manual intervention
- **Comprehensive Parsing**: Extracts order date, payment method, customer name, financial details, and items
- **File Export**: Saves order details as both text summaries and raw HTML

## Bug Fixes

This version fixes critical parsing bugs from the reference implementation:

### 1. Discount Parsing
- **Previous Bug**: Summed ALL negative numbers in the page, including unrelated values
- **Fix**: Uses proper regex pattern to find discount labels ("Multisave Discount", "Savings", "Member Discount", etc.)
- **Multiple Discounts**: Handles orders with multiple discount types by summing them all
- **Result**: Discount is ALWAYS returned as a negative value (e.g., `-0.76` or `-3.75` for multiple discounts)

### 2. Delivery Fee Parsing
- **Previous Bug**: Would leave delivery as `None` when not found, causing errors
- **Fix**: Defaults to `0.00` when no delivery/shipping fee is present
- **Result**: Correct handling of orders with no delivery charge

### 3. Total and Subtotal
- **Verification**: Uses proper regex patterns to extract these values accurately

## Requirements

- **Windows** (tested on Windows 10/11)
- **Python 3.13.9** or later
- **Outlook Desktop** application (with MAPI access)
- Internet connection for accessing Walmart.ca

## Installation

### Quick Start

1. **Clone/Download** this repository
2. **Run the installer**:
   ```cmd
   install.cmd
   ```
   This will:
   - Create a virtual environment
   - Install all Python dependencies
   - Install Playwright Chromium browser

3. **Configure** (optional):
   - Copy `.env.example` to `.env`
   - Edit `.env` to customize your Outlook folder path if needed

### Manual Installation

If you prefer to install manually:

```cmd
# Create virtual environment
python -m venv .venv

# Activate it
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
python -m playwright install chromium
```

## Configuration

The default configuration is:
- **Outlook Folder**: `Inbox/Shopping/Supermarkets/Walmart`
- **Email Subject**: `Your Walmart order was delivered`

To customize, create a `.env` file (copy from `.env.example`):

```env
OUTLOOK_FOLDER_PATH=your.email@outlook.com/Inbox/Shopping/Supermarkets/Walmart
EMAIL_SUBJECT_FILTER=Your Walmart order was delivered
```

## Usage

### Run the Pipeline

1. **Double-click** `run_all.cmd`
2. **Enter** the period when prompted (format: `YYYY-MM`, e.g., `2025-10`)
3. The script will:
   - Connect to Outlook
   - Find emails in the specified period
   - Extract order numbers
   - Open Chromium and navigate to each order page
   - **Pause** if a robot gate or login page is detected
   - Parse and save order details

### Example Output

```
============================================================
               Walmart Importer – Pipeline Runner
============================================================

Enter period (YYYY-MM, e.g., 2025-10): 2025-10

Starting pipeline for period: 2025-10

[Main] Target period: 2025-10
[Excel] Preflight OK. Output directory ready: C:\...\walmart-importer\out
[Outlook] Connected successfully.
[Outlook] Folder found: 'Inbox/Shopping/Supermarkets/Walmart' — 980 item(s).
[Filter] Emails in 2025-10: 65 item(s).
[Extract] Unique order numbers found (subject = 'Your Walmart order was delivered'): 11
 - 600000046846089
 - 600000047123456
 ...
[Fetch] Fetching 11 order page(s)...
[Fetch] (1/11) https://www.walmart.ca/en/orders/600000046846089
[Order] 600000046846089 | Date: Oct 19, 2025 | Payment: ****1529 | Name: Luis | Total: $75.71
[Items] Found 8
[Save] Wrote C:\...\walmart-importer\out\600000046846089.txt
...
[Main] Pipeline completed successfully!
```

### Output Files

For each order, two files are created in the `out/` directory:

1. **`{order_no}.txt`**: Text summary with order details
2. **`{order_no}.html`**: Raw HTML of the order page

#### Example Text Summary (`600000046846089.txt`)

```
Order: 600000046846089
URL: https://www.walmart.ca/en/orders/600000046846089
Date: Oct 19, 2025
Payment: ****1529
Name: Luis
Subtotal: 75.71
Discount: -0.76
Delivery: 0.00
Taxes: 5.32
Total: 80.27
Items:
- Product Name 1 | Qty: 2 | Price: 12.99
- Product Name 2 | Qty: 1 | Price: 24.99
...
```

## How It Works

### 1. Outlook Connection

The app connects to Outlook desktop using `win32com` (MAPI) and navigates to your specified folder.

### 2. Email Filtering

Emails are filtered by:
- **ReceivedTime**: Within the specified month (e.g., `2025-10`)
- **Subject**: Exact match for "Your Walmart order was delivered"

### 3. Order Number Extraction

The app parses email bodies (HTML and text) to find Walmart order URLs like:
```
https://www.walmart.ca/en/orders/600000046846089
```

It handles:
- URL encoding/decoding
- Outlook SafeLinks unwrapping
- HTML entity decoding

### 4. Web Scraping with Playwright

For each order:
1. Opens the order page in Chromium (non-headless)
2. **Detects gates**:
   - **Robot page**: "We like real shoppers, not robots!"
   - **Login page**: Sign-in form
3. **Pauses for manual intervention** when gates are detected
4. **Waits** for "Payment method" text to confirm order page loaded
5. **Expands** items section if collapsed
6. **Extracts**:
   - Date (from "Delivered on..." or header)
   - Payment method and last 4 digits
   - Customer name (from Address section)
   - Financial summary: Subtotal, Discount, Delivery, Taxes, Total
   - Items: Name, quantity, price

### 5. Parsing Logic

The parser (`parsing.py`) uses:
- **BeautifulSoup** for HTML parsing
- **Regex patterns** for extracting specific fields
- **Resilient selectors** that fall back to text patterns

**Critical Rules**:
- **Discount**: Uses regex `RE_DISCOUNT` to find ALL discount labels (can be multiple), sums them, returns as negative value
- **Delivery**: Uses regex `RE_DELIVERY` to find delivery/shipping fees, defaults to 0.00 if not found
- **Money parsing**: Strips `$`, commas, spaces, handles parentheses as negative

## Project Structure

```
walmart-importer/
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── .env.example             # Environment config template
├── install.cmd              # Installation script
├── run_all.cmd              # Main launcher (prompts for period)
├── run_inner.cmd            # Inner script (activates venv, runs pipeline)
├── importer/                # Main package
│   ├── __init__.py
│   ├── main.py              # Entry point, orchestrates pipeline
│   ├── config.py            # Configuration settings
│   ├── utils.py             # Utility functions (money parsing, etc.)
│   ├── parsing.py           # Data models and HTML parsing
│   ├── outlook_fetcher.py   # Outlook MAPI integration
│   └── walmart_fetcher.py   # Playwright web scraping
├── out/                     # Output directory (created automatically)
├── logs/                    # Logs directory (reserved for future use)
└── .pw-user-data/          # Playwright browser user data (created automatically)
```

## Troubleshooting

### Outlook Security Prompts

**Problem**: Outlook shows security warnings when accessing emails programmatically.

**Solution**: Click "Allow" when prompted. You may need to configure Outlook Trust Center settings to allow programmatic access.

### Robot Page Doesn't Appear

**Problem**: The robot/CAPTCHA page appears but isn't detected.

**Solution**: The script will wait for content to load and then prompt you anyway. Just solve it manually and press Enter.

### Walmart Stylesheet Changes

**Problem**: Parsing fails because Walmart changed their page structure.

**Solution**: The parser uses multiple fallback strategies:
- Primary: Specific data attributes (`data-testid="..."`)
- Fallback 1: CSS class names (`.bill-item-quantity`)
- Fallback 2: XPath with text contains
- Fallback 3: Regex on visible text

If parsing still fails, you may need to update the selectors in `walmart_fetcher.py` and `parsing.py`.

### Python Version Issues

**Problem**: Installation fails with Python version errors.

**Solution**: Ensure you have Python 3.13 or later. Check with:
```cmd
python --version
```

### Missing Order Fields

**Problem**: Some orders are missing fields (e.g., no name, no date).

**Solution**:
- Check the raw HTML file in `out/{order_no}.html`
- The parser may need adjustment for edge cases
- Verify the order page loaded correctly (not a login/error page)

### Browser Launch Fails

**Problem**: Playwright fails to launch browser.

**Solution**:
1. Ensure Chromium was installed: `python -m playwright install chromium`
2. Try installing browsers manually: `python -m playwright install`
3. Check if antivirus is blocking the browser

## Testing

### Run Parser Unit Tests

```cmd
.venv\Scripts\activate
python -m importer.parsing
```

Expected output:
```
[Test] Discount parsing tests passed!
[Test] Delivery parsing tests passed!
[Test] All parsing tests passed!
```

### Test Individual Components

```cmd
# Test Outlook connection
python -c "from importer.outlook_fetcher import connect_outlook; ns = connect_outlook(); print('OK' if ns else 'FAIL')"

# Test configuration
python -c "from importer.config import OUTLOOK_FOLDER_PATH, OUTPUT_DIR; print(f'Folder: {OUTLOOK_FOLDER_PATH}'); print(f'Output: {OUTPUT_DIR}')"
```

## Development

### Adding New Features

The codebase is modular:
- **Outlook changes**: Edit `outlook_fetcher.py`
- **Walmart parsing**: Edit `parsing.py` and `walmart_fetcher.py`
- **Configuration**: Edit `config.py`
- **Pipeline flow**: Edit `main.py`

### Debugging

Enable verbose output by adding debug prints or using a debugger:

```cmd
.venv\Scripts\activate
python -m pdb -m importer.main --period 2025-10
```

## License

This is a personal project. Use at your own risk.

## Acknowledgments

- Built with [Playwright](https://playwright.dev/python/)
- Uses [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) for HTML parsing
- Outlook integration via [pywin32](https://github.com/mhammond/pywin32)
