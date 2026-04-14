from __future__ import annotations

import argparse

from app.config import SUPPORTED_AI_PROVIDERS, load_settings
from app.pipeline import PipelineContext, PipelineOptions, build_default_pipeline
from app.utils import get_target_date, setup_logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate yesterday's important news summary.")
    parser.add_argument("--date", help="Target date in YYYY-MM-DD. Defaults to yesterday in configured timezone.")
    parser.add_argument("--skip-ai", action="store_true", help="Skip AI summarization and use local fallback.")
    parser.add_argument(
        "--ai-provider",
        choices=SUPPORTED_AI_PROVIDERS,
        help="Choose AI provider: openai, ollama, or none. Defaults to AI_PROVIDER from .env.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Run pipeline without external delivery.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_settings()
    target_date = get_target_date(args.date, settings.target_timezone)
    logger = setup_logger(target_date)

    context = PipelineContext(
        settings=settings,
        logger=logger,
        target_date=target_date,
        options=PipelineOptions(skip_ai=args.skip_ai, ai_provider=args.ai_provider, dry_run=args.dry_run),
    )
    build_default_pipeline().run(context)


if __name__ == "__main__":
    main()
