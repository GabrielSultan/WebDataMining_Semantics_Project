"""
Phase 2 Step 2: Entity Linking with Europeana

For each private entity: if found in Europeana (Search/Entity API), link with owl:sameAs.
If not found, create new entity in ontology with rdf:type and rdfs:subClassOf.
Output: mapping table (CSV), ontology file, alignment file.
"""

import pandas as pd
import httpx
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS

import config

NS = Namespace("http://example.org/localhistory/")
EDM = Namespace("http://www.europeana.eu/schemas/edm/")

EUROPEANA_SEARCH_URL = "https://api.europeana.eu/record/v2/search.json"
EUROPEANA_ENTITY_SUGGEST = "https://api.europeana.eu/entity/v2/suggest.json"


def search_europeana_entity(label: str) -> list[tuple[str, float]]:
    """
    Search Europeana for entity by label.
    Uses Search API: find records matching the label, use first result's Europeana URL as reference.
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
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(EUROPEANA_SEARCH_URL, params=params)

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
        confidence = 0.9 - (i * 0.1)
        results.append((url, confidence))
    return results


def main():
    entities_df = pd.read_csv(config.EXTRACTED_KNOWLEDGE)
    unique_entities = entities_df["entity"].drop_duplicates().dropna().astype(str).tolist()

    mapping_rows = []
    alignment = Graph()
    alignment.bind("lh", str(NS))
    alignment.bind("edm", str(EDM))
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
        results = search_europeana_entity(entity)
        if results:
            uri, score = results[0]
            mapping_rows.append({
                "Private_Entity": entity,
                "External_URI": uri,
                "Confidence": round(score, 2),
            })
            lh_name = entity.replace(" ", "_").replace("-", "_")
            lh_name = "".join(c for c in lh_name if c.isalnum() or c == "_")
            if lh_name:
                alignment.add((URIRef(NS[lh_name]), OWL.sameAs, URIRef(uri)))
        else:
            mapping_rows.append({
                "Private_Entity": entity,
                "External_URI": "NEW",
                "Confidence": 0.0,
            })
            lh_name = entity.replace(" ", "_").replace("-", "_")
            lh_name = "".join(c for c in lh_name if c.isalnum() or c == "_")
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
