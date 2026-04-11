from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from app.utils import write_json, write_text


def render_markdown(payload: dict) -> str:
    lines = [
        f"# 昨日重要新闻摘要 - {payload['date']}",
        "",
    ]

    overview = payload.get("overview", "").strip()
    if overview:
        lines.extend(["## 总览", "", overview, ""])

    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in payload.get("news", []):
        grouped[item.get("category", "其他")].append(item)

    for category, items in grouped.items():
        lines.extend([f"## {category}", ""])
        for index, item in enumerate(items, start=1):
            lines.append(f"### {index}. {item.get('title', '').strip()}")
            lines.append("")
            lines.append(item.get("summary", "").strip() or "暂无摘要")
            lines.append("")
            meta = [
                f"- 来源：{item.get('source', '') or '未知'}",
                f"- 日期：{item.get('date', '') or payload['date']}",
            ]
            if item.get("importance"):
                meta.append(f"- 入选原因：{item['importance']}")
            if item.get("url"):
                meta.append(f"- 链接：{item['url']}")
            if item.get("raw_sources"):
                meta.append(f"- 合并来源：{', '.join(item['raw_sources'])}")
            lines.extend(meta)
            lines.append("")

    return "\n".join(lines).strip() + "\n"


def export_json(path: Path, payload: dict) -> None:
    write_json(path, payload)


def export_markdown(path: Path, payload: dict) -> None:
    write_text(path, render_markdown(payload))


def export_csv(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["category", "title", "summary", "importance", "source", "date", "url", "raw_sources"],
        )
        writer.writeheader()
        for item in payload.get("news", []):
            row = dict(item)
            row["raw_sources"] = ", ".join(item.get("raw_sources", []))
            writer.writerow(row)
