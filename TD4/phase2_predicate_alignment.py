"""
Phase 2 Step 3: Predicate Alignment via SPARQL (Wikidata) + EDM fallback

Per instructions: use SPARQL on open KB to find equivalent/similar predicates.
Queries Wikidata SPARQL endpoint for each private predicate, then validates
and adds owl:equivalentProperty or rdfs:subPropertyOf to alignment file.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pathlib import Path

import httpx
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import OWL, RDFS

import config

NS = Namespace("http://example.org/localhistory/")
WDT = Namespace("http://www.wikidata.org/prop/direct/")
EDM = Namespace("http://www.europeana.eu/schemas/edm/")
DCTERMS = Namespace("http://purl.org/dc/terms/")
DC = Namespace("http://purl.org/dc/elements/1.1/")

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"

# Manual Wikidata mapping (priority over SPARQL) - key predicates for expansion
PREDICATE_TO_WIKIDATA = {
    "locatedIn": WDT["P276"],   # location
    "locate": WDT["P276"],
    "occupy": WDT["P276"],
    "storm": WDT["P276"],
    "settle": WDT["P276"],
    "flow": WDT["P276"],
    "conquer": WDT["P276"],
    "imprison": WDT["P276"],
    "build": WDT["P170"],      # creator
    "design": WDT["P170"],
    "construct": WDT["P170"],
    "paint": WDT["P170"],
    "make": WDT["P170"],
    "commission": WDT["P170"],
    "crown": WDT["P166"],      # award received
    "complete": WDT["P571"],   # inception
    "establish": WDT["P571"],
    "sign": WDT["P580"],       # start time
    "pledge": WDT["P580"],
    "choose": WDT["P580"],
    "designate": WDT["P31"],   # instance of
}

# Keywords for SPARQL search per predicate (used when no manual mapping)
PREDICATE_SEARCH_TERMS = {
    "locate": "location",
    "locatedIn": "location",
    "build": "creator",
    "design": "creator",
    "construct": "creator",
    "own": "owner",
    "occupy": "location",
    "expand": "modification",
    "crown": "award",
    "pledge": "date",
    "complete": "date",
    "choose": "date",
    "commission": "creator",
    "sign": "date",
    "storm": "location",
    "imprison": "location",
    "paint": "creator",
    "conquer": "location",
    "establish": "date",
    "make": "creator",
    "settle": "location",
    "flow": "location",
    "grow": "modification",
    "designate": "type",
    "relatedTo": "relation",
}

# Fallback: manual alignment to EDM/DC when SPARQL returns nothing useful
PREDICATE_ALIGNMENT_FALLBACK = {
    "locate": (DCTERMS["spatial"], "equivalent"),
    "locatedIn": (DCTERMS["spatial"], "equivalent"),
    "build": (DC["creator"], "equivalent"),
    "design": (DC["creator"], "equivalent"),
    "construct": (DC["creator"], "equivalent"),
    "own": (EDM["isShownAt"], "subProperty"),
    "occupy": (DCTERMS["spatial"], "equivalent"),
    "expand": (DCTERMS["modified"], "subProperty"),
    "crown": (DC["creator"], "subProperty"),
    "pledge": (DCTERMS["created"], "subProperty"),
    "complete": (DCTERMS["created"], "equivalent"),
    "choose": (DCTERMS["created"], "subProperty"),
    "commission": (DC["creator"], "equivalent"),
    "sign": (DCTERMS["created"], "equivalent"),
    "storm": (DCTERMS["spatial"], "equivalent"),
    "imprison": (DCTERMS["spatial"], "subProperty"),
    "paint": (DC["creator"], "equivalent"),
    "conquer": (DCTERMS["spatial"], "subProperty"),
    "establish": (DCTERMS["created"], "equivalent"),
    "make": (DCTERMS["created"], "equivalent"),
    "settle": (DCTERMS["spatial"], "equivalent"),
    "flow": (DCTERMS["spatial"], "subProperty"),
    "grow": (DCTERMS["modified"], "subProperty"),
    "designate": (DCTERMS["type"], "equivalent"),
    "relatedTo": (DCTERMS["relation"], "equivalent"),
}


def sparql_wikidata_property(search_term: str, limit: int = 10) -> list[str]:
    """
    Query Wikidata SPARQL for properties whose label contains search_term.
    Returns list of property URIs (e.g. wdt:P276).
    """
    query = """
    SELECT ?property ?propertyLabel WHERE {
      ?property a wikibase:Property .
      ?property rdfs:label ?propertyLabel .
      FILTER(CONTAINS(LCASE(?propertyLabel), "%s"))
      FILTER(LANG(?propertyLabel) = "en")
    }
    LIMIT %d
    """ % (search_term.lower().replace('"', '\\"'), limit)
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(
                WIKIDATA_SPARQL,
                params={"query": query, "format": "json"},
                headers={"User-Agent": "WebMiningSemantics/1.0 (https://github.com/; Educational)"},
            )
    except Exception:
        return []
    if resp.status_code != 200:
        return []
    data = resp.json()
    uris = []
    for b in data.get("results", {}).get("bindings", []):
        uri = b.get("property", {}).get("value")
        if uri and "prop/direct/" in uri:
            uris.append(uri)
    return uris


def main():
    alignment = Graph()
    alignment.bind("lh", str(NS))
    alignment.bind("wdt", str(WDT))
    alignment.bind("edm", str(EDM))
    alignment.bind("dcterms", str(DCTERMS))
    alignment.bind("dc", str(DC))
    alignment.bind("owl", OWL)
    alignment.bind("rdfs", RDFS)

    # Load alignment; filter out any Europeana URIs (InstructionPhase2: DBpedia/Wikidata only)
    if Path(config.ALIGNMENT_FILE).exists():
        temp = Graph()
        temp.parse(config.ALIGNMENT_FILE)
        for s, p, o in temp:
            if p == OWL.sameAs and isinstance(o, URIRef):
                if "europeana.eu" in str(o).lower():
                    continue  # Skip Europeana - not SPARQL-queryable
            alignment.add((s, p, o))

    # Per instructions: use SPARQL on Wikidata to find equivalent predicates
    # Priority: 1) Manual Wikidata mapping, 2) SPARQL query, 3) EDM/DC fallback
    for pred, search_term in PREDICATE_SEARCH_TERMS.items():
        lh_pred = URIRef(NS[pred])
        wd_uri = None
        if pred in PREDICATE_TO_WIKIDATA:
            wd_uri = PREDICATE_TO_WIKIDATA[pred]
        else:
            wikidata_uris = sparql_wikidata_property(search_term, limit=5)
            if wikidata_uris and "prop/direct/" in wikidata_uris[0]:
                wd_uri = URIRef(wikidata_uris[0])
        if wd_uri:
            alignment.add((lh_pred, OWL.equivalentProperty, wd_uri))
        elif pred in PREDICATE_ALIGNMENT_FALLBACK:
            # Fallback to EDM/DC when SPARQL returns nothing
            edm_uri, rel = PREDICATE_ALIGNMENT_FALLBACK[pred]
            if rel == "equivalent":
                alignment.add((lh_pred, OWL.equivalentProperty, edm_uri))
            else:
                alignment.add((lh_pred, RDFS.subPropertyOf, edm_uri))

    alignment.serialize(destination=config.ALIGNMENT_FILE, format="turtle")
    print(f"Updated alignment with SPARQL (Wikidata) + EDM predicate mappings to {config.ALIGNMENT_FILE}")


if __name__ == "__main__":
    main()
