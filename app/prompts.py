from __future__ import annotations

import json


def build_news_prompt(target_date: str, categories: list[str], raw_items: list[dict], max_items: int) -> str:
    sampled_items = raw_items[:max_items]
    serialized_items = json.dumps(sampled_items, ensure_ascii=False, indent=2)
    category_text = "、".join(categories)

    return f"""
你是一个严谨的中文新闻编辑。你的任务是基于给定的新闻原始数据，生成“{target_date}的重要新闻摘要”。

要求：
1. 只保留与 {target_date} 直接相关，或在 {target_date} 明显持续推进的重要新闻。
2. 去重：同一事件如果多来源重复，只保留一条，并在 source 字段中优先保留最可信的来源名。
3. 分类必须限制在这些类别里：{category_text}。
4. 当候选新闻充足时，科技 / AI / 计算机 / 半导体 / 软件 / 云计算 / 网络安全相关内容应占大多数。
5. 每条 summary 用中文写成 2 到 3 句，简洁、信息密度高，不要夸张，不要加猜测。
6. importance 字段写一句中文，解释为什么这条值得进入日报。
7. 如果原始数据里没有足够信息，不要编造；缺失字段可以留空字符串。
8. 最多输出 12 条新闻，优先保留 AI、半导体、计算机、软件、云计算、网络安全、机器人等科技新闻，其次再补充具有国际影响的商业、政策和金融事件。

返回格式：
- 只返回 JSON
- 不要使用 Markdown 代码块
- JSON 结构必须是：
{{
  "date": "{target_date}",
  "overview": "100字以内的中文总览",
  "news": [
    {{
      "category": "科技",
      "title": "新闻标题",
      "summary": "中文摘要",
      "importance": "入选原因",
      "source": "Reuters",
      "date": "{target_date}",
      "time": "09:30",
      "url": "https://...",
      "raw_sources": ["Reuters", "BBC"]
    }}
  ]
}}

原始新闻数据如下：
{serialized_items}
""".strip()
