"""
Phase 2 Step 1: Build Initial Private Knowledge Base

Converts extracted entities and triples from Phase 1 into RDF format.
Uses URIs (not plain strings), camelCase predicates, deduplication.
Target: >= 100 triplets, >= 50 entities.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF

import pandas as pd

import config

# Private namespace for our Local History KB
NS = Namespace("http://example.org/localhistory/")


def to_uri(name: str) -> str:
    """Convert entity name to URI-safe form."""
    s = str(name).replace(" ", "_").replace("-", "_").replace("'", "")
    s = "".join(c for c in s if c.isalnum() or c == "_")
    return s


def to_predicate(verb: str) -> str:
    """Convert verb to camelCase predicate. Normalize related_to -> relatedTo."""
    v = str(verb).strip()
    if v.lower() in {"related_to", "relatedto"}:
        return "relatedTo"
    # Keep existing camelCase inputs stable (e.g. relatedTo).
    if any(ch.isupper() for ch in v[1:]) and "_" not in v and "-" not in v and " " not in v:
        return v[0].lower() + v[1:]
    words = v.lower().replace("-", " ").split()
    if not words:
        return "relatedTo"
    return words[0] + "".join(w.capitalize() for w in words[1:])


def main():
    entities_df = pd.read_csv(config.EXTRACTED_KNOWLEDGE)
    triples_df = pd.read_csv(config.EXTRACTED_TRIPLES)

    g = Graph()
    g.bind("lh", str(NS))
    g.bind("rdf", RDF)

    type_map = {"PERSON": "Person", "ORG": "Organization", "GPE": "Place", "DATE": "Temporal"}

    for _, row in entities_df.iterrows():
        name = to_uri(row["entity"])
        if not name:
            continue
        subj = URIRef(NS[name])
        etype = type_map.get(str(row["entity_type"]), "Thing")
        g.add((subj, RDF.type, NS[etype]))
        g.add((subj, NS["hasSource"], Literal(str(row["source_url"]))))

    # Add triples; objects in triples may not be in entities CSV
    seen = set()
    for _, row in triples_df.iterrows():
        s = to_uri(row["subject"])
        o = to_uri(row["object"])
        if not s or not o:
            continue
        pred = to_predicate(row["predicate"])
        key = (s, pred, o)
        if key in seen:
            continue
        seen.add(key)
        g.add((URIRef(NS[s]), NS[pred], URIRef(NS[o])))

    g.serialize(destination=config.KB_INITIAL, format="turtle")
    n_triples = len(g)
    n_entities = len(set(s for s, p, o in g) | set(o for s, p, o in g if isinstance(o, URIRef)))
    print(f"Saved initial KB to {config.KB_INITIAL}")
    print(f"  Triples: {n_triples}")
    print(f"  Entities: {n_entities}")


if __name__ == "__main__":
    main()
