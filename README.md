# Web Mining and Semantics - End-of-Year Project

Domain: **Local History** (monuments, historical figures, places)

## Seed URLs / Data Sources (Phase 1)

Per Phase 1 instructions (5–10 seed URLs): we use the **Europeana Search API** with the following queries as equivalent "seeds" (API avoids anti-robot blocking):

- `Paris history`, `Notre-Dame Paris`, `Eiffel Tower`, `Louvre Museum`, `Palace of Versailles`, `Arc de Triomphe Paris`, `Bastille Paris`, `Sainte-Chapelle Paris`

Each query returns multiple records; items with ≥500 words are kept. See `config.py` for `EUROPEANA_QUERIES` and `EUROPEANA_EXPANSION_QUERIES`.

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

**Ollama** (Phase 4 - RAG): Install from https://ollama.ai/ and run `ollama run gemma:2b` before the RAG demo.

### Hardware requirements

- **RAM**: ≥8 GB (KB ~110k triples loads in memory; KGE training benefits from more RAM)
- **Disk**: ~2 GB for models (spaCy `en_core_web_trf` ~500 MB, Gemma 2B ~1.5 GB)
- **Phase 3 (KGE)**: CPU sufficient; GPU optional for faster training

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

### Phase 4 (TD6)

8. **RAG with Knowledge Graphs:**
   ```bash
   ollama run gemma:2b   # Start Ollama first
   python TD6/lab_rag_sparql_gen.py
   ```
   RAG avec RDF/SPARQL et LLM local (Ollama). Convertit les questions en langage naturel en SPARQL, exécute sur la KB et affiche les résultats. Voir `TD6/README.md` pour les détails.

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

## Screenshot

![RAG Demo](screenshots/rag_demo.svg)

*RAG demo: natural language question → SPARQL generation → grounded results from the KB. Run `ollama run gemma:2b` then `python TD6/lab_rag_sparql_gen.py` to reproduce.*

## Report

Compile the LaTeX report:
```bash
cd report && pdflatex report.tex
```
