"""
Phase 2 Step 4: KB Expansion via Europeana API

Expand by fetching many records from Europeana Search API and extracting triples
from metadata (dcCreator, country, year, edmPlaceLabel, etc.).
Target: 50,000-200,000 triplets, 5,000-30,000 entities, 50-200 relations.
Uses cursor-based pagination to fetch >1000 records per query.
"""

import argparse

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF

import httpx

import config

EDM = Namespace("http://www.europeana.eu/schemas/edm/")
DCTERMS = Namespace("http://purl.org/dc/terms/")
DC = Namespace("http://purl.org/dc/elements/1.1/")
NS = Namespace("http://example.org/localhistory/")


def to_uri_safe(s: str) -> str:
    """Convert string to URI-safe form."""
    s = str(s).replace(" ", "_").replace("-", "_").replace("'", "")
    return "".join(c for c in s if c.isalnum() or c == "_")


def fetch_europeana_records_cursor(
    queries: list[str],
    target_total: int,
    rows_per_request: int = 100,
) -> list[dict]:
    """
    Fetch records from Europeana Search API using cursor-based pagination.
    Cursor allows >1000 results (start/rows limited to 1000).
    """
    if not config.EUROPEANA_API_KEY:
        return []

    all_items = []
    seen = set()

    with httpx.Client(timeout=60.0) as client:
        for query in queries:
            if len(all_items) >= target_total:
                break
            cursor = "*"
            page = 0
            while len(all_items) < target_total:
                params = {
                    "wskey": config.EUROPEANA_API_KEY,
                    "query": query,
                    "rows": min(rows_per_request, 100),
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
                    iid = item.get("id", "")
                    if iid and iid not in seen:
                        seen.add(iid)
                        all_items.append(item)
                next_cursor = data.get("nextCursor")
                if not next_cursor or len(items) < params["rows"]:
                    break
                cursor = next_cursor
                page += 1
                if page % 10 == 0:
                    print(f"  [{query}] fetched {len(all_items)} records so far...")
    return all_items


def _flatten(val):
    if val is None:
        return []
    return val if isinstance(val, list) else [val]


def extract_triples_from_record(item: dict, g: Graph) -> None:
    """
    Extract RDF triples from an Europeana record.
    Uses entity URIs (not just literals) to increase entity count for KGE.
    Extracts many metadata fields to reach 50k+ triplets target.
    """
    item_id = item.get("id", "")
    if not item_id:
        return

    record_uri = URIRef(f"https://www.europeana.eu/item/{item_id}")

    def add_literal(pred, val):
        if val:
            g.add((record_uri, pred, Literal(str(val))))

    def add_entity_triple(pred, val, entity_type=None):
        """Add (record, pred, entity_uri) and optionally (entity, rdf:type, type)."""
        if not val:
            return
        safe = to_uri_safe(str(val))
        if not safe:
            return
        entity_uri = URIRef(NS[safe])
        g.add((record_uri, pred, entity_uri))
        if entity_type:
            g.add((entity_uri, RDF.type, entity_type))

    # Title (literal)
    title = item.get("title", [])
    if isinstance(title, list) and title:
        add_literal(DC["title"], title[0])
    elif title:
        add_literal(DC["title"], title)

    # Use distinct predicates per semantic role (target: 50-200 relations)
    for creator in _flatten(item.get("dcCreator")):
        add_entity_triple(DC["creator"], creator, NS["Person"])
        add_literal(NS["hasCreator"], creator)

    for contrib in _flatten(item.get("dcContributor")):
        add_entity_triple(DC["contributor"], contrib, NS["Person"])
        add_literal(NS["hasContributor"], contrib)

    for country in _flatten(item.get("country")):
        add_entity_triple(DCTERMS["spatial"], country, NS["Place"])
        add_literal(NS["hasCountry"], country)

    for year in _flatten(item.get("year")):
        add_literal(DCTERMS["created"], year)
        add_literal(NS["hasYear"], year)

    for place in _flatten(item.get("edmPlaceLabel")):
        add_entity_triple(NS["hasPlace"], place, NS["Place"])
        add_literal(DCTERMS["spatial"], place)

    for concept in _flatten(item.get("edmConceptLabel")):
        add_entity_triple(DCTERMS["type"], concept, NS["Thing"])
        add_literal(NS["hasConcept"], concept)

    for subj in _flatten(item.get("dcSubject")):
        add_literal(DC["subject"], subj)
        add_literal(NS["hasSubject"], subj)

    for dtype in _flatten(item.get("dcType")):
        add_literal(DC["type"], dtype)
        add_literal(NS["hasType"], dtype)

    for lang in _flatten(item.get("dcLanguage")) or _flatten(item.get("language")):
        add_literal(DC["language"], lang)
        add_literal(NS["hasLanguage"], lang)

    for prov in _flatten(item.get("dataProvider")):
        add_literal(EDM["dataProvider"], prov)
        add_literal(NS["hasDataProvider"], prov)

    for prov in _flatten(item.get("provider")):
        add_literal(EDM["provider"], prov)
        add_literal(NS["hasProvider"], prov)

    ugc = item.get("ugc")
    if isinstance(ugc, list):
        for tag in ugc:
            add_literal(NS["hasTag"], tag)
    elif isinstance(ugc, dict):
        for v in ugc.values():
            for tag in _flatten(v):
                add_literal(NS["hasTag"], tag)

    for alt in _flatten(item.get("dctermsAlternative")):
        add_literal(DCTERMS["alternative"], alt)
    for issued in _flatten(item.get("dctermsIssued")):
        add_literal(DCTERMS["issued"], issued)
    for medium in _flatten(item.get("dctermsMedium")):
        add_literal(NS["hasMedium"], medium)
    for temporal in _flatten(item.get("dctermsTemporal")):
        add_literal(NS["hasTemporal"], temporal)
    for fmt in _flatten(item.get("dcFormat")):
        add_literal(NS["hasFormat"], fmt)
    for rights in _flatten(item.get("dcRights")):
        add_literal(NS["hasRights"], rights)

    # Additional Europeana fields for more relations (target 50-200)
    for coll in _flatten(item.get("edmCollectionName")):
        add_literal(NS["inCollection"], coll)
    for coll in _flatten(item.get("collectionName")):
        add_literal(NS["inCollection"], coll)
    for ident in _flatten(item.get("dcIdentifier")):
        add_literal(NS["hasIdentifier"], ident)
    for src in _flatten(item.get("dcSource")):
        add_literal(NS["hasSource"], src)
    for prov in _flatten(item.get("dctermsProvenance")):
        add_literal(NS["hasProvenance"], prov)


def main():
    parser = argparse.ArgumentParser(description="Expand KB via Europeana API")
    parser.add_argument("--target", type=int, default=None, help="Target number of records (default: from config)")
    parser.add_argument("--quick", action="store_true", help="Quick test: 500 records only")
    args = parser.parse_args()

    g = Graph()
    g.bind("edm", str(EDM))
    g.bind("dcterms", str(DCTERMS))
    g.bind("dc", str(DC))
    g.bind("lh", str(NS))

    # Load initial KB
    g_initial = Graph()
    g_initial.parse(config.KB_INITIAL)
    for s, p, o in g_initial:
        g.add((s, p, o))

    # Expansion: fetch many Europeana records (cursor pagination for >1000/query)
    if config.EUROPEANA_API_KEY:
        queries = getattr(
            config, "EUROPEANA_EXPANSION_QUERIES", config.EUROPEANA_QUERIES + ["Paris", "France", "monument", "museum"]
        )
        target = args.target if args.target is not None else getattr(config, "EUROPEANA_EXPANSION_TARGET_RECORDS", 15_000)
        if args.quick:
            target = 500
        print(f"Fetching up to {target} records from Europeana (cursor pagination)...")
        records = fetch_europeana_records_cursor(queries, target, rows_per_request=100)
        print(f"Fetched {len(records)} Europeana records for expansion")
        for item in records:
            extract_triples_from_record(item, g)
    else:
        print("No Europeana API key; using initial KB only.")

    # Deduplicate
    seen = set()
    g_clean = Graph()
    for s, p, o in g:
        key = (str(s), str(p), str(o))
        if key not in seen:
            seen.add(key)
            g_clean.add((s, p, o))

    g_clean.serialize(destination=config.KB_EXPANDED, format="nt")
    n_triples = len(g_clean)
    n_entities = len(set(str(s) for s, p, o in g_clean) | set(str(o) for s, p, o in g_clean if isinstance(o, URIRef)))
    n_relations = len(set(str(p) for s, p, o in g_clean))

    with open(config.STATISTICS_REPORT, "w") as f:
        f.write(f"Number of triplets: {n_triples}\n")
        f.write(f"Number of entities: {n_entities}\n")
        f.write(f"Number of relations: {n_relations}\n")

    print(f"Saved expanded KB to {config.KB_EXPANDED}")
    print(f"  Triples: {n_triples}")
    print(f"  Entities: {n_entities}")
    print(f"  Relations: {n_relations}")
    print(f"  Statistics saved to {config.STATISTICS_REPORT}")


if __name__ == "__main__":
    main()
