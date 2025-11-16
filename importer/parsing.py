"""
Data models and parsing logic for Walmart orders.
"""

from dataclasses import dataclass
from typing import Optional
import re
from bs4 import BeautifulSoup
from .utils import money_to_float


@dataclass
class OrderItem:
    """Represents a single item in an order."""
    title: str
    qty: int
    price_each: float


@dataclass
class OrderSummary:
    """Represents a complete order summary."""
    order_no: str
    url: str
    date_str: str          # as displayed (e.g., "Oct 19, 2025")
    payment_last4: str     # "****1529"
    name: str
    subtotal: float
    discount: float        # negative number; e.g., -0.76
    delivery: float        # 0.00 if not present in page
    taxes: float
    total: float
    items: list[OrderItem]


# Regex patterns for extracting order information
RE_DATE_DELIVERED = re.compile(r"Delivered on\s+([A-Za-z]{3,9}\s+\d{1,2})", re.IGNORECASE)
RE_DATE_HEADER = re.compile(r"\b([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})\b.*?\bOrder#\b", re.IGNORECASE | re.DOTALL)
RE_HEADER_SIMPLE = re.compile(r"\b([A-Z][a-z]{2})\s+(\d{1,2}),\s*(\d{4})\b")

# Financial fields - CRITICAL for bug fix
RE_TOTAL = re.compile(r"\bTotal\b\s*\$?\s*([0-9]+\.[0-9]{2})", re.IGNORECASE)
RE_SUBTOTAL = re.compile(r"\bSubtotal\b\s*\$?\s*([0-9]+\.[0-9]{2})", re.IGNORECASE)

# BUG FIX: Proper discount pattern that looks for discount/savings labels
RE_DISCOUNT = re.compile(
    r"\b(?:Savings|Multisave\s*Discount|[\w\s]*Discount)\b\s*[-]?\s*\$?\s*([0-9]+(?:\.[0-9]{2})?)",
    re.IGNORECASE
)

# BUG FIX: Delivery pattern accepts both "Delivery" and "Shipping" labels
RE_DELIVERY = re.compile(
    r"\b(?:Delivery(?:\s*fee)?|Shipping(?:\s*fee)?|Free Delivery From Store)\b.*?\$?\s*([0-9]+\.[0-9]{2})",
    re.IGNORECASE | re.DOTALL
)

RE_TAXES = re.compile(r"\bTaxes\b\s*\$?\s*([0-9]+\.[0-9]{2})", re.IGNORECASE)

# Payment patterns
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


def parse_order_page(html: str, order_no: str, url: str) -> OrderSummary:
    """
    Parse a Walmart order page HTML and extract order details.

    CRITICAL BUG FIXES:
    - Discount: Always returned as negative value (e.g., -0.76)
    - Delivery: Returns 0.00 if not found in page/HTML

    Args:
        html: The HTML content of the order page
        order_no: The order number
        url: The order page URL

    Returns:
        OrderSummary with all extracted fields
    """
    soup = BeautifulSoup(html, 'html.parser')

    # Extract visible text for regex parsing
    text = soup.get_text(separator=' ', strip=True)
    text_norm = re.sub(r"[ \t]+", " ", text)

    # Extract date
    date_str = ""
    m = RE_DATE_DELIVERED.search(text_norm)
    if m:
        date_str = m.group(1).strip()
    else:
        m2 = RE_DATE_HEADER.search(text_norm)
        if m2:
            date_str = m2.group(1).strip()

    # Ensure year in date
    if date_str and "," not in date_str:
        m = RE_HEADER_SIMPLE.search(text_norm)
        if m:
            parts = date_str.split()
            if len(parts) >= 2:
                date_str = f"{parts[0]} {parts[1]}, {m.group(3)}"

    # Extract payment info
    payment_brand = None
    payment_last4 = None

    idx = text_norm.lower().find("payment method")
    window = text_norm[idx: idx + 500] if idx != -1 else text_norm

    for pat in PAYMENT_BRANDS:
        m = re.search(pat, window, flags=re.IGNORECASE)
        if m:
            payment_brand = re.sub(r"\s+", " ", m.group(0)).strip()
            payment_brand = payment_brand.replace("Master Card", "Mastercard").replace("American Express", "Amex")
            break

    m4 = RE_ENDING_IN.search(window) or RE_ENDING_IN.search(text_norm)
    if m4:
        payment_last4 = m4.group(1)

    # Extract customer name
    name = ""
    m = RE_ADDRESS_NAME_LINE.search(text_norm)
    if m:
        candidate = m.group(1).strip()
        name_tokens = [t for t in candidate.split() if re.match(r"^[A-Za-zÀ-ÖØ-öø-ÿ'-]+$", t)]
        if name_tokens:
            name = name_tokens[0]

    # Extract financial fields with BUG FIXES
    subtotal = 0.0
    m = RE_SUBTOTAL.search(text_norm)
    if m:
        subtotal = money_to_float(m.group(1))

    # BUG FIX: Proper discount extraction
    # Use the RE_DISCOUNT pattern to find discount values
    # ALWAYS return as NEGATIVE value
    discount = 0.0
    m = RE_DISCOUNT.search(text_norm)
    if m:
        discount_value = money_to_float(m.group(1))
        # Ensure it's negative
        discount = -abs(discount_value)

    # BUG FIX: Delivery defaults to 0.00 if not found
    delivery = 0.0
    m = RE_DELIVERY.search(text_norm)
    if m:
        delivery = money_to_float(m.group(1))
    # else: delivery stays 0.0 (default)

    taxes = 0.0
    m = RE_TAXES.search(text_norm)
    if m:
        taxes = money_to_float(m.group(1))

    total = 0.0
    m = RE_TOTAL.search(text_norm)
    if m:
        total = money_to_float(m.group(1))

    # Format payment display
    if payment_brand and payment_last4:
        payment_display = f"****{payment_last4}"
    elif payment_last4:
        payment_display = f"****{payment_last4}"
    else:
        payment_display = "N/A"

    # Parse items (placeholder - will be filled by DOM parsing in fetcher)
    items = []

    return OrderSummary(
        order_no=order_no,
        url=url,
        date_str=date_str,
        payment_last4=payment_display,
        name=name,
        subtotal=subtotal,
        discount=discount,
        delivery=delivery,
        taxes=taxes,
        total=total,
        items=items
    )


# Unit tests for critical bug fixes
def _test_discount_parsing():
    """Test that discount is always negative."""
    # Test case 1: Discount shown as "$0.76"
    html1 = "<html><body>Subtotal $75.71 Multisave Discount $0.76 Taxes $5.00 Total $80.71</body></html>"
    result1 = parse_order_page(html1, "TEST001", "http://test.com")
    assert result1.discount == -0.76, f"Expected -0.76, got {result1.discount}"

    # Test case 2: Discount with minus sign
    html2 = "<html><body>Subtotal $75.71 Savings -$0.76 Taxes $5.00 Total $80.71</body></html>"
    result2 = parse_order_page(html2, "TEST002", "http://test.com")
    assert result2.discount == -0.76, f"Expected -0.76, got {result2.discount}"

    # Test case 3: No discount
    html3 = "<html><body>Subtotal $75.71 Taxes $5.00 Total $80.71</body></html>"
    result3 = parse_order_page(html3, "TEST003", "http://test.com")
    assert result3.discount == 0.0, f"Expected 0.0, got {result3.discount}"

    print("[Test] Discount parsing tests passed!")


def _test_delivery_parsing():
    """Test that delivery defaults to 0.00 when missing."""
    # Test case 1: No delivery fee mentioned
    html1 = "<html><body>Subtotal $75.71 Multisave Discount $0.76 Taxes $5.00 Total $80.71</body></html>"
    result1 = parse_order_page(html1, "TEST001", "http://test.com")
    assert result1.delivery == 0.0, f"Expected 0.00, got {result1.delivery}"

    # Test case 2: Delivery fee present
    html2 = "<html><body>Subtotal $75.71 Delivery fee $5.00 Taxes $5.00 Total $85.71</body></html>"
    result2 = parse_order_page(html2, "TEST002", "http://test.com")
    assert result2.delivery == 5.0, f"Expected 5.00, got {result2.delivery}"

    # Test case 3: Shipping (alternate label)
    html3 = "<html><body>Subtotal $75.71 Shipping $3.50 Taxes $5.00 Total $84.21</body></html>"
    result3 = parse_order_page(html3, "TEST003", "http://test.com")
    assert result3.delivery == 3.5, f"Expected 3.50, got {result3.delivery}"

    print("[Test] Delivery parsing tests passed!")


if __name__ == "__main__":
    # Run unit tests
    _test_discount_parsing()
    _test_delivery_parsing()
    print("[Test] All parsing tests passed!")
