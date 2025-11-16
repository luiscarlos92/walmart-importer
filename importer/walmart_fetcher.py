"""
Walmart order fetcher using Playwright.
"""

from typing import List
import time
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

from .config import (
    WALMART_ORDER_URL_TEMPLATE,
    OUTPUT_DIR,
    PW_USER_DATA_DIR,
    PAGE_NAVIGATION_TIMEOUT,
    PAGE_CONTENT_TIMEOUT,
    ELEMENT_TIMEOUT,
)
from .parsing import parse_order_page, OrderSummary, OrderItem, RE_QTY, RE_PRICE


def _launch_context(p):
    """
    Launch a Playwright browser context with persistent user data.
    Uses Chromium browser.
    """
    PW_USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

    try:
        return p.chromium.launch_persistent_context(
            user_data_dir=str(PW_USER_DATA_DIR),
            channel=None,  # Use Playwright's bundled Chromium
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-web-security",
            ]
        )
    except Exception as e:
        print(f"[Browser] Failed to launch persistent context: {e}")
        # Fallback to regular launch
        return p.chromium.launch(headless=False)


def _visible_text(page) -> str:
    """Extract visible text from page using innerText."""
    try:
        return page.evaluate("document.body.innerText || ''")
    except Exception:
        return ""


def _check_robot_page(page) -> bool:
    """
    Check if the robot/CAPTCHA page is displayed.

    Returns:
        True if robot page is detected
    """
    text = _visible_text(page).lower()
    if "we like real shoppers, not robots" in text:
        return True

    try:
        # Check for PRESS & HOLD button
        button = page.locator("button:has-text('PRESS & HOLD')").first
        if button.count() > 0:
            return True
    except Exception:
        pass

    return False


def _check_login_page(page) -> bool:
    """
    Check if the login page is displayed.

    Returns:
        True if login page is detected
    """
    text = _visible_text(page).lower()

    # Check for sign-in heading
    if "sign in" in text:
        try:
            # Look for email/password inputs
            email_input = page.locator("input[type='email']").first
            password_input = page.locator("input[type='password']").first

            if email_input.count() > 0 or password_input.count() > 0:
                return True
        except Exception:
            pass

    return False


def _wait_for_order_content(page, timeout_ms=PAGE_CONTENT_TIMEOUT) -> bool:
    """
    Wait for order content to load.

    Returns:
        True if content loaded, False if timeout
    """
    try:
        page.wait_for_selector("text=Payment method", timeout=timeout_ms)
        return True
    except PwTimeout:
        return False


def _expand_items_if_needed(page):
    """Expand the items section if it's collapsed."""
    try:
        toggle = page.locator("button[data-automation-id='items-toggle-link']").first
        if toggle.count():
            expanded = toggle.get_attribute("aria-expanded") or ""
            if expanded.lower() != "true":
                toggle.click()
                time.sleep(0.4)

        # Wait for at least one item tile to appear
        page.wait_for_selector("div[data-testid='itemtile-stack']", timeout=ELEMENT_TIMEOUT)
    except Exception:
        pass


def _parse_items_from_dom(page) -> List[OrderItem]:
    """
    Parse order items from the DOM.

    Returns:
        List of OrderItem objects
    """
    items = []
    _expand_items_if_needed(page)

    tiles = page.locator("div[data-testid='itemtile-stack']")
    count = tiles.count()

    for i in range(count):
        tile = tiles.nth(i)
        try:
            # Extract product name
            try:
                name = tile.locator("[data-testid='productName']").first.inner_text(timeout=1000).strip()
            except Exception:
                name = ""

            # Extract quantity
            try:
                qty_txt = tile.locator(".bill-item-quantity").first.inner_text(timeout=800).strip()
            except Exception:
                # Fallback: any node containing "Qty"
                try:
                    qty_txt = tile.locator("xpath=.//*[contains(translate(text(),'QTY','qty'),'qty')]").first.inner_text(timeout=800).strip()
                except Exception:
                    qty_txt = ""

            mqty = RE_QTY.search(qty_txt)
            qty = int(mqty.group(1)) if mqty else 1

            # Extract price
            price = 0.0
            try:
                price_txt = tile.locator("[data-testid='line-price']").first.inner_text(timeout=800).strip()
                m = RE_PRICE.search(price_txt)
                if m:
                    price = float(m.group(1))
            except Exception:
                # Last resort: any $ in tile text
                try:
                    anytxt = tile.inner_text(timeout=800)
                    m = RE_PRICE.search(anytxt)
                    if m:
                        price = float(m.group(1))
                except Exception:
                    price = 0.0

            if name and price:
                items.append(OrderItem(title=name, qty=qty, price_each=price))
        except Exception:
            continue

    return items


def _extract_first_name_dom(page) -> str:
    """
    Extract first name from DOM near "Address" heading.

    Returns:
        First name or empty string
    """
    xpaths = [
        "xpath=//*[normalize-space(text())='Address']/following::*[1]",
        "xpath=//h2[normalize-space()='Address']/following::*[1]",
        "xpath=//div[.//*[normalize-space(text())='Address']]//following-sibling::*[1]",
    ]

    for xp in xpaths:
        try:
            loc = page.locator(xp).first
            if loc.count():
                txt = loc.inner_text(timeout=2000).strip()
                if txt and txt.lower() != "address":
                    first = txt.split()[0]
                    if len(first) > 1 and first.isalpha():
                        return first
        except Exception:
            continue

    return ""


def _write_order_files(order_summary: OrderSummary):
    """
    Write order summary to .txt and .html files.

    Args:
        order_summary: OrderSummary object with all order details
    """
    order_no = order_summary.order_no

    # Write text summary
    txt_path = OUTPUT_DIR / f"{order_no}.txt"
    lines = [
        f"Order: {order_no}",
        f"URL: {order_summary.url}",
        f"Date: {order_summary.date_str}",
        f"Payment: {order_summary.payment_last4}",
        f"Name: {order_summary.name}",
        f"Subtotal: {order_summary.subtotal:.2f}",
        f"Discount: {order_summary.discount:.2f}",
        f"Delivery: {order_summary.delivery:.2f}",
        f"Taxes: {order_summary.taxes:.2f}",
        f"Total: {order_summary.total:.2f}",
        "Items:",
    ]

    for item in order_summary.items:
        lines.append(f"- {item.title} | Qty: {item.qty} | Price: {item.price_each:.2f}")

    txt_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[Save] Wrote {txt_path}")


def fetch_orders(order_numbers: List[str]):
    """
    Fetch Walmart order pages using Playwright and parse order details.

    This function:
    1. Launches a browser
    2. Navigates to each order page
    3. Handles robot/login gates by pausing for user input
    4. Parses order details using the corrected parsing module
    5. Saves order details to files

    Args:
        order_numbers: List of order numbers to fetch
    """
    with sync_playwright() as p:
        ctx = _launch_context(p)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        for idx, order_no in enumerate(order_numbers, start=1):
            url = WALMART_ORDER_URL_TEMPLATE.format(order_no=order_no)
            print(f"[Fetch] ({idx}/{len(order_numbers)}) {url}")

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=PAGE_NAVIGATION_TIMEOUT)
            except Exception as e:
                print(f"[Fetch] Navigation error for {order_no}: {e}")
                continue

            # Check for robot page
            if _check_robot_page(page):
                print("[Gate] Robot page detected — please solve in Chromium, then press Enter here to continue...")
                try:
                    input()
                except Exception:
                    pass

            # Check for login page
            if _check_login_page(page):
                print("[Gate] Login page detected — please sign in, then press Enter here to continue...")
                try:
                    input()
                except Exception:
                    pass

            # Wait for order content
            if not _wait_for_order_content(page, timeout_ms=PAGE_CONTENT_TIMEOUT):
                print("[Fetch] Waiting for content... if a login/gate is visible, complete it, then press Enter.")
                try:
                    input()
                except Exception:
                    pass

            time.sleep(0.7)

            # Extract data
            html = page.content()
            text = _visible_text(page)

            # Parse using the corrected parsing module
            order_summary = parse_order_page(html, order_no, url)

            # Try to get first name from DOM if not found in text
            if not order_summary.name:
                dom_name = _extract_first_name_dom(page)
                if dom_name:
                    # Create a new OrderSummary with the updated name
                    order_summary = OrderSummary(
                        order_no=order_summary.order_no,
                        url=order_summary.url,
                        date_str=order_summary.date_str,
                        payment_last4=order_summary.payment_last4,
                        name=dom_name,
                        subtotal=order_summary.subtotal,
                        discount=order_summary.discount,
                        delivery=order_summary.delivery,
                        taxes=order_summary.taxes,
                        total=order_summary.total,
                        items=order_summary.items
                    )

            # Parse items from DOM
            items = _parse_items_from_dom(page)

            # Update order summary with parsed items
            order_summary = OrderSummary(
                order_no=order_summary.order_no,
                url=order_summary.url,
                date_str=order_summary.date_str,
                payment_last4=order_summary.payment_last4,
                name=order_summary.name,
                subtotal=order_summary.subtotal,
                discount=order_summary.discount,
                delivery=order_summary.delivery,
                taxes=order_summary.taxes,
                total=order_summary.total,
                items=items
            )

            # Print summary line
            print(
                f"[Order] {order_no} | Date: {order_summary.date_str} | "
                f"Payment: {order_summary.payment_last4} | Name: {order_summary.name} | "
                f"Total: ${order_summary.total:.2f}"
            )
            print(f"[Items] Found {len(items)}")

            # Write files
            _write_order_files(order_summary)

            # Also save raw HTML
            html_path = OUTPUT_DIR / f"{order_no}.html"
            html_path.write_text(html, encoding="utf-8")

        try:
            ctx.close()
        except Exception:
            pass
