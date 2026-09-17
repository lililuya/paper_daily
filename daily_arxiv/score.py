"""规则打分：按兴趣关键词加权表给论文打分，筛选出值得 LLM 增强的候选。

防失衡设计：
1. 关键词命中封顶 —— 标题每个关键词最多计 1 次、摘要最多计 2 次，
   避免某词在摘要中反复出现导致分数爆炸（如 "agent" 出现 20 次）。
2. 单方向贡献封顶 —— 每个方向对总分的贡献有上限，避免通用词方向霸榜。
3. 核心方向配额 —— select_balanced 对三大核心方向轮询选取，
   保证图像编辑 / 视频模型 / Agent 在日报中都有足够篇幅。
"""

from .config import CORE_DIRECTIONS, INTERESTS, SCORE_THRESHOLD


def _count_hits(text: str, keyword: str, cap: int) -> int:
    return min(text.count(keyword), cap)


def score_paper(paper: dict) -> dict:
    title = (paper.get("title") or "").lower()
    abstract = (paper.get("abstract") or "").lower()
    total = 0.0
    matched = []
    for direction, cfg in INTERESTS.items():
        d_score = 0
        t_total = 0
        a_total = 0
        for kw in cfg["keywords"]:
            k = kw.lower()
            t = _count_hits(title, k, 1)
            a = _count_hits(abstract, k, 2)
            if t or a:
                d_score += t * 3 + a
                t_total += t
                a_total += a
        # 方向成立条件：标题命中过关键词，或摘要累计命中 >=3（单次擦边不算，防误报）
        if d_score > 0 and (t_total > 0 or a_total >= 3):
            total += min(d_score, 12) * cfg["weight"]
            matched.append(direction)
    paper["score"] = round(total, 1)
    paper["matched_directions"] = matched
    # HF 社区精选保底进入候选
    if paper.get("source") in ("hf_daily", "arxiv+hf") and paper.get("hf_upvotes", 0) >= 10:
        paper["score"] = max(paper["score"], SCORE_THRESHOLD + 1)
        if "HF精选" not in paper["matched_directions"]:
            paper["matched_directions"].append("HF精选")
    return paper


def score_and_filter(papers: list) -> tuple[list, int]:
    """打分并返回（达到门槛的论文按分数降序, 被过滤数量）。"""
    scored = [score_paper(p) for p in papers]
    kept = [p for p in scored if p["score"] >= SCORE_THRESHOLD]
    kept.sort(key=lambda p: (p["score"], p.get("hf_upvotes", 0)), reverse=True)
    print(f"[score] {len(scored)} 篇打分，{len(kept)} 篇达到门槛(>={SCORE_THRESHOLD}分)", flush=True)
    return kept, len(scored) - len(kept)


def _primary_direction(paper: dict) -> str:
    """论文的主核心方向：按 CORE_DIRECTIONS 优先级取第一个命中的。"""
    matched = paper.get("matched_directions", [])
    for d in CORE_DIRECTIONS:
        if d in matched:
            return d
    return ""


def select_balanced(papers: list, max_n: int) -> list:
    """三大核心方向轮询配额选取，保证每个方向都有曝光，剩余按总分补齐。"""
    buckets = {d: [] for d in CORE_DIRECTIONS}
    rest = []
    for p in papers:  # papers 已按分数降序
        d = _primary_direction(p)
        if d:
            buckets[d].append(p)
        else:
            rest.append(p)

    counts = {d: len(v) for d, v in buckets.items()}
    print(f"[score] 核心方向候选量：{counts}，其余 {len(rest)} 篇", flush=True)

    selected = []
    idx = {d: 0 for d in CORE_DIRECTIONS}
    # 轮询：每轮从每个核心方向取 1 篇
    while len(selected) < max_n:
        picked = False
        for d in CORE_DIRECTIONS:
            if len(selected) >= max_n:
                break
            if idx[d] < len(buckets[d]):
                selected.append(buckets[d][idx[d]])
                idx[d] += 1
                picked = True
        if not picked:
            break
    # 剩余额度按总分补齐
    chosen_ids = {p["id"] for p in selected}
    for p in rest + [q for d in CORE_DIRECTIONS for q in buckets[d][idx[d]:]]:
        if len(selected) >= max_n:
            break
        if p["id"] not in chosen_ids:
            selected.append(p)
            chosen_ids.add(p["id"])

    print(f"[score] 配额选取 {len(selected)} 篇进入 LLM 增强", flush=True)
    return selected
