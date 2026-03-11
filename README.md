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
   Per InstructionPhase2: SPARQL 1-Hop expansion on Wikidata (from aligned entities), then Europeana API complement if volume < 50k triplets. Target: 50k--200k triplets, 5k--30k entities.
   Options: `--quick` (skip SPARQL, 500 Europeana records), `--no-sparql`, `--target N`.

## Où sont les statistiques (triplets, entités, relations) ?

Les chiffres **179 412 triplets, 6 728 entités, 22 relations** se trouvent dans **`livrable/kb_expanded.nt`** (un triplet par ligne). Voir `data/DATA_README.md` pour le détail.

## Livrables (dossier `livrable/`)

Les fichiers à rendre (InstructionPhase2) sont dans **`livrable/`** :

| File | Description |
|------|-------------|
| `livrable/kb_expanded.nt` | Expanded KB (N-Triples) |
| `livrable/ontology.ttl` | Ontology for new entities |
| `livrable/alignment.ttl` | Entity and predicate alignments |
| `livrable/mapping_table.csv` | Private entity → Wikidata/DBpedia URI mapping with confidence |
| `livrable/statistics_report.txt` | KB statistics |
| `report/report.tex` | Lab report (Phase 1 + Phase 2) |

## Données intermédiaires (dossier `data/`)

| File | Description |
|------|-------------|
| `data/crawler_output.jsonl` | Cleaned text and metadata |
| `data/extracted_knowledge.csv` | Entities (entity, type, source_url) |
| `data/extracted_triples.csv` | Subject-predicate-object triples |
| `data/kb_initial.ttl` | Initial RDF KB |

## Report

Compile the LaTeX report:
```bash
cd report && pdflatex report.tex
```
