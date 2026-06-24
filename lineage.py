"""Deterministic COLUMN-LEVEL lineage — the auditable backbone of "Find My Data Path".

sqllineage parses the pipeline SQL (text only — NO data is read, which is the on-prem design) and
yields column-to-column paths. We assemble them into a networkx DAG (the "river") so we can trace any
column (the "fish") upstream to its source columns or downstream to its consumers.

This layer is DETERMINISTIC and reproducible — the part you could put in front of an auditor.
(The LLM layer, added later, only *explains* derivations; it never invents lineage.)
"""
from __future__ import annotations

import networkx as nx

import config


def load_sql() -> str:
    """Concatenate the pipeline SQL files in order (staging -> integration -> mart)."""
    return "\n\n".join(p.read_text(encoding="utf-8") for p in sorted(config.SQL_DIR.glob("*.sql")))


def column_paths() -> list[list[str]]:
    """Deterministic column-level lineage: a list of paths (source col -> ... -> target col)."""
    from sqllineage.runner import LineageRunner
    runner = LineageRunner(load_sql(), dialect=config.DIALECT)
    return [[str(col) for col in path] for path in runner.get_column_lineage()]


def build_graph() -> nx.DiGraph:
    """The lineage DAG: nodes = qualified columns, edges = 'feeds into'."""
    g = nx.DiGraph()
    for path in column_paths():
        for src, dst in zip(path, path[1:]):
            g.add_edge(src, dst)
    return g


def find_node(g: nx.DiGraph, name: str) -> str | None:
    """Resolve a (possibly unqualified) column name to a graph node (handles the '<default>' schema)."""
    name = name.lower()
    if name in g:
        return name
    cands = [n for n in g.nodes if n.lower() == name
             or n.lower().endswith("." + name) or n.lower().endswith(name)]
    return cands[0] if cands else None


def trace_to_source(g: nx.DiGraph, column: str):
    """Upstream trace: the SOURCE columns (DAG roots) feeding `column`, plus every river path to them."""
    node = find_node(g, column)
    if node is None:
        return None, [], []
    ancestors = nx.ancestors(g, node)
    roots = sorted(n for n in ancestors if g.in_degree(n) == 0)
    paths = [p for r in roots for p in nx.all_simple_paths(g, r, node)]
    return node, roots, paths


DEMO_TARGETS = ["mart_risk_summary.stressed_rwa", "mart_risk_summary.regulatory_bucket",
                "mart_portfolio_concentration.total_expected_loss"]


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    g = build_graph()
    print(f"Lineage graph: {g.number_of_nodes()} columns, {g.number_of_edges()} edges "
          f"(deterministic, from SQL text only)\n")

    print("=== All column lineage paths (source -> ... -> target) ===")
    for p in column_paths():
        print("  " + "  ->  ".join(p))
    print()

    for target in DEMO_TARGETS:
        node, roots, paths = trace_to_source(g, target)
        print(f"=== Find My Data Path:  {target} ===")
        if node is None:
            print("  (column not found in lineage)\n")
            continue
        print("  Source columns:", ", ".join(roots) if roots else "(this IS a source)")
        for p in paths:
            print("   river ~>  " + "  ~>  ".join(p))
        print()
