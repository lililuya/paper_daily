"""生成博客日报 Markdown（data/{date}.blogs.md）：按推荐指数分组。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from daily_arxiv.config import DATA_DIR  # noqa: E402

RATING_STAR = {5: "⭐⭐⭐⭐⭐", 4: "⭐⭐⭐⭐", 3: "⭐⭐⭐", 2: "⭐⭐", 1: "⭐"}


def _article_md(a: dict, detailed: bool) -> str:
    stars = RATING_STAR.get(a.get("rating", 0), "⭐⭐⭐")
    published = (a.get("published") or "")[:10]
    lines = [
        f"### {stars} {a.get('title_zh') or a['title']}",
        "",
        f"**站点**：{a.get('site', '')} | **发布**：{published} | [原文]({a['url']})",
        "",
    ]
    oneline = (a.get("oneline_zh") or "").strip()
    if oneline:
        lines.append(f"**导读**：{oneline}")
        lines.append("")
    if detailed and a.get("highlights"):
        lines.append("**要点**：")
        lines.append("")
        for h in a["highlights"]:
            lines.append(f"- {h}")
        lines.append("")
    if (a.get("title_zh") or "") != a["title"]:
        lines.append(f"<sub>英文标题：{a['title']}</sub>")
        lines.append("")
    summary = (a.get("summary") or "").strip()
    if summary:
        one_line = " ".join(summary.split())
        if len(one_line) > 600:
            one_line = one_line[:600] + "…"
        lines.append(f"> {one_line}")
        lines.append("")
    return "\n".join(lines)


def convert_blogs(date_str: str, articles: list) -> str:
    """生成博客精选 Markdown，返回文件路径。"""
    must_read = [a for a in articles if (a.get("rating") or 0) >= 4]
    others = [a for a in articles if 3 <= (a.get("rating") or 0) < 4]
    must_read.sort(key=lambda a: (a.get("rating", 0), a.get("published", "")), reverse=True)
    others.sort(key=lambda a: a.get("published", ""), reverse=True)

    parts = [
        f"# 技术博客精选 {date_str}",
        "",
        f"> 共 {len(articles)} 篇 · 必读 {len(must_read)} 篇 · 值得一看 {len(others)} 篇",
        "",
    ]
    if must_read:
        parts.append("## 今日必读")
        parts.append("")
        for a in must_read:
            parts.append(_article_md(a, detailed=True))
    if others:
        parts.append("## 值得一看")
        parts.append("")
        for a in others:
            parts.append(_article_md(a, detailed=False))

    os.makedirs(DATA_DIR, exist_ok=True)
    out_path = os.path.join(DATA_DIR, f"{date_str}.blogs.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts).rstrip() + "\n")
    print(f"[to_md] 博客日报已生成：{out_path}", flush=True)
    return out_path
