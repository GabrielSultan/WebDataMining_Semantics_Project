# Web Mining and Semantics - End-of-Year Project

Domain: **Local History** (monuments, historical figures, places)

## Setup

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_trf
```

If `en_core_web_trf` is too large (~500MB), use the smaller model:
```bash
python -m spacy download en_core_web_sm
```

**Europeana API key** (recommended for Phase 1 - avoids anti-robot blocking):
1. Get a free key at https://pro.europeana.eu/page/get-api
2. Set the environment variable: `set EUROPEANA_API_KEY=your_key` (Windows) or `export EUROPEANA_API_KEY=your_key` (Linux/Mac)

## Pipeline

### Phase 1

1. **Crawling (Europeana API):**
   ```bash
   python phase1_crawler.py
   ```
   With `EUROPEANA_API_KEY` set, the crawler uses the Europeana API (no scraping, no 403).
   Use `--demo` for sample data when the API key is not set.

2. **Extraction (NER + relations):**
   ```bash
   python phase1_extraction.py
   ```

### Phase 2

3. **Build initial KB:**
   ```bash
   python phase2_build_kb.py
   ```

4. **Entity linking:**
   ```bash
   python phase2_entity_linking.py
   ```

5. **Predicate alignment:**
   ```bash
   python phase2_predicate_alignment.py
   ```

6. **KB expansion:**
   ```bash
   python phase2_expand_kb.py
   ```
   Uses cursor-based pagination to fetch 700+ records. Target: 50k--200k triplets, 5k--30k entities.
   Options: `--quick` (500 records), `--target N` (custom record count).

## Deliverables

| File | Description |
|------|-------------|
| `data/crawler_output.jsonl` | Cleaned text and metadata |
| `data/extracted_knowledge.csv` | Entities (entity, type, source_url) |
| `data/extracted_triples.csv` | Subject-predicate-object triples |
| `data/kb_initial.ttl` | Initial RDF KB |
| `data/kb_expanded.nt` | Expanded KB (N-Triples) |
| `data/ontology.ttl` | Ontology for new entities |
| `data/alignment.ttl` | Entity and predicate alignments |
| `data/mapping_table.csv` | Private entity → Europeana URI mapping |
| `data/statistics_report.txt` | KB statistics |
| `report/report.tex` | Lab report (Phase 1 + Phase 2) |

## Report

Compile the LaTeX report:
```bash
cd report && pdflatex report.tex
```
