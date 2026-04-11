from __future__ import annotations

import json

from app.clean_news import standardize_final_items
from app.prompts import build_news_prompt
from app.utils import strip_code_fence


def _import_openai():
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Missing dependency 'openai'. Install requirements.txt first.") from exc

    return OpenAI


def summarize_with_openai(
    *,
    api_key: str,
    model: str,
    categories: list[str],
    raw_items: list[dict],
    target_date: str,
    max_items_for_model: int,
    max_final_items: int,
) -> tuple[str, dict]:
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing.")

    prompt = build_news_prompt(
        target_date=target_date,
        categories=categories,
        raw_items=raw_items,
        max_items=max_items_for_model,
    )

    OpenAI = _import_openai()
    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model,
        input=prompt,
    )

    raw_text = (response.output_text or "").strip()
    if not raw_text:
        raise RuntimeError("OpenAI response was empty.")

    payload = json.loads(strip_code_fence(raw_text))
    payload["news"] = standardize_final_items(
        payload.get("news", []),
        target_date=target_date,
        max_final_items=max_final_items,
    )
    payload.setdefault("date", target_date)
    payload.setdefault("overview", "")
    return raw_text, payload
