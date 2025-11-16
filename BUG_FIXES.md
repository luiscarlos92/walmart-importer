# Bug Fixes - Order Value Parsing

This document details the bugs that were fixed in the new implementation compared to the reference code.

## Bug Summary

The reference implementation had critical bugs in parsing order values:
- **Total**: ✅ Working correctly
- **Subtotal**: ✅ Working correctly
- **Delivery**: ❌ **BUG** - Not defaulting to 0.00 when missing
- **Discounts**: ❌ **BUG** - Incorrect extraction logic and wrong sign

## Detailed Bug Analysis

### 1. Discount Parsing Bug

**Location**: `reference/walmart_fetcher.py:136-143`

**Reference Code (BUGGY)**:
```python
# Sum all negative amounts in the rail as discounts
discount_total = 0.0
for dm in re.finditer(r"-(?:\$)?([0-9]+(?:\.[0-9]{2})?)", text_norm):
    try:
        discount_total += float(dm.group(1))
    except Exception:
        pass
fields["discount"] = f"{discount_total:.2f}" if discount_total else "0"
```

**Problems**:
1. Searches for ALL negative numbers in the text, not just discount-related ones
2. Could pick up random negative values (refunds, credits, etc.)
3. Returns positive value (e.g., `0.76`) instead of negative (spec requires `-0.76`)
4. Doesn't use the `RE_DISCOUNT` regex that was already defined but never used

**New Code (FIXED)** in `importer/parsing.py:156-168`:
```python
# BUG FIX: Proper discount extraction
# Find ALL discount values (there can be multiple: Multisave Discount, Savings, etc.)
# They appear between Subtotal and Taxes in the HTML
# ALWAYS return as NEGATIVE value
discount = 0.0
discount_total = 0.0
for m in RE_DISCOUNT.finditer(text_norm):
    discount_value = money_to_float(m.group(1))
    discount_total += abs(discount_value)

# Return as negative (all discounts summed)
if discount_total > 0:
    discount = -discount_total
```

**Improvements**:
1. ✅ Uses proper `RE_DISCOUNT` regex pattern that looks for discount labels
2. ✅ Pattern: `\b(?:Savings|Multisave\s*Discount|[\w\s]*Discount)\b`
3. ✅ Only captures values near discount-related labels
4. ✅ Handles **MULTIPLE discounts** by using `finditer()` instead of `search()`
5. ✅ Sums all discounts together (e.g., Multisave Discount + Member Discount)
6. ✅ ALWAYS returns negative value using `-discount_total`

**Test Cases**:
```python
# Test 1: Single discount
# Input: "Subtotal $75.71 Multisave Discount $0.76 Taxes $5.00 Total $80.71"
# Expected: discount = -0.76
# Reference Result: 0.76 (WRONG - positive, and might include other negatives)
# New Result: -0.76 (CORRECT)

# Test 2: Multiple discounts
# Input: "Subtotal $100.00 Multisave Discount $2.50 Savings $1.25 Taxes $6.00 Total $102.25"
# Expected: discount = -3.75 (sum of -2.50 and -1.25)
# Reference Result: Would only find first or sum random negatives (WRONG)
# New Result: -3.75 (CORRECT - sums all discount types)
```

### 2. Delivery Fee Bug

**Location**: `reference/walmart_fetcher.py:144-146`

**Reference Code (BUGGY)**:
```python
m = RE_DELIVERY.search(text_norm)
if m:
    fields["delivery"] = m.group(1).strip()
# No else clause - delivery stays None if not found
```

**Problems**:
1. If no delivery fee is found, `fields["delivery"]` stays `None`
2. This causes issues when writing files or calculating totals
3. Spec requires: "If no Delivery/Shipping fee is visible, set **0.00**"
4. **CRITICAL**: The regex pattern `r"\b(?:Delivery(?:\s*fee)?|Shipping(?:\s*fee)?|Free Delivery From Store)\b.*?\$?\s*([0-9]+\.[0-9]{2})"` with `DOTALL` flag is too greedy
5. It matches "Delivered on" or "Delivery from store" and then captures ANY price later (including item prices)
6. Example: "Delivered on Oct 20, Delivery from store" ... [page content] ... "Item: Pasta $1.97" would incorrectly capture $1.97 as delivery fee

**New Code (FIXED)** in `importer/parsing.py:51-57` and `170-175`:
```python
# Regex pattern - much more restrictive
RE_DELIVERY = re.compile(
    r"\b(?:Delivery|Shipping)\s*(?:fee)?\s*[:\-]?\s*\$\s*([0-9]+\.[0-9]{2})\b",
    re.IGNORECASE
)

# Usage
delivery = 0.0
m = RE_DELIVERY.search(text_norm)
if m:
    delivery = money_to_float(m.group(1))
# else: delivery stays 0.0 (default)
```

**Improvements**:
1. ✅ Initializes `delivery = 0.0` as default
2. ✅ Only updates if delivery fee is found
3. ✅ **NEW**: Pattern requires dollar sign `$` immediately after "Delivery"/"Shipping" (with optional "fee", colons, dashes)
4. ✅ **NEW**: Removed `DOTALL` flag - prevents matching across entire page
5. ✅ **NEW**: Will NOT match "Delivered on..." or "Delivery from store" followed by item prices
6. ✅ Matches spec requirement exactly

**Test Cases**:
```python
# Test 1: No delivery fee
# Input: "Subtotal $75.71 Multisave Discount $0.76 Taxes $5.00 Total $80.71"
# Expected: delivery = 0.00
# Reference Result: None (WRONG)
# New Result: 0.00 (CORRECT)

# Test 2: Delivery fee present
# Input: "Subtotal $75.71 Delivery fee $5.00 Taxes $5.00 Total $85.71"
# Expected: delivery = 5.00
# New Result: 5.00 (CORRECT)

# Test 3: False positive (real-world bug from order 600000046848554)
# Input: "Delivered on Oct 20, Delivery from store, 12 items
#         Subtotal $44.83 Item: Pasta $1.97 ... Taxes $0.32 Total $43.79"
# Expected: delivery = 0.00 (no fee line exists)
# Reference Result: 1.97 (WRONG - captured first item price!)
# New Result: 0.00 (CORRECT - doesn't match false positive)
```

### 3. Total and Subtotal (Verified Working)

**Code** in `importer/parsing.py:132-139`:
```python
# Extract financial fields with BUG FIXES
subtotal = 0.0
m = RE_SUBTOTAL.search(text_norm)
if m:
    subtotal = money_to_float(m.group(1))

# ... similar for total ...
total = 0.0
m = RE_TOTAL.search(text_norm)
if m:
    total = money_to_float(m.group(1))
```

These were working correctly in the reference code and remain correct.

## Regex Patterns Used

### Discount Pattern (Fixed)
```python
RE_DISCOUNT = re.compile(
    r"\b(?:Savings|Multisave\s*Discount|[\w\s]*Discount)\b\s*[-]?\s*\$?\s*([0-9]+(?:\.[0-9]{2})?)",
    re.IGNORECASE
)
```

Matches:
- "Multisave Discount $0.76"
- "Savings $1.50"
- "Total Discount $2.00"
- "Discount -$0.76" (with or without minus sign)

### Delivery Pattern (Enhanced)
```python
RE_DELIVERY = re.compile(
    r"\b(?:Delivery(?:\s*fee)?|Shipping(?:\s*fee)?|Free Delivery From Store)\b.*?\$?\s*([0-9]+\.[0-9]{2})",
    re.IGNORECASE | re.DOTALL
)
```

Matches:
- "Delivery fee $5.00"
- "Delivery $5.00"
- "Shipping $3.50"
- "Shipping fee $3.50"
- "Free Delivery From Store $0.00"

## Unit Tests

The new implementation includes unit tests to verify these fixes:

```python
def _test_discount_parsing():
    """Test that discount is always negative."""
    # Test case 1: Discount shown as "$0.76"
    html1 = "<html><body>Subtotal $75.71 Multisave Discount $0.76 Taxes $5.00 Total $80.71</body></html>"
    result1 = parse_order_page(html1, "TEST001", "http://test.com")
    assert result1.discount == -0.76, f"Expected -0.76, got {result1.discount}"

    # ... more test cases ...

def _test_delivery_parsing():
    """Test that delivery defaults to 0.00 when missing."""
    # Test case 1: No delivery fee mentioned
    html1 = "<html><body>Subtotal $75.71 Multisave Discount $0.76 Taxes $5.00 Total $80.71</body></html>"
    result1 = parse_order_page(html1, "TEST001", "http://test.com")
    assert result1.delivery == 0.0, f"Expected 0.00, got {result1.delivery}"

    # ... more test cases ...
```

Run tests with:
```cmd
.venv\Scripts\activate
python -m importer.parsing
```

## Example Output Comparison

### Reference Implementation (BUGGY)
```
Order: 600000046846089
Subtotal: 75.71
Discount: 0.76          ← WRONG: Should be negative
Delivery:               ← WRONG: Should be 0.00, but it's None
Taxes: 5.32
Total: 80.27
```

### New Implementation (FIXED)
```
Order: 600000046846089
Subtotal: 75.71
Discount: -0.76         ← CORRECT: Negative value
Delivery: 0.00          ← CORRECT: Defaults to 0.00
Taxes: 5.32
Total: 80.27
```

## Summary of Changes

| Field | Reference | New | Status |
|-------|-----------|-----|--------|
| Total | Regex extraction | Regex extraction | ✅ No change needed |
| Subtotal | Regex extraction | Regex extraction | ✅ No change needed |
| Discount | Sum all negatives (wrong) | Use RE_DISCOUNT pattern | ✅ **FIXED** |
| Discount Sign | Positive | Negative (using -abs()) | ✅ **FIXED** |
| Delivery Missing | None | 0.00 | ✅ **FIXED** |

## Files Changed

1. **`importer/parsing.py`**: Complete rewrite with corrected logic
   - Lines 132-165: Financial field extraction with bug fixes
   - Lines 250-270: Unit tests for verification

2. **`importer/walmart_fetcher.py`**: Refactored to use parsing module
   - Delegates parsing to `parse_order_page()` function
   - Focuses on DOM extraction and file writing

## Verification

After installation, verify the fixes work:

1. Run unit tests:
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

2. Run a real import and check the output files in `out/` directory

3. Verify that:
   - Discount values are negative (e.g., `-0.76`)
   - Orders with no delivery show `Delivery: 0.00`
   - Total, Subtotal match the Walmart page exactly
