# Daily News Automation

一个按日自动生成“昨天的重要新闻摘要”的 Python 项目，包含：

- 原始新闻抓取存档
- 本地去重与分类
- OpenAI 总结与重写
- Markdown / CSV / JSON 导出
- 可选发送到 Notion / Telegram / Email

## 目录结构

```text
news_automation/
├─ app/
│  ├─ main.py
│  ├─ config.py
│  ├─ prompts.py
│  ├─ fetch_news.py
│  ├─ summarize_news.py
│  ├─ clean_news.py
│  ├─ export_news.py
│  ├─ deliver_news.py
│  └─ utils.py
├─ data/
│  ├─ raw/
│  ├─ gpt_raw/
│  ├─ cleaned/
│  └─ logs/
├─ .env.example
├─ requirements.txt
└─ README.md
```

## Workflow

每天 07:00 由调度器执行：

```bash
python -m app.main
```

主流程：

1. 计算昨天日期
2. 从 RSS 抓取新闻
3. 存档 `data/raw/news_raw_YYYY-MM-DD.json`
4. 本地先做一轮去重
5. 调 OpenAI Responses API 生成结构化中文摘要
6. 保存模型原始输出到 `data/gpt_raw/`
7. 输出最终结果到 `data/cleaned/`
8. 可选推送到 Notion / Telegram / Email

## 安装

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

然后编辑 `.env`，至少配置：

```env
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-5.4-mini
```

## 运行

默认跑“昨天”：

```bash
python -m app.main
```

指定日期：

```bash
python -m app.main --date 2026-04-11
```

只跑抓取和本地清洗，不调用 OpenAI：

```bash
python -m app.main --skip-ai
```

只生成文件，不发送到外部渠道：

```bash
python -m app.main --dry-run
```

## 输出文件

- 原始抓取：`data/raw/news_raw_YYYY-MM-DD.json`
- 模型原始输出：`data/gpt_raw/gpt_news_YYYY-MM-DD.json`
- 最终 Markdown：`data/cleaned/news_final_YYYY-MM-DD.md`
- 最终 CSV：`data/cleaned/news_final_YYYY-MM-DD.csv`
- 最终 JSON：`data/cleaned/news_final_YYYY-MM-DD.json`
- 日志：`data/logs/news_YYYY-MM-DD.log`

## Windows 定时执行

在 Task Scheduler 里创建一个每日任务：

- Trigger: 每天 07:00
- Program/script: `python`
- Add arguments: `-m app.main`
- Start in: 项目根目录

如果你使用虚拟环境，建议把 `Program/script` 改成虚拟环境里的 `python.exe`。

## 可扩展点

### 1. 替换新闻源

通过 `.env` 中的 `NEWS_FEEDS` 覆盖默认 RSS 列表：

```env
NEWS_FEEDS=[{"name":"My Feed","url":"https://example.com/rss.xml","category":"科技"}]
```

### 2. 调整分类

```env
NEWS_CATEGORIES=["国际","科技","商业","金融","政策","其他"]
```

### 3. 打开外部发送

Telegram：

```env
ENABLE_TELEGRAM=true
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

Notion：

```env
ENABLE_NOTION=true
NOTION_TOKEN=...
NOTION_DATABASE_ID=...
NOTION_TITLE_PROPERTY=Name
NOTION_DATE_PROPERTY=Date
```

如果你的 Notion 数据库标题列或日期列名字不是 `Name` / `Date`，要同步修改这两个配置。

Email：

```env
ENABLE_EMAIL=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=...
SMTP_PASSWORD=...
EMAIL_SENDER=...
EMAIL_RECIPIENT=...
```

## 说明

- RSS 的发布时间格式不完全统一，脚本会按目标日期过滤，但不同站点仍可能有轻微偏差。
- 默认 RSS 只是一个可运行起点，正式使用建议替换成你更信任的新闻源。
- 如果 OpenAI 不可用，脚本会退回本地去重后的兜底结果，链路不会中断。
