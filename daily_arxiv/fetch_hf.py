"""Hugging Face Daily Papers 抓取：解析官方页面内嵌的 data-props JSON。"""

import html
import json
import re
import time
import urllib.request

HF_PAPERS_URL = "https://huggingface.co/papers"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def _get(url: str, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:
            if attempt == retries - 1:
                raise
            print(f"  [hf] 请求失败({e})，重试 {attempt + 2}/{retries}", flush=True)
            time.sleep(10 * (attempt + 1))


def fetch_hf(papers_by_id: dict) -> dict:
    """抓取 HF Daily Papers 精选论文，合并进 papers_by_id（以 arXiv id 去重）。

    已存在于 papers_by_id 的论文仅标记 hf_upvotes / source=hf_daily。
    """
    page = _get(HF_PAPERS_URL)
    daily = None
    for m in re.finditer(r'data-props="([^"]+)"', page):
        try:
            d = json.loads(html.unescape(m.group(1)))
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and "dailyPapers" in d:
            daily = d
            break
    if daily is None:
        print("[hf] 未找到 dailyPapers 数据块，跳过", flush=True)
        return papers_by_id

    new_count = 0
    merge_count = 0
    for item in daily.get("dailyPapers", []):
        paper = item.get("paper", {})
        pid = (paper.get("id") or "").strip()
        if not pid:
            continue
        title = paper.get("title", "")
        authors = [a.get("name", "") for a in paper.get("authors", []) if isinstance(a, dict)]
        upvotes = paper.get("upvotes", 0) or 0
        if pid in papers_by_id:
            papers_by_id[pid]["hf_upvotes"] = upvotes
            papers_by_id[pid]["source"] = "arxiv+hf"
            merge_count += 1
            continue
        papers_by_id[pid] = {
            "id": pid,
            "title": title,
            "authors": authors,
            "abstract": paper.get("summary", ""),
            "categories": [],
            "url": f"https://arxiv.org/abs/{pid}",
            "pdf_url": f"https://arxiv.org/pdf/{pid}",
            "source": "hf_daily",
            "hf_upvotes": upvotes,
        }
        new_count += 1

    print(f"[hf] 完成：新增 {new_count} 篇，标记社区精选 {merge_count} 篇", flush=True)
    return papers_by_id


if __name__ == "__main__":
    out = {}
    fetch_hf(out)
    print(json.dumps(list(out.values())[:1], ensure_ascii=False, indent=2)[:1500])
