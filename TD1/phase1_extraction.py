"""
Phase 1: Information Extraction
Domain: Local History

Uses spaCy with en_core_web_trf (transformer-based model) for NER and dependency parsing.
The trf model provides better accuracy than the smaller sm/md models for entity recognition.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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
    "glass", "art", "europhot", "country", "creatie", "bouw", "movement",
    "style", "creation", "techniek", "materiaal", "architectuur",
    "beeldhouwkunst", "europhot", "neoclassicistisch",
    # Europeana metadata labels (not named entities)
    "creatie/bouw", "movement/style", "creation/building", "creation/construction",
    "techniek/materiaal", "movement/style: classicism",
    # Multilingual false positives (Polish, German, Danish, Romanian)
    "prawdopodobnie", "bild", "fundet", "nedatat", "unternehmen", "meisterstück",
    "anliegen", "litografia", "francuska", "papier", "alles",
}

# Fragments, Dutch/Polish/German common words, and non-entity strings (multilingual content)
FILTER_FRAGMENTS = {
    "sygn", "aut", "pod", "kompoz", "dia", "toegevoegde", "fotograaf",
    "architectuur", "glasdia", "tussen", "jusqu", "authentiques", "par",
    "def", "ozn", "z", "de", "la", "le", "du", "des", "en", "et", "mm",
    "stroming", "huidige", "locatie", "creatie", "gebouw", "straat", "brug",
    # Polish, German, Danish, Romanian
    "prawdopodobnie", "fundet", "nedatat", "litografia", "graf", "r.m",
    "der", "das", "und", "oder", "für", "von", "mit", "auf", "aus",
    "country", "caption", "movement/style", "creation/building",
}

# Override NER type for known domain entities (spaCy sometimes mislabels)
ENTITY_TYPE_OVERRIDES = {
    "ku leuven": "ORG",
    "université de louvain": "ORG",
    "art history": "ORG",
    "place de la bourse": "GPE",
    "rue de richelieu": "GPE",
    "place charles de gaulle": "GPE",
    "18th-19th century": "DATE",
    "between 1839 and 1939": "DATE",
    "eiffel tower ku leuven": "GPE",
    "porte saint-denis ku leuven": "GPE",
    "arc de triomphe ku leuven": "GPE",
    "théâtre-français ku leuven": "GPE",
    "alexandre iii ku leuven": "GPE",
    "la bourse de paris ku leuven": "ORG",
}

# Non-English predicate lemmas to reject or replace with relatedTo
FILTER_PREDICATES = {"tussen", "seine", "das", "und", "oder", "z", "de", "het"}

# Words indicating non-English sentences (skip relation extraction if ratio too high)
NON_ENGLISH_INDICATORS = {
    "der", "das", "und", "oder", "für", "von", "mit", "auf", "aus", "ist", "sind",
    "het", "de", "een", "van", "op", "in", "voor", "met", "zijn", "worden",
    "prawdopodobnie", "jest", "są", "z", "w", "na", "do", "od",
    "fotograaf", "toegevoegde", "stroming", "creatie", "gebouw", "huidige",
}

# Minimum length for entity text (filter very short fragments)
MIN_ENTITY_LEN = 3

# Reject entities that are mostly digits or special chars
def _is_valid_entity(text: str) -> bool:
    """Check if entity text is valid (not a fragment, not garbage)."""
    t = text.strip()
    if len(t) < MIN_ENTITY_LEN:
        return False
    if t.lower() in FILTER_FRAGMENTS:
        return False
    # Reject if it looks like a fragment (e.g. "architectuur en", "pod kompoz")
    words = t.lower().split()
    if len(words) <= 2 and any(w in FILTER_FRAGMENTS for w in words):
        return False
    # Reject if mostly non-alphanumeric
    alpha = sum(1 for c in t if c.isalnum() or c.isspace())
    if alpha < len(t) * 0.5:
        return False
    # Reject long noisy chunks (often metadata fragments)
    if len(t.split()) > 6:
        return False
    # Reject obvious punctuation-heavy fragments
    if any(ch in t for ch in ["/", "\\", "[", "]", "{", "}", "=", "|"]):
        return False
    # Require at least one alphabetic character
    if not any(c.isalpha() for c in t):
        return False
    return True


def load_nlp():
    """Load spaCy model with NER and parser. Use en_core_web_trf per instructions."""
    for model in ("en_core_web_trf", "en_core_web_sm"):
        try:
            return spacy.load(model)
        except OSError:
            continue
    raise OSError("No spaCy model found. Run: python -m spacy download en_core_web_trf")


def extract_entities(doc, source_url: str) -> list[dict]:
    """Extract PERSON, ORG, GPE, DATE entities. Filter common nouns and fragments."""
    rows = []
    seen = set()
    for ent in doc.ents:
        if ent.label_ not in ENTITY_LABELS:
            continue
        text = ent.text.strip()
        if not text or len(text) < MIN_ENTITY_LEN:
            continue
        if text.lower() in FILTER_ENTITIES:
            continue
        if not _is_valid_entity(text):
            continue
        # Apply type overrides for known domain entities
        etype = ENTITY_TYPE_OVERRIDES.get(text.lower(), ent.label_)
        key = (text, etype, source_url)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "entity": text,
            "entity_type": etype,
            "source_url": source_url,
        })
    return rows


def _is_likely_non_english(sent) -> bool:
    """Skip sentences where too many tokens indicate non-English (multilingual content)."""
    tokens = [t.text.lower() for t in sent if t.is_alpha and len(t.text) > 1]
    if len(tokens) < 5:
        return False
    non_en = sum(1 for t in tokens if t in NON_ENGLISH_INDICATORS)
    return non_en / len(tokens) > 0.4


def extract_relations(doc, source_url: str) -> list[dict]:
    """
    Find entities in same sentence and verb connecting them via dependency parsing.
    Uses nsubj (subject), dobj (direct object), pobj (prepositional object).
    Only outputs relations when a verb syntactically connects the entities;
    skips co-occurrence-only pairs (e.g. lists of authors) to avoid noise.
    Skips sentences likely in non-English (multilingual Europeana content).
    """
    relations = []
    for sent in doc.sents:
        if _is_likely_non_english(sent):
            continue
        entities_in_sent = [
            ent for ent in sent.ents
            if ent.label_ in ENTITY_LABELS
            and ent.text.strip().lower() not in FILTER_ENTITIES
            and _is_valid_entity(ent.text)
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
                # Prefer real verb; reject non-English predicates (tussen, seine, etc.)
                if verb and verb.lower() in FILTER_PREDICATES:
                    verb = None
                if verb:
                    pred = verb
                elif len(entities_in_sent) == 2:
                    pred = "relatedTo"
                else:
                    continue  # Skip: 3+ entities with no verb = likely list co-occurrence
                relations.append({
                    "subject": e1.text.strip(),
                    "predicate": pred,
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
