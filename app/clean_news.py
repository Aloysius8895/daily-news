from __future__ import annotations

import re
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
        "tiktok",
        "social media",
    ],
    "金融": ["bank", "bond", "interest rate", "inflation", "fed", "ecb", "stock", "market"],
    "政策": ["tariff", "policy", "regulation", "election", "sanction", "government", "blockade"],
    "商业": ["earnings", "deal", "acquisition", "merger", "shipping", "port", "supply chain"],
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

STRATEGIC_PRIORITY_TERMS = {
    "war",
    "blockade",
    "hormuz",
    "shipping",
    "oil",
    "sanction",
    "tariff",
    "policy",
    "regulation",
    "airstrike",
    "strike",
    "killed",
    "execution",
    "executions",
    "corruption",
    "probe",
    "lawsuit",
    "antitrust",
    "south china sea",
    "cybersecurity",
    "hack",
    "quantum",
    "chip",
    "semiconductor",
    "election",
    "earnings",
}

LOW_PRIORITY_TERMS = {
    "celebrity",
    "singer",
    "tributes",
    "rehab",
    "rock band",
    "buyer, beware",
    "tips",
    "how to",
    "fans",
    "visit",
    "trip",
    "video",
    "refreshers",
    "mcdonald",
    "drinks",
    "hollywood",
    "magazine",
    "studio",
}

SOURCE_PRIORITY_SCORES = {
    "Reuters Technology": 16,
    "NYTimes Technology": 15,
    "BBC Technology": 13,
    "Reuters Business": 11,
    "NYTimes Business": 10,
    "Reuters World": 10,
    "BBC World": 8,
}

STOPWORDS = {
    "the",
    "a",
    "an",
    "of",
    "to",
    "in",
    "on",
    "for",
    "and",
    "with",
    "after",
    "over",
    "into",
    "from",
    "at",
    "is",
    "are",
    "be",
    "will",
    "how",
    "what",
    "why",
}


def keyword_in_text(keyword: str, text: str) -> bool:
    normalized_keyword = keyword.strip().lower()
    normalized_text = text.lower()
    if not normalized_keyword:
        return False

    if re.fullmatch(r"[a-z0-9][a-z0-9\s./+-]*", normalized_keyword):
        pattern = r"\b" + re.escape(normalized_keyword).replace(r"\ ", r"\s+") + r"\b"
        return re.search(pattern, normalized_text) is not None

    return normalized_keyword in normalized_text


def source_priority_score(source: str) -> int:
    return SOURCE_PRIORITY_SCORES.get(source, 2)


def similar_titles(left: str, right: str, threshold: float) -> bool:
    if left == right:
        return True

    if left in right or right in left:
        return True

    return SequenceMatcher(a=left, b=right).ratio() >= threshold


def topic_tokens(item: dict) -> set[str]:
    raw_text = " ".join([item.get("title", ""), item.get("summary", "")]).lower()
    tokens = set(re.findall(r"[a-z0-9]{3,}", raw_text))
    return {token for token in tokens if token not in STOPWORDS}


def is_topic_overlapping(candidate: dict, selected: list[dict], threshold: float = 0.5) -> bool:
    candidate_tokens = topic_tokens(candidate)
    if not candidate_tokens:
        return False

    for existing in selected:
        existing_tokens = topic_tokens(existing)
        if not existing_tokens:
            continue
        overlap = len(candidate_tokens & existing_tokens) / min(len(candidate_tokens), len(existing_tokens))
        if overlap >= threshold:
            return True

    return False


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

            if source_priority_score(item.get("source", "")) > source_priority_score(matched.get("source", "")):
                for field in ("source", "feed_category", "url", "published_at", "published_datetime", "time", "title"):
                    if item.get(field):
                        matched[field] = item.get(field)

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
            item.get("source", "").lower(),
        ]
    )

    keyword_scores: dict[str, int] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        matches = sum(1 for keyword in keywords if keyword_in_text(keyword, haystack))
        if matches:
            keyword_scores[category] = matches

    feed_category = item.get("feed_category")
    if feed_category:
        keyword_scores[feed_category] = keyword_scores.get(feed_category, 0) + 2

    if keyword_scores:
        return max(keyword_scores.items(), key=lambda pair: pair[1])[0]

    return "其他"


def is_tech_priority(item: dict) -> bool:
    if infer_category(item) == "科技":
        return True

    haystack = " ".join(
        [
            item.get("title", "").lower(),
            item.get("summary", "").lower(),
            item.get("source", "").lower(),
            item.get("feed_category", "").lower(),
        ]
    )
    return any(keyword_in_text(keyword, haystack) for keyword in TECH_PRIORITY_TERMS)


def item_priority_score(item: dict) -> int:
    haystack = " ".join(
        [
            item.get("title", "").lower(),
            item.get("summary", "").lower(),
            item.get("source", "").lower(),
            item.get("feed_category", "").lower(),
        ]
    )

    score = 0
    category = infer_category(item)
    if category == "科技":
        score += 40
    elif category == "商业":
        score += 14
    elif category == "国际":
        score += 12
    elif category == "政策":
        score += 12
    elif category == "金融":
        score += 10

    if is_tech_priority(item):
        score += 10

    for keyword in TECH_PRIORITY_TERMS:
        if keyword_in_text(keyword, haystack):
            score += 6

    for keyword in STRATEGIC_PRIORITY_TERMS:
        if keyword_in_text(keyword, haystack):
            score += 8

    if any(keyword_in_text(keyword, haystack) for keyword in ["ai", "artificial intelligence", "chatgpt", "openai", "llm"]):
        score += 20

    score += source_priority_score(item.get("source", ""))

    if item.get("summary"):
        score += min(len(item["summary"]) // 60, 6)

    if "/videos/" in item.get("url", "").lower() or keyword_in_text("video", haystack):
        score -= 12

    for keyword in LOW_PRIORITY_TERMS:
        if keyword_in_text(keyword, haystack):
            score -= 14

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
    selected: list[dict] = []

    for item in tech_items:
        if is_topic_overlapping(item, selected):
            continue
        selected.append(item)
        if len(selected) >= desired_tech_count:
            break

    spillover = tech_items[desired_tech_count:] + other_items
    spillover.sort(key=lambda item: (-item["priority_score"], item.get("time") or "99:99", item.get("title", "")))
    for item in spillover:
        if is_topic_overlapping(item, selected):
            continue
        selected.append(item)
        if len(selected) >= max_final_items:
            break

    if len(selected) < max_final_items:
        fallback_pool = tech_items + other_items
        fallback_pool.sort(key=lambda item: (-item["priority_score"], item.get("time") or "99:99", item.get("title", "")))
        existing_keys = {
            (item.get("url") or "").strip() or normalize_title(item.get("title", ""))
            for item in selected
        }
        for item in fallback_pool:
            key = (item.get("url") or "").strip() or normalize_title(item.get("title", ""))
            if key in existing_keys:
                continue
            existing_keys.add(key)
            selected.append(item)
            if len(selected) >= max_final_items:
                break

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

    tech_count = sum(1 for item in final_items if item.get("category") == "科技")
    return {
        "date": target_date,
        "overview": (
            f"{target_date} 共整理 {len(final_items)} 条重要新闻，"
            f"其中科技与 AI 相关内容 {tech_count} 条。当前为未经过模型重写的本地兜底结果。"
        ),
        "news": final_items,
    }
