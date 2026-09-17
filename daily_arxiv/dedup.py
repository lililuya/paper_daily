"""去重：维护历史已见论文 ID 库（data/seen_ids.json），过滤老论文。"""

import json
import os

from .config import DATA_DIR, SEEN_IDS_FILE


def load_seen_ids() -> set:
    if not os.path.exists(SEEN_IDS_FILE):
        return set()
    try:
        with open(SEEN_IDS_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    except (json.JSONDecodeError, OSError):
        return set()


def save_seen_ids(seen: set) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SEEN_IDS_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, ensure_ascii=False, indent=0)


def dedup(papers: list) -> tuple[list, set]:
    """返回（新论文列表, 更新后的完整 seen 集合）。不落盘，由调用方决定何时 save。"""
    seen = load_seen_ids()
    fresh = [p for p in papers if p["id"] not in seen]
    fresh_ids = {p["id"] for p in fresh}
    print(f"[dedup] 输入 {len(papers)} 篇，历史已见 {len(seen)} 篇，本次新增 {len(fresh)} 篇", flush=True)
    return fresh, seen | fresh_ids
