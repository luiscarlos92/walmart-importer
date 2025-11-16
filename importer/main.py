"""
Main entry point for Walmart Outlook Importer.
"""

import argparse
import sys
from pathlib import Path

from .config import (
    OUTLOOK_FOLDER_PATH,
    EMAIL_SUBJECT_FILTER,
    OUTPUT_DIR,
)
from .outlook_fetcher import (
    connect_outlook,
    get_folder_by_path,
    get_items_for_period,
    extract_order_numbers_from_items,
)
from .walmart_fetcher import fetch_orders


def print_banner():
    """Print application banner."""
    print("=" * 60)
    print(" " * 15 + "Walmart Importer – Pipeline Runner")
    print("=" * 60)
    print()


def run_pipeline(period: str):
    """
    Run the complete import pipeline.

    Args:
        period: Period string like "2025-10"
    """
    print(f"[Main] Target period: {period}")

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[Excel] Preflight OK. Output directory ready: {OUTPUT_DIR}")

    # Connect to Outlook
    ns = connect_outlook()
    if ns is None:
        print("[Outlook] Connection failed.")
        sys.exit(1)

    print("[Outlook] Connected successfully.")

    # Get target folder
    folder = get_folder_by_path(ns, OUTLOOK_FOLDER_PATH)
    if folder is None:
        print(f"[Outlook] Folder NOT found: {OUTLOOK_FOLDER_PATH}")
        sys.exit(1)

    print(f"[Outlook] Folder found: '{OUTLOOK_FOLDER_PATH}' — {folder.Items.Count} item(s).")

    # Filter by period
    items_in_period = get_items_for_period(folder, period)
    if items_in_period is None:
        print(f"[Filter] Period '{period}' is invalid. Use YYYY-MM.")
        sys.exit(1)

    print(f"[Filter] Emails in {period}: {items_in_period.Count} item(s).")

    # Extract order numbers
    order_numbers = extract_order_numbers_from_items(items_in_period, subject_exact=EMAIL_SUBJECT_FILTER)
    order_numbers = sorted(order_numbers)

    print(f"[Extract] Unique order numbers found (subject = '{EMAIL_SUBJECT_FILTER}'): {len(order_numbers)}")
    for n in order_numbers:
        print(f" - {n}")

    # Fetch orders from Walmart
    if order_numbers:
        print(f"[Fetch] Fetching {len(order_numbers)} order page(s)...")
        fetch_orders(order_numbers)
        print()
        print("[Main] Pipeline completed successfully!")
    else:
        print("[Main] No orders found for the specified period.")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Walmart Outlook Importer - Import orders from Outlook emails and Walmart.ca"
    )
    parser.add_argument(
        "--period",
        required=True,
        help="Period to import (YYYY-MM format, e.g., 2025-10)"
    )

    args = parser.parse_args()

    print_banner()
    run_pipeline(args.period)


if __name__ == "__main__":
    main()
