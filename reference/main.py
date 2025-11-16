
import argparse
from outlook_fetcher import (
    connect_outlook,
    get_folder_by_path,
    get_items_for_period,
    extract_order_numbers_from_items,
)
from excel_fetcher import preflight_excel_for_period
from walmart_fetcher import fetch_orders

TARGET_FOLDER_PATH = "luis.rodrigues.oliveira@outlook.com/Inbox/Shopping/Supermarkets/Walmart"
TARGET_SUBJECT = "Your Walmart order was delivered"

def run_pipeline(period: str):
    # 1) Excel preflight (stub for now — prints where we'll write later)
    preflight_excel_for_period(period)

    # 2) Outlook subset
    ns = connect_outlook()
    if ns is None:
        print("[Outlook] Connection failed."); return
    print("[Outlook] Connected successfully.")

    folder = get_folder_by_path(ns, TARGET_FOLDER_PATH)
    if folder is None:
        print(f"[Outlook] Folder NOT found: {TARGET_FOLDER_PATH}"); return
    print(f"[Outlook] Folder found: '{TARGET_FOLDER_PATH}' — {folder.Items.Count} item(s).")

    items_in_period = get_items_for_period(folder, period)
    if items_in_period is None:
        print(f"[Filter] Period '{period}' is invalid. Use YYYY-MM."); return
    print(f"[Filter] Emails in {period}: {items_in_period.Count} item(s).")

    order_numbers = extract_order_numbers_from_items(items_in_period, subject_exact=TARGET_SUBJECT)
    order_numbers = sorted(order_numbers)
    print(f"[Extract] Unique order numbers found (subject = '{TARGET_SUBJECT}'): {len(order_numbers)}")
    for n in order_numbers:
        print(f" - {n}")

    # 3) Walmart fetcher
    if order_numbers:
        print(f"[Fetch] Fetching {len(order_numbers)} order page(s)...")
        fetch_orders(order_numbers)

def main():
    parser = argparse.ArgumentParser(description="Pipeline: Excel preflight -> Outlook filter -> Walmart fetch")
    parser.add_argument("--period", required=True, help="YYYY-MM, e.g. 2025-10")
    parser.add_argument("--pipeline", action="store_true", help="Run the full pipeline sequence")
    args = parser.parse_args()

    print(f"[Main] Target period: {args.period}")
    if args.pipeline:
        run_pipeline(args.period)
    else:
        # Default: behave like previous step (only outlook + extract)
        ns = connect_outlook()
        if ns is None:
            print("[Outlook] Connection failed."); return
        print("[Outlook] Connected successfully.")
        folder = get_folder_by_path(ns, TARGET_FOLDER_PATH)
        if folder is None:
            print(f"[Outlook] Folder NOT found: {TARGET_FOLDER_PATH}"); return
        print(f"[Outlook] Folder found: '{TARGET_FOLDER_PATH}' — {folder.Items.Count} item(s).")
        items_in_period = get_items_for_period(folder, args.period)
        if items_in_period is None:
            print(f"[Filter] Period '{args.period}' is invalid. Use YYYY-MM."); return
        print(f"[Filter] Emails in {args.period}: {items_in_period.Count} item(s).")
        order_numbers = extract_order_numbers_from_items(items_in_period, subject_exact=TARGET_SUBJECT)
        print(f"[Extract] Unique order numbers found (subject = '{TARGET_SUBJECT}'): {len(order_numbers)}")
        for n in sorted(order_numbers):
            print(f" - {n}")

if __name__ == "__main__":
    main()
