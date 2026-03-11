"""
Phase 2 Step 3: Predicate Alignment with Europeana EDM

For each private predicate, align to EDM (Europeana Data Model) properties.
Adds owl:equivalentProperty or rdfs:subPropertyOf to alignment file.
"""

from pathlib import Path

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import OWL, RDFS

import config

NS = Namespace("http://example.org/localhistory/")
EDM = Namespace("http://www.europeana.eu/schemas/edm/")
DCTERMS = Namespace("http://purl.org/dc/terms/")
DC = Namespace("http://purl.org/dc/elements/1.1/")

# Manual alignment: private predicate -> (EDM URI, relationship)
PREDICATE_ALIGNMENT = {
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
}


def main():
    alignment = Graph()
    alignment.bind("lh", str(NS))
    alignment.bind("edm", str(EDM))
    alignment.bind("dcterms", str(DCTERMS))
    alignment.bind("dc", str(DC))
    alignment.bind("owl", OWL)
    alignment.bind("rdfs", RDFS)

    if Path(config.ALIGNMENT_FILE).exists():
        alignment.parse(config.ALIGNMENT_FILE)

    for pred, (edm_uri, rel) in PREDICATE_ALIGNMENT.items():
        lh_pred = URIRef(NS[pred])
        if rel == "equivalent":
            alignment.add((lh_pred, OWL.equivalentProperty, edm_uri))
        else:
            alignment.add((lh_pred, RDFS.subPropertyOf, edm_uri))

    alignment.serialize(destination=config.ALIGNMENT_FILE, format="turtle")
    print(f"Updated alignment with EDM predicate mappings to {config.ALIGNMENT_FILE}")


if __name__ == "__main__":
    main()
