"""前研技术追踪 - 每日流水线入口。

用法:
    python run_pipeline.py                # 抓今天的，正常跑（需 OPENAI_API_KEY）
    python run_pipeline.py --dry-run      # 不调用 LLM，仅规则打分
    python run_pipeline.py --date 2026-09-17
    python run_pipeline.py --no-dedup     # 忽略历史去重（调试用）

流水线: arXiv 抓取 + HF Daily Papers -> 去重 -> 规则打分 -> LLM 增强 -> Markdown 日报
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai.enhance import enhance  # noqa: E402
from daily_arxiv.config import DATA_DIR, FILE_LIST, MAX_LLM_PAPERS  # noqa: E402
from daily_arxiv.dedup import dedup, save_seen_ids  # noqa: E402
from daily_arxiv.fetch_arxiv import fetch_arxiv  # noqa: E402
from daily_arxiv.fetch_hf import fetch_hf  # noqa: E402
from daily_arxiv.fetch_kimi import fetch_kimi  # noqa: E402
from daily_arxiv.score import score_and_filter, select_balanced  # noqa: E402
from to_md.convert import convert  # noqa: E402


def beijing_today() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")


def update_file_list() -> None:
    os.makedirs(os.path.dirname(FILE_LIST), exist_ok=True)
    files = sorted(
        f for f in os.listdir(DATA_DIR) if f.endswith(".jsonl")
    )
    with open(FILE_LIST, "w", encoding="utf-8") as f:
        f.write("\n".join(files))


def merge_with_existing(jsonl_path: str, new_papers: list) -> list:
    """同日重复运行时把新论文并入已有日报，避免覆盖已发布内容。

    规则：
    - 已有条目一律保留（沿用其 LLM 增强与 Kimi 解读，不重复花钱）；
    - 新增论文按原顺序补足到 MAX_LLM_PAPERS 上限，超出部分丢弃；
    - 合并后按分数降序，保证日报顺序稳定。
    """
    if not os.path.exists(jsonl_path):
        return new_papers

    old = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                old.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if not old:
        return new_papers

    old_ids = {p.get("id") for p in old}
    room = max(0, MAX_LLM_PAPERS - len(old))
    added = [p for p in new_papers if p.get("id") not in old_ids][:room]
    print(
        f"[merge] 同日已有 {len(old)} 篇，新增 {len(added)} 篇（上限 {MAX_LLM_PAPERS}）",
        flush=True,
    )
    merged = old + added
    merged.sort(key=lambda p: (p.get("score", 0), p.get("hf_upvotes", 0)), reverse=True)
    return merged


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=beijing_today(), help="日报日期 YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="不调用 LLM")
    parser.add_argument("--no-dedup", action="store_true", help="跳过历史去重")
    args = parser.parse_args()

    print(f"===== 前研追踪流水线 {args.date} {'(dry-run)' if args.dry_run else ''} =====", flush=True)

    # 1. 抓取
    papers_by_id = {}
    fetch_arxiv(papers_by_id)
    fetch_hf(papers_by_id)
    all_papers = list(papers_by_id.values())
    if not all_papers:
        print("未抓到任何论文，退出", flush=True)
        return 1

    # 2. 去重
    if args.no_dedup:
        fresh, new_seen = all_papers, set()
        print(f"[dedup] 跳过（--no-dedup），共 {len(fresh)} 篇", flush=True)
    else:
        fresh, new_seen = dedup(all_papers)
        if not fresh:
            print("去重后无新论文，跳过今日日报", flush=True)
            return 0

    # 3. 打分过滤 + 核心方向配额选取
    kept, _ = score_and_filter(fresh)
    candidates = select_balanced(kept, MAX_LLM_PAPERS)

    # 4. LLM 增强
    enhanced = enhance(candidates, dry_run=args.dry_run)

    # 5. papers.cool Kimi 摘要（可选，可能很慢）
    fetch_kimi(enhanced)

    # 6. 存档 JSONL + 生成 Markdown（同日重跑与已有数据合并，不覆盖已发布内容）
    os.makedirs(DATA_DIR, exist_ok=True)
    jsonl_path = os.path.join(DATA_DIR, f"{args.date}.jsonl")
    merged = merge_with_existing(jsonl_path, enhanced)
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for p in merged:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    convert(args.date, merged, stats={"total": len(all_papers)})

    # 7. 更新 seen_ids 和文件列表
    if not args.no_dedup:
        save_seen_ids(new_seen)
    update_file_list()

    print(f"===== 完成：{len(enhanced)} 篇精选 / {len(all_papers)} 篇抓取 =====", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
