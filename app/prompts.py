from __future__ import annotations

import json


def build_news_prompt(target_date: str, categories: list[str], raw_items: list[dict], max_items: int) -> str:
    sampled_items = raw_items if max_items <= 0 else raw_items[:max_items]
    serialized_items = json.dumps(sampled_items, ensure_ascii=False, indent=2)
    category_text = "、".join(categories)
    target_count = len(sampled_items)

    return f"""
你是一个严谨的中文新闻编辑。给定的新闻数据已经完成本地去重和重要性初筛，你的任务是把它们整理成“{target_date}的重要新闻摘要”。

要求：
1. 输入里的新闻已经是候选重点新闻。除非是明显重复或明显不重要的边角项，否则应尽量保留全部。
2. 如果候选条数充足，目标是输出接近 {target_count} 条，不要无故缩成 1 到 3 条。
3. 分类必须限制在这些类别里：{category_text}。
4. 当候选新闻充足时，科技 / AI / 计算机 / 半导体 / 软件 / 云计算 / 网络安全相关内容应占大多数。
5. 每条 summary 用中文写成 2 到 3 句，简洁、信息密度高，不要夸张，不要加猜测。
6. importance 字段写一句中文，解释为什么这条值得进入日报。
7. 如果原始数据里没有足够信息，不要编造；缺失字段可以留空字符串。
8. 保留原有的 title、source、date、time、url、raw_sources，不要改写链接，不要新增不存在的新闻。

返回格式：
- 只返回 JSON
- 不要使用 Markdown 代码块
- JSON 结构必须是：
{{
  "date": "{target_date}",
  "overview": "120字以内的中文总览",
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

候选新闻数据如下：
{serialized_items}
""".strip()
