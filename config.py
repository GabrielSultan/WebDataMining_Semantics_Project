"""
Project configuration.
Domain: Local History — French / Parisian heritage, English-language Europeana records (see EUROPEANA_QUERIES, EUROPEANA_QUERY_FILTERS).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root so EUROPEANA_API_KEY is available
load_dotenv(Path(__file__).resolve().parent / ".env")

# Minimum word count for a page to be considered useful
MIN_WORD_COUNT = 500

# For Phase 1 compliance: keep only "useful" pages with >= 500 words.
# We apply the same threshold to API-sourced content.
MIN_WORD_COUNT_API = 500

# Target number of useful documents to keep in crawler_output.jsonl.
# This helps ensure a sufficient Phase 1 sample while respecting word threshold.
TARGET_USEFUL_DOCS = 10

# User agent for crawling - identifiable as requested for web ethics
USER_AGENT = "WebMiningSemanticsStudent/1.0 (Educational project; Python/httpx)"

# Europeana API (instructions: use APIs when anti-robot checking occurs)
# Get a free key at https://pro.europeana.eu/page/get-api
# Set via env: EUROPEANA_API_KEY, or assign directly below
EUROPEANA_API_KEY = os.environ.get("EUROPEANA_API_KEY", "")  # e.g. "abc123xyz"
EUROPEANA_SEARCH_URL = "https://api.europeana.eu/record/v2/search.json"

# Europeana query refinements (repeatable `qf` parameter). LANGUAGE:en keeps English metadata/text.
# Optional: append "COUNTRY:france" to bias toward France-based providers (can reduce recall).
EUROPEANA_QUERY_FILTERS = [
    "LANGUAGE:en",
]

# Search queries: English wording, France and/or Paris local history (avoids ambiguous "Paris" matches).
EUROPEANA_QUERIES = [
    "Paris France history",
    "French history Paris monuments",
    "Notre-Dame cathedral Paris France",
    "Eiffel Tower Paris France",
    "Louvre Museum Paris France",
    "Palace of Versailles France history",
    "Arc de Triomphe Paris France",
    "Bastille Paris French history",
    "Sainte-Chapelle Paris France",
    "Versailles palace France history",
]


def europeana_search_params(
    query: str,
    cursor: str,
    *,
    rows: int = 100,
) -> list[tuple[str, str]]:
    """Build Europeana Search API params (multiple `qf` filters)."""
    pairs: list[tuple[str, str]] = [
        ("wskey", EUROPEANA_API_KEY),
        ("query", query),
        ("rows", str(rows)),
        ("cursor", cursor),
        ("profile", "rich"),
        ("reusability", "open"),
    ]
    for qf in EUROPEANA_QUERY_FILTERS:
        pairs.append(("qf", qf))
    return pairs

# Expansion: many queries to reach 50k-200k triplets (InstructionPhase2)
# English + France/Paris themes; same LANGUAGE filter as phase 1 (see EUROPEANA_QUERY_FILTERS).
EUROPEANA_EXPANSION_QUERIES = [
    "Paris France history",
    "France history museum",
    "French Revolution Paris",
    "Versailles France palace",
    "Louvre Paris France",
    "Notre-Dame Paris France",
    "Eiffel Tower Paris",
    "French heritage monument",
    "medieval France Paris",
    "Napoleon France history",
    "Louis XIV Versailles",
    "French cathedral history",
    "Bastille Paris history",
    "Normandy France history",
    "French castle heritage",
    "Paris archaeological France",
    "French art history museum",
    "Versailles garden history",
    "French Renaissance architecture",
]

# Target records for expansion (InstructionPhase2: 50k-200k triplets, 5k-30k entities)
# ~280 triples/record → 700 records ≈ 150k triplets (within 50k-200k)
EUROPEANA_EXPANSION_TARGET_RECORDS = 700

# SPARQL expansion on Wikidata (InstructionPhase2: "extend it via SPARQL queries")
WIKIDATA_SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
SPARQL_EXPANSION_LIMIT_PER_ENTITY = 1000  # 1-Hop: LIMIT per entity
SPARQL_EXPANSION_MIN_CONFIDENCE = 0.85  # Only expand from confidently aligned entities

# Output paths (Phase 1: data/; Phase 2: kg_artifacts/)
DATA_DIR = "data"
KG_ARTIFACTS_DIR = "kg_artifacts"
os.makedirs(KG_ARTIFACTS_DIR, exist_ok=True)

CRAWLER_OUTPUT = f"{DATA_DIR}/crawler_output.jsonl"
EXTRACTED_KNOWLEDGE = f"{DATA_DIR}/extracted_knowledge.csv"
EXTRACTED_TRIPLES = f"{DATA_DIR}/extracted_triples.csv"
KB_INITIAL = f"{DATA_DIR}/kb_initial.ttl"

# KB artifacts (Phase 2 deliverables)
KB_EXPANDED = f"{KG_ARTIFACTS_DIR}/kb_expanded.nt"
ONTOLOGY_FILE = f"{KG_ARTIFACTS_DIR}/ontology.ttl"
ALIGNMENT_FILE = f"{KG_ARTIFACTS_DIR}/alignment.ttl"
MAPPING_TABLE = f"{KG_ARTIFACTS_DIR}/mapping_table.csv"
STATISTICS_REPORT = f"{KG_ARTIFACTS_DIR}/statistics_report.txt"
