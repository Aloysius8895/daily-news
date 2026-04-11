from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any

from app.utils import normalize_title, parse_datetime, to_display_time, to_iso_date


def _import_feedparser():
    try:
        import feedparser
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency 'feedparser'. Install requirements.txt first."
        ) from exc

    return feedparser


def _entry_date(entry: Any, fallback: date) -> str | None:
    candidates = [
        getattr(entry, "published", None),
        getattr(entry, "updated", None),
        entry.get("published"),
        entry.get("updated"),
    ]

    for candidate in candidates:
        parsed = to_iso_date(candidate)
        if parsed:
            return parsed

    return fallback.isoformat()


def _clean_summary(entry: Any) -> str:
    summary = entry.get("summary") or entry.get("description") or ""
    return " ".join(str(summary).split())


def fetch_news(feeds: Iterable[dict], target_date: date, max_items_per_source: int) -> list[dict]:
    feedparser = _import_feedparser()

    items: list[dict] = []
    target_iso = target_date.isoformat()

    for feed in feeds:
        parsed = feedparser.parse(feed["url"])
        source_items = 0

        for entry in parsed.entries:
            raw_published = (
                getattr(entry, "published", None)
                or getattr(entry, "updated", None)
                or entry.get("published")
                or entry.get("updated")
            )
            published_dt = parse_datetime(raw_published)
            published_iso = _entry_date(entry, target_date)
            if published_iso != target_iso:
                continue

            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or "").strip()
            if not title or not link:
                continue

            items.append(
                {
                    "title": title,
                    "summary": _clean_summary(entry),
                    "source": feed["name"],
                    "feed_category": feed.get("category", "其他"),
                    "published_at": published_iso,
                    "published_datetime": published_dt.isoformat() if published_dt else "",
                    "time": to_display_time(published_dt),
                    "url": link,
                    "normalized_title": normalize_title(title),
                }
            )
            source_items += 1

            if source_items >= max_items_per_source:
                break

    return items
