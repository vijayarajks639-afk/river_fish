# ADR 001 — Column-Level Lineage Backbone Choice

**Status:** Accepted (v1)  
**Date:** 2026-06-24  
**Deciders:** Vijayaraj Shanmugam (portfolio project)

---

## Context

"Find My Data Path" needs a deterministic, reproducible engine to extract column-level lineage
from a multi-stage SQL pipeline (staging → integration → mart). The result must be audit-grade
(i.e. certifiable to a BCBS 239 auditor), on-prem safe, and free to run locally.

Four candidates were evaluated:

| Tool | Layer | Schema-aware | Column-level accuracy | License / cost |
|---|---|---|---|---|
| **sqllineage** (LineageRunner) | High-level Python | ❌ No built-in provider | ~80–90% explicit-SELECT | Apache 2.0 / free |
| **sqlglot.lineage** | Low-level AST | ✅ Schema dict injected | ~95%+ with schema | MIT / free |
| **DataHub / datahub-lineage** | Platform SDK | ✅ Catalog-backed | 97–99% (own claims) | Apache 2.0, heavy infra |
| **OpenLineage** (Marquez) | Runtime events | ✅ Catalog-backed | 100% at runtime | Apache 2.0, runtime-only |

---

## Decision: **sqllineage (v1) with a planned migration path to sqlglot.lineage**

### Why sqllineage for v1

1. **Sufficient accuracy on the explicit-column pipeline.** All four SQL files use explicit `SELECT col1, col2` — no `SELECT *`. sqllineage correctly resolved 54 columns and 49 edges including nested CASE derivations and multi-source JOINs. The QA ground-truth audit found zero wrong edges on this pipeline.

2. **Zero setup friction.** `pip install sqllineage` — no catalog, no platform, no daemon. Matches the on-prem / air-gapped / learning-project constraint where standing up DataHub or Marquez is out of scope.

3. **Enough for the deterministic backbone demo.** The primary portfolio goal is to show the *pattern* (deterministic backbone + governed LLM explanation + NL interface), not to compete with production-grade lineage platforms. sqllineage gets us there without infrastructure overhead.

4. **P1 hardening mitigates the main gap.** The absence of a schema provider (Reviewer B High finding) is addressed by:
   - Banning `SELECT *` in the pipeline SQL (enforced by comment in `10_staging.sql`)
   - `schema.py` `validate_lineage_nodes()` catching any unknown nodes at runtime and emitting an abstain message
   - The test suite in `test_lineage.py` acting as a regression guard

### Why NOT sqlglot.lineage for v1

`sqlglot.lineage` is the stronger long-term choice (finer-grained AST, schema dict parameter,
actively maintained by the Tobiko/SQLMesh team), but it requires rewriting `build_graph()` to use
a different API and injecting the schema dict on every call. **This is the planned M3/v2 upgrade**
when we add the NL layer — at that point schema-awareness becomes load-bearing (because the LLM
will generate SQL and we need the parser to validate it). Migrating then costs one refactor; doing
it now costs time with no user-visible benefit on the current pipeline.

### Why NOT DataHub / OpenLineage for v1

- **DataHub** needs a running metadata platform (Docker) and a DataHub server. Suitable for
  production; over-engineered for a local portfolio demo. The DataHub team's claimed "97–99% CLL"
  is measured against their own catalog-backed parser — the number is not independently audited on
  arbitrary SQL.

- **OpenLineage** is a *runtime event schema*, not a static parser. It captures lineage as queries
  execute (e.g. via Spark/dbt/Airflow integrations). Our pipeline is static SQL text — there is no
  runtime query execution to instrument. OpenLineage and our approach are complementary, not
  competing: we will **emit OpenLineage-format events from our DAG** (P2 item, RF backlog) so the
  output is interoperable with Marquez/DataHub consumers without changing the parser.

---

## Trade-offs accepted

| Trade-off | Mitigation |
|---|---|
| No schema provider → SELECT * unresolvable | Banned in pipeline SQL; `schema.py` abstain guard; test suite |
| LineageRunner parses SQL twice per call (Med bug) | Fixed in this sprint: `_runner()` helper parses once |
| DataHub claims higher CLL accuracy | Our pipeline uses explicit SELECTs — the gap doesn't materialise here |
| sqllineage less actively maintained than sqlglot | Migration to sqlglot.lineage planned for M3 when schema-awareness is load-bearing |

---

## Known boundaries (what static SQL parsing cannot do)

This is intentionally scoped to **SQL-expressed lineage**. The following are out of scope for v1
and should not be implied in demos or interviews:

- **Non-SQL ETL** (Ab Initio, Informatica, PySpark DataFrames, stored procedures with dynamic SQL)
  — these require runtime capture (OpenLineage events, custom instrumentation) or manual stitching.
- **`SELECT *` / dynamic column lists** — parser produces table-level lineage only; abstain message
  fired; column-level label withheld.
- **Runtime vs static** — Databricks Unity Catalog and Snowflake lineage do *runtime* capture via
  query-plan hooks; ours is *static AST parse*. Both are valid designs for different constraints
  (runtime = higher accuracy; static = no query execution needed, air-gap compatible).
- **Scale** — `nx.all_simple_paths` is exponential on dense DAGs. For pipelines with 1000s of
  columns and complex fan-in/fan-out, switch to a bounded traversal (depth limit + path count cap).

---

## Migration plan (v2 / M3)

When the NL layer (M4) is added, migrate the backbone to `sqlglot.lineage`:

```python
# v2 target (sqlglot.lineage)
from sqlglot.lineage import lineage as sqlglot_lineage
from schema import KNOWN_SCHEMA

schema_for_sqlglot = {tbl: {col: "UNKNOWN" for col in cols}
                      for tbl, cols in KNOWN_SCHEMA.items()}

result = sqlglot_lineage(
    column="stressed_rwa",
    sql=mart_sql,
    schema=schema_for_sqlglot,
    dialect="ansi",
)
```

This makes `SELECT *` resolvable (sqlglot expands it against the schema dict) and gives
per-expression sub-lineage (e.g. which sub-expression of a CASE contributes to a column).
