"""
Phase 1: Information Extraction
Domain: Local History

Uses spaCy with en_core_web_trf (transformer-based model) for NER and dependency parsing.
The trf model provides better accuracy than the smaller sm/md models for entity recognition.
"""

import json
import pandas as pd
import spacy

import config

# Entity types we care about (graph nodes)
ENTITY_LABELS = {"PERSON", "ORG", "GPE", "DATE"}

# Common nouns / generic terms to filter out (NER sometimes mislabels these)
FILTER_ENTITIES = {
    "the", "a", "an", "history", "century", "year", "years", "world",
    "war", "city", "building", "museum", "tower", "palace", "cathedral",
}


def load_nlp():
    """Load spaCy model with NER and parser. Use en_core_web_trf per instructions."""
    for model in ("en_core_web_trf", "en_core_web_sm"):
        try:
            return spacy.load(model)
        except OSError:
            continue
    raise OSError("No spaCy model found. Run: python -m spacy download en_core_web_trf")


def extract_entities(doc, source_url: str) -> list[dict]:
    """Extract PERSON, ORG, GPE, DATE entities. Filter common nouns."""
    rows = []
    seen = set()
    for ent in doc.ents:
        if ent.label_ not in ENTITY_LABELS:
            continue
        text = ent.text.strip()
        if not text or len(text) < 2:
            continue
        if text.lower() in FILTER_ENTITIES:
            continue
        key = (text, ent.label_, source_url)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "entity": text,
            "entity_type": ent.label_,
            "source_url": source_url,
        })
    return rows


def extract_relations(doc, source_url: str) -> list[dict]:
    """
    Find entities in same sentence and verb connecting them via dependency parsing.
    Uses nsubj (subject), dobj (direct object), pobj (prepositional object).
    """
    relations = []
    for sent in doc.sents:
        entities_in_sent = [
            ent for ent in sent.ents
            if ent.label_ in ENTITY_LABELS and ent.text.strip().lower() not in FILTER_ENTITIES
        ]
        if len(entities_in_sent) < 2:
            continue

        for i, e1 in enumerate(entities_in_sent):
            for e2 in entities_in_sent[i + 1 :]:
                if e1.text.strip() == e2.text.strip():
                    continue
                verb = None
                for token in sent:
                    if token.pos_ not in ("VERB", "AUX"):
                        continue
                    subjs = [c for c in token.children if c.dep_ in ("nsubj", "nsubjpass")]
                    objs = [c for c in token.children if c.dep_ in ("dobj", "pobj", "attr")]
                    for s in subjs:
                        for o in objs:
                            if (s in e1 and o in e2) or (s in e2 and o in e1):
                                verb = token.lemma_
                                break
                        if verb:
                            break
                    if verb:
                        break
                if not verb:
                    verb = "related_to"
                relations.append({
                    "subject": e1.text.strip(),
                    "predicate": verb,
                    "object": e2.text.strip(),
                    "source_url": source_url,
                })
    return relations


def main():
    nlp = load_nlp()

    entities = []
    relations = []

    with open(config.CRAWLER_OUTPUT, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            url = rec["url"]
            text = rec["text"]

            doc = nlp(text)
            entities.extend(extract_entities(doc, url))
            relations.extend(extract_relations(doc, url))

    # Build CSV: entity, entity_type, source_url (and optionally triples)
    df_entities = pd.DataFrame(entities)
    if not df_entities.empty:
        df_entities = df_entities.drop_duplicates(subset=["entity", "entity_type", "source_url"])

    df_entities.to_csv(config.EXTRACTED_KNOWLEDGE, index=False)
    print(f"Saved {len(df_entities)} entities to {config.EXTRACTED_KNOWLEDGE}")

    # Also save triples for Phase 2
    triples_path = config.EXTRACTED_TRIPLES
    df_triples = pd.DataFrame(relations)
    if not df_triples.empty:
        df_triples = df_triples.drop_duplicates(subset=["subject", "predicate", "object"])
    df_triples.to_csv(triples_path, index=False)
    print(f"Saved {len(df_triples)} triples to {triples_path}")


if __name__ == "__main__":
    main()
