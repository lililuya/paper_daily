"""LLM 增强：调用 OpenAI 兼容接口（DeepSeek），为每篇候选论文生成中文摘要、
亮点、方向标签与推荐指数。无 API Key 时自动降级为 dry-run（仅规则打分）。
"""

import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from daily_arxiv.config import (  # noqa: E402
    DEEP_SUMMARY_RATING,
    INTERESTS,
    MAX_LLM_PAPERS,
    MODEL_NAME,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
)

SYSTEM_PROMPT = (
    "你是一位前沿 AI 研究分析师，每天为中文读者筛选和解读最新论文。"
    "读者关注的方向（按优先级）：" + "、".join(INTERESTS.keys()) + "。"
    "请对给定论文输出 JSON：\n"
    '{"title_zh": "准确通顺的中文标题", '
    '"oneline_zh": "一句话中文摘要(不超过60字，讲清楚做了什么、效果如何)", '
    '"summary_zh": "150-250字中文详细摘要，突出方法与结论", '
    '"highlights": ["研究亮点1", "研究亮点2"], '
    '"tags": ["1-3个中文方向标签"], '
    '"rating": 1-5的整数推荐指数}\n'
    "评分标准：5=该方向重大突破或必读工作；4=有显著贡献值得精读；"
    "3=扎实的增量工作；2=与读者方向关系不大；1=无关或低质量。"
    "严格只输出 JSON。"
)


def _chat(messages: list, retries: int = 4) -> dict:
    payload = json.dumps({
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 1200,
        "response_format": {"type": "json_object"},
    }).encode()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions",
                data=payload, headers=headers, method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read().decode())
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception as e:  # noqa: BLE001
            last_err = e
            wait = 5 * (attempt + 1)
            print(f"  [ai] 调用失败({e})，{wait}s 后重试 {attempt + 2}/{retries}", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"LLM 调用最终失败: {last_err}")


def _rating_from_score(paper: dict) -> int:
    """dry-run 降级：根据规则分和社区热度估算推荐指数。"""
    score = paper.get("score", 0)
    upvotes = paper.get("hf_upvotes", 0)
    if upvotes >= 40 or score >= 40:
        return 5
    if upvotes >= 15 or score >= 25:
        return 4
    if score >= 12:
        return 3
    return 2


def enhance(papers: list, dry_run: bool = False) -> list:
    """对候选论文做 LLM 增强（列表应已按 score 降序）。返回增强后的列表。"""
    candidates = papers[:MAX_LLM_PAPERS]
    if not dry_run and not OPENAI_API_KEY:
        print("[ai] 未配置 OPENAI_API_KEY，自动降级为 dry-run 模式", flush=True)
        dry_run = True

    if dry_run:
        print(f"[ai] dry-run：{len(candidates)} 篇仅用规则打分，不调用 LLM", flush=True)
        for p in candidates:
            p["title_zh"] = p["title"]
            # oneline 留空：abstract 已完整展示，不再重复首句
            p["oneline_zh"] = ""
            p["summary_zh"] = ""
            p["highlights"] = p.get("matched_directions", [])[:2]
            p["tags"] = p.get("matched_directions", [])[:3]
            p["rating"] = _rating_from_score(p)
        return candidates

    ok, fail = 0, 0
    for i, p in enumerate(candidates, 1):
        user_msg = (
            f"标题: {p['title']}\n摘要: {p['abstract']}\n"
            f"arXiv类别: {', '.join(p.get('categories', []) or [])}\n"
            f"社区点赞数: {p.get('hf_upvotes', 0)}\n"
            f"规则匹配方向: {', '.join(p.get('matched_directions', []))}"
        )
        try:
            result = _chat([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ])
        except RuntimeError:
            fail += 1
            p["rating"] = _rating_from_score(p)
            p["title_zh"] = p["title"]
            p["oneline_zh"] = ""
            p["summary_zh"] = ""
            p["highlights"] = []
            p["tags"] = p.get("matched_directions", [])[:3]
            continue
        p["title_zh"] = result.get("title_zh") or p["title"]
        p["oneline_zh"] = result.get("oneline_zh") or ""
        rating = result.get("rating")
        p["rating"] = rating if isinstance(rating, int) and 1 <= rating <= 5 else _rating_from_score(p)
        if p["rating"] >= DEEP_SUMMARY_RATING:
            p["summary_zh"] = result.get("summary_zh") or ""
            p["highlights"] = [h for h in (result.get("highlights") or []) if h][:3]
        else:
            p["summary_zh"] = ""
            p["highlights"] = []
        p["tags"] = [t for t in (result.get("tags") or []) if t][:3]
        ok += 1
        if i % 10 == 0 or i == len(candidates):
            print(f"  [ai] 进度 {i}/{len(candidates)}（成功 {ok}，失败 {fail}）", flush=True)
        time.sleep(0.5)

    print(f"[ai] 完成：成功 {ok}，失败 {fail}", flush=True)
    return candidates


if __name__ == "__main__":
    test = [{
        "id": "2609.00001", "title": "Test Paper", "authors": ["A"],
        "abstract": "A test abstract about video generation.", "categories": ["cs.CV"],
        "score": 10, "matched_directions": ["视频生成"], "hf_upvotes": 0,
    }]
    print(json.dumps(enhance(test), ensure_ascii=False, indent=2)[:1500])
