from __future__ import annotations

from difflib import SequenceMatcher
from typing import Iterable

from app.utils import normalize_title


CATEGORY_KEYWORDS = {
    "科技": ["ai", "artificial intelligence", "chip", "semiconductor", "tech", "software"],
    "金融": ["bank", "bond", "interest rate", "inflation", "fed", "ecb", "market", "stock"],
    "政策": ["tariff", "policy", "regulation", "election", "sanction", "government"],
    "商业": ["earnings", "deal", "acquisition", "merger", "company", "business"],
}


def similar_titles(left: str, right: str, threshold: float) -> bool:
    if left == right:
        return True

    if left in right or right in left:
        return True

    return SequenceMatcher(a=left, b=right).ratio() >= threshold


def deduplicate_items(items: Iterable[dict], threshold: float) -> list[dict]:
    deduped: list[dict] = []

    for item in items:
        normalized = item.get("normalized_title") or normalize_title(item.get("title", ""))
        matched = None

        for existing in deduped:
            existing_normalized = existing.get("normalized_title") or normalize_title(existing.get("title", ""))
            if similar_titles(normalized, existing_normalized, threshold):
                matched = existing
                break

        if matched:
            if len(item.get("summary", "")) > len(matched.get("summary", "")):
                matched["summary"] = item.get("summary", "")
            matched.setdefault("raw_sources", [])
            if item.get("source") and item["source"] not in matched["raw_sources"]:
                matched["raw_sources"].append(item["source"])
            continue

        cloned = dict(item)
        cloned["raw_sources"] = [item["source"]] if item.get("source") else []
        deduped.append(cloned)

    return deduped


def infer_category(item: dict) -> str:
    if item.get("category"):
        return item["category"]

    feed_category = item.get("feed_category")
    if feed_category:
        return feed_category

    haystack = " ".join(
        [
            item.get("title", "").lower(),
            item.get("summary", "").lower(),
        ]
    )

    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            return category

    return "其他"


def standardize_final_items(items: Iterable[dict], target_date: str, max_final_items: int) -> list[dict]:
    standardized: list[dict] = []

    for item in items:
        standardized.append(
            {
                "category": infer_category(item),
                "title": item.get("title", "").strip(),
                "summary": item.get("summary", "").strip(),
                "importance": item.get("importance", "").strip(),
                "source": item.get("source", "").strip(),
                "date": item.get("date") or item.get("published_at") or target_date,
                "url": item.get("url", "").strip(),
                "raw_sources": item.get("raw_sources", []),
            }
        )

    return standardized[:max_final_items]


def build_local_fallback(items: list[dict], target_date: str, max_final_items: int, threshold: float) -> dict:
    deduped = deduplicate_items(items, threshold)
    final_items = standardize_final_items(deduped, target_date, max_final_items)

    return {
        "date": target_date,
        "overview": f"{target_date} 共整理 {len(final_items)} 条重要新闻，当前为未经过模型重写的本地兜底结果。",
        "news": final_items,
    }
