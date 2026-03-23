from __future__ import annotations

import re
from datetime import UTC, datetime

_DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S+00:00",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
)

_DATE_PATTERNS = [
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}",
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}",
    r"\d{4}-\d{2}-\d{2}",
    r"Q[1-4]\s+\d{4}",
]


def parse_date(val: str | datetime) -> datetime:
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=UTC)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(val, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {val}")


def extract_dates_from_text(text: str) -> list[str]:
    dates: list[str] = []
    for pattern in _DATE_PATTERNS:
        dates.extend(re.findall(pattern, text, re.IGNORECASE))
    return dates
