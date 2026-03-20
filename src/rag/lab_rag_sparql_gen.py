"""
Phase 4: RAG with RDF/SPARQL and Local Small LLM

Retrieval-Augmented Generation: convert natural language questions to SPARQL,
execute on the knowledge graph, and present grounded results.
Compares baseline (no RAG) vs SPARQL-generation RAG with self-repair loop.
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple

import requests
from rdflib import Graph, Namespace

# Project root for config
_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_root))
import config

# ----------------------------
# Configuration
# ----------------------------
KB_PATH = _root / config.KB_EXPANDED
OLLAMA_URL = "http://localhost:11434/api/generate"
GEMMA_MODEL = "gemma:2b"  # If 'model not found', try "gemma2:2b"
OLLAMA_TIMEOUT = 600  # SPARQL generation with large schema can take several minutes
MAX_PREDICATES = 80
MAX_CLASSES = 40
SAMPLE_TRIPLES = 20

# ----------------------------
# 0) Utility: call local LLM (Ollama)
# ----------------------------


def ask_local_llm(prompt: str, model: str = GEMMA_MODEL) -> str:
    """
    Send a prompt to a local Ollama model using the REST API.
    Returns the full text response as a single string.
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,  # important: disable streaming for simpler integration
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Cannot connect to Ollama. Ensure Ollama is running (ollama run gemma:2b)"
        )
    except requests.exceptions.ReadTimeout:
        raise RuntimeError(
            f"Ollama timed out after {OLLAMA_TIMEOUT}s. Try a smaller model (qwen3.5:0.8b) "
            "or increase OLLAMA_TIMEOUT in the script."
        )
    if response.status_code != 200:
        raise RuntimeError(
            f"Ollama API error {response.status_code}: {response.text}"
        )
    data = response.json()
    return data.get("response", "")


# ----------------------------
# 1) Load RDF graph
# ----------------------------


# Prefixes to bind to graph so SPARQL queries can use them (e.g. when LLM uses wdt)
GRAPH_PREFIXES = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "edm": "http://www.europeana.eu/schemas/edm/",
    "lh": "http://example.org/localhistory/",
    "schema": "https://schema.org/",
    "wdt": "http://www.wikidata.org/prop/direct/",
}


def _bind_prefixes(g: Graph) -> None:
    """Bind common prefixes to graph so SPARQL queries resolve correctly."""
    for prefix, uri in GRAPH_PREFIXES.items():
        g.namespace_manager.bind(prefix, Namespace(uri), override=False)


def load_graph(path: Path) -> Graph:
    """Load RDF graph from N-Triples or Turtle file."""
    g = Graph()
    fmt = "nt" if str(path).endswith(".nt") else "turtle"
    g.parse(str(path), format=fmt)
    _bind_prefixes(g)
    print(f"Loaded {len(g)} triples from {path}")
    return g


# ----------------------------
# 2) Build a small schema summary
# ----------------------------


# Only these prefixes in schema summary (reduces prompt size so LLM has room for SELECT/WHERE)
SCHEMA_PREFIXES = ("dc", "dcterms", "edm", "lh", "rdf", "rdfs", "owl", "xsd")


def get_prefix_block(g: Graph) -> str:
    """Return a minimal prefix block for the schema summary (avoids overwhelming the LLM)."""
    ns_map = {p: str(ns) for p, ns in GRAPH_PREFIXES.items() if p in SCHEMA_PREFIXES}
    lines = [f"PREFIX {p}: <{ns}>" for p, ns in sorted(ns_map.items())]
    return "\n".join(lines)


def list_distinct_predicates(g: Graph, limit: int = MAX_PREDICATES) -> List[str]:
    """List unique predicates for schema summary (reduces prompt size)."""
    q = f"""
    SELECT DISTINCT ?p WHERE {{
        ?s ?p ?o .
    }} LIMIT {limit}
    """
    return [str(row.p) for row in g.query(q)]


def list_distinct_classes(g: Graph, limit: int = MAX_CLASSES) -> List[str]:
    """List unique rdf:type classes for schema summary."""
    q = f"""
    SELECT DISTINCT ?cls WHERE {{
        ?s a ?cls .
    }} LIMIT {limit}
    """
    return [str(row.cls) for row in g.query(q)]


def sample_triples(
    g: Graph, limit: int = SAMPLE_TRIPLES
) -> List[Tuple[str, str, str]]:
    """Sample triples to give LLM concrete examples of graph structure."""
    q = f"""
    SELECT ?s ?p ?o WHERE {{
        ?s ?p ?o .
    }} LIMIT {limit}
    """
    return [(str(r.s), str(r.p), str(r.o)) for r in g.query(q)]


def build_schema_summary(g: Graph) -> str:
    prefixes = get_prefix_block(g)
    preds = list_distinct_predicates(g)
    clss = list_distinct_classes(g)
    samples = sample_triples(g)
    pred_lines = "\n".join(f"- {p}" for p in preds)
    cls_lines = "\n".join(f"- {c}" for c in clss)
    sample_lines = "\n".join(f"- {s} {p} {o}" for s, p, o in samples)
    summary = f"""
{prefixes}
# Predicates (sampled, unique up to {MAX_PREDICATES})
{pred_lines}
# Classes / rdf:type (sampled, unique up to {MAX_CLASSES})
{cls_lines}
# Sample triples (up to {SAMPLE_TRIPLES})
{sample_lines}
"""
    return summary.strip()


# ----------------------------
# 3) Prompting Gemma: NL -> SPARQL
# ----------------------------

SPARQL_INSTRUCTIONS = """
You are a SPARQL generator. Convert the user QUESTION into a valid SPARQL 1.1 SELECT query.
CRITICAL: Your response MUST include a complete query: PREFIX (only dc, dcterms, lh) + SELECT + WHERE {{ ... }}.
The local-history namespace is PREFIX lh: <http://example.org/localhistory/> — use exactly the prefix lh:, never rh: or localhistory:.
Example for "Which items are linked to Romania?":
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX lh: <http://example.org/localhistory/>
SELECT ?item WHERE {{
  ?item dcterms:spatial ?place .
  FILTER(REGEX(STR(?place), "Romania|Roumanie|Roménia|Romunija|Rumunija|Errumania", "i"))
}}
- Use ONLY predicates from the schema: dcterms:spatial (location), dc:subject, dc:creator.
- Do NOT use Wikidata (wdt:). Return ONLY the SPARQL in a ```sparql code block.
"""


def make_sparql_prompt(schema_summary: str, question: str) -> str:
    return f"""{SPARQL_INSTRUCTIONS}
SCHEMA SUMMARY:
{schema_summary}
QUESTION:
{question}
Return only the SPARQL query in a code block.
"""


CODE_BLOCK_RE = re.compile(
    r"```(?:sparql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL
)


def _strip_schema_from_query(content: str) -> str:
    """Remove schema summary lines if LLM mistakenly included them in the code block."""
    lines = content.split("\n")
    kept = []
    for line in lines:
        stripped = line.strip()
        # Stop at schema section headers or predicate/class list items
        if stripped.startswith("# Predicates") or stripped.startswith("# Classes") or stripped.startswith("# Sample"):
            break
        if stripped.startswith("- ") and ("http://" in stripped or "https://" in stripped):
            break
        kept.append(line)
    return "\n".join(kept).strip()


def normalize_lh_prefix(query: str) -> str:
    """Force local-history namespace to lh: (models sometimes emit rh: by typo)."""
    uri = GRAPH_PREFIXES["lh"]
    uri_esc = re.escape(uri)
    query = re.sub(
        rf"PREFIX\s+rh:\s*<\s*{uri_esc}\s*>",
        f"PREFIX lh: <{uri}>",
        query,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\brh:", "lh:", query, flags=re.IGNORECASE)


def extract_sparql_from_text(text: str) -> str:
    """Extract the first code block content; fallback to whole text.
    Strips any schema summary the LLM may have mistakenly included."""
    m = CODE_BLOCK_RE.search(text)
    if m:
        content = m.group(1).strip()
    else:
        content = text.strip()
    return normalize_lh_prefix(_strip_schema_from_query(content))


def generate_sparql(question: str, schema_summary: str) -> str:
    raw = ask_local_llm(make_sparql_prompt(schema_summary, question))
    query = extract_sparql_from_text(raw)
    return query


# ----------------------------
# 4) Execute SPARQL with rdflib (and optional self-repair)
# ----------------------------


def run_sparql(g: Graph, query: str) -> Tuple[List[str], List[Tuple]]:
    res = g.query(query)
    vars_ = [str(v) for v in res.vars]
    rows = [tuple(str(cell) for cell in r) for r in res]
    return vars_, rows


REPAIR_INSTRUCTIONS = """
Return a COMPLETE corrected query (PREFIX + SELECT + WHERE).
If the error says "found end of text" or "Expected SelectQuery", the query was INCOMPLETE — you MUST add the full SELECT ... WHERE {{ ... }}.
Local-history resources use PREFIX lh: <http://example.org/localhistory/> only — never rh:.
Example for "items linked to Romania":
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX lh: <http://example.org/localhistory/>
SELECT ?item WHERE {{ ?item dcterms:spatial ?place . FILTER(REGEX(STR(?place), "Romania|Roumanie|Roménia|Romunija|Rumunija|Errumania", "i")) }}
- Use dcterms:spatial for locations. Do NOT use wdt:. Return ONLY the SPARQL in a ```sparql code block.
"""


def repair_sparql(
    schema_summary: str,
    question: str,
    bad_query: str,
    error_msg: str,
) -> str:
    prompt = f"""{REPAIR_INSTRUCTIONS}
SCHEMA SUMMARY:
{schema_summary}
ORIGINAL QUESTION:
{question}
BAD SPARQL:
{bad_query}
ERROR MESSAGE:
{error_msg}
Return only the corrected SPARQL in a code block. The block must contain ONLY the query (PREFIX + SELECT + WHERE), NOT the schema summary.
"""
    raw = ask_local_llm(prompt)
    return extract_sparql_from_text(raw)


def answer_with_sparql_generation(
    g: Graph,
    schema_summary: str,
    question: str,
    try_repair: bool = True,
) -> dict:
    sparql = generate_sparql(question, schema_summary)
    # Try execution; optionally repair on parse/execution error
    try:
        vars_, rows = run_sparql(g, sparql)
        return {
            "query": sparql,
            "vars": vars_,
            "rows": rows,
            "repaired": False,
            "error": None,
        }
    except Exception as e:
        err = str(e)
        if try_repair:
            repaired = repair_sparql(schema_summary, question, sparql, err)
            try:
                vars_, rows = run_sparql(g, repaired)
                return {
                    "query": repaired,
                    "vars": vars_,
                    "rows": rows,
                    "repaired": True,
                    "error": None,
                }
            except Exception as e2:
                return {
                    "query": repaired,
                    "vars": [],
                    "rows": [],
                    "repaired": True,
                    "error": str(e2),
                }
        else:
            return {
                "query": sparql,
                "vars": [],
                "rows": [],
                "repaired": False,
                "error": err,
            }


# ----------------------------
# 5) (Baseline) Direct LLM answer w/o KG
# ----------------------------


def answer_no_rag(question: str) -> str:
    prompt = f"Answer the following question as best as you can:\n\n{question}"
    return ask_local_llm(prompt)


# ----------------------------
# 6) CLI demo
# ----------------------------


def pretty_print_result(result: dict):
    if result.get("error"):
        print("\n[Execution Error]", result["error"])
    print("\n[SPARQL Query Used]")
    print(result["query"])
    print("\n[Repaired?]", result["repaired"])
    vars_ = result.get("vars", [])
    rows = result.get("rows", [])
    if not rows:
        print("\n[No rows returned]")
        return
    print("\n[Results]")
    print(" | ".join(vars_))
    for r in rows[:20]:
        print(" | ".join(r))
    if len(rows) > 20:
        print(f"... (showing 20 of {len(rows)})")


def main():
    if not KB_PATH.exists():
        print(f"KB file not found: {KB_PATH}")
        print("Run the pipeline first (Phase 2) to generate kb_expanded.nt")
        sys.exit(1)

    g = load_graph(KB_PATH)
    schema = build_schema_summary(g)

    while True:
        q = input("\nQuestion (or 'quit'): ").strip()
        if q.lower() == "quit":
            break
        print("\n--- Baseline (No RAG) ---")
        try:
            print(answer_no_rag(q))
        except RuntimeError as e:
            print(f"Error: {e}")
        print("\n--- SPARQL-generation RAG (Gemma 2B + rdflib) ---")
        try:
            result = answer_with_sparql_generation(g, schema, q, try_repair=True)
            pretty_print_result(result)
        except RuntimeError as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
