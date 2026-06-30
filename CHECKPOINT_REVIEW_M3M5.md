# Checkpoint Review — M3–M5 (pre-completion)

**Date:** 2026-06-25 · **Reviewer:** orchestrator self-review
**Caveat (honest):** the *independent* QA agent hit a session limit and returned no findings. This is a
self-review, not an independent one. An independent QA re-run is recommended after the limit resets (10pm
IST) — non-blocking for a learning/portfolio push, but listed as a follow-up.

## Scope
M3 (`explain.py`), M4 (`nl.py`), M5 (`app.py`), extended-graph support (`lineage.py`, `config.py`), the
`schema.py` duplicate-key merge, `gap_analysis.py`, `market_data.py`, and `eval.py`.

## Verification run
| Check | Result |
|---|---|
| `test_lineage.py` (regression) | ✅ 18/18 |
| `eval.py` (correctness, guardrails, governance, adversarial) | ✅ 20/20 |
| `AppTest` (app loads, key-less, DuckDB-free) | ✅ 5 tabs, 0 exceptions |
| Lineage correctness vs hand-authored ground truth | ✅ all 6 targets exact |
| CASE-key discrimination (reg_bucket excl. / stressed_rwa incl. internal_rating) | ✅ |

## Findings
| # | Sev | Area | Finding | Status |
|---|---|---|---|---|
| 1 | **MED** | app/nl/explain | `lstrip("<default>.")` strips a char-set, not a prefix → extended names (`loans.*`, `atm_channel.*`) rendered corrupted | ✅ FIXED (proper prefix removal) |
| 2 | LOW | nl.suggest_columns | suggested `SELECT *` (`.*`) nodes as traceable columns | ✅ FIXED (filtered) |
| 3 | LOW | explain.py | re-parses all SQL via sqlglot on each `explain_column` call | Accepted (graph is cached; fine for demo — memoize if scaled) |
| 4 | INFO | deploy | local Streamlit 1.58 deprecates `use_container_width`; deploy pins 1.41 where it's correct | Verify HF still serves 1.41 at deploy time |
| 5 | INFO | lineage | `nx.all_simple_paths` is exponential on dense DAGs | Current DAG is shallow; bound depth/path-count if scaled |
| 6 | INFO | process | independent QA not completed (agent session limit) | Re-run after 10pm IST |

## Governance verdict — PASS
`eval.py` proves it mechanically: the lineage module imports no `duckdb`, `load_sql` reads only `.sql`
text, and the explain prompt carries metadata/SQL only. No data rows reach an LLM. Synthetic customer
data; real public market data only.

## Guardrail verdict — PASS
Out-of-scope and analytics questions abstain; the NL layer never returns a column absent from the graph;
ambiguous bare names raise rather than silently pick; the `'loss'` substring trap is rejected.

## Recommendation
**PASS for push** — the one MED and one LOW are fixed; residual items are INFO/accepted and non-blocking.
Recommend an **independent QA re-run** post-reset as a confidence check before any external showcase.
