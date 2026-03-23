# Knowledge graph artifacts

- **`ontology.ttl`** — Ontology for local entities and properties.
- **`alignment.ttl`** — Entity and predicate alignments to Wikidata / vocabularies.
- **`kb_expanded.nt`** — Expanded KB (N-Triples). May be omitted from Git due to size; run `python run_pipeline.py` from the repo root to regenerate (requires `EUROPEANA_API_KEY`). Content follows Phase~1 settings in `config.py` (English Europeana queries, France/Paris focus); regenerate after changing queries or filters.
- **`mapping_table.csv`** — Private label → external URI + confidence.
- **`statistics_report.txt`** — Triple / entity / relation counts (source of truth for report figures).
- **`family.owl`** — Toy ontology for Phase 3 reasoning demo.
- **`kge_splits/`** — `train.txt`, `valid.txt`, `test.txt`, PyKEEN outputs (`transe_result/`, `complex_result/`).
