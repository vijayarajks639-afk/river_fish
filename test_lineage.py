"""P1-2 tests: schema validation, find_node ambiguity, SELECT * graceful degradation.

Run:  python test_lineage.py
"""
from __future__ import annotations

import sys
import traceback

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from lineage import build_graph, find_node, trace_to_source
from schema import validate_lineage_nodes, abstain_message, KNOWN_SCHEMA

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
_results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    _results.append((name, condition, detail))
    print(f"  [{status}]  {name}" + (f"  — {detail}" if detail else ""))


# ── build graph once ──────────────────────────────────────────────────────────
print("\nBuilding lineage graph …")
G = build_graph()
print(f"  {G.number_of_nodes()} columns, {G.number_of_edges()} edges\n")


# ════════════════════════════════════════════════════════════════════════
# Suite 1 — Graph integrity
# ════════════════════════════════════════════════════════════════════════
print("Suite 1 — Graph integrity")
check("Graph is a DAG (no cycles)", __import__("networkx").is_directed_acyclic_graph(G))
check("Node count ≥ 50 (synthetic pipeline)", G.number_of_nodes() >= 50)
check("Edge count ≥ 40", G.number_of_edges() >= 40)

# known ground-truth traces
node, roots, paths = trace_to_source(G, "mart_risk_summary.stressed_rwa")
check("stressed_rwa resolves", node is not None)
check("stressed_rwa has ≥ 2 source roots", len(roots) >= 2,
      f"roots={roots}")
check("stressed_rwa root includes pd",
      any("pd" in r for r in roots), f"roots={roots}")
check("stressed_rwa root includes internal_rating",
      any("internal_rating" in r for r in roots), f"roots={roots}")

_, rb_roots, _ = trace_to_source(G, "mart_risk_summary.regulatory_bucket")
check("regulatory_bucket does NOT trace to internal_rating",
      not any("internal_rating" in r for r in rb_roots),
      f"roots={rb_roots}")


# ════════════════════════════════════════════════════════════════════════
# Suite 2 — find_node: exact & dotted-suffix matches
# ════════════════════════════════════════════════════════════════════════
print("\nSuite 2 — find_node resolution")
check("Qualified name resolves",
      find_node(G, "mart_risk_summary.stressed_rwa") is not None,
      f"returned: {find_node(G, 'mart_risk_summary.stressed_rwa')}")

node_pd = find_node(G, "stg_credit.pd")
check("Dotted-suffix resolves stg_credit.pd", node_pd is not None)

# 'pd' alone is ambiguous across stg_credit, creditmart, int_exposure
try:
    find_node(G, "pd")
    ambiguous_raised = False
except ValueError as e:
    ambiguous_raised = True
    ambig_msg = str(e)
check("Bare 'pd' raises ValueError (ambiguous)",
      ambiguous_raised, ambig_msg if ambiguous_raised else "no exception raised")

# 'loss' must NOT match 'expected_loss' — bare-suffix false-match (the P1-1 bug)
try:
    result = find_node(G, "loss")
    false_match = result is not None  # if it resolved, it's a false match
    raises = False
except ValueError:
    false_match = False
    raises = True
check("'loss' does NOT false-match 'expected_loss'",
      not false_match, "(P1-1 regression guard: bare suffix must not resolve)")

# unqualified name that IS unambiguous should still resolve
node_rwa = find_node(G, "mart_risk_summary.stressed_rwa")
check("Fully-qualified name resolves directly", node_rwa is not None)


# ════════════════════════════════════════════════════════════════════════
# Suite 3 — Schema validation (P1-2)
# ════════════════════════════════════════════════════════════════════════
print("\nSuite 3 — Schema validation")
report = validate_lineage_nodes(G)
unknown = report["unknown"]
valid = report["valid"]

check("All pipeline nodes are schema-known (no unknown nodes)",
      len(unknown) == 0,
      f"{len(unknown)} unknown: {unknown[:5]}" if unknown else f"{len(valid)} valid")

# Every known pipeline table appears in KNOWN_SCHEMA
expected_tables = {
    "stg_credit", "stg_market", "ref_counterparty",
    "int_exposure", "mart_risk_summary", "mart_portfolio_concentration",
}
check("All pipeline tables in KNOWN_SCHEMA",
      expected_tables.issubset(KNOWN_SCHEMA.keys()),
      f"missing={expected_tables - set(KNOWN_SCHEMA.keys())}")


# ════════════════════════════════════════════════════════════════════════
# Suite 4 — SELECT * graceful degradation (boundary demo)
# ════════════════════════════════════════════════════════════════════════
print("\nSuite 4 — SELECT * graceful degradation")

SELECT_STAR_SQL = """
CREATE TABLE bad_staging AS
SELECT *
FROM creditmart.raw_credit_exposures;

CREATE TABLE mart_risk_summary AS
SELECT b.*, s.var_1d
FROM bad_staging b
JOIN stg_market s ON b.counterparty_id = s.counterparty_id;
"""

try:
    from sqllineage.runner import LineageRunner
    import networkx as nx

    star_runner = LineageRunner(SELECT_STAR_SQL, dialect="ansi")
    star_paths = [[str(c) for c in p] for p in star_runner.get_column_lineage()]
    star_g = nx.DiGraph()
    for path in star_paths:
        for src, dst in zip(path, path[1:]):
            star_g.add_edge(src, dst)

    star_report = validate_lineage_nodes(star_g)
    star_unknown = star_report["unknown"]
    msg = abstain_message(star_unknown)

    check("SELECT * yields fewer column-level edges than explicit SELECT",
          star_g.number_of_edges() < G.number_of_edges(),
          f"star edges={star_g.number_of_edges()}, full pipeline edges={G.number_of_edges()}")

    check("SELECT * produces unknown/unresolvable nodes in schema check",
          len(star_unknown) > 0 or star_g.number_of_edges() == 0,
          f"unknown={star_unknown}, edges={star_g.number_of_edges()}")

    check("abstain_message fires when schema has unknowns",
          (msg is not None) == (len(star_unknown) > 0),
          msg[:80] if msg else "(no unknowns — parser resolved them)")

    print(f"\n  SELECT * boundary demo:")
    print(f"    Column-level edges resolved: {star_g.number_of_edges()}")
    print(f"    Unresolvable nodes: {star_unknown}")
    if msg:
        print(f"    Abstain message:\n      {msg[:200]}")

except Exception as exc:
    print(f"  [SKIP] SELECT * test errored (environment issue): {exc}")
    check("SELECT * test ran without environment error", False, str(exc))


# ════════════════════════════════════════════════════════════════════════
# Summary
# ════════════════════════════════════════════════════════════════════════
total = len(_results)
passed = sum(1 for _, ok, _ in _results if ok)
failed = total - passed
print(f"\n{'='*55}")
print(f"  {passed}/{total} passed" + (f"  ({failed} FAILED)" if failed else "  — all green"))
print(f"{'='*55}\n")

if failed:
    raise SystemExit(1)
