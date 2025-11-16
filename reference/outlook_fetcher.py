
from typing import List, Optional, Tuple, Set
import re
import datetime as _dt
from urllib.parse import unquote, parse_qs, urlparse
import html

def connect_outlook():
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
    parts: List[str] = [p for p in path.split('/') if p]
    if not parts:
        return None
    try:
        root = None
        for store in namespace.Folders:
            if store.Name.lower() == parts[0].lower():
                root = store
                break
        if root is None:
            try:
                default_store = namespace.Folders.Item(1)
                if default_store and default_store.Name.lower() == parts[0].lower():
                    root = default_store
            except Exception:
                pass
        if root is None:
            return None

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
    m = re.fullmatch(r"(\d{4})-(\d{1,2})", period.strip())
    if not m:
        return None
    year = int(m.group(1))
    month = int(m.group(2))
    if not 1 <= month <= 12:
        return None
    start = _dt.datetime(year, month, 1, 0, 0, 0)
    end = _dt.datetime(year + (month // 12), (month % 12) + 1, 1, 0, 0, 0)
    return start, end

def _to_outlook_dt(dt: _dt.datetime) -> str:
    return dt.strftime("%m/%d/%Y %I:%M %p")

def get_items_for_period(folder, period: str):
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

# ---------- Extraction helpers ----------
ORDER_RE = re.compile(r"/orders/(\d+)", re.IGNORECASE)

def _decode_candidates(s: str):
    variants = []
    if not s:
        return variants
    variants.append(s)
    try:
        h = html.unescape(s)
        if h != s:
            variants.append(h)
        u1 = unquote(h)
        if u1 not in variants: variants.append(u1)
        u2 = unquote(u1)
        if u2 not in variants: variants.append(u2)
        u3 = unquote(u2)
        if u3 not in variants: variants.append(u3)
    except Exception:
        pass
    return variants

def _extract_urls_from_safelinks(s: str):
    out = []
    if not s:
        return out
    try:
        for m in re.finditer(r"https?://\S+", s):
            url = m.group(0).rstrip("').,>\\\"]")
            parsed = urlparse(url)
            if "safelinks.protection.outlook.com" in (parsed.netloc or ""):
                qs = parse_qs(parsed.query or "")
                target = qs.get("url", [None])[0]
                if target:
                    t1 = unquote(target); t2 = unquote(t1); t3 = unquote(t2)
                    out.append(t3)
            else:
                out.append(url)
    except Exception:
        pass
    return out

def extract_order_numbers_from_items(items, subject_exact: Optional[str] = None):
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
                sub = (it.Subject or "").strip()
                if subject_exact and sub.lower() != subject_exact.strip().lower():
                    continue
                html_body = ""; text_body = ""
                try: html_body = it.HTMLBody or ""
                except Exception: pass
                try: text_body = it.Body or ""
                except Exception: pass

                cand_strings = _decode_candidates(html_body) + _decode_candidates(text_body)
                all_urls = []
                for s in cand_strings:
                    all_urls.extend(_extract_urls_from_safelinks(s))
                for u in all_urls:
                    cand_strings.extend(_decode_candidates(u))

                for s in cand_strings:
                    for m in ORDER_RE.finditer(s):
                        numbers.add(m.group(1))
            except Exception:
                continue
    except Exception as e:
        print(f"[Extract] Error iterating items: {e}")
    return list(numbers)
