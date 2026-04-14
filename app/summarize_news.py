from __future__ import annotations

import json

import requests

from app.clean_news import standardize_final_items
from app.prompts import build_news_prompt
from app.utils import strip_code_fence


def _import_openai():
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Missing dependency 'openai'. Install requirements.txt first.") from exc

    return OpenAI


def _finalize_payload(raw_text: str, *, target_date: str, max_final_items: int) -> tuple[str, dict]:
    payload = _parse_payload_json(raw_text)
    payload["news"] = standardize_final_items(
        payload.get("news", []),
        target_date=target_date,
        max_final_items=max_final_items,
    )
    payload.setdefault("date", target_date)
    payload.setdefault("overview", "")
    return raw_text, payload


def _parse_payload_json(raw_text: str) -> dict:
    cleaned = strip_code_fence(raw_text)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = cleaned[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    raise RuntimeError("Model output was not valid JSON.")


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

    return _finalize_payload(
        raw_text,
        target_date=target_date,
        max_final_items=max_final_items,
    )


def summarize_with_ollama(
    *,
    base_url: str,
    model: str,
    categories: list[str],
    raw_items: list[dict],
    target_date: str,
    max_items_for_model: int,
    max_final_items: int,
    timeout_seconds: int,
    num_predict: int,
) -> tuple[str, dict]:
    prompt = build_news_prompt(
        target_date=target_date,
        categories=categories,
        raw_items=raw_items,
        max_items=max_items_for_model,
    )

    response_fragments: list[str] = []

    try:
        with requests.post(
            f"{base_url.rstrip('/')}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": True,
                "format": "json",
                "options": {
                    "temperature": 0.1,
                    "num_predict": num_predict,
                },
            },
            timeout=(10, timeout_seconds),
            stream=True,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue

                try:
                    data = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise RuntimeError("Ollama returned an invalid JSON stream chunk.") from exc

                if data.get("error"):
                    raise RuntimeError(f"Ollama error: {data['error']}")

                chunk = data.get("response") or ""
                if chunk:
                    response_fragments.append(chunk)
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed to call Ollama at {base_url}: {exc}") from exc

    raw_text = "".join(response_fragments).strip()
    if not raw_text:
        raise RuntimeError("Ollama response was empty.")

    return _finalize_payload(
        raw_text,
        target_date=target_date,
        max_final_items=max_final_items,
    )


def summarize_news(
    *,
    provider: str,
    api_key: str,
    openai_model: str,
    ollama_base_url: str,
    ollama_model: str,
    ollama_timeout_seconds: int,
    ollama_num_predict: int,
    categories: list[str],
    raw_items: list[dict],
    target_date: str,
    max_items_for_model: int,
    max_final_items: int,
) -> tuple[str, dict]:
    normalized_provider = provider.strip().lower()

    if normalized_provider == "openai":
        return summarize_with_openai(
            api_key=api_key,
            model=openai_model,
            categories=categories,
            raw_items=raw_items,
            target_date=target_date,
            max_items_for_model=max_items_for_model,
            max_final_items=max_final_items,
        )

    if normalized_provider == "ollama":
        return summarize_with_ollama(
            base_url=ollama_base_url,
            model=ollama_model,
            categories=categories,
            raw_items=raw_items,
            target_date=target_date,
            max_items_for_model=max_items_for_model,
            max_final_items=max_final_items,
            timeout_seconds=ollama_timeout_seconds,
            num_predict=ollama_num_predict,
        )

    raise RuntimeError(f"Unsupported AI provider: {provider}")
