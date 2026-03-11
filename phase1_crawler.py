"""
Phase 1: Web Crawling and Cleaning
Domain: Local History

Uses Europeana API only (instructions: use APIs when anti-robot checking occurs).
No trafilatura needed - text is extracted directly from the API response.
Fallback: --demo for sample data when API key is missing.
"""

import argparse
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
                "rows": 12,
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


def generate_demo_data() -> list[dict]:
    """Generate sample Local History content when Europeana API is unavailable."""
    samples = [
        {
            "url": "https://www.europeana.eu/item/123/sample",
            "title": "History of Paris",
            "text": """The history of Paris dates back to approximately 259 BC, when the Parisii, a Celtic tribe, settled on the banks of the Seine. In 52 BC, the Romans conquered the settlement and established Lutetia. The city became known as Paris in the 4th century. Clovis I, King of the Franks, made Paris his capital in 508. During the Middle Ages, Paris grew as a center of learning with the University of Paris, founded around 1150. The Louvre was originally built as a fortress by King Philip II in the 12th century. Napoleon Bonaparte was crowned Emperor at Notre-Dame Cathedral in 1804. The Eiffel Tower was constructed for the 1889 World's Fair. During World War II, Paris was occupied by Nazi Germany from 1940 to 1944.""",
        },
        {
            "url": "https://www.europeana.eu/item/456/sample",
            "title": "Notre-Dame de Paris",
            "text": """Notre-Dame de Paris is a medieval Catholic cathedral on the Île de la Cité in Paris, France. Construction began in 1163 under Bishop Maurice de Sully and was largely completed by 1260. Victor Hugo's 1831 novel The Hunchback of Notre-Dame drew attention to the building. Napoleon Bonaparte was crowned Emperor of the French here in 1804. The cathedral suffered a major fire in April 2019. President Emmanuel Macron pledged to restore the cathedral by 2024. The building is one of the finest examples of French Gothic architecture.""",
        },
        {
            "url": "https://www.europeana.eu/item/789/sample",
            "title": "Eiffel Tower",
            "text": """The Eiffel Tower is a wrought-iron lattice tower on the Champ de Mars in Paris, France. It is named after the engineer Gustave Eiffel, whose company designed and built the tower. Constructed from 1887 to 1889, it was initially criticized by some of France's leading artists. The tower is 330 metres tall. It was the tallest structure in the world until the Chrysler Building in New York City was completed in 1930.""",
        },
        {
            "url": "https://www.europeana.eu/item/101/sample",
            "title": "Louvre Museum",
            "text": """The Louvre is the world's most-visited art museum and a historic monument in Paris, France. The museum is housed in the Louvre Palace, originally built in the late 12th century under Philip II. In 1682, Louis XIV chose the Palace of Versailles for his household. The museum opened on 10 August 1793. The Mona Lisa by Leonardo da Vinci is among the most famous works. Napoleon Bonaparte expanded the collection during the Napoleonic Wars.""",
        },
        {
            "url": "https://www.europeana.eu/item/102/sample",
            "title": "Palace of Versailles",
            "text": """The Palace of Versailles is a former royal residence built by King Louis XIV in Versailles, France, about 19 kilometres west of Paris. The palace is owned by the French Republic and managed by the French Ministry of Culture. The court of Versailles was the centre of political power in France from 1682. The Treaty of Versailles, which ended World War I, was signed in the Hall of Mirrors in 1919. The palace and park were designated a World Heritage Site by UNESCO in 1979.""",
        },
    ]
    for s in samples:
        s["word_count"] = len(s["text"].split())
    return samples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Use sample data when Europeana API is unavailable",
    )
    args = parser.parse_args()

    output_path = config.CRAWLER_OUTPUT
    results = []

    if config.EUROPEANA_API_KEY:
        print("Fetching from Europeana API...")
        results = fetch_europeana_via_api()
        for r in results:
            print(f"Saved: {r['title'][:50]}... ({r['word_count']} words)")

    if not results and args.demo:
        print("Using demo data.")
        results = generate_demo_data()
        for r in results:
            print(f"Demo: {r['title'][:50]}... ({r['word_count']} words)")

    if not results:
        if not config.EUROPEANA_API_KEY:
            print("No Europeana API key. Set EUROPEANA_API_KEY in .env")
            print("Get a free key at https://pro.europeana.eu/page/get-api")
        print("No pages saved. Try --demo for sample data.")
        return

    with open(output_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\nOutput written to {output_path}")


if __name__ == "__main__":
    main()
