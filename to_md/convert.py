"""生成 Markdown 日报：按推荐指数 + 方向分组。"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from daily_arxiv.config import DATA_DIR  # noqa: E402

RATING_STAR = {5: "⭐⭐⭐⭐⭐", 4: "⭐⭐⭐⭐", 3: "⭐⭐⭐", 2: "⭐⭐", 1: "⭐"}
DIRECTION_ORDER = ["视频模型", "图像编辑", "Agent", "大语言模型", "多模态", "系统与基础设施", "HF精选"]


def _paper_md(p: dict, detailed: bool) -> str:
    stars = RATING_STAR.get(p.get("rating", 0), "⭐⭐⭐")
    authors = p.get("authors", [])
    author_str = ", ".join(authors[:3]) + (f" 等 {len(authors)} 人" if len(authors) > 3 else "")
    tags = " · ".join(p.get("tags", []))
    upvote = f" · 👍 {p['hf_upvotes']}" if p.get("hf_upvotes") else ""
    lines = [
        f"### {stars} {p.get('title_zh') or p['title']}",
        "",
        f"**方向**：{tags or '未分类'}{upvote} | **作者**：{author_str} | "
        f"[原文]({p['url']}) | [PDF]({p.get('pdf_url') or p['url'] + '.pdf'})",
        "",
        f"> {p.get('oneline_zh', '')}",
        "",
    ]
    if detailed and p.get("highlights"):
        lines.append("**亮点**：" + "；".join(p["highlights"]))
        lines.append("")
    if detailed and p.get("summary_zh"):
        lines.append(f"**摘要**：{p['summary_zh']}")
        lines.append("")
    lines.append(f"<sub>英文标题：{p['title']}</sub>")
    lines.append("")

    # papers.cool 链接
    pc_url = f"https://papers.cool/arxiv/{p['id']}"
    lines.append(f"[papers.coool / Kimi]({pc_url})")
    lines.append("")

    # Kimi Q&A 摘要（如已抓取）
    kimi = p.get("kimi_qa") or []
    if kimi:
        lines.append("<details><summary>Kimi 深度解读（点击展开）</summary>")
        lines.append("")
        for i, (q, a) in enumerate(kimi, 1):
            lines.append(f"**Q{i}. {q.strip()}**")
            lines.append("")
            lines.append(a.strip())
            lines.append("")
        lines.append("</details>")
        lines.append("")
    return "\n".join(lines)


def _direction_of(p: dict) -> str:
    tags = set(p.get("tags", [])) | set(p.get("matched_directions", []))
    for d in DIRECTION_ORDER:
        if d in tags:
            return d
    return "其他"


def convert(date_str: str, papers: list, stats: dict) -> str:
    """生成日报 Markdown，返回文件路径。"""
    must_read = [p for p in papers if p.get("rating", 0) >= 4]
    must_read.sort(key=lambda p: (p.get("rating", 0), p.get("score", 0)), reverse=True)

    by_dir = {}
    for p in papers:
        if p.get("rating", 0) >= 4:
            continue
        by_dir.setdefault(_direction_of(p), []).append(p)
    for lst in by_dir.values():
        lst.sort(key=lambda p: p.get("score", 0), reverse=True)

    parts = [
        f"# 前研日报 {date_str}",
        "",
        f"> 抓取 {stats.get('total', len(papers))} 篇新论文 · 精选 {len(papers)} 篇 · "
        f"必读 {len(must_read)} 篇（推荐指数 ≥ 4）",
        "",
        "## 今日必读",
        "",
    ]
    if must_read:
        for p in must_read:
            parts.append(_paper_md(p, detailed=True))
    else:
        parts.append("今日暂无高推荐论文。")
        parts.append("")

    for d in DIRECTION_ORDER + ["其他"]:
        if d in by_dir and by_dir[d]:
            parts.append(f"## {d}（{len(by_dir[d])} 篇）")
            parts.append("")
            for p in by_dir[d]:
                parts.append(_paper_md(p, detailed=False))

    os.makedirs(DATA_DIR, exist_ok=True)
    out_path = os.path.join(DATA_DIR, f"{date_str}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts).rstrip() + "\n")
    print(f"[to_md] 日报已生成：{out_path}", flush=True)
    return out_path


if __name__ == "__main__":
    print(re.sub(r"\d+", "x", sys.argv[0]) if len(sys.argv) > 1 else "ok")
