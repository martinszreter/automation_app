"""CHF formatting the Swiss way: CHF 1'390, CHF 49, CHF 1.50."""

from __future__ import annotations


def chf(cents: int) -> str:
    francs, rappen = divmod(int(cents), 100)
    grouped = f"{francs:,}".replace(",", "'")
    if rappen:
        return f"CHF {grouped}.{rappen:02d}"
    return f"CHF {grouped}"


def chf_plain(amount: int | None) -> str:
    """Whole francs typed by the buyer (budget), grouped the same way."""
    if amount is None:
        return ""
    return chf(int(amount) * 100)
