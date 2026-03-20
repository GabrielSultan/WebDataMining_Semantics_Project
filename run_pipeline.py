"""
Run the full Web Mining and Semantics pipeline (Phase 1 + Phase 2).

Phase 1: Europeana API (requires EUROPEANA_API_KEY).
Phase 2: Entity linking (Wikidata), predicate alignment (SPARQL),
         KB expansion (SPARQL 1-Hop on Wikidata + Europeana complement).

Phase 3 (SWRL + KGE): run src/kge/phase3_knowledge_reasoning.ipynb
Phase 4 (RAG): run src/rag/lab_rag_sparql_gen.py (requires Ollama)
"""

import subprocess
import sys

import config


def run(cmd: list[str], desc: str) -> bool:
    """Run a Python script and return True if successful."""
    print(f"\n--- {desc} ---")
    result = subprocess.run([sys.executable] + cmd)
    if result.returncode != 0:
        print(f"Failed: {' '.join(cmd)}")
        return False
    return True


def main():
    # Execute pipeline steps in order (Phase 1 -> Phase 2)
    steps = [
        (["src/crawl/phase1_crawler.py"], "Phase 1: Crawling (Europeana API)"),
        (["src/ie/phase1_extraction.py"], "Phase 1: NER + Relation extraction"),
        (["src/kg/phase2_build_kb.py"], "Phase 2: Build initial KB"),
        (["src/kg/phase2_entity_linking.py"], "Phase 2: Entity linking (Wikidata)"),
        (["src/kg/phase2_predicate_alignment.py"], "Phase 2: Predicate alignment (SPARQL + EDM)"),
        (["src/kg/phase2_expand_kb.py"], "Phase 2: KB expansion (SPARQL Wikidata + Europeana)"),
    ]

    for cmd, desc in steps:
        if not run(cmd, desc):
            sys.exit(1)

    print("\n--- Pipeline complete ---")


if __name__ == "__main__":
    main()
