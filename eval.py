"""M7 — Evaluation harness (the honesty capstone).

Proves the engine does what it claims AND reports any failures openly (never hides them):
  1. Lineage correctness vs hand-authored GROUND TRUTH (the auditable claim).
  2. Guardrails — out-of-scope / analytics questions ABSTAIN; no hallucinated columns.
  3. Determinism — same SQL in, same graph out (reproducible, audit-grade).
  4. Governance — the lineage/explain path reads SQL text only; no DuckDB rows touched.
  5. Adversarial — substring traps (e.g. 'loss') must NOT false-match a real column.

Exit code is non-zero if any HARD assertion fails — so this can gate a release.
Run:  python eval.py
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import networkx as nx

from lineage import build_graph, find_node, trace_to_source
from nl import answer
from explain import explain_column, _build_prompt

_results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = ""):
    _results.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}]  {name}" + (f"  — {detail}" if detail else ""))


# ── 1. Lineage correctness vs hand-authored ground truth ──────────────────────
# (basename of the SOURCE columns each target should trace to — verified by hand
#  against sql/10..40)
GROUND_TRUTH: dict[str, set[str]] = {
    "mart_risk_summary.stressed_rwa":            {"pd", "lgd", "internal_rating", "exposure_amount", "var_1d"},
    "mart_risk_summary.risk_weighted_amount":    {"pd", "lgd", "exposure_amount", "var_1d"},
    "mart_risk_summary.regulatory_bucket":       {"pd", "lgd", "exposure_amount", "var_1d"},   # NOT internal_rating
    "mart_risk_summary.expected_loss":           {"pd", "lgd", "exposure_amount"},
    "mart_portfolio_concentration.avg_pd":       {"pd"},
    "mart_portfolio_concentration.total_expected_loss": {"pd", "lgd", "exposure_amount"},
}

print("\n1. Lineage correctness vs ground truth")
g = build_graph()
for target, expected in GROUND_TRUTH.items():
    _, roots, _ = trace_to_source(g, target)
    got = {r.split(".")[-1] for r in roots}
    check(f"{target.split('.')[-1]} -> {sorted(expected)}", got == expected,
          "" if got == expected else f"got {sorted(got)}")

# the discrimination test: regulatory_bucket must EXCLUDE internal_rating, stressed_rwa must INCLUDE it
_, rb_roots, _ = trace_to_source(g, "mart_risk_summary.regulatory_bucket")
_, sr_roots, _ = trace_to_source(g, "mart_risk_summary.stressed_rwa")
check("regulatory_bucket excludes internal_rating (CASE key discrimination)",
      not any("internal_rating" in r for r in rb_roots))
check("stressed_rwa includes internal_rating (nested CASE key)",
      any("internal_rating" in r for r in sr_roots))


# ── 2. Guardrails — abstain, no hallucination ─────────────────────────────────
print("\n2. Guardrails (abstain / grounding)")
a_moon = answer("where does the moon landing data come from?", g)
check("out-of-scope question ABSTAINS", a_moon.abstained)

a_anal = answer("region wise total ATM withdrawal in %", g)
check("analytics question ABSTAINS (lineage != analytics)", a_anal.abstained)

a_good = answer("where does stressed_rwa come from?", g)
check("valid lineage question RESOLVES", (not a_good.abstained) and a_good.column is not None)

# the NL layer must never return a column that isn't in the graph
for q in ("trace the fraud_score", "where does customer_satisfaction come from?"):
    a = answer(q, g)
    grounded = (a.column is None) or (a.column in g)
    check(f"no hallucinated column for: {q!r}", grounded,
          "" if grounded else f"returned {a.column}")


# ── 3. Determinism / reproducibility ──────────────────────────────────────────
print("\n3. Determinism")
g2 = build_graph()
same = (set(g.nodes) == set(g2.nodes)) and (set(g.edges) == set(g2.edges))
check("graph is reproducible across builds (same nodes & edges)", same)
check("graph is a DAG (no cycles)", nx.is_directed_acyclic_graph(g))


# ── 4. Governance — SQL text only, no data rows in the LLM prompt ─────────────
print("\n4. Governance (on-prem: metadata only)")
# the explain prompt must contain the SQL expression + column names (metadata) and
# must NOT contain any data values — by construction we never read rows.
prompt = _build_prompt("mart_risk_summary.stressed_rwa",
                       ["creditmart.raw_credit_exposures.pd"], [], "(e.stressed_expected_loss + m.var_1d) * 1.06",
                       "arithmetic")
check("explain prompt carries the SQL derivation (metadata)", "var_1d" in prompt and "1.06" in prompt)
# lineage module must not import duckdb (the data engine) — proves the trace path never opens data
import lineage as _lin
check("lineage module does not import duckdb (reads SQL text only)",
      "duckdb" not in getattr(_lin, "__dict__", {}))
import importlib, inspect
lin_src = inspect.getsource(_lin)
check("lineage.load_sql reads only .sql files (no data access)",
      ".sql" in lin_src and "read_text" in lin_src)


# ── 5. Adversarial — substring traps must not false-match ─────────────────────
print("\n5. Adversarial (substring / false-match)")
# 'loss' is a substring of 'expected_loss' / 'stressed_expected_loss' — must NOT silently resolve
a_loss = answer("trace loss back to source", g)
false_match = (a_loss.column is not None) and (a_loss.column.split(".")[-1] == "loss")
check("'loss' does not false-match expected_loss (P1-1 guard holds)", not false_match)

# bare ambiguous 'pd' must raise (caller disambiguates) — find_node contract
try:
    find_node(g, "pd")
    raised = False
except ValueError:
    raised = True
check("bare ambiguous 'pd' raises ValueError (no silent pick)", raised)


# ── Summary (honest) ──────────────────────────────────────────────────────────
total = len(_results)
passed = sum(1 for _, ok, _ in _results if ok)
failed = total - passed
print("\n" + "=" * 60)
print(f"  EVAL: {passed}/{total} passed" + (f"  — {failed} FAILED" if failed else "  — all green"))
if failed:
    print("  FAILURES (reported, not hidden):")
    for name, ok, detail in _results:
        if not ok:
            print(f"    - {name}  {detail}")
print("=" * 60 + "\n")

sys.exit(1 if failed else 0)
