"""
Phase 2 Step 4a: KB Expansion via SPARQL on Wikidata

Per InstructionPhase2: "extend it via SPARQL queries"
Per QueryWithOpenKB.pdf: Entity linking → Subgraph extraction via SPARQL → Merge

1-Hop expansion: SELECT ?p ?o WHERE { wd:Q7186 ?p ?o . } LIMIT 1000
Only expand from entities confidently aligned to Wikidata (confidence >= 0.85).
Filters verbose literals to keep KB suitable for KGE.
"""

import sys
from pathlib import Path

# Project root for config import
_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_root))

import re
import time
from pathlib import Path

import httpx
from rdflib import Graph, Literal, URIRef

import config

WIKIDATA_ENTITY = "https://www.wikidata.org/entity/"
WIKIDATA_PROP_DIRECT = "http://www.wikidata.org/prop/direct/"

# Core properties to always keep (coordinates, country, dates, types)
KEEP_PROPERTIES = {"P31", "P17", "P571", "P580", "P582", "P625", "P569", "P570"}
# Max literal length for descriptions (filter verbose text)
MAX_LITERAL_LENGTH = 200

# InstructionPhase2 Step 4: 50-200 relations. Whitelist of Wikidata properties to keep.
# Only triples with these predicates are included (avoids 1000+ relation types from 1-Hop).
ALLOWED_WIKIDATA_PROPERTIES = {
    "P31", "P17", "P571", "P580", "P582", "P625", "P569", "P570",  # KEEP
    "P276", "P131", "P170", "P27", "P19", "P20", "P106", "P166", "P1412", "P937",
    "P21", "P18", "P856", "P1448", "P373", "P1476", "P2048", "P112", "P159",
    "P136", "P156", "P361", "P527", "P138", "P135", "P1366", "P39", "P102",
    "P140", "P1343", "P1433", "P488", "P69", "P108",
}

# Wikidata properties for Predicate-Controlled Expansion (InstructionPhase2 Step 4)
PREDICATE_CONTROLLED_PROPERTIES = {
    "P276", "P131", "P170", "P27", "P19", "P20", "P569", "P570",
    "P31", "P106", "P166", "P1412", "P937",
}


def get_wikidata_qids_from_mapping(mapping_path: str, min_confidence: float) -> list[str]:
    """
    Extract Wikidata Q-IDs from mapping table where confidence >= min_confidence.
    Returns list of Q-IDs (e.g. ['Q90', 'Q142']).
    """
    import csv

    qids = []
    path = Path(mapping_path)
    if not path.exists():
        return qids

    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            uri = row.get("External_URI", "")
            try:
                conf = float(row.get("Confidence", 0))
            except ValueError:
                conf = 0
            if "wikidata.org/entity/Q" in uri and conf >= min_confidence:
                match = re.search(r"entity/(Q\d+)", uri)
                if match:
                    qids.append(match.group(1))
    return list(dict.fromkeys(qids))  # deduplicate preserving order


def get_wikidata_qids_from_alignment(alignment_path: str) -> list[str]:
    """
    Extract Wikidata Q-IDs from alignment.ttl (owl:sameAs to wikidata.org/entity/).
    Used when mapping table is not available or has fewer entries.
    """
    from rdflib import Graph as RDFGraph
    from rdflib.namespace import OWL

    qids = []
    path = Path(alignment_path)
    if not path.exists():
        return qids

    g = RDFGraph()
    g.parse(alignment_path, format="turtle")
    for s, p, o in g:
        if p == OWL.sameAs and isinstance(o, URIRef):
            uri = str(o)
            if "wikidata.org/entity/Q" in uri:
                match = re.search(r"entity/(Q\d+)", uri)
                if match:
                    qids.append(match.group(1))
    return list(dict.fromkeys(qids))


def sparql_1hop(qid: str, limit: int = 1000) -> list[tuple[str, str, str]]:
    """
    Execute 1-Hop expansion on Wikidata for entity qid.
    Returns list of (subject_uri, predicate_uri, object_str) - object as string for URIs or literal value.
    """
    query = f"""
    PREFIX wd: <http://www.wikidata.org/entity/>
    SELECT ?p ?o WHERE {{
      wd:{qid} ?p ?o .
    }}
    LIMIT {limit}
    """
    endpoint = getattr(config, "WIKIDATA_SPARQL_ENDPOINT", "https://query.wikidata.org/sparql")
    headers = {
        "User-Agent": "WebMiningSemanticsStudent/1.0 (Educational project; https://github.com/; SPARQL expansion)",
        "Accept": "application/sparql-results+json",
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(
                endpoint,
                params={"query": query, "format": "json"},
                headers=headers,
            )
    except Exception as e:
        print(f"  SPARQL error for {qid}: {e}")
        return []

    if resp.status_code != 200:
        return []

    data = resp.json()
    subj_uri = f"https://www.wikidata.org/entity/{qid}"
    results = []

    for b in data.get("results", {}).get("bindings", []):
        p_val = b.get("p", {}).get("value", "")
        o_bind = b.get("o", {})

        # Only keep direct properties (wdt:) - skip statement nodes (wds:, p:, ps:)
        if "prop/direct/" not in p_val:
            continue

        # InstructionPhase2: 50-200 relations - only keep whitelisted predicates
        m_prop = re.search(r"prop/direct/(P\d+)", p_val)
        if m_prop and m_prop.group(1) not in ALLOWED_WIKIDATA_PROPERTIES:
            continue

        o_type = o_bind.get("type", "")
        o_val = o_bind.get("value", "")

        if o_type == "uri":
            results.append((subj_uri, p_val, o_val))
        else:
            # Literal: filter verbose descriptions
            prop_id = ""
            m = re.search(r"prop/direct/(P\d+)", p_val)
            if m:
                prop_id = m.group(1)
            if prop_id in KEEP_PROPERTIES:
                results.append((subj_uri, p_val, o_val))
            elif len(str(o_val)) <= MAX_LITERAL_LENGTH:
                results.append((subj_uri, p_val, o_val))
            # else skip long literals

    return results


def sparql_2hop(qid: str, limit: int = 500) -> list[tuple[str, str, str]]:
    """
    Execute 2-Hop expansion on Wikidata (InstructionPhase2).
    Fetches triples where intermediate entities connect the seed to new facts.
    Returns (subject_uri, predicate_uri, object_str).
    """
    query = f"""
    PREFIX wd: <http://www.wikidata.org/entity/>
    PREFIX wdt: <http://www.wikidata.org/prop/direct/>
    SELECT ?intermediate ?p ?o WHERE {{
      wd:{qid} ?p1 ?intermediate .
      FILTER(STRSTARTS(STR(?p1), "http://www.wikidata.org/prop/direct/"))
      ?intermediate ?p ?o .
      FILTER(STRSTARTS(STR(?p), "http://www.wikidata.org/prop/direct/"))
      FILTER(isURI(?intermediate))
    }}
    LIMIT {limit}
    """
    endpoint = getattr(config, "WIKIDATA_SPARQL_ENDPOINT", "https://query.wikidata.org/sparql")
    headers = {
        "User-Agent": "WebMiningSemanticsStudent/1.0 (Educational project; SPARQL 2-hop expansion)",
        "Accept": "application/sparql-results+json",
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(endpoint, params={"query": query, "format": "json"}, headers=headers)
    except Exception as e:
        print(f"  SPARQL 2-hop error for {qid}: {e}")
        return []
    if resp.status_code != 200:
        return []
    data = resp.json()
    results = []
    for b in data.get("results", {}).get("bindings", []):
        inter = b.get("intermediate", {}).get("value", "")
        p_val = b.get("p", {}).get("value", "")
        o_bind = b.get("o", {})
        if "prop/direct/" not in p_val or not inter:
            continue
        m_prop = re.search(r"prop/direct/(P\d+)", p_val)
        if m_prop and m_prop.group(1) not in ALLOWED_WIKIDATA_PROPERTIES:
            continue
        o_type = o_bind.get("type", "")
        o_val = o_bind.get("value", "")
        if o_type == "uri":
            results.append((inter, p_val, o_val))
        else:
            prop_id = ""
            m = re.search(r"prop/direct/(P\d+)", p_val)
            if m:
                prop_id = m.group(1)
            if prop_id in KEEP_PROPERTIES or len(str(o_val)) <= MAX_LITERAL_LENGTH:
                results.append((inter, p_val, o_val))
    return results


def sparql_predicate_controlled(prop_id: str, limit: int = 5000) -> list[tuple[str, str, str]]:
    """
    Predicate-Controlled Expansion (InstructionPhase2 Step 4).
    SELECT ?s ?p ?o WHERE { ?s wdt:Pxxx ?o . } to add many triples for a given relation.
    """
    prop_uri = f"http://www.wikidata.org/prop/direct/{prop_id}"
    query = f"""
    PREFIX wdt: <http://www.wikidata.org/prop/direct/>
    SELECT ?s ?p ?o WHERE {{
      ?s wdt:{prop_id} ?o .
      BIND(<{prop_uri}> AS ?p)
    }}
    LIMIT {limit}
    """
    endpoint = getattr(config, "WIKIDATA_SPARQL_ENDPOINT", "https://query.wikidata.org/sparql")
    headers = {
        "User-Agent": "WebMiningSemanticsStudent/1.0 (Educational project; SPARQL predicate expansion)",
        "Accept": "application/sparql-results+json",
    }
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.get(endpoint, params={"query": query, "format": "json"}, headers=headers)
    except Exception as e:
        print(f"  SPARQL predicate error for {prop_id}: {e}")
        return []
    if resp.status_code != 200:
        return []
    data = resp.json()
    results = []
    for b in data.get("results", {}).get("bindings", []):
        s_val = b.get("s", {}).get("value", "")
        o_bind = b.get("o", {})
        o_type = o_bind.get("type", "")
        o_val = o_bind.get("value", "")
        if not s_val or "entity/" not in s_val:
            continue
        if o_type == "uri":
            results.append((s_val, prop_uri, o_val))
        else:
            if len(str(o_val)) <= MAX_LITERAL_LENGTH:
                results.append((s_val, prop_uri, o_val))
    return results


def expand_via_sparql(
    mapping_path: str | None = None,
    alignment_path: str | None = None,
    min_confidence: float | None = None,
    limit_per_entity: int | None = None,
) -> Graph:
    """
    Expand KB by fetching 1-Hop neighbourhoods from Wikidata for aligned entities.
    Returns an rdflib Graph with the fetched triples.
    """
    mapping_path = mapping_path or config.MAPPING_TABLE
    alignment_path = alignment_path or config.ALIGNMENT_FILE
    min_confidence = min_confidence or getattr(config, "SPARQL_EXPANSION_MIN_CONFIDENCE", 0.85)
    limit_per_entity = limit_per_entity or getattr(config, "SPARQL_EXPANSION_LIMIT_PER_ENTITY", 1000)

    # Prefer mapping table; fallback to alignment.ttl
    qids = get_wikidata_qids_from_mapping(mapping_path, min_confidence)
    if not qids:
        qids = get_wikidata_qids_from_alignment(alignment_path)
        print("  Using alignment.ttl for Wikidata Q-IDs (mapping had none with sufficient confidence)")

    if not qids:
        print("  No Wikidata-aligned entities found for SPARQL expansion")
        return Graph()

    print(f"  Expanding from {len(qids)} Wikidata entities (1-Hop, limit={limit_per_entity}/entity)...")

    g = Graph()
    seen = set()

    def add_triples(triples: list, label: str = ""):
        for s, p, o in triples:
            key = (s, p, o)
            if key not in seen:
                seen.add(key)
                subj = URIRef(s)
                pred = URIRef(p)
                if o.startswith("http"):
                    obj = URIRef(o)
                else:
                    obj = Literal(o)
                g.add((subj, pred, obj))

    # 1-Hop expansion (primary source per InstructionPhase2)
    for i, qid in enumerate(qids):
        triples = sparql_1hop(qid, limit=limit_per_entity)
        add_triples(triples)
        if (i + 1) % 20 == 0:
            print(f"    Processed {i + 1}/{len(qids)} entities, {len(g)} triples so far...")
        time.sleep(0.2)

    # 2-Hop expansion (InstructionPhase2) - sample of entities to avoid timeout
    hop2_limit = min(30, len(qids))
    print(f"  2-Hop expansion from {hop2_limit} entities...")
    for i, qid in enumerate(qids[:hop2_limit]):
        triples = sparql_2hop(qid, limit=200)
        add_triples(triples)
        time.sleep(0.3)
    print(f"    After 2-hop: {len(g)} triples")

    # Predicate-Controlled Expansion (InstructionPhase2) - adds relation diversity
    print("  Predicate-controlled expansion...")
    for prop_id in list(PREDICATE_CONTROLLED_PROPERTIES)[:8]:  # Limit to avoid timeout
        triples = sparql_predicate_controlled(prop_id, limit=2000)
        add_triples(triples)
        if triples:
            print(f"    {prop_id}: +{len(triples)} triples")
        time.sleep(0.5)

    return g


def main():
    """Run SPARQL expansion and save to a temporary file for merge, or print stats."""
    g = expand_via_sparql()
    n = len(g)
    print(f"  SPARQL expansion: {n} triplets from Wikidata")
    if n > 0:
        # Save to a file that phase2_expand_kb can merge
        out = Path(config.KG_ARTIFACTS_DIR) / "kb_sparql_expansion.nt"
        g.serialize(destination=str(out), format="nt", encoding="utf-8")
        print(f"  Saved to {out} (to be merged by phase2_expand_kb)")


if __name__ == "__main__":
    main()
