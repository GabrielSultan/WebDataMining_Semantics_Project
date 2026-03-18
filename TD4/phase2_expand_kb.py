"""
Phase 2 Step 4: KB Expansion (SPARQL on Wikidata + Europeana complement)

Per InstructionPhase2: "extend it via SPARQL queries"
1. SPARQL 1-Hop expansion on Wikidata for aligned entities (primary)
2. Europeana API complement if volume < 50k triplets
3. Cleanup malformed literals (JSON artifacts)
4. Deduplicate and export
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import re
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF

import httpx

import config

# Try importing SPARQL expansion (may fail if alignment not yet run)
try:
    from phase2_expand_sparql import expand_via_sparql
except ImportError:
    expand_via_sparql = None

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
    """Flatten Europeana API values. Handle dict like {'def': ['x']} -> ['x'], extract strings only."""
    if val is None:
        return []
    if isinstance(val, dict):
        out = []
        for v in val.values():
            out.extend(_flatten(v))
        return out
    if isinstance(val, list):
        out = []
        for x in val:
            if isinstance(x, str):
                out.append(x)
            else:
                out.extend(_flatten(x))
        return out
    if isinstance(val, str):
        return [val]
    return []


def _is_url_literal(val: str) -> bool:
    """Return True if value looks like an HTTP/HTTPS URL (not useful as literal for KGE)."""
    s = str(val).strip()
    return s.startswith("http://") or s.startswith("https://")


def _clean_literal(obj):
    """
    Fix malformed literals that look like JSON/Python dict reprs.
    e.g. "{'def': 'Roménia'}" -> Literal("Roménia")
    Filter out URL literals (e.g. "http://id.worldcat.org/...") - not useful for KGE.
    Returns (cleaned_obj, keep) - keep=False to drop the triple.
    """
    if not isinstance(obj, Literal):
        return obj, True
    s = str(obj)
    # Filter URL literals (Europeana sometimes returns URLs as text values)
    if _is_url_literal(s):
        return None, False
    if not (s.startswith("{") and ("'def'" in s or '"def"' in s)):
        return obj, True
    m = re.search(r"['\"]def['\"]\s*:\s*['\"]([^'\"]*)['\"]", s)
    if m:
        return Literal(m.group(1)), True
    return None, False


def cleanup_malformed_literals(g: Graph) -> Graph:
    """Remove or fix triples with malformed literal objects."""
    out = Graph()
    for s, p, o in g:
        obj, keep = _clean_literal(o)
        if keep and obj is not None:
            out.add((s, p, obj))
    return out


def compute_connectivity_stats(g: Graph) -> tuple[int, int, int]:
    """
    Compute undirected connectivity metrics on URI-only entity graph.
    Returns: (number_of_components, largest_component_size, isolated_entities_count).
    """
    adj = {}
    entities = set()
    for s, p, o in g:
        if isinstance(s, URIRef) and isinstance(o, URIRef):
            s_str = str(s)
            o_str = str(o)
            entities.add(s_str)
            entities.add(o_str)
            adj.setdefault(s_str, set()).add(o_str)
            adj.setdefault(o_str, set()).add(s_str)

    visited = set()
    component_sizes = []
    for node in entities:
        if node in visited:
            continue
        stack = [node]
        size = 0
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            size += 1
            for nei in adj.get(cur, set()):
                if nei not in visited:
                    stack.append(nei)
        component_sizes.append(size)

    if not component_sizes:
        return 0, 0, 0
    n_components = len(component_sizes)
    largest = max(component_sizes)
    isolated = sum(1 for s in component_sizes if s == 1)
    return n_components, largest, isolated


def extract_triples_from_record(item: dict, g: Graph) -> None:
    """
    Extract RDF triples from an Europeana record.
    InstructionPhase2 Step 4: 50-200 relations. We use ONE canonical predicate per
    semantic role (DC/DCTERMS/EDM standard) to avoid relation explosion.
    """
    item_id = item.get("id", "")
    if not item_id:
        return

    record_uri = URIRef(f"https://www.europeana.eu/item/{item_id}")

    def add_literal(pred, val):
        if val and not _is_url_literal(str(val)):
            g.add((record_uri, pred, Literal(str(val))))

    def add_entity_triple(pred, val, entity_type=None):
        """Add (record, pred, entity_uri) and optionally (entity, rdf:type, type)."""
        if not val or _is_url_literal(str(val)):
            return
        safe = to_uri_safe(str(val))
        if not safe:
            return
        entity_uri = URIRef(NS[safe])
        g.add((record_uri, pred, entity_uri))
        if entity_type:
            g.add((entity_uri, RDF.type, entity_type))

    # Canonical predicates only (DC/DCTERMS/EDM) - target 50-200 relations total
    title = item.get("title", [])
    if isinstance(title, list) and title:
        add_literal(DC["title"], title[0])
    elif title:
        add_literal(DC["title"], title)

    for creator in _flatten(item.get("dcCreator")) + _flatten(item.get("dcContributor")):
        add_entity_triple(DC["creator"], creator, NS["Person"])

    for place_val in _flatten(item.get("country")) + _flatten(item.get("edmPlaceLabel")):
        add_entity_triple(DCTERMS["spatial"], place_val, NS["Place"])

    for year in _flatten(item.get("year")) + _flatten(item.get("dctermsIssued")):
        add_literal(DCTERMS["created"], year)

    for concept in _flatten(item.get("edmConceptLabel")) + _flatten(item.get("dcSubject")):
        add_entity_triple(DC["subject"], concept, NS["Thing"])

    for dtype in _flatten(item.get("dcType")):
        add_literal(DC["type"], dtype)

    for lang in _flatten(item.get("dcLanguage")) or _flatten(item.get("language")):
        add_literal(DC["language"], lang)

    for prov in _flatten(item.get("dataProvider")):
        add_literal(EDM["dataProvider"], prov)
    for prov in _flatten(item.get("provider")):
        add_literal(EDM["provider"], prov)

    for alt in _flatten(item.get("dctermsAlternative")):
        add_literal(DCTERMS["alternative"], alt)
    for medium in _flatten(item.get("dctermsMedium")):
        add_literal(DCTERMS["medium"], medium)
    for temporal in _flatten(item.get("dctermsTemporal")):
        add_literal(DCTERMS["temporal"], temporal)
    for fmt in _flatten(item.get("dcFormat")):
        add_literal(DC["format"], fmt)
    for rights in _flatten(item.get("dcRights")):
        add_literal(DC["rights"], rights)

    # Additional predicates to reach 50+ relations (InstructionPhase2)
    ugc = item.get("ugc")
    if isinstance(ugc, list):
        for tag in ugc:
            add_literal(NS["hasTag"], tag)
    elif isinstance(ugc, dict):
        for v in ugc.values():
            for tag in _flatten(v):
                add_literal(NS["hasTag"], tag)

    for coll in _flatten(item.get("edmCollectionName")) + _flatten(item.get("collectionName")):
        add_literal(NS["inCollection"], coll)
    for ident in _flatten(item.get("dcIdentifier")):
        add_literal(DC["identifier"], ident)
    for src in _flatten(item.get("dcSource")):
        add_literal(DCTERMS["source"], src)
    for prov in _flatten(item.get("dctermsProvenance")):
        add_literal(DCTERMS["provenance"], prov)

    for agent in _flatten(item.get("edmAgentLabel")):
        add_entity_triple(DC["creator"], agent, NS["Person"])
    for timespan in _flatten(item.get("edmTimespanLabel")):
        add_literal(DCTERMS["temporal"], timespan)
    for concept in _flatten(item.get("skosConceptLabel")) or _flatten(item.get("skosConceptPrefLabel")):
        add_entity_triple(DC["subject"], concept, NS["Thing"])
    for isPartOf in _flatten(item.get("edmIsPartOf")):
        add_literal(DCTERMS["isPartOf"], isPartOf)
    for current in _flatten(item.get("edmCurrentLocation")):
        add_literal(EDM["currentLocation"], current)
    for hasView in _flatten(item.get("edmHasView")):
        add_literal(EDM["hasView"], hasView)
    for isRelatedTo in _flatten(item.get("edmIsRelatedTo")):
        add_literal(EDM["isRelatedTo"], isRelatedTo)


def main():
    parser = argparse.ArgumentParser(description="Expand KB via SPARQL (Wikidata) + Europeana")
    parser.add_argument("--target", type=int, default=None, help="Target Europeana records (default: from config)")
    parser.add_argument("--quick", action="store_true", help="Quick test: 500 records only, skip SPARQL")
    parser.add_argument("--no-sparql", action="store_true", help="Skip SPARQL expansion (Europeana only)")
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

    # 1. SPARQL expansion on Wikidata (per InstructionPhase2)
    if expand_via_sparql and not args.no_sparql and not args.quick:
        print("Step 1: SPARQL 1-Hop expansion on Wikidata...")
        g_sparql = expand_via_sparql()
        for s, p, o in g_sparql:
            g.add((s, p, o))
        print(f"  Merged {len(g_sparql)} triplets from Wikidata")

    # 2. Europeana complement if volume < 50k (InstructionPhase2: 50k-200k triplets)
    target_triples = 50_000
    max_triples = 200_000
    if len(g) < target_triples and config.EUROPEANA_API_KEY:
        queries = getattr(
            config, "EUROPEANA_EXPANSION_QUERIES",
            config.EUROPEANA_QUERIES + ["Paris", "France", "monument", "museum"],
        )
        target = args.target or getattr(config, "EUROPEANA_EXPANSION_TARGET_RECORDS", 700)
        if args.quick:
            target = 500
        print(f"Step 2: Europeana complement (target {target} records, max {max_triples} triplets)...")
        records = fetch_europeana_records_cursor(queries, target, rows_per_request=100)
        print(f"  Fetched {len(records)} Europeana records")
        for item in records:
            if len(g) >= max_triples:
                print(f"  Stopping: reached {max_triples} triplets (InstructionPhase2 cap)")
                break
            extract_triples_from_record(item, g)

    # 3. Cleanup malformed literals (JSON artifacts)
    print("Step 3: Cleaning malformed literals...")
    g = cleanup_malformed_literals(g)

    # 4. Deduplicate
    seen = set()
    g_clean = Graph()
    for s, p, o in g:
        key = (str(s), str(p), str(o))
        if key not in seen:
            seen.add(key)
            g_clean.add((s, p, o))

    # 5. Cap triplets at 200k (InstructionPhase2 Step 4)
    if len(g_clean) > max_triples:
        triples_list = list(g_clean)
        g_clean = Graph()
        for s, p, o in triples_list[:max_triples]:
            g_clean.add((s, p, o))
        print(f"  Capped at {max_triples} triplets (was {len(triples_list)})")

    g_clean.serialize(destination=config.KB_EXPANDED, format="nt", encoding="utf-8")
    n_triples = len(g_clean)
    n_entities = len(set(str(s) for s, p, o in g_clean) | set(str(o) for s, p, o in g_clean if isinstance(o, URIRef)))
    n_relations = len(set(str(p) for s, p, o in g_clean))
    n_components, largest_component, isolated_entities = compute_connectivity_stats(g_clean)

    with open(config.STATISTICS_REPORT, "w") as f:
        f.write(f"Number of triplets: {n_triples}\n")
        f.write(f"Number of entities: {n_entities}\n")
        f.write(f"Number of relations: {n_relations}\n")
        f.write(f"Connected components: {n_components}\n")
        f.write(f"Largest component size: {largest_component}\n")
        f.write(f"Isolated entities: {isolated_entities}\n")

    print(f"Saved expanded KB to {config.KB_EXPANDED}")
    print(f"  Triples: {n_triples}")
    print(f"  Entities: {n_entities}")
    print(f"  Relations: {n_relations}")
    print(f"  Connected components: {n_components} (largest={largest_component}, isolated={isolated_entities})")
    print(f"  Statistics saved to {config.STATISTICS_REPORT}")


if __name__ == "__main__":
    main()
