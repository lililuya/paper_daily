"""papers.cool Kimi 摘要抓取（可选）。

调用 POST https://papers.cool/arxiv/kimi?paper={arxiv_id}
返回 HTML，包含 faq-q（问题）和 faq-a（答案）配对。
并发数与超时可通过环境变量调整。
"""

import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, __file__.rsplit("\\daily_arxiv\\", 1)[0].rsplit("/daily_arxiv/", 1)[0])

from daily_arxiv.config import (  # noqa: E402
    PAPERS_COOL_FETCH,
    PAPERS_COOL_RETRIES,
    PAPERS_COOL_RETRY_WAIT,
    PAPERS_COOL_TIMEOUT,
    PAPERS_COOL_WORKERS,
)

HEADERS_BASE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
}
PA_FAQ_Q = re.compile(r'<p\s+class="faq-q">\s*<strong>Q\d+</strong>:\s*([^<]+)</p>', re.S)
PA_FAQ_A = re.compile(r'<div\s+class="faq-a">\s*(.*?)\s*</div>', re.S)


def _fetch_one(arxiv_id: str, deadline: float | None = None) -> tuple[str, list]:
    """返回 (arxiv_id, [(q, a_md), ...])。qa 列表为空表示抓取失败。

    papers.cool 的 Kimi 生成串行排队：未缓存论文常先返回 HTTP 错误（忙），
    稍后重试可排进生成位（生成需 2-6 分钟）。deadline 为整体时间预算截止戳。
    """
    url = f"https://papers.cool/arxiv/kimi?paper={arxiv_id}"
    headers = {**HEADERS_BASE, "Referer": f"https://papers.cool/arxiv/{arxiv_id}"}
    start = time.time()
    html = ""
    for attempt in range(PAPERS_COOL_RETRIES):
        if deadline is not None and time.time() > deadline:
            print(f"  [kimi] {arxiv_id} 时间预算用尽，放弃 ({time.time()-start:.0f}s)", flush=True)
            return arxiv_id, []
        try:
            req = urllib.request.Request(url, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=PAPERS_COOL_TIMEOUT) as r:
                html = r.read().decode("utf-8", "ignore")
            break
        except urllib.error.HTTPError as e:
            if attempt < PAPERS_COOL_RETRIES - 1:
                time.sleep(PAPERS_COOL_RETRY_WAIT)
                continue
            print(f"  [kimi] {arxiv_id} 失败：HTTP {e.code} ({time.time()-start:.0f}s)", flush=True)
            return arxiv_id, []
        except Exception as e:  # noqa: BLE001
            if attempt < PAPERS_COOL_RETRIES - 1:
                time.sleep(PAPERS_COOL_RETRY_WAIT)
                continue
            print(f"  [kimi] {arxiv_id} 失败：{type(e).__name__} ({time.time()-start:.0f}s)", flush=True)
            return arxiv_id, []
    elapsed = time.time() - start
    qs = [(m.start(), m.group(1).strip()) for m in PA_FAQ_Q.finditer(html)]
    pairs = []
    for i, (qpos, qtext) in enumerate(qs):
        next_qpos = qs[i + 1][0] if i + 1 < len(qs) else len(html)
        a_match = PA_FAQ_A.search(html, qpos, next_qpos)
        if a_match:
            pairs.append((qtext, _html_to_md(a_match.group(1))))
    print(f"  [kimi] {arxiv_id} ✓ {len(pairs)} 组 Q&A ({elapsed:.0f}s)", flush=True)
    return arxiv_id, pairs


def _html_to_md(s: str) -> str:
    # 极简 HTML -> 文本：保留段落与列表，去除标签
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"</p>\s*<p>", "\n\n", s)
    s = re.sub(r"<p[^>]*>", "", s)
    s = re.sub(r"</p>", "", s)
    s = re.sub(r"<li[^>]*>", "• ", s)
    s = re.sub(r"</li>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"&nbsp;", " ", s)
    s = re.sub(r"&lt;", "<", s)
    s = re.sub(r"&gt;", ">", s)
    s = re.sub(r"&amp;", "&", s)
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    return s


def fetch_kimi(papers: list, budget_seconds: int | None = None) -> int:
    """为每篇论文抓取 Kimi Q&A 摘要，结果写入 paper['kimi_qa']。返回成功篇数。

    budget_seconds：整体时间预算（秒），超时后不再发起新的重试轮。
    """
    if not PAPERS_COOL_FETCH:
        print("[kimi] 已通过 PAPERS_COOL_FETCH=0 关闭", flush=True)
        return 0
    if not papers:
        return 0
    deadline = (time.time() + budget_seconds) if budget_seconds else None
    budget_note = f"，预算 {budget_seconds}s" if budget_seconds else ""
    print(f"[kimi] 并发={PAPERS_COOL_WORKERS}，抓取 {len(papers)} 篇{budget_note}...", flush=True)
    for p in papers:
        p.setdefault("kimi_qa", [])
    ok = 0
    with ThreadPoolExecutor(max_workers=PAPERS_COOL_WORKERS) as pool:
        futures = {pool.submit(_fetch_one, p["id"], deadline): p for p in papers}
        for fut in as_completed(futures):
            paper = futures[fut]
            try:
                _id, qa = fut.result()
                paper["kimi_qa"] = qa
                if qa:
                    ok += 1
            except Exception as e:  # noqa: BLE001
                print(f"  [kimi] {paper['id']} 异常：{e}", flush=True)
    print(f"[kimi] 完成：成功 {ok}/{len(papers)}", flush=True)
    return ok


if __name__ == "__main__":
    test = [{"id": "2609.18326"}]
    fetch_kimi(test)
    print(test)