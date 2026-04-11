from __future__ import annotations

from difflib import SequenceMatcher
from typing import Iterable

from app.utils import normalize_title, to_display_time


CATEGORY_KEYWORDS = {
    "科技": [
        "ai",
        "artificial intelligence",
        "openai",
        "chatgpt",
        "llm",
        "model",
        "chip",
        "gpu",
        "nvidia",
        "amd",
        "intel",
        "semiconductor",
        "server",
        "cloud",
        "tech",
        "software",
        "hardware",
        "robot",
        "robotics",
        "data center",
        "cybersecurity",
        "quantum",
        "developer",
        "programming",
        "computer",
    ],
    "金融": ["bank", "bond", "interest rate", "inflation", "fed", "ecb", "market", "stock"],
    "政策": ["tariff", "policy", "regulation", "election", "sanction", "government"],
    "商业": ["earnings", "deal", "acquisition", "merger", "company", "business"],
}

TECH_PRIORITY_TERMS = set(CATEGORY_KEYWORDS["科技"]) | {
    "microsoft",
    "google",
    "meta",
    "amazon",
    "apple",
    "tesla",
    "anthropic",
    "deepmind",
    "startup",
    "enterprise software",
    "operating system",
    "database",
    "api",
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

    haystack = " ".join(
        [
            item.get("title", "").lower(),
            item.get("summary", "").lower(),
        ]
    )

    keyword_scores: dict[str, int] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        matches = sum(1 for keyword in keywords if keyword in haystack)
        if matches:
            keyword_scores[category] = matches

    if keyword_scores:
        return max(keyword_scores.items(), key=lambda pair: pair[1])[0]

    feed_category = item.get("feed_category")
    if feed_category:
        return feed_category

    return "其他"


def is_tech_priority(item: dict) -> bool:
    category = infer_category(item)
    if category == "科技":
        return True

    haystack = " ".join(
        [
            item.get("title", "").lower(),
            item.get("summary", "").lower(),
            item.get("feed_category", "").lower(),
        ]
    )
    return any(keyword in haystack for keyword in TECH_PRIORITY_TERMS)


def item_priority_score(item: dict) -> int:
    haystack = " ".join(
        [
            item.get("title", "").lower(),
            item.get("summary", "").lower(),
            item.get("feed_category", "").lower(),
        ]
    )

    score = 0
    category = infer_category(item)
    if category == "科技":
        score += 30
    elif category == "商业":
        score += 10
    elif category == "国际":
        score += 8
    elif category == "金融":
        score += 6

    for keyword in TECH_PRIORITY_TERMS:
        if keyword in haystack:
            score += 6

    if any(keyword in haystack for keyword in ["ai", "artificial intelligence", "chatgpt", "openai", "llm"]):
        score += 20

    if item.get("source"):
        score += 2

    if item.get("summary"):
        score += min(len(item["summary"]) // 60, 6)

    return score


def standardize_final_items(
    items: Iterable[dict],
    target_date: str,
    max_final_items: int,
    tech_focus_ratio: float = 0.67,
) -> list[dict]:
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
                "time": item.get("time") or to_display_time(item.get("published_datetime")),
                "url": item.get("url", "").strip(),
                "raw_sources": item.get("raw_sources", []),
                "priority_score": item_priority_score(item),
                "tech_priority": is_tech_priority(item),
            }
        )

    tech_items = [item for item in standardized if item["tech_priority"]]
    other_items = [item for item in standardized if not item["tech_priority"]]

    tech_items.sort(key=lambda item: (-item["priority_score"], item.get("time") or "99:99", item.get("title", "")))
    other_items.sort(key=lambda item: (-item["priority_score"], item.get("time") or "99:99", item.get("title", "")))

    desired_tech_count = min(len(tech_items), max(1, round(max_final_items * tech_focus_ratio)))
    selected = tech_items[:desired_tech_count]

    remaining_slots = max_final_items - len(selected)
    if remaining_slots > 0:
        spillover = tech_items[desired_tech_count:] + other_items
        spillover.sort(key=lambda item: (-item["priority_score"], item.get("time") or "99:99", item.get("title", "")))
        selected.extend(spillover[:remaining_slots])

    selected.sort(key=lambda item: (item.get("time") or "99:99", -item["priority_score"], item.get("title", "")))
    for item in selected:
        item.pop("priority_score", None)
        item.pop("tech_priority", None)
    return selected


def build_local_fallback(
    items: list[dict],
    target_date: str,
    max_final_items: int,
    threshold: float,
    tech_focus_ratio: float = 0.67,
) -> dict:
    deduped = deduplicate_items(items, threshold)
    final_items = standardize_final_items(
        deduped,
        target_date,
        max_final_items,
        tech_focus_ratio=tech_focus_ratio,
    )

    tech_count = sum(1 for item in final_items if is_tech_priority(item))
    return {
        "date": target_date,
        "overview": (
            f"{target_date} 共整理 {len(final_items)} 条重要新闻，"
            f"其中科技与 AI 相关内容 {tech_count} 条。当前为未经过模型重写的本地兜底结果。"
        ),
        "news": final_items,
    }
