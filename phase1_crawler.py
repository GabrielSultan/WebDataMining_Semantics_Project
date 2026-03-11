"""
Phase 1: Web Crawling and Cleaning
Domain: Local History

Uses Europeana API only (instructions: use APIs when anti-robot checking occurs).
No trafilatura needed - text is extracted directly from the API response.
"""

import json
import re

import httpx

import config


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
        for query in config.EUROPEANA_QUERIES:
            params = {
                "wskey": config.EUROPEANA_API_KEY,
                "query": query,
                "rows": 50,
                "profile": "rich",
                "reusability": "open",
            }
            resp = client.get(config.EUROPEANA_SEARCH_URL, params=params)

            if resp.status_code != 200:
                continue

            data = resp.json()
            items = data.get("items", [])

            for item in items:
                item_id = item.get("id", "")
                if item_id in seen_ids:
                    continue
                seen_ids.add(item_id)

                title_parts = item.get("title", [])
                title = title_parts[0] if isinstance(title_parts, list) and title_parts else str(title_parts)

                desc_parts = item.get("dcDescription") or item.get("dcDescriptionLangAware", {}).get("en")
                if isinstance(desc_parts, dict):
                    desc_parts = desc_parts.get("def", []) or (list(desc_parts.values())[0] if desc_parts else [])
                if desc_parts is None:
                    desc_parts = []
                if not isinstance(desc_parts, list):
                    desc_parts = [desc_parts]

                desc_text = " ".join(str(d) for d in desc_parts if d)
                text = f"{title}\n\n{desc_text}".strip()

                year = item.get("year", [])
                if isinstance(year, list) and year:
                    text += f"\n\nDate: {year[0]}"
                country = item.get("country", [])
                if isinstance(country, list) and country:
                    text += f"\n\nCountry: {country[0]}"

                text = re.sub(r"\s+", " ", text).strip()
                word_count = len(text.split())

                if word_count < config.MIN_WORD_COUNT_API:
                    continue

                url = item.get("guid", "") or f"https://www.europeana.eu/item/{item.get('id', '')}"

                results.append({
                    "url": url,
                    "text": text,
                    "title": title[:200] if title else "Untitled",
                    "word_count": word_count,
                })

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
