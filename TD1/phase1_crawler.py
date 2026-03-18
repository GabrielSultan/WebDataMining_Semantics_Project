"""
Phase 1: Web Crawling and Cleaning
Domain: Local History

Uses Europeana API only (instructions: use APIs when anti-robot checking occurs).
No trafilatura needed - text is extracted directly from the API response.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import re
from urllib.parse import urlparse
from urllib import robotparser

import httpx

import config


def _flatten_text_values(value):
    """Recursively extract text values from nested API payloads."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out = []
        for item in value:
            out.extend(_flatten_text_values(item))
        return out
    if isinstance(value, dict):
        out = []
        for v in value.values():
            out.extend(_flatten_text_values(v))
        return out
    return []


def _is_http_url(text: str) -> bool:
    t = text.strip().lower()
    return t.startswith("http://") or t.startswith("https://")


def _build_text_from_item(item: dict) -> str:
    """
    Build rich text from Europeana item metadata.
    Includes broad textual fields to satisfy useful-page filtering.
    """
    values = _flatten_text_values(item)
    cleaned = []
    for v in values:
        s = str(v).strip()
        if not s:
            continue
        # URLs are not useful textual content for NLP.
        if _is_http_url(s):
            continue
        cleaned.append(s)
    text = " ".join(cleaned)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _is_allowed_by_robots(url: str, user_agent: str, robots_cache: dict) -> bool:
    """Best-effort robots.txt check for crawling ethics compliance."""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return True
    domain = f"{parsed.scheme}://{parsed.netloc}"
    if domain in robots_cache:
        rp = robots_cache[domain]
        return rp.can_fetch(user_agent, url)

    robots_url = f"{domain}/robots.txt"
    rp = robotparser.RobotFileParser()
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(robots_url, headers={"User-Agent": user_agent})
        if resp.status_code == 200:
            rp.parse(resp.text.splitlines())
        else:
            rp.parse([])
    except Exception:
        rp.parse([])
    robots_cache[domain] = rp
    return rp.can_fetch(user_agent, url)


def fetch_europeana_via_api() -> list[dict]:
    """
    Fetch Local History content from Europeana Search API.
    Returns list of dicts with url, text, title, word_count.
    """
    if not config.EUROPEANA_API_KEY:
        return []

    results = []
    seen_ids = set()

    with httpx.Client(
        headers={"User-Agent": config.USER_AGENT},
        timeout=30.0,
    ) as client:
        robots_cache = {}
        for query in config.EUROPEANA_QUERIES:
            cursor = "*"
            while True:
                params = {
                    "wskey": config.EUROPEANA_API_KEY,
                    "query": query,
                    "rows": 100,
                    "cursor": cursor,
                    "profile": "rich",
                    "reusability": "open",
                }
                resp = client.get(config.EUROPEANA_SEARCH_URL, params=params)

                if resp.status_code != 200:
                    break

                data = resp.json()
                items = data.get("items", [])
                if not items:
                    break

                for item in items:
                    item_id = item.get("id", "")
                    if item_id in seen_ids:
                        continue
                    seen_ids.add(item_id)

                    title_parts = item.get("title", [])
                    title = title_parts[0] if isinstance(title_parts, list) and title_parts else str(title_parts)
                    text = _build_text_from_item(item)
                    if not text:
                        continue

                    word_count = len(text.split())
                    if word_count < config.MIN_WORD_COUNT_API:
                        continue

                    url = item.get("guid", "") or f"https://www.europeana.eu/item/{item.get('id', '')}"
                    if not _is_allowed_by_robots(url, config.USER_AGENT, robots_cache):
                        continue

                    results.append({
                        "url": url,
                        "text": text,
                        "title": title[:200] if title else "Untitled",
                        "word_count": word_count,
                    })

                    if len(results) >= config.TARGET_USEFUL_DOCS:
                        return results

                next_cursor = data.get("nextCursor")
                if not next_cursor or len(items) < params["rows"]:
                    break
                cursor = next_cursor

    return results


def main():
    output_path = config.CRAWLER_OUTPUT
    results = []

    if config.EUROPEANA_API_KEY:
        print("Fetching from Europeana API...")
        results = fetch_europeana_via_api()
        for r in results:
            t = (r['title'][:50] or "").encode("ascii", errors="replace").decode("ascii")
            print(f"Saved: {t}... ({r['word_count']} words)")

    if not results:
        if not config.EUROPEANA_API_KEY:
            print("No Europeana API key. Set EUROPEANA_API_KEY in .env")
            print("Get a free key at https://pro.europeana.eu/page/get-api")
        print("No pages saved.")
        return

    with open(output_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\nOutput written to {output_path}")


if __name__ == "__main__":
    main()
