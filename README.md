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

### Phase 1 (TD1)

1. **Crawling (Europeana API):**
   ```bash
   python TD1/phase1_crawler.py
   ```
   With `EUROPEANA_API_KEY` set, the crawler uses the Europeana API (no scraping, no 403).

2. **Extraction (NER + relations):**
   ```bash
   python TD1/phase1_extraction.py
   ```

### Phase 2 (TD4)

3. **Build initial KB:**
   ```bash
   python TD4/phase2_build_kb.py
   ```

4. **Entity linking:**
   ```bash
   python TD4/phase2_entity_linking.py
   ```

5. **Predicate alignment:**
   ```bash
   python TD4/phase2_predicate_alignment.py
   ```

6. **KB expansion:**
   ```bash
   python TD4/phase2_expand_kb.py
   ```
   Per InstructionPhase2: SPARQL 1-Hop expansion on Wikidata (from aligned entities), then Europeana API complement if volume < 50k triplets. Target: 50k--200k triplets, 5k--30k entities.
   Options: `--quick` (skip SPARQL, 500 Europeana records), `--no-sparql`, `--target N`.

### Phase 3 (TD5)

7. **Knowledge Reasoning (SWRL + KGE):**
   Ouvrir et exécuter le notebook `TD5/phase3_knowledge_reasoning.ipynb` (Jupyter ou VS Code).
   Partie 1 : raisonnement SWRL avec OWLReady2. Partie 2 : Knowledge Graph Embedding (PyKEEN).

## Où sont les statistiques (triplets, entités, relations) ?

Les statistiques de la dernière exécution se trouvent dans **`livrable/statistics_report.txt`**.  
Le fichier **`livrable/kb_expanded.nt`** contient la KB finale (un triplet par ligne).

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
