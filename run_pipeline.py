"""
Run the full Web Mining and Semantics pipeline.
Phase 1: Europeana API (or --demo when no API key).
Phase 2: Entity linking (Wikidata primary, Europeana fallback), predicate alignment (SPARQL), expansion.
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
    crawler_cmd = ["phase1_crawler.py"]
    if not config.EUROPEANA_API_KEY:
        crawler_cmd.append("--demo")
    steps = [
        (crawler_cmd, "Phase 1: Crawling (Europeana API or demo)"),
        (["phase1_extraction.py"], "Phase 1: NER + Relation extraction"),
        (["phase2_build_kb.py"], "Phase 2: Build initial KB"),
        (["phase2_entity_linking.py"], "Phase 2: Entity linking (Europeana)"),
        (["phase2_predicate_alignment.py"], "Phase 2: Predicate alignment (EDM)"),
        (["phase2_expand_kb.py"], "Phase 2: KB expansion (Europeana API)"),
    ]

    for cmd, desc in steps:
        if not run(cmd, desc):
            sys.exit(1)

    print("\n--- Pipeline complete ---")


if __name__ == "__main__":
    main()
