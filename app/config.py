from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
GPT_RAW_DIR = DATA_DIR / "gpt_raw"
CLEANED_DIR = DATA_DIR / "cleaned"
ARCHIVE_DIR = DATA_DIR / "archive"
LOG_DIR = DATA_DIR / "logs"

DEFAULT_FEEDS = [
    {
        "name": "Reuters Technology",
        "url": "https://feeds.reuters.com/reuters/technologyNews",
        "category": "科技",
    },
    {
        "name": "NYTimes Technology",
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
        "category": "科技",
    },
    {
        "name": "BBC Technology",
        "url": "http://feeds.bbci.co.uk/news/technology/rss.xml",
        "category": "科技",
    },
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "category": "科技",
    },
    {
        "name": "WIRED AI",
        "url": "https://www.wired.com/feed/tag/ai/latest/rss",
        "category": "科技",
    },
    {
        "name": "WIRED Security",
        "url": "https://www.wired.com/feed/category/security/latest/rss",
        "category": "科技",
    },
    {
        "name": "WIRED Top Stories",
        "url": "https://www.wired.com/feed/rss",
        "category": "科技",
    },
    {
        "name": "Reuters World",
        "url": "https://feeds.reuters.com/Reuters/worldNews",
        "category": "国际",
    },
    {
        "name": "Reuters Business",
        "url": "https://feeds.reuters.com/reuters/businessNews",
        "category": "商业",
    },
    {
        "name": "BBC World",
        "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
        "category": "国际",
    },
    {
        "name": "NYTimes Business",
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
        "category": "商业",
    },
]

DEFAULT_CATEGORIES = ["国际", "科技", "商业", "金融", "政策", "其他"]
SUPPORTED_AI_PROVIDERS = ("openai", "ollama", "none")


def load_dotenv_if_present() -> None:
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return

    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    load_dotenv(env_file, override=True)


def _parse_json_env(name: str, default):
    raw_value = os.getenv(name)
    if not raw_value:
        return default

    try:
        return json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} must be valid JSON.") from exc


def _parse_feeds() -> list[dict]:
    return _parse_json_env("NEWS_FEEDS", DEFAULT_FEEDS)


def normalize_ai_provider(value: str | None) -> str:
    provider = (value or "openai").strip().lower()
    if provider not in SUPPORTED_AI_PROVIDERS:
        supported = ", ".join(SUPPORTED_AI_PROVIDERS)
        raise ValueError(f"AI provider must be one of: {supported}.")
    return provider


def ensure_directories() -> None:
    for path in (DATA_DIR, RAW_DIR, GPT_RAW_DIR, CLEANED_DIR, ARCHIVE_DIR, LOG_DIR):
        path.mkdir(parents=True, exist_ok=True)


@dataclass(slots=True)
class Settings:
    ai_provider: str = "openai"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.4-mini"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2:3b"
    ollama_timeout_seconds: int = 600
    ollama_max_items_for_model: int = 20
    ollama_num_predict: int = 1200
    target_timezone: str = "Asia/Kuala_Lumpur"
    max_feed_items_per_source: int = 30
    max_items_for_model: int = 40
    max_final_items: int = 20
    similarity_threshold: float = 0.88
    tech_focus_ratio: float = 0.75
    enable_ai_summary: bool = True
    enable_notion: bool = False
    enable_telegram: bool = False
    enable_email: bool = False
    notion_token: str | None = None
    notion_database_id: str | None = None
    notion_title_property: str = "Name"
    notion_date_property: str = "Date"
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    email_sender: str | None = None
    email_recipient: str | None = None
    feeds: list[dict] = field(default_factory=_parse_feeds)
    categories: list[str] = field(
        default_factory=lambda: _parse_json_env("NEWS_CATEGORIES", DEFAULT_CATEGORIES)
    )


def load_settings() -> Settings:
    load_dotenv_if_present()
    ensure_directories()

    return Settings(
        ai_provider=normalize_ai_provider(os.getenv("AI_PROVIDER", "openai")),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
        ollama_timeout_seconds=int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "600")),
        ollama_max_items_for_model=int(os.getenv("OLLAMA_MAX_ITEMS_FOR_MODEL", "20")),
        ollama_num_predict=int(os.getenv("OLLAMA_NUM_PREDICT", "1200")),
        target_timezone=os.getenv("TARGET_TIMEZONE", "Asia/Kuala_Lumpur"),
        max_feed_items_per_source=int(os.getenv("MAX_FEED_ITEMS_PER_SOURCE", "30")),
        max_items_for_model=int(os.getenv("MAX_ITEMS_FOR_MODEL", "40")),
        max_final_items=int(os.getenv("MAX_FINAL_ITEMS", "20")),
        similarity_threshold=float(os.getenv("SIMILARITY_THRESHOLD", "0.88")),
        tech_focus_ratio=float(os.getenv("TECH_FOCUS_RATIO", "0.75")),
        enable_ai_summary=os.getenv("ENABLE_AI_SUMMARY", "true").lower() == "true",
        enable_notion=os.getenv("ENABLE_NOTION", "false").lower() == "true",
        enable_telegram=os.getenv("ENABLE_TELEGRAM", "false").lower() == "true",
        enable_email=os.getenv("ENABLE_EMAIL", "false").lower() == "true",
        notion_token=os.getenv("NOTION_TOKEN"),
        notion_database_id=os.getenv("NOTION_DATABASE_ID"),
        notion_title_property=os.getenv("NOTION_TITLE_PROPERTY", "Name"),
        notion_date_property=os.getenv("NOTION_DATE_PROPERTY", "Date"),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
        smtp_host=os.getenv("SMTP_HOST"),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_username=os.getenv("SMTP_USERNAME"),
        smtp_password=os.getenv("SMTP_PASSWORD"),
        email_sender=os.getenv("EMAIL_SENDER"),
        email_recipient=os.getenv("EMAIL_RECIPIENT"),
    )
