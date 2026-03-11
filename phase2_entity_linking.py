"""
Phase 2 Step 2: Entity Linking with Wikidata / DBpedia / Europeana

Per instructions: if entity exists in DBpedia or Wikidata → link it.
If not found → create new entity in ontology.
Primary: Wikidata API (LOD). Fallback: Europeana when Wikidata has no match.
Output: mapping table (CSV) with confidence, ontology file, alignment file.
"""

import pandas as pd
import httpx
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS

import config

NS = Namespace("http://example.org/localhistory/")
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
EUROPEANA_SEARCH_URL = "https://api.europeana.eu/record/v2/search.json"


def search_wikidata_entity(label: str) -> list[tuple[str, float]]:
    """
    Search Wikidata for entity by label (per instructions: DBpedia or Wikidata).
    Returns list of (wikidata_uri, confidence) tuples.
    Confidence: 0.95 for exact label match, 0.85 for partial.
    """
    params = {
        "action": "wbsearchentities",
        "search": label,
        "language": "en",
        "format": "json",
        "limit": 5,
    }
    headers = {"User-Agent": "WebMiningSemantics/1.0 (https://github.com/; Educational project)"}
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(WIKIDATA_API, params=params, headers=headers)
    except Exception:
        return []
    if resp.status_code != 200:
        return []
    data = resp.json()
    results = []
    for i, item in enumerate(data.get("search", [])):
        eid = item.get("id")
        if not eid:
            continue
        uri = f"https://www.wikidata.org/entity/{eid}"
        wlabel = (item.get("label") or "").strip()
        conf = 0.95 if wlabel.lower() == label.strip().lower() else 0.85 - (i * 0.05)
        conf = max(0.6, conf)
        results.append((uri, round(conf, 2)))
    return results


def search_europeana_entity(label: str) -> list[tuple[str, float]]:
    """
    Fallback: Search Europeana when Wikidata has no match.
    Returns list of (europeana_uri, confidence) tuples.
    """
    if not config.EUROPEANA_API_KEY:
        return []

    params = {
        "wskey": config.EUROPEANA_API_KEY,
        "query": f'"{label}"',
        "rows": 3,
        "profile": "minimal",
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(EUROPEANA_SEARCH_URL, params=params)
    except Exception:
        return []
    if resp.status_code != 200:
        return []

    data = resp.json()
    items = data.get("items", [])
    results = []
    for i, item in enumerate(items):
        item_id = item.get("id", "")
        if not item_id:
            continue
        url = item.get("guid", "") or f"https://www.europeana.eu/item/{item_id}"
        confidence = 0.8 - (i * 0.1)  # Lower than Wikidata (fallback)
        results.append((url, round(confidence, 2)))
    return results


def _to_uri_safe(entity: str) -> str:
    """Convert entity name to URI-safe form."""
    s = str(entity).replace(" ", "_").replace("-", "_").replace("'", "")
    return "".join(c for c in s if c.isalnum() or c == "_")


def main():
    entities_df = pd.read_csv(config.EXTRACTED_KNOWLEDGE)
    unique_entities = entities_df["entity"].drop_duplicates().dropna().astype(str).tolist()

    mapping_rows = []
    alignment = Graph()
    alignment.bind("lh", str(NS))
    alignment.bind("owl", OWL)

    ontology = Graph()
    ontology.bind("lh", str(NS))
    ontology.bind("rdf", RDF)
    ontology.bind("rdfs", RDFS)

    ontology.add((NS["Person"], RDF.type, RDFS.Class))
    ontology.add((NS["Organization"], RDF.type, RDFS.Class))
    ontology.add((NS["Place"], RDF.type, RDFS.Class))
    ontology.add((NS["Temporal"], RDF.type, RDFS.Class))
    ontology.add((NS["Thing"], RDF.type, RDFS.Class))
    for c in [NS["Person"], NS["Organization"], NS["Place"], NS["Temporal"]]:
        ontology.add((c, RDFS.subClassOf, NS["Thing"]))
    ontology.add((NS["locatedIn"], RDFS.domain, NS["Thing"]))
    ontology.add((NS["locatedIn"], RDFS.range, NS["Place"]))

    for entity in unique_entities:
        # Primary: Wikidata (per instructions: DBpedia or Wikidata)
        results = search_wikidata_entity(entity)
        if not results:
            results = search_europeana_entity(entity)
        if results:
            uri, score = results[0]
            mapping_rows.append({
                "Private_Entity": entity,
                "External_URI": uri,
                "Confidence": score,
            })
            lh_name = _to_uri_safe(entity)
            if lh_name:
                alignment.add((URIRef(NS[lh_name]), OWL.sameAs, URIRef(uri)))
        else:
            mapping_rows.append({
                "Private_Entity": entity,
                "External_URI": "NEW",
                "Confidence": 0.0,
            })
            lh_name = _to_uri_safe(entity)
            if lh_name:
                ontology.add((URIRef(NS[lh_name]), RDF.type, NS["Thing"]))

    pd.DataFrame(mapping_rows).to_csv(config.MAPPING_TABLE, index=False)
    alignment.serialize(destination=config.ALIGNMENT_FILE, format="turtle")
    ontology.serialize(destination=config.ONTOLOGY_FILE, format="turtle")

    print(f"Saved mapping table to {config.MAPPING_TABLE}")
    print(f"Saved alignment to {config.ALIGNMENT_FILE}")
    print(f"Saved ontology to {config.ONTOLOGY_FILE}")
    linked = sum(1 for r in mapping_rows if r["External_URI"] != "NEW")
    print(f"  Linked: {linked}, New: {len(mapping_rows) - linked}")


if __name__ == "__main__":
    main()
