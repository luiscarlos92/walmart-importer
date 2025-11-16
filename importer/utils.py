"""
Utility functions for parsing and file operations.
"""

import re
from typing import Optional
from pathlib import Path


def money_to_float(value: str) -> float:
    """
    Convert a money string to float.

    Examples:
        >>> money_to_float("$12.34")
        12.34
        >>> money_to_float("1,234.56")
        1234.56
        >>> money_to_float("(12.34)")
        -12.34
    """
    if not value:
        return 0.0

    # Remove currency symbols, spaces, and commas
    cleaned = value.strip()
    cleaned = re.sub(r'[$\s,\xa0]', '', cleaned)

    # Handle parentheses as negative
    is_negative = False
    if cleaned.startswith('(') and cleaned.endswith(')'):
        is_negative = True
        cleaned = cleaned[1:-1]

    # Handle explicit negative sign
    if cleaned.startswith('-'):
        is_negative = True
        cleaned = cleaned[1:]

    try:
        result = float(cleaned)
        return -result if is_negative else result
    except ValueError:
        return 0.0


def find_text_near_label(text: str, label_variants: list[str], max_distance: int = 100) -> Optional[str]:
    """
    Find text content near a label in a larger text block.

    Args:
        text: The text to search in
        label_variants: List of possible label texts to search for
        max_distance: Maximum character distance to search after the label

    Returns:
        The found text or None
    """
    if not text:
        return None

    for label in label_variants:
        pattern = re.escape(label) + r'\s*[:\-]?\s*(.{1,' + str(max_distance) + r'}?)\s*(?:\n|$)'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return None


def ensure_output_dir(path: Path) -> None:
    """Ensure the output directory exists."""
    path.mkdir(parents=True, exist_ok=True)


def sanitize_filename(filename: str) -> str:
    """Remove or replace characters that are invalid in filenames."""
    # Replace invalid characters with underscore
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, '_', filename)
    return sanitized
