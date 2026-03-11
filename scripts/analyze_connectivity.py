"""
Analyze connectivity of the expanded Knowledge Base.

Computes connected components (BFS) on the undirected entity graph.
Useful for KGE: isolated components can harm embedding quality.
Run: python scripts/analyze_connectivity.py
"""

import sys
from pathlib import Path

# Add project root for config
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rdflib import Graph, URIRef

import config


def get_entity_graph(kb_path: str) -> tuple[dict[str, set[str]], set[str]]:
    """
    Build undirected adjacency list from KB.
    Only considers URIs (entities); literals are ignored for connectivity.
    Returns (adjacency dict, set of all entity URIs).
    """
    g = Graph()
    g.parse(kb_path, format="nt")
    adj: dict[str, set[str]] = {}
    entities = set()
    for s, p, o in g:
        if isinstance(s, URIRef) and isinstance(o, URIRef):
            s_str = str(s)
            o_str = str(o)
            entities.add(s_str)
            entities.add(o_str)
            adj.setdefault(s_str, set()).add(o_str)
            adj.setdefault(o_str, set()).add(s_str)
    return adj, entities


def connected_components(adj: dict[str, set[str]], entities: set[str]) -> list[set[str]]:
    """Compute connected components via BFS."""
    visited = set()
    components = []
    for e in entities:
        if e in visited:
            continue
        comp = set()
        stack = [e]
        while stack:
            n = stack.pop()
            if n in visited:
                continue
            visited.add(n)
            comp.add(n)
            for neighbor in adj.get(n, set()):
                if neighbor not in visited:
                    stack.append(neighbor)
        components.append(comp)
    return components


def main():
    kb_path = config.KB_EXPANDED
    if not Path(kb_path).exists():
        print(f"KB file not found: {kb_path}")
        print("Run the pipeline first: python run_pipeline.py")
        sys.exit(1)

    print(f"Loading KB from {kb_path}...")
    adj, entities = get_entity_graph(kb_path)
    print(f"  Entities (URI nodes): {len(entities)}")

    components = connected_components(adj, entities)
    sizes = sorted((len(c) for c in components), reverse=True)

    print(f"\nConnectivity analysis:")
    print(f"  Number of connected components: {len(components)}")
    print(f"  Largest component size: {sizes[0] if sizes else 0}")
    if len(sizes) > 1:
        print(f"  Second largest: {sizes[1]}")
    isolated = sum(1 for s in sizes if s == 1)
    if isolated:
        print(f"  Isolated entities (size=1): {isolated}")

    # Optionally list a few isolated entities
    if isolated > 0:
        isolated_comps = [c for c in components if len(c) == 1]
        sample = list(isolated_comps[:5])
        print(f"\n  Sample isolated entities:")
        for comp in sample:
            uri = next(iter(comp))
            short = uri.split("/")[-1][:60] if "/" in uri else uri[:60]
            print(f"    - {short}...")


if __name__ == "__main__":
    main()
