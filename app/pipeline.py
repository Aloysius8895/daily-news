from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from logging import Logger
from pathlib import Path
from typing import Callable

from app.clean_news import build_local_fallback, deduplicate_items
from app.config import CLEANED_DIR, GPT_RAW_DIR, RAW_DIR, Settings
from app.deliver_news import send_email, send_to_notion, send_to_telegram
from app.export_news import export_csv, export_json, export_markdown, render_markdown
from app.fetch_news import fetch_news
from app.summarize_news import summarize_with_openai
from app.utils import write_json, write_text


StageFn = Callable[["PipelineContext"], None]


@dataclass(slots=True)
class PipelineOptions:
    skip_ai: bool = False
    dry_run: bool = False


@dataclass(slots=True)
class PipelineContext:
    settings: Settings
    logger: Logger
    target_date: date
    options: PipelineOptions
    target_iso: str = field(init=False)
    raw_items: list[dict] = field(default_factory=list)
    deduped_raw_items: list[dict] = field(default_factory=list)
    raw_archive: dict = field(default_factory=dict)
    payload: dict = field(default_factory=dict)
    markdown_content: str = ""
    gpt_raw_text: str = ""
    raw_path: Path | None = None
    gpt_raw_path: Path | None = None
    final_json_path: Path | None = None
    final_md_path: Path | None = None
    final_csv_path: Path | None = None

    def __post_init__(self) -> None:
        self.target_iso = self.target_date.isoformat()

    @property
    def use_ai(self) -> bool:
        return (
            self.settings.enable_ai_summary
            and not self.options.skip_ai
            and bool(self.settings.openai_api_key)
            and bool(self.deduped_raw_items)
        )


@dataclass(slots=True)
class PipelineStage:
    name: str
    handler: StageFn

    def run(self, context: PipelineContext) -> None:
        context.logger.info("Stage started: %s", self.name)
        self.handler(context)
        context.logger.info("Stage completed: %s", self.name)


class NewsPipeline:
    def __init__(self, stages: list[PipelineStage]) -> None:
        self.stages = stages

    def run(self, context: PipelineContext) -> PipelineContext:
        context.logger.info("Pipeline started for %s", context.target_iso)
        for stage in self.stages:
            stage.run(context)
        context.logger.info("Pipeline finished for %s", context.target_iso)
        return context


def stage_fetch_news(context: PipelineContext) -> None:
    context.raw_items = fetch_news(
        feeds=context.settings.feeds,
        target_date=context.target_date,
        max_items_per_source=context.settings.max_feed_items_per_source,
    )
    context.logger.info("Fetched %s raw items", len(context.raw_items))


def stage_archive_raw(context: PipelineContext) -> None:
    context.raw_archive = {
        "target_date": context.target_iso,
        "fetched_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "feeds": context.settings.feeds,
        "count": len(context.raw_items),
        "items": context.raw_items,
    }
    context.raw_path = RAW_DIR / f"news_raw_{context.target_iso}.json"
    write_json(context.raw_path, context.raw_archive)
    context.logger.info("Saved raw archive to %s", context.raw_path)


def stage_deduplicate(context: PipelineContext) -> None:
    context.deduped_raw_items = deduplicate_items(
        context.raw_items,
        context.settings.similarity_threshold,
    )
    context.logger.info(
        "Reduced raw items to %s after local deduplication",
        len(context.deduped_raw_items),
    )


def stage_generate_payload(context: PipelineContext) -> None:
    if context.use_ai:
        context.logger.info(
            "Generating summary with OpenAI model %s",
            context.settings.openai_model,
        )
        try:
            raw_text, payload = summarize_with_openai(
                api_key=context.settings.openai_api_key or "",
                model=context.settings.openai_model,
                categories=context.settings.categories,
                raw_items=context.deduped_raw_items,
                target_date=context.target_iso,
                max_items_for_model=context.settings.max_items_for_model,
                max_final_items=context.settings.max_final_items,
            )
            context.gpt_raw_text = raw_text
            context.payload = payload
            context.gpt_raw_path = GPT_RAW_DIR / f"gpt_news_{context.target_iso}.json"
            write_text(context.gpt_raw_path, raw_text)
            context.logger.info("Saved model raw output to %s", context.gpt_raw_path)
            return
        except Exception as exc:
            context.logger.exception(
                "AI summarization failed, falling back to local pipeline: %s",
                exc,
            )
            context.gpt_raw_text = f"AI summarization failed:\n{exc}\n"
            context.gpt_raw_path = GPT_RAW_DIR / f"gpt_news_{context.target_iso}_error.txt"
            write_text(context.gpt_raw_path, context.gpt_raw_text)

    context.payload = build_local_fallback(
        items=context.deduped_raw_items,
        target_date=context.target_iso,
        max_final_items=context.settings.max_final_items,
        threshold=context.settings.similarity_threshold,
    )
    if context.gpt_raw_path is None:
        context.gpt_raw_text = "AI skipped. Local fallback used.\n"
        context.gpt_raw_path = GPT_RAW_DIR / f"gpt_news_{context.target_iso}.txt"
        write_text(context.gpt_raw_path, context.gpt_raw_text)
    context.logger.info("Using local fallback payload")


def stage_export_outputs(context: PipelineContext) -> None:
    context.final_json_path = CLEANED_DIR / f"news_final_{context.target_iso}.json"
    context.final_md_path = CLEANED_DIR / f"news_final_{context.target_iso}.md"
    context.final_csv_path = CLEANED_DIR / f"news_final_{context.target_iso}.csv"

    export_json(context.final_json_path, context.payload)
    export_markdown(context.final_md_path, context.payload)
    export_csv(context.final_csv_path, context.payload)
    context.markdown_content = render_markdown(context.payload)
    context.logger.info(
        "Exported final outputs: %s, %s, %s",
        context.final_json_path,
        context.final_md_path,
        context.final_csv_path,
    )


def stage_deliver_outputs(context: PipelineContext) -> None:
    if context.options.dry_run:
        context.logger.info("Dry run enabled, skipping deliveries")
        return

    settings = context.settings
    markdown_content = context.markdown_content

    if settings.enable_telegram and settings.telegram_bot_token and settings.telegram_chat_id:
        send_to_telegram(settings.telegram_bot_token, settings.telegram_chat_id, markdown_content)
        context.logger.info("Telegram delivery completed")

    if (
        settings.enable_email
        and settings.smtp_host
        and settings.smtp_username
        and settings.smtp_password
        and settings.email_sender
        and settings.email_recipient
    ):
        send_email(
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            smtp_username=settings.smtp_username,
            smtp_password=settings.smtp_password,
            sender=settings.email_sender,
            recipient=settings.email_recipient,
            subject=f"Yesterday News Summary - {context.target_iso}",
            body=markdown_content,
        )
        context.logger.info("Email delivery completed")

    if settings.enable_notion and settings.notion_token and settings.notion_database_id:
        send_to_notion(
            settings.notion_token,
            settings.notion_database_id,
            context.payload,
            markdown_content,
            settings.notion_title_property,
            settings.notion_date_property,
        )
        context.logger.info("Notion delivery completed")


def build_default_pipeline() -> NewsPipeline:
    return NewsPipeline(
        stages=[
            PipelineStage("fetch_news", stage_fetch_news),
            PipelineStage("archive_raw", stage_archive_raw),
            PipelineStage("deduplicate", stage_deduplicate),
            PipelineStage("generate_payload", stage_generate_payload),
            PipelineStage("export_outputs", stage_export_outputs),
            PipelineStage("deliver_outputs", stage_deliver_outputs),
        ]
    )
