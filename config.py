"""
Configuration for the Web Mining and Semantics project.
Domain: Local History (monuments, historical figures, places).
"""

import os

from dotenv import load_dotenv

load_dotenv()  # Load .env file so EUROPEANA_API_KEY is available

# Minimum word count for a page to be considered "useful" (Phase 1 requirement)
MIN_WORD_COUNT = 500

# Lower threshold for API-sourced content (InstructionPhase1 suggests 500 for scraped pages).
# Europeana descriptions are typically shorter; 80 allows more items while filtering
# very short metadata. Documented in report as pragmatic choice.
MIN_WORD_COUNT_API = 80

# User agent for crawling - identifiable as requested for web ethics
USER_AGENT = "WebMiningSemanticsStudent/1.0 (Educational project; Python/httpx)"

# Europeana API (instructions: use APIs when anti-robot checking occurs)
# Get a free key at https://pro.europeana.eu/page/get-api
# Set via env: EUROPEANA_API_KEY, or assign directly below
EUROPEANA_API_KEY = os.environ.get("EUROPEANA_API_KEY", "")  # e.g. "abc123xyz"
EUROPEANA_SEARCH_URL = "https://api.europeana.eu/record/v2/search.json"

# Search queries for Local History domain (Paris, monuments, heritage)
EUROPEANA_QUERIES = [
    "Paris history",
    "Notre-Dame Paris",
    "Eiffel Tower",
    "Louvre Museum",
    "Palace of Versailles",
    "Arc de Triomphe Paris",
    "Bastille Paris",
    "Sainte-Chapelle Paris",
]

# Expansion: many queries to reach 50k-200k triplets (InstructionPhase2)
# Cursor-based pagination allows >1000 results per query
EUROPEANA_EXPANSION_QUERIES = [
    "Paris", "France", "monument", "museum", "cathedral", "palace", "tower",
    "history", "château", "church", "abbey", "castle", "fortress", "statue",
    "painting", "sculpture", "archaeology", "heritage", "medieval", "renaissance",
    "Louis XIV", "Napoleon", "Versailles", "Louvre", "Notre-Dame", "Eiffel",
    "art", "architecture", "photograph", "manuscript", "archive",
]

# Target records for expansion (InstructionPhase2: 50k-200k triplets, 5k-30k entities)
# ~280 triples/record → 700 records ≈ 150k triplets (within 50k-200k)
EUROPEANA_EXPANSION_TARGET_RECORDS = 700

# SPARQL expansion on Wikidata (InstructionPhase2: "extend it via SPARQL queries")
WIKIDATA_SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
SPARQL_EXPANSION_LIMIT_PER_ENTITY = 1000  # 1-Hop: LIMIT per entity
SPARQL_EXPANSION_MIN_CONFIDENCE = 0.85  # Only expand from confidently aligned entities

# Output paths
DATA_DIR = "data"
LIVRABLE_DIR = "livrable"  # Fichiers à rendre (InstructionPhase2)
os.makedirs(LIVRABLE_DIR, exist_ok=True)

CRAWLER_OUTPUT = f"{DATA_DIR}/crawler_output.jsonl"
EXTRACTED_KNOWLEDGE = f"{DATA_DIR}/extracted_knowledge.csv"
EXTRACTED_TRIPLES = f"{DATA_DIR}/extracted_triples.csv"
KB_INITIAL = f"{DATA_DIR}/kb_initial.ttl"

# Livrables Phase 2 (dans livrable/)
KB_EXPANDED = f"{LIVRABLE_DIR}/kb_expanded.nt"
ONTOLOGY_FILE = f"{LIVRABLE_DIR}/ontology.ttl"
ALIGNMENT_FILE = f"{LIVRABLE_DIR}/alignment.ttl"
MAPPING_TABLE = f"{LIVRABLE_DIR}/mapping_table.csv"
STATISTICS_REPORT = f"{LIVRABLE_DIR}/statistics_report.txt"
