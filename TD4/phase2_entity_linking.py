"""
Phase 2 Step 2: Entity Linking with Wikidata / DBpedia

Per instructions: if entity exists in DBpedia or Wikidata → link it.
If not found → create new entity in ontology.
Primary: Wikidata API (LOD). Europeana is NOT used for alignment (not SPARQL-queryable).
Only Wikidata/DBpedia URIs are added to alignment for SPARQL expansion.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import httpx
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS

import config

NS = Namespace("http://example.org/localhistory/")
WIKIDATA_API = "https://www.wikidata.org/w/api.php"

# Type hints for disambiguation (QueryWithOpenKB.pdf): GPE->place, PERSON->human, etc.
ENTITY_TYPE_DESCRIPTION_HINTS = {
    "GPE": ("city", "country", "place", "location", "capital"),
    "PERSON": ("person", "human", "politician", "scientist", "artist"),
    "ORG": ("organization", "company", "university", "institution"),
}

# Entities to never add to ontology (adjectives, common nouns, fragments, misclassified)
ENTITY_BLACKLIST = {
    "architectuur", "neoclassicistisch", "architectuur.", "d'anatomie",
    "des galeries de minéralogie et", "et de la vallée suisse",
    "bild", "papier", "fundet", "nedatat", "prawdopodobnie", "litografia",
    "meisterstück", "anliegen", "panorama", "grundriss", "gartenplan",
    "kupferstich", "architectuur en", "exposition universelle de 19001245",
}

# Type corrections: entity -> "EXCLUDE" means do not add to ontology
ENTITY_TYPE_CORRECTIONS = {
    "architectuur": "EXCLUDE",
    "neoclassicistisch": "EXCLUDE",
    "d'anatomie": "EXCLUDE",
}


def search_wikidata_entity(label: str, entity_type: str | None = None) -> list[tuple[str, float]]:
    """
    Search Wikidata for entity by label (per instructions: DBpedia or Wikidata).
    Returns list of (wikidata_uri, confidence) tuples.
    Uses API match info when available. Optionally filters by entity_type (PERSON, ORG, GPE, DATE).
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
    hints = ENTITY_TYPE_DESCRIPTION_HINTS.get(entity_type or "", ()) if entity_type else ()

    for i, item in enumerate(data.get("search", [])):
        eid = item.get("id")
        if not eid:
            continue
        uri = f"https://www.wikidata.org/entity/{eid}"
        wlabel = (item.get("label") or "").strip()
        desc = (item.get("description") or "").lower()
        match = item.get("match") or {}
        match_type = match.get("type", "")

        # Confidence from API: label match > entity match > default
        if wlabel.lower() == label.strip().lower():
            conf = 0.95
        elif match_type == "label":
            conf = 0.92
        else:
            conf = 0.85 - (i * 0.05)

        # Type-based disambiguation: boost if description matches expected type
        if hints and any(h in desc for h in hints):
            conf = min(0.98, conf + 0.05)
        conf = max(0.6, round(conf, 2))
        results.append((uri, conf))
    return results


def _to_uri_safe(entity: str) -> str:
    """Convert entity name to URI-safe form."""
    s = str(entity).replace(" ", "_").replace("-", "_").replace("'", "")
    return "".join(c for c in s if c.isalnum() or c == "_")


def _add_new_entity_to_ontology(ontology, NS, entity: str, entity_type: str):
    """Add new entity to ontology with precise type (Person, Organization, Place, Temporal)."""
    lh_name = _to_uri_safe(entity)
    if not lh_name:
        return
    type_map = {"PERSON": "Person", "ORG": "Organization", "GPE": "Place", "DATE": "Temporal"}
    rdf_type = type_map.get(entity_type, "Thing")
    ontology.add((URIRef(NS[lh_name]), RDF.type, NS[rdf_type]))


def main():
    entities_df = pd.read_csv(config.EXTRACTED_KNOWLEDGE)
    # Build entity -> type mapping (use first occurrence per entity)
    entity_types = entities_df.drop_duplicates("entity").set_index("entity")["entity_type"].to_dict()
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
        etype = entity_types.get(entity, "Thing")
        # Apply type corrections; EXCLUDE = do not add to ontology
        etype = ENTITY_TYPE_CORRECTIONS.get(entity.lower().strip(), etype)
        if etype == "EXCLUDE" or entity.lower().strip() in ENTITY_BLACKLIST:
            mapping_rows.append({
                "Private_Entity": entity,
                "External_URI": "NEW",
                "Confidence": 0.0,
            })
            continue  # Skip ontology creation for blacklisted/misclassified entities
        results = search_wikidata_entity(entity, entity_type=etype)

        if results:
            uri, score = results[0]
            # Per InstructionPhase2: only DBpedia or Wikidata. Never Europeana (not SPARQL-queryable).
            if "europeana.eu" in str(uri).lower():
                uri, score = "NEW", 0.0
            mapping_rows.append({
                "Private_Entity": entity,
                "External_URI": uri,
                "Confidence": score,
            })
            # Only add to alignment if Wikidata/DBpedia (LOD). Europeana URIs excluded.
            if uri != "NEW" and ("wikidata.org/entity/" in str(uri) or "dbpedia.org" in str(uri)):
                lh_name = _to_uri_safe(entity)
                if lh_name:
                    alignment.add((URIRef(NS[lh_name]), OWL.sameAs, URIRef(uri)))
            elif uri == "NEW":
                lh_name = _to_uri_safe(entity)
                if lh_name:
                    _add_new_entity_to_ontology(ontology, NS, entity, etype)
        else:
            mapping_rows.append({
                "Private_Entity": entity,
                "External_URI": "NEW",
                "Confidence": 0.0,
            })
            lh_name = _to_uri_safe(entity)
            if lh_name:
                _add_new_entity_to_ontology(ontology, NS, entity, etype)

    pd.DataFrame(mapping_rows).to_csv(config.MAPPING_TABLE, index=False)
    alignment.serialize(destination=config.ALIGNMENT_FILE, format="turtle")
    ontology.serialize(destination=config.ONTOLOGY_FILE, format="turtle")

    print(f"Saved mapping table to {config.MAPPING_TABLE}")
    print(f"Saved alignment to {config.ALIGNMENT_FILE}")
    print(f"Saved ontology to {config.ONTOLOGY_FILE}")
    linked = sum(1 for r in mapping_rows if r["External_URI"] != "NEW")
    wikidata_linked = sum(1 for r in mapping_rows if "wikidata.org" in str(r.get("External_URI", "")))
    print(f"  Linked (total): {linked}, Wikidata (for SPARQL): {wikidata_linked}, New: {len(mapping_rows) - linked}")


if __name__ == "__main__":
    main()
