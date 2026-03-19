"""
Run the full Web Mining and Semantics pipeline (Phase 1 + Phase 2).

Phase 1: Europeana API (requires EUROPEANA_API_KEY).
Phase 2: Entity linking (Wikidata), predicate alignment (SPARQL),
         KB expansion (SPARQL 1-Hop on Wikidata + Europeana complement).

Phase 3 (SWRL + KGE): run TD5/phase3_knowledge_reasoning.ipynb
Phase 4 (RAG): run TD6/lab_rag_sparql_gen.py (requires Ollama)
"""

import subprocess
import sys

import config


def run(cmd: list[str], desc: str) -> bool:
    """Run a command and return True if successful."""
    print(f"\n--- {desc} ---")
    result = subprocess.run([sys.executable] + cmd)
    if result.returncode != 0:
        print(f"Failed: {' '.join(cmd)}")
        return False
    return True


def main():
    crawler_cmd = ["TD1/phase1_crawler.py"]
    steps = [
        (crawler_cmd, "Phase 1: Crawling (Europeana API)"),
        (["TD1/phase1_extraction.py"], "Phase 1: NER + Relation extraction"),
        (["TD4/phase2_build_kb.py"], "Phase 2: Build initial KB"),
        (["TD4/phase2_entity_linking.py"], "Phase 2: Entity linking (Wikidata)"),
        (["TD4/phase2_predicate_alignment.py"], "Phase 2: Predicate alignment (SPARQL + EDM)"),
        (["TD4/phase2_expand_kb.py"], "Phase 2: KB expansion (SPARQL Wikidata + Europeana)"),
    ]

    for cmd, desc in steps:
        if not run(cmd, desc):
            sys.exit(1)

    print("\n--- Pipeline complete ---")


if __name__ == "__main__":
    main()
