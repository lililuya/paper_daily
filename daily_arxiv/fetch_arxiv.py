"""arXiv 官方 API 抓取：按类别 + 提交日期窗口，分页拉取当日新论文。"""

import json
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from .config import ARXIV_LOOKBACK_DAYS, ARXIV_PAGE_SIZE, ARXIV_RATE_LIMIT_SECONDS, CATEGORIES

ARXIV_API = "https://export.arxiv.org/api/query"
ARXIV_API_FALLBACK = "https://arxiv.org/api/query"
ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/atom+xml, text/xml, application/xml, */*",
    "Accept-Language": "en-US,en;q=0.9",
}
CURL_BIN = shutil.which("curl")


def _get_urllib(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "ignore")


def _get_curl(url: str) -> str:
    """curl 回退：arXiv 对 Python urllib 的 TLS 指纹返回 406，curl 可通过。"""
    if not CURL_BIN:
        raise RuntimeError("curl 不可用")
    cmd = [
        CURL_BIN, "-sS", "--fail", "-m", "60", "--compressed",
        "-A", HEADERS["User-Agent"],
        "-H", f"Accept: {HEADERS['Accept']}",
        "-H", f"Accept-Language: {HEADERS['Accept-Language']}",
        url,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError(f"curl exit={r.returncode}: {r.stderr[:120]}")
    return r.stdout


def _get(url: str, retries: int = 3) -> str:
    """每轮先试 urllib，失败换 curl，再失败换备用端点。"""
    last_err = None
    for attempt in range(retries):
        u = url if attempt % 2 == 0 else url.replace(ARXIV_API, ARXIV_API_FALLBACK)
        for fetcher, name in ((_get_urllib, "urllib"), (_get_curl, "curl")):
            try:
                return fetcher(u)
            except Exception as e:
                last_err = e
                print(f"  [arxiv] {name} 请求失败({e})", flush=True)
        if attempt < retries - 1:
            wait = 10 * (attempt + 1)
            print(f"  [arxiv] {wait}s 后进入第 {attempt + 2}/{retries} 轮重试", flush=True)
            time.sleep(wait)
    raise last_err  # pragma: no cover


def _parse_entry(entry) -> dict:
    raw_id = entry.findtext(f"{ATOM_NS}id", "").replace("http://arxiv.org/abs/", "")
    m = re.match(r"(.+?)v\d+$", raw_id)
    arxiv_id = m.group(1) if m else raw_id
    title = " ".join(entry.findtext(f"{ATOM_NS}title", "").split())
    summary = " ".join(entry.findtext(f"{ATOM_NS}summary", "").split())
    authors = [a.findtext(f"{ATOM_NS}name", "") for a in entry.findall(f"{ATOM_NS}author")]
    categories = [c.get("term", "") for c in entry.findall(f"{ATOM_NS}category")]
    pdf_url = ""
    for link in entry.findall(f"{ATOM_NS}link"):
        if link.get("title") == "pdf":
            pdf_url = link.get("href", "")
    return {
        "id": arxiv_id,
        "title": title,
        "authors": authors,
        "abstract": summary,
        "categories": categories,
        "url": f"https://arxiv.org/abs/{arxiv_id}",
        "pdf_url": pdf_url,
        "source": "arxiv",
    }


def fetch_arxiv(papers_by_id: dict) -> dict:
    """抓取近 N 天提交的指定类别论文，合并进 papers_by_id（以 id 去重）。"""
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=ARXIV_LOOKBACK_DAYS)).strftime("%Y%m%d0000")
    end = now.strftime("%Y%m%d2359")
    cat_query = " OR ".join(f"cat:{c}" for c in CATEGORIES)
    query = f"({cat_query}) AND submittedDate:[{start} TO {end}]"

    total_new = 0
    start_idx = 0
    while True:
        params = urllib.parse.urlencode({
            "search_query": query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": ARXIV_PAGE_SIZE,
            "start": start_idx,
        })
        xml_text = _get(f"{ARXIV_API}?{params}")
        root = ET.fromstring(xml_text)
        entries = root.findall(f"{ATOM_NS}entry")
        if not entries:
            break
        for entry in entries:
            p = _parse_entry(entry)
            if p["id"] and p["id"] not in papers_by_id:
                papers_by_id[p["id"]] = p
                total_new += 1
        print(f"  [arxiv] 已抓取 {start_idx + len(entries)} 篇（新增 {total_new}）", flush=True)
        if len(entries) < ARXIV_PAGE_SIZE:
            break
        start_idx += ARXIV_PAGE_SIZE
        time.sleep(ARXIV_RATE_LIMIT_SECONDS)

    print(f"[arxiv] 完成，共新增 {total_new} 篇", flush=True)
    return papers_by_id


if __name__ == "__main__":
    out = {}
    fetch_arxiv(out)
    print(json.dumps(list(out.values())[:2], ensure_ascii=False, indent=2)[:2000])
    print(f"total: {len(out)}", file=sys.stderr)
