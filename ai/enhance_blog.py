"""博客中文导读：用 DeepSeek 为每篇文章生成中文标题、一句话导读、要点与推荐指数。

与论文增强（ai/enhance.py）分开，因为两者输入形态和判断标准不同：
论文看重方法与实验结果，博客看重观点、工程经验与信息价值。
关键点：明确要求 LLM 给「与 AI 前沿无关」的内容（个人生活、摄影、无关产品发布）
打 1-2 分，前端默认只展示 3 分以上，这样高产博客里的杂项不会污染日报。
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.enhance import _chat  # noqa: E402  复用 OpenAI 兼容接口调用（含重试）
from daily_arxiv.config import INTERESTS, OPENAI_API_KEY  # noqa: E402

SYSTEM_PROMPT = (
    "你是一位 AI 技术编辑，为中文读者导读前沿技术博客文章。"
    "读者关注的方向（按优先级）：" + "、".join(INTERESTS.keys()) + "。"
    "请对给定文章输出 JSON：\n"
    '{"title_zh": "准确通顺的中文标题", '
    '"oneline_zh": "一句话中文导读(不超过70字，点出文章的核心观点或结论)", '
    '"highlights": ["要点1", "要点2", "要点3"], '
    '"tags": ["1-3个中文方向标签"], '
    '"relevant": true 或 false, '
    '"rating": 1-5的整数推荐指数}\n'
    "评分标准：5=该方向必读的重磅内容（新模型/新方法/关键洞察）；"
    "4=有实质技术内容，值得精读；3=有参考价值的技术分享或行业观察；"
    "2=与读者关注方向关系不大；1=与 AI 前沿技术无关。\n"
    "重要：如果文章与 AI / 前沿技术无关（例如个人生活、摄影、与 AI 无关的产品发布），"
    "必须把 relevant 设为 false、rating 设为 1 或 2，不要勉强归到某个方向。\n"
    "严格只输出 JSON。"
)


def _rating_from_score(article: dict) -> int:
    """dry-run 降级：仅用规则分估个中间值，无法判断相关性。"""
    score = article.get("score", 0)
    if score >= 20:
        return 4
    if score > 0:
        return 3
    return 3  # 无法判断相关性时不轻易过滤，交给前端评级筛选


def _fallback(article: dict) -> None:
    article["title_zh"] = article["title"]
    article["oneline_zh"] = ""
    article["highlights"] = []
    article["rating"] = _rating_from_score(article)
    article["relevant"] = True


def enhance_blogs(articles: list, dry_run: bool = False) -> list:
    """对文章列表做 LLM 中文导读（列表应已排序）。返回增强后的列表。"""
    if not articles:
        return []

    if not dry_run and not OPENAI_API_KEY:
        print("[blog-ai] 未配置 OPENAI_API_KEY，自动降级为 dry-run", flush=True)
        dry_run = True

    if dry_run:
        print(f"[blog-ai] dry-run：{len(articles)} 篇不调用 LLM", flush=True)
        for a in articles:
            _fallback(a)
        return articles

    ok, fail = 0, 0
    for i, a in enumerate(articles, 1):
        user_msg = (
            f"站点: {a.get('site', '')}\n"
            f"标题: {a['title']}\n"
            f"发布时间: {a.get('published', '')[:10]}\n"
            f"规则匹配方向: {', '.join(a.get('matched_directions', [])) or '无'}\n"
            f"正文概要:\n{(a.get('summary') or '')[:1500]}"
        )
        try:
            result = _chat([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ])
        except RuntimeError as e:
            print(f"  [blog-ai] {a['site']} 生成失败：{e}", flush=True)
            fail += 1
            _fallback(a)
            continue

        a["title_zh"] = result.get("title_zh") or a["title"]
        a["oneline_zh"] = result.get("oneline_zh") or ""
        a["highlights"] = [h for h in (result.get("highlights") or []) if h][:3]
        a["tags"] = [t for t in (result.get("tags") or []) if t][:3] or a.get("tags", [])
        rating = result.get("rating")
        a["rating"] = rating if isinstance(rating, int) and 1 <= rating <= 5 else _rating_from_score(a)
        rel = result.get("relevant")
        a["relevant"] = rel if isinstance(rel, bool) else a["rating"] >= 3
        if not a["relevant"]:
            a["rating"] = min(a["rating"], 2)
        ok += 1
        if i % 5 == 0 or i == len(articles):
            print(f"  [blog-ai] 进度 {i}/{len(articles)}（成功 {ok}，失败 {fail}）", flush=True)
        time.sleep(0.4)

    print(f"[blog-ai] 完成：成功 {ok}，失败 {fail}", flush=True)
    return articles


if __name__ == "__main__":
    demo = [{
        "id": "blog:demo:1", "site": "Simon Willison", "title": "How To Write With An LLM",
        "published": "2026-09-17T00:00:00+00:00",
        "summary": "Thomas Ptacek on using LLMs as copyeditors, not as writing assistants.",
        "score": 10, "matched_directions": ["大语言模型"], "tags": ["大语言模型"],
    }]
    print(enhance_blogs(demo, dry_run=True)[0])
