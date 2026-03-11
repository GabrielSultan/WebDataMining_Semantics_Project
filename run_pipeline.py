"""
Run the full Web Mining and Semantics pipeline.
Uses Europeana API only (Phase 1 crawler, Phase 2 entity linking and expansion).
"""

import subprocess
import sys


def run(cmd: list[str], desc: str) -> bool:
    """Run a command and return True if successful."""
    print(f"\n--- {desc} ---")
    result = subprocess.run([sys.executable] + cmd)
    if result.returncode != 0:
        print(f"Failed: {' '.join(cmd)}")
        return False
    return True


def main():
    steps = [
        (["phase1_crawler.py"], "Phase 1: Crawling (Europeana API)"),
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
