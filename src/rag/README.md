# Phase 4 - RAG with Knowledge Graphs

Retrieval-Augmented Generation: convert natural language questions to SPARQL, execute on the graph, and present grounded results.

## Prerequisites

- Ollama installed and running
- Knowledge base: `../kg_artifacts/kb_expanded.nt`

## Run

From project root:

```bash
ollama run gemma:2b   # Start Ollama first
python src/rag/lab_rag_sparql_gen.py
```

## Example Questions

- Which items are linked to France?
- What places are associated with Paris?
- How many items have subject archaeology?
- What entity types exist in the KB?
- What creators appear in the base?
