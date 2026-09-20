"""技术博客抓取：解析各家 RSS 2.0 / Atom 源，去重后交给 LLM 生成中文导读。

只用标准库（urllib + xml.etree），与项目其余部分保持一致：
- 零第三方依赖，GitHub Actions 上不需要 pip install
- 单个源失败不影响其他源（并发抓取，异常隔离）
- 用 seen_blogs.json 记录已抓过的文章 id，避免重复进入日报
"""

import email.utils
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

sys.path.insert(0, __file__.rsplit("\\daily_arxiv\\", 1)[0].rsplit("/daily_arxiv/", 1)[0])

from daily_arxiv.config import (  # noqa: E402
    BLOG_ENABLED,
    BLOG_FETCH_WORKERS,
    BLOG_LOOKBACK_DAYS,
    BLOG_MAX_ENTRIES_PER_FEED,
    BLOG_MAX_ITEMS,
    BLOG_MAX_PER_SITE,
    BLOG_PAGE_LIMIT,
    BLOG_PAGE_SUMMARY_MIN,
    BLOG_PAGE_WORKERS,
    BLOG_SUMMARY_CHARS,
    INTERESTS,
    SEEN_BLOGS_FILE,
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

ATOM = "{http://www.w3.org/2005/Atom}"
TAG_RE = re.compile(r"<[^>]+>")
DROP_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
BLOCK_BREAK_RE = re.compile(r"<br\s*/?>|</p>|</div>|</li>", re.I)
SPACE_RE = re.compile(r"[ \t\u00a0]+")


# ---------------------------------------------------------------- 工具函数

def _clean_html(raw: str) -> str:
    """把 feed 里的 HTML 正文压成纯文本（保留段落换行）。"""
    if not raw:
        return ""
    s = DROP_RE.sub(" ", raw)
    s = BLOCK_BREAK_RE.sub("\n", s)
    s = TAG_RE.sub(" ", s)
    s = html.unescape(s)
    s = SPACE_RE.sub(" ", s)
    s = re.sub(r"\n\s*\n\s*\n+", "\n\n", s)
    return s.strip()


def _strip_duplicated_lead(text: str) -> str:
    """部分源（如 NVIDIA）会把「截断的摘要开头 + 完整正文」拼在一起，去掉重复的开头。

    判断方式：首段前 60 字若在后文原样出现，说明首段是重复的引导语，丢弃它。
    """
    parts = [p for p in text.split("\n\n") if p.strip()]
    if len(parts) < 2 or len(parts[0].strip()) < 40:
        return text
    probe = parts[0].strip()[:60]
    if probe and probe in "\n\n".join(parts[1:]):
        return "\n\n".join(parts[1:])
    return text


def _parse_date(raw: str) -> datetime | None:
    """兼容 RFC 822（RSS）与 ISO 8601（Atom / 各大静态站）两种日期格式。"""
    if not raw:
        return None
    s = raw.strip()
    try:
        dt = email.utils.parsedate_to_datetime(s)
        if dt:
            return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError, IndexError):
        pass
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    return None


def _text(el) -> str:
    """取元素文本（含 CDATA 已由 ElementTree 处理）。"""
    if el is None:
        return ""
    return (el.text or "").strip()


def _entry_link(entry) -> str:
    """RSS 的 <link>text</link> 与 Atom 的 <link rel=alternate href=...> 统一取第一个可用链接。"""
    link = entry.find("link")
    if link is not None and (link.text or "").strip():
        return link.text.strip()
    for link in entry.findall(f"{ATOM}link"):
        rel = link.get("rel") or "alternate"
        if rel == "alternate" and link.get("href"):
            return link.get("href").strip()
    for link in entry.findall(f"{ATOM}link"):
        if link.get("href"):
            return link.get("href").strip()
    return ""


def _article_id(feed_key: str, url: str) -> str:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    return f"blog:{feed_key}:{digest}"


def load_seen() -> dict:
    if not os.path.exists(SEEN_BLOGS_FILE):
        return {}
    try:
        with open(SEEN_BLOGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_seen(seen: dict) -> None:
    os.makedirs(os.path.dirname(SEEN_BLOGS_FILE), exist_ok=True)
    # 只保留最近 4000 条，防止文件无限增长
    if len(seen) > 4000:
        items = sorted(seen.items(), key=lambda kv: kv[1], reverse=True)[:4000]
        seen = dict(items)
    with open(SEEN_BLOGS_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=0)


# ---------------------------------------------------------------- 抓取与解析

def _fetch_feed(feed: dict) -> tuple[dict, str | None, list]:
    """抓取并解析单个源，返回 (feed, 错误信息, 文章列表)。"""
    url = feed["url"]
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=40) as r:
            raw = r.read()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError) as e:
        return feed, f"{type(e).__name__}: {e}", []

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        return feed, f"XML 解析失败: {e}", []

    entries = root.findall(".//item") or root.findall(f".//{ATOM}entry")
    if not entries:
        return feed, "未解析到条目", []

    articles = []
    for entry in entries[:BLOG_MAX_ENTRIES_PER_FEED]:
        title = _clean_html(_text(entry.find("title")) or _text(entry.find(f"{ATOM}title")))
        link = _entry_link(entry)
        if not (title and link):
            continue

        date_raw = (
            _text(entry.find("pubDate"))
            or _text(entry.find("published"))
            or _text(entry.find(f"{ATOM}published"))
            or _text(entry.find(f"{ATOM}updated"))
            or _text(entry.find("updated"))
        )
        published = _parse_date(date_raw)

        body = (
            _text(entry.find("description"))
            or _text(entry.find(f"{ATOM}summary"))
            or _text(entry.find("summary"))
        )
        content = ""
        for tag in ("encoded", f"{ATOM}content", "content"):
            node = entry.find(tag) if tag.startswith("{") else entry.find(tag)
            if node is None:
                # 处理 content:encoded 这类带命名空间的标签
                for child in entry:
                    if child.tag.endswith("}encoded") or child.tag.endswith("}content"):
                        node = child
                        break
            if node is not None and (node.text or "").strip():
                content = _text(node)
                break

        text_body = _clean_html(content) or _clean_html(body)
        if len(text_body) < 40:  # 正文太短说明 feed 只给了标题，退回用 description
            text_body = _clean_html(body) or text_body
        text_body = _strip_duplicated_lead(text_body)

        author = (
            _text(entry.find("author"))
            or _text(entry.find(f"{ATOM}author/{ATOM}name"))
            or ""
        )

        articles.append({
            "id": _article_id(feed["key"], link),
            "type": "blog",
            "title": title,
            "url": link,
            "site": feed["name"],
            "site_key": feed["key"],
            "author": author,
            "published": published.isoformat() if published else "",
            "summary": text_body[:BLOG_SUMMARY_CHARS],
            "feed_date_raw": date_raw,
        })
    return feed, None, articles


# ---------------------------------------------------------------- 页面摘要回退

META_PATTERNS = (
    r'<meta[^>]+property=["\']og:description["\'][^>]*?content=["\']([^"\']*)["\']',
    r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*?property=["\']og:description["\']',
    r'<meta[^>]+name=["\']description["\'][^>]*?content=["\']([^"\']*)["\']',
    r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*?name=["\']description["\']',
)


def _fetch_page_summary(url: str) -> str:
    """抓文章页，取 og:description / meta description。

    HuggingFace 的 feed 只有标题和链接、DeepMind 的 description 是空标签，
    这类源必须回退到页面才能拿到正文，否则 LLM 无从摘要。
    """
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=25) as r:
            page = r.read().decode("utf-8", "ignore")
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError):
        return ""
    for pat in META_PATTERNS:
        m = re.search(pat, page, re.I | re.S)
        if m and m.group(1).strip():
            return _clean_html(html.unescape(m.group(1)))
    return ""


def fill_missing_summaries(articles: list) -> int:
    """为摘要缺失或过短的文章回退抓取页面描述，返回补全的篇数。"""
    targets = [a for a in articles if len(a.get("summary") or "") < BLOG_PAGE_SUMMARY_MIN]
    if not targets:
        return 0
    targets = targets[:BLOG_PAGE_LIMIT]
    print(f"[blog] {len(targets)} 篇缺少正文摘要，回退抓取文章页…", flush=True)
    filled = 0
    with ThreadPoolExecutor(max_workers=BLOG_PAGE_WORKERS) as pool:
        futures = {pool.submit(_fetch_page_summary, a["url"]): a for a in targets}
        for fut in as_completed(futures):
            art = futures[fut]
            text = fut.result()
            if text:
                art["summary"] = text[:BLOG_SUMMARY_CHARS]
                art["summary_from"] = "page"
                filled += 1
    print(f"[blog] 页面回退补全 {filled}/{len(targets)} 篇", flush=True)
    return filled


# ---------------------------------------------------------------- 打分

def score_article(article: dict) -> dict:
    """复用论文的关键词表给文章打方向标签与相关度分（仅用于排序，不做淘汰）。"""
    title = (article.get("title") or "").lower()
    body = (article.get("summary") or "").lower()
    total = 0.0
    matched = []
    for direction, cfg in INTERESTS.items():
        d_score = 0
        for kw in cfg["keywords"]:
            k = kw.lower()
            d_score += min(title.count(k), 1) * 3 + min(body.count(k), 2)
        if d_score > 0:
            total += min(d_score, 12) * cfg["weight"]
            matched.append(direction)
    article["score"] = round(total, 1)
    article["matched_directions"] = matched
    article["tags"] = matched[:3]
    return article


# ---------------------------------------------------------------- 主入口

def fetch_blogs() -> list:
    """抓取全部源，返回 lookback 窗口内、未见过的新文章（按发布时间倒序）。"""
    if not BLOG_ENABLED:
        print("[blog] 已通过 BLOG_ENABLED=0 关闭", flush=True)
        return []

    from daily_arxiv.config import BLOG_FEEDS

    seen = load_seen()
    cutoff = datetime.now(timezone.utc) - timedelta(days=BLOG_LOOKBACK_DAYS)
    now_iso = datetime.now(timezone.utc).isoformat()

    print(f"[blog] 并发={BLOG_FETCH_WORKERS}，抓取 {len(BLOG_FEEDS)} 个博客源…", flush=True)
    all_articles, errors = [], []
    with ThreadPoolExecutor(max_workers=BLOG_FETCH_WORKERS) as pool:
        futures = {pool.submit(_fetch_feed, f): f for f in BLOG_FEEDS}
        for fut in as_completed(futures):
            feed, err, articles = fut.result()
            if err:
                errors.append((feed["name"], err))
                continue
            all_articles.extend(articles)

    fresh = []
    for a in all_articles:
        if a["id"] in seen:
            continue
        dt = _parse_date(a.get("feed_date_raw") or "")
        if dt and dt < cutoff:
            continue  # 太旧的文章不入选（但仍会在下轮被 seen 之外的逻辑跳过）
        if not a["published"]:
            a["published"] = now_iso  # 少数源不给日期，按抓取时间处理
        fresh.append(score_article(a))

    fresh.sort(key=lambda a: a["published"], reverse=True)
    for name, err in errors:
        print(f"  [blog] {name} 抓取失败：{err[:90]}", flush=True)

    total = len(fresh)
    fresh = select_top(fresh, BLOG_MAX_ITEMS)
    if fill_missing_summaries(fresh):
        for a in fresh:  # 补全正文后重新打分，方向标签才准确
            score_article(a)
    print(
        f"[blog] 完成：{len(all_articles)} 篇候选，{total} 篇为新文章，"
        f"取 {len(fresh)} 篇进入增强（{len(errors)} 个源失败）",
        flush=True,
    )
    return fresh


def mark_seen(articles: list, seen: dict | None = None) -> dict:
    """把文章写入 seen 记录，返回更新后的 dict。"""
    seen = seen if seen is not None else load_seen()
    for a in articles:
        seen[a["id"]] = a.get("published") or datetime.now(timezone.utc).isoformat()
    return seen


def select_top(articles: list, max_n: int) -> list:
    """按上限截取：新文章优先，同时限制单源篇数，避免高产博客（如 Simon Willison）霸榜。"""
    if len(articles) <= max_n:
        return articles

    picked, overflow, per_site = [], [], {}
    for a in articles:  # articles 已按发布时间倒序
        key = a["site_key"]
        if per_site.get(key, 0) < BLOG_MAX_PER_SITE:
            picked.append(a)
            per_site[key] = per_site.get(key, 0) + 1
        else:
            overflow.append(a)

    # 名额没用满时，用溢出的文章按相关度+时间补齐，最大限度保留关于关注方向的内容
    if len(picked) < max_n:
        overflow.sort(key=lambda a: (a.get("score", 0), a["published"]), reverse=True)
        picked.extend(overflow[: max_n - len(picked)])
    picked = picked[:max_n]
    picked.sort(key=lambda a: a["published"], reverse=True)
    print(
        f"[blog] 候选 {len(articles)} 篇超过上限 {max_n}，"
        f"每源限 {BLOG_MAX_PER_SITE} 篇后取 {len(picked)} 篇",
        flush=True,
    )
    return picked


if __name__ == "__main__":
    arts = fetch_blogs()
    print(json.dumps(arts[:2], ensure_ascii=False, indent=2)[:1600])
    time.sleep(0)
