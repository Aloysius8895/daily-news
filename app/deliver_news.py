from __future__ import annotations

import json
import smtplib
from email.mime.text import MIMEText


def _import_requests():
    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("Missing dependency 'requests'. Install requirements.txt first.") from exc

    return requests


def send_to_telegram(bot_token: str, chat_id: str, markdown_content: str) -> None:
    requests = _import_requests()
    response = requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        timeout=30,
        json={
            "chat_id": chat_id,
            "text": markdown_content[:4000],
            "disable_web_page_preview": True,
        },
    )
    response.raise_for_status()


def send_email(
    *,
    smtp_host: str,
    smtp_port: int,
    smtp_username: str,
    smtp_password: str,
    sender: str,
    recipient: str,
    subject: str,
    body: str,
) -> None:
    message = MIMEText(body, "plain", "utf-8")
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.sendmail(sender, [recipient], message.as_string())


def send_to_notion(
    token: str,
    database_id: str,
    payload: dict,
    markdown_content: str,
    title_property: str,
    date_property: str,
) -> None:
    requests = _import_requests()
    response = requests.post(
        "https://api.notion.com/v1/pages",
        timeout=30,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
        json={
            "parent": {"database_id": database_id},
            "properties": {
                title_property: {
                    "title": [
                        {
                            "text": {
                                "content": f"昨日重要新闻摘要 - {payload['date']}",
                            }
                        }
                    ]
                },
                date_property: {"date": {"start": payload["date"]}},
            },
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {
                                    "content": markdown_content[:1800],
                                },
                            }
                        ]
                    },
                },
                {
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {
                                    "content": json.dumps(payload, ensure_ascii=False, indent=2)[:1800],
                                },
                            }
                        ],
                        "language": "json",
                    },
                },
            ],
        },
    )
    response.raise_for_status()
