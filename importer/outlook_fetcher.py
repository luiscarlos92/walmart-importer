"""
Outlook email fetcher for extracting Walmart order numbers.
"""

from typing import List, Optional, Set
import re
import datetime as dt
from urllib.parse import unquote, parse_qs, urlparse
import html


# Order number extraction regex
ORDER_RE = re.compile(r"/orders/(\d+)", re.IGNORECASE)


def connect_outlook():
    """
    Connect to Outlook desktop application via MAPI.

    Returns:
        Outlook namespace object or None on failure
    """
    try:
        import win32com.client
        outlook = win32com.client.gencache.EnsureDispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        namespace.Logon("", "", False, False)
        return namespace
    except Exception as e:
        print(f"[Outlook] Error connecting to Outlook: {e}")
        return None


def get_folder_by_path(namespace, path: str):
    """
    Navigate to an Outlook folder by path.

    Args:
        namespace: Outlook MAPI namespace
        path: Folder path like "Inbox/Shopping/Supermarkets/Walmart"

    Returns:
        Folder object or None if not found
    """
    parts: List[str] = [p for p in path.split('/') if p]
    if not parts:
        return None

    try:
        # Find root folder (usually the email account)
        root = None
        for store in namespace.Folders:
            if store.Name.lower() == parts[0].lower():
                root = store
                break

        if root is None:
            # Try default store
            try:
                default_store = namespace.Folders.Item(1)
                if default_store and default_store.Name.lower() == parts[0].lower():
                    root = default_store
            except Exception:
                pass

        if root is None:
            return None

        # Navigate down the folder hierarchy
        current = root
        for name in parts[1:]:
            found = None
            for f in current.Folders:
                if f.Name.lower() == name.lower():
                    found = f
                    break
            if found is None:
                return None
            current = found

        return current
    except Exception as e:
        print(f"[Outlook] Error while traversing folders: {e}")
        return None


def _parse_period(period: str):
    """
    Parse a period string like "2025-10" into start and end dates.

    Returns:
        Tuple of (start_datetime, end_datetime) or None if invalid
    """
    m = re.fullmatch(r"(\d{4})-(\d{1,2})", period.strip())
    if not m:
        return None

    year = int(m.group(1))
    month = int(m.group(2))

    if not 1 <= month <= 12:
        return None

    start = dt.datetime(year, month, 1, 0, 0, 0)

    # Calculate first day of next month
    if month == 12:
        end = dt.datetime(year + 1, 1, 1, 0, 0, 0)
    else:
        end = dt.datetime(year, month + 1, 1, 0, 0, 0)

    return start, end


def _to_outlook_dt(dt_obj: dt.datetime) -> str:
    """Convert datetime to Outlook filter format."""
    return dt_obj.strftime("%m/%d/%Y %I:%M %p")


def get_items_for_period(folder, period: str):
    """
    Filter folder items by received time period.

    Args:
        folder: Outlook folder object
        period: Period string like "2025-10"

    Returns:
        Filtered items collection or None if invalid period
    """
    parsed = _parse_period(period)
    if not parsed:
        return None

    start, end = parsed

    try:
        items = folder.Items
        items.Sort("[ReceivedTime]", True)
        filter_str = f"[ReceivedTime] >= '{_to_outlook_dt(start)}' AND [ReceivedTime] < '{_to_outlook_dt(end)}'"
        return items.Restrict(filter_str)
    except Exception as e:
        print(f"[Filter] Error restricting items: {e}")
        return None


def _decode_candidates(s: str) -> List[str]:
    """
    Generate decoded variants of a string (HTML unescape, URL decode, etc.).
    """
    variants = []
    if not s:
        return variants

    variants.append(s)

    try:
        # HTML unescape
        h = html.unescape(s)
        if h != s:
            variants.append(h)

        # URL decode (multiple passes to handle double encoding)
        u1 = unquote(h)
        if u1 not in variants:
            variants.append(u1)

        u2 = unquote(u1)
        if u2 not in variants:
            variants.append(u2)

        u3 = unquote(u2)
        if u3 not in variants:
            variants.append(u3)
    except Exception:
        pass

    return variants


def _extract_urls_from_safelinks(s: str) -> List[str]:
    """
    Extract URLs from text, unwrapping Outlook SafeLinks.
    """
    out = []
    if not s:
        return out

    try:
        for m in re.finditer(r"https?://\S+", s):
            url = m.group(0).rstrip("').,>\\\"]")
            parsed = urlparse(url)

            # Unwrap Outlook SafeLinks
            if "safelinks.protection.outlook.com" in (parsed.netloc or ""):
                qs = parse_qs(parsed.query or "")
                target = qs.get("url", [None])[0]
                if target:
                    # Decode multiple times
                    t1 = unquote(target)
                    t2 = unquote(t1)
                    t3 = unquote(t2)
                    out.append(t3)
            else:
                out.append(url)
    except Exception:
        pass

    return out


def extract_order_numbers_from_items(items, subject_exact: Optional[str] = None) -> List[str]:
    """
    Extract unique order numbers from email items.

    Args:
        items: Outlook items collection
        subject_exact: If provided, only process emails with this exact subject

    Returns:
        Sorted list of unique order numbers
    """
    numbers: Set[str] = set()

    if items is None:
        return []

    try:
        for i in range(1, items.Count + 1):
            try:
                it = items.Item(i)
            except Exception:
                continue

            try:
                # Check subject filter
                sub = (it.Subject or "").strip()
                if subject_exact and sub.lower() != subject_exact.strip().lower():
                    continue

                # Get email bodies
                html_body = ""
                text_body = ""
                try:
                    html_body = it.HTMLBody or ""
                except Exception:
                    pass
                try:
                    text_body = it.Body or ""
                except Exception:
                    pass

                # Generate decoded variants
                cand_strings = _decode_candidates(html_body) + _decode_candidates(text_body)

                # Extract URLs
                all_urls = []
                for s in cand_strings:
                    all_urls.extend(_extract_urls_from_safelinks(s))

                # Decode URLs
                for u in all_urls:
                    cand_strings.extend(_decode_candidates(u))

                # Extract order numbers
                for s in cand_strings:
                    for m in ORDER_RE.finditer(s):
                        numbers.add(m.group(1))
            except Exception:
                continue
    except Exception as e:
        print(f"[Extract] Error iterating items: {e}")

    return sorted(list(numbers))
