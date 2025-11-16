
from typing import List, Optional, Dict, Tuple
import re, os, time, io
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

ORDER_URL_TMPL = "https://www.walmart.ca/en/orders/{order_no}"

RE_DATE_DELIVERED = re.compile(r"Delivered on\s+([A-Za-z]{3,9}\s+\d{1,2})", re.IGNORECASE)
RE_DATE_HEADER = re.compile(r"\b([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})\b.*?\bOrder#\b", re.IGNORECASE | re.DOTALL)
RE_HEADER_SIMPLE = re.compile(r"\b([A-Z][a-z]{2})\s+(\d{1,2}),\s*(\d{4})\b")

RE_TOTAL = re.compile(r"\bTotal\b\s*\$?\s*([0-9]+\.[0-9]{2})", re.IGNORECASE)
RE_SUBTOTAL = re.compile(r"\bSubtotal\b\s*\$?\s*([0-9]+\.[0-9]{2})", re.IGNORECASE)
RE_DISCOUNT = re.compile(r"\b(?:Savings|[\w\s]*Discount)\b\s*([-]?)\s*\$?\s*([0-9]+\.[0-9]{2})", re.IGNORECASE)
RE_DELIVERY = re.compile(r"\b(?:Delivery(?:\s*fee)?|Free Delivery From Store)\b.*?\$?\s*([0-9]+\.[0-9]{2})", re.IGNORECASE | re.DOTALL)
RE_TAXES = re.compile(r"\bTaxes\b\s*\$?\s*([0-9]+\.[0-9]{2})", re.IGNORECASE)

PAYMENT_BRANDS = [
    r"Apple\s*Pay",
    r"Google\s*Pay",
    r"PayPal",
    r"Visa",
    r"Master\s*Card|Mastercard",
    r"American\s*Express|Amex",
    r"Discover",
    r"Debit(?:\s*Card)?",
    r"Credit\s*Card",
    r"Gift\s*Card|Walmart\s*Gift\s*Card",
]

RE_ENDING_IN = re.compile(r"Ending in\s*(\d{4})", re.IGNORECASE)
RE_ADDRESS_NAME_LINE = re.compile(
    r"Address\s+([A-Z][A-Za-zÀ-ÖØ-öø-ÿ' -]{1,}(?:\s+[A-Z][A-Za-zÀ-ÖØ-öø-ÿ' -]{1,})*)",
    re.IGNORECASE
)

RE_QTY = re.compile(r"\bQty\s*([0-9]+)\b", re.IGNORECASE)
RE_PRICE = re.compile(r"\$([0-9]+(?:\.[0-9]{2}))")

def _user_data_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, ".pw-user-data")

def _orders_dir() -> Path:
    here = Path(os.path.abspath(os.path.dirname(__file__)))
    out = here / "Orders"
    out.mkdir(parents=True, exist_ok=True)
    return out

def _launch_context(p):
    os.makedirs(_user_data_dir(), exist_ok=True)
    for ch in ["msedge", "chrome", "chromium"]:
        try:
            return p.chromium.launch_persistent_context(
                user_data_dir=_user_data_dir(),
                channel=(ch if ch != "chromium" else None),
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--disable-web-security",
                ]
            )
        except Exception:
            continue
    return p.chromium.launch(headless=False)

def _visible_text(page) -> str:
    try:
        return page.evaluate("document.body.innerText || ''")
    except Exception:
        return ""

def _extract_payment(text: str) -> Tuple[Optional[str], Optional[str]]:
    if not text:
        return None, None
    t = text
    idx = t.lower().find("payment method")
    window = t[idx: idx + 500] if idx != -1 else t
    brand = None
    for pat in PAYMENT_BRANDS:
        m = re.search(pat, window, flags=re.IGNORECASE)
        if m:
            brand = re.sub(r"\s+", " ", m.group(0)).strip()
            brand = brand.replace("Master Card", "Mastercard").replace("American Express", "Amex")
            break
    last4 = None
    m4 = RE_ENDING_IN.search(window) or RE_ENDING_IN.search(t)
    if m4:
        last4 = m4.group(1)
    return brand, last4

def _extract_first_name_dom(page) -> Optional[str]:
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
    return None

def _extract_fields_from_text(text: str) -> Dict[str, Optional[str]]:
    fields = {
        "date": None, "date_header": None, "total": None, "method": None, "last4": None, "first_name": None,
        "subtotal": None, "discount": None, "delivery": None, "taxes": None,
    }
    if not text:
        return fields

    text_norm = re.sub(r"[ \t]+", " ", text)

    m = RE_DATE_DELIVERED.search(text_norm)
    if m:
        fields["date"] = m.group(1).strip()
    m2 = RE_DATE_HEADER.search(text_norm)
    if m2:
        fields["date_header"] = m2.group(1).strip()

    m = RE_TOTAL.search(text_norm)
    if m:
        fields["total"] = m.group(1).strip()
    m = RE_SUBTOTAL.search(text_norm)
    if m:
        fields["subtotal"] = m.group(1).strip()
    # Sum all negative amounts in the rail as discounts
    discount_total = 0.0
    for dm in re.finditer(r"-(?:\$)?([0-9]+(?:\.[0-9]{2})?)", text_norm):
        try:
            discount_total += float(dm.group(1))
        except Exception:
            pass
    fields["discount"] = f"{discount_total:.2f}" if discount_total else "0"
    m = RE_DELIVERY.search(text_norm)
    if m:
        fields["delivery"] = m.group(1).strip()
    m = RE_TAXES.search(text_norm)
    if m:
        fields["taxes"] = m.group(1).strip()

    brand, last4 = _extract_payment(text_norm)
    fields["method"] = brand
    fields["last4"] = last4

    m = RE_ADDRESS_NAME_LINE.search(text_norm)
    if m:
        candidate = m.group(1).strip()
        name_tokens = [t for t in candidate.split() if re.match(r"^[A-Za-zÀ-ÖØ-öø-ÿ'-]+$", t)]
        if name_tokens:
            fields["first_name"] = name_tokens[0]
    return fields

def _ensure_year_for_file(fields: Dict[str, Optional[str]], text: str) -> str:
    if fields.get("date_header"):
        return fields["date_header"]
    date_simple = fields.get("date") or ""
    if date_simple and "," not in date_simple:
        m = RE_HEADER_SIMPLE.search(text)
        if m:
            parts = date_simple.split()
            if len(parts) >= 2:
                return f"{parts[0]} {parts[1]}, {m.group(3)}"
        return date_simple
    return date_simple

def _wait_for_order_content(page, timeout_ms=25000) -> bool:
    try:
        page.wait_for_selector("text=Payment method", timeout=timeout_ms)
        return True
    except PwTimeout:
        return False

def _expand_items_if_needed(page):
    try:
        toggle = page.locator("button[data-automation-id='items-toggle-link']").first
        if toggle.count():
            expanded = toggle.get_attribute("aria-expanded") or ""
            if expanded.lower() != "true":
                toggle.click()
                time.sleep(0.4)
        # wait for at least one item tile to appear
        page.wait_for_selector("div[data-testid='itemtile-stack']", timeout=4000)
    except Exception:
        pass

def _parse_items_from_dom(page):
    items = []
    _expand_items_if_needed(page)
    tiles = page.locator("div[data-testid='itemtile-stack']")
    count = tiles.count()
    for i in range(count):
        tile = tiles.nth(i)
        try:
            name = tile.locator("[data-testid='productName']").first.inner_text(timeout=1000).strip()
        except Exception:
            name = ""
        try:
            qty_txt = tile.locator(".bill-item-quantity").first.inner_text(timeout=800).strip()
        except Exception:
            # fallback: any node containing "Qty"
            try:
                qty_txt = tile.locator("xpath=.//*[contains(translate(text(),'QTY','qty'),'qty')]").first.inner_text(timeout=800).strip()
            except Exception:
                qty_txt = ""
        mqty = RE_QTY.search(qty_txt)
        qty = mqty.group(1) if mqty else "1"
        # price
        price = ""
        try:
            price_txt = tile.locator("[data-testid='line-price']").first.inner_text(timeout=800).strip()
            m = RE_PRICE.search(price_txt)
            if m: price = m.group(1)
        except Exception:
            # last resort: any $ in tile text
            try:
                anytxt = tile.inner_text(timeout=800)
                m = RE_PRICE.search(anytxt)
                if m: price = m.group(1)
            except Exception:
                price = ""
        if name and price:
            items.append({"name": name, "qty": qty, "price": price})
    return items

def _write_order_file(order_no: str, url: str, fields: Dict[str, Optional[str]], full_text: str, items):
    outdir = _orders_dir()
    path = outdir / f"{order_no}.txt"
    pay_display = "N/A"
    if fields.get("method") and fields.get("last4"):
        pay_display = f"{fields['method']} ****{fields['last4']}"
    elif fields.get("method"):
        pay_display = fields["method"]
    elif fields.get("last4"):
        pay_display = f"****{fields['last4']}"

    date_for_file = _ensure_year_for_file(fields, full_text)
    discount_val = fields.get("discount") if fields.get("discount") not in (None, "") else "0"

    def fmt(val):
        return "" if val is None else str(val)

    content = io.StringIO()
    content.write(f"Order: {order_no}\n")
    content.write(f"URL: {url}\n")
    content.write(f"Date: {fmt(date_for_file)}\n")
    content.write(f"Payment: {pay_display}\n")
    content.write(f"Name: {fmt(fields.get('first_name'))}\n")
    content.write(f"Subtotal: {fmt(fields.get('subtotal'))}\n")
    content.write(f"Discount: {discount_val}\n")
    content.write(f"Delivery: {fmt(fields.get('delivery'))}\n")
    content.write(f"Taxes: {fmt(fields.get('taxes'))}\n")
    content.write(f"Total: {fmt(fields.get('total'))}\n")
    content.write("Items:\n")
    for it in items:
        content.write(f"- {it['name']} | Qty: {it['qty']} | Price: {it['price']}\n")

    path.write_text(content.getvalue(), encoding="utf-8")
    print(f"[Save] Wrote {path}")

def fetch_orders(order_numbers: List[str]):
    with sync_playwright() as p:
        ctx = _launch_context(p)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        for idx, order_no in enumerate(order_numbers, start=1):
            url = ORDER_URL_TMPL.format(order_no=order_no)
            print(f"[Fetch] ({idx}/{len(order_numbers)}) {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=120000)
            except Exception as e:
                print(f"[Fetch] Navigation error for {order_no}: {e}")
                continue

            if not _wait_for_order_content(page, timeout_ms=25000):
                print("[Fetch] Waiting for content... if a login/gate is visible, complete it, then press Enter.")
                try: input()
                except Exception: pass

            time.sleep(0.7)
            first_name_dom = _extract_first_name_dom(page)
            text = _visible_text(page)
            fields = _extract_fields_from_text(text)
            if not fields.get("first_name") and first_name_dom:
                fields["first_name"] = first_name_dom

            items = _parse_items_from_dom(page)

            pay_display = "N/A"
            if fields.get("method") and fields.get("last4"):
                pay_display = f"{fields['method']} ****{fields['last4']}"
            elif fields.get("method"):
                pay_display = fields["method"]
            elif fields.get("last4"):
                pay_display = f"****{fields['last4']}"
            print(f"[Order] {order_no} | Date: {fields['date']} | Payment: {pay_display} | Name: {fields['first_name']} | Total: ${fields['total']}")
            print(f"[Items] Found {len(items)}")

            _write_order_file(order_no, url, fields, text, items)

        try:
            ctx.close()
        except Exception:
            pass
