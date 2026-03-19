# Web Mining and Semantics - End-of-Year Project

Domain: **Local History** (monuments, historical figures, places)

Project structure (per Grading Guide):

```
project-root/
├─ src/
│  ├─ crawl/      # Phase 1: Crawling
│  ├─ ie/         # Phase 1: NER + Relation extraction
│  ├─ kg/         # Phase 2: KB build, entity linking, predicate alignment, expansion
│  ├─ reason/     # Phase 3: SWRL (see notebooks/)
│  ├─ kge/        # Phase 3: KGE (see notebooks/)
│  └─ rag/        # Phase 4: RAG with SPARQL
├─ data/
│  ├─ samples/
│  └─ README.md
├─ kg_artifacts/
│  ├─ ontology.ttl
│  ├─ kb_expanded.nt
│  ├─ alignment.ttl
│  └─ ...
├─ reports/
│  └─ report.tex
├─ README.md
├─ requirements.txt
├─ .gitignore
└─ LICENSE
```

## Seed URLs / Data Sources (Phase 1)

We use the **Europeana Search API** with queries: `Paris history`, `Notre-Dame Paris`, `Eiffel Tower`, `Louvre Museum`, `Palace of Versailles`, `Arc de Triomphe Paris`, `Bastille Paris`, `Sainte-Chapelle Paris`. Items with ≥500 words are kept.

## Setup

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_trf
```

If `en_core_web_trf` is too large (~500MB), use: `python -m spacy download en_core_web_sm`

**Europeana API key:** Get a free key at https://pro.europeana.eu/page/get-api and set `EUROPEANA_API_KEY` in `.env` or environment.

**Ollama** (Phase 4 - RAG): Install from https://ollama.ai/ and run `ollama run gemma:2b` before the RAG demo.

### Hardware requirements

- **RAM**: ≥8 GB
- **Disk**: ~2 GB for models (spaCy ~500 MB, Gemma 2B ~1.5 GB)
- **Phase 3 (KGE)**: CPU sufficient; GPU optional

## Pipeline

### Phase 1

1. **Crawling:**
   ```bash
   python src/crawl/phase1_crawler.py
   ```

2. **Extraction (NER + relations):**
   ```bash
   python src/ie/phase1_extraction.py
   ```

### Phase 2

3. **Build initial KB:**
   ```bash
   python src/kg/phase2_build_kb.py
   ```

4. **Entity linking:**
   ```bash
   python src/kg/phase2_entity_linking.py
   ```

5. **Predicate alignment:**
   ```bash
   python src/kg/phase2_predicate_alignment.py
   ```

6. **KB expansion:**
   ```bash
   python src/kg/phase2_expand_kb.py
   ```
   Options: `--quick` (500 records, skip SPARQL), `--no-sparql`, `--target N`

### Phase 3

7. **Knowledge Reasoning (SWRL + KGE):**
   Open and run `src/reason/phase3_knowledge_reasoning.ipynb` (Jupyter or VS Code).

### Phase 4

8. **RAG with Knowledge Graphs:**
   ```bash
   ollama run gemma:2b   # Start Ollama first
   python src/rag/lab_rag_sparql_gen.py
   ```

## Run full pipeline (Phase 1 + 2)

```bash
python run_pipeline.py
```

## Statistics

Statistics: `kg_artifacts/statistics_report.txt`  
Expanded KB: `kg_artifacts/kb_expanded.nt`

## Livrables (kg_artifacts/)

| File | Description |
|------|-------------|
| `kb_expanded.nt` | Expanded KB (N-Triples) |
| `ontology.ttl` | Ontology for new entities |
| `alignment.ttl` | Entity and predicate alignments |
| `mapping_table.csv` | Private entity → Wikidata URI mapping |
| `statistics_report.txt` | KB statistics |

## Report

```bash
cd reports && pdflatex report.tex
```

## Screenshot

![RAG Demo](screenshots/rag_demo.svg)
