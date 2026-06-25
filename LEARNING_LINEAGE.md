# Learning Log: Column-Level Data Lineage

> Concepts learned + crisp interview talking points from building the river_fish engine.
> Written for a senior banking data/AI practitioner. No fundamentals padded in.

---

## 1. Provenance Theory — the Academic Bedrock

Data lineage engineering is applied database provenance theory. Three foundational works define
the vocabulary:

### Why, How, Where — Buneman, Khanna, Tan (2001)
"Why and Where: A Characterization of Data Provenance" (ICDT 2001, London) introduced the
conceptual vocabulary: *why-provenance* (which source tuples contributed to a result tuple),
*where-provenance* (which specific cells in the source data a result cell came from), and
*how-provenance* (the algebraic expression of how inputs were combined). Column-level lineage
is operationalized *where-provenance*: trace a result column cell back to the specific source
column(s) that produced it.

Source: [Why and Where — Semantic Scholar](https://www.semanticscholar.org/paper/Why-and-Where:-A-Characterization-of-Data-Buneman-Khanna/71ef214efae92e788b4020358d23d83525ab193e)

### Provenance in Databases — Cheney, Chiticariu, Tan (2009)
"Provenance in Databases: Why, How, and Where" (*Foundations and Trends in Databases*, 1:379–474,
2009) is the canonical survey: formal provenance models (polynomials, semirings), query
transformations, and the transition from theory to practical database provenance. If you need
one citation for "the academic foundations of data lineage," this is it.

Source: [Provenance in Databases — ACM DL](https://dl.acm.org/doi/10.1561/1900000006)

### W3C PROV (2013)
The W3C PROV-DM (PROV Data Model) is the international standard for expressing provenance
metadata as entities, activities, and agents, with JSON-LD and RDF serializations. OpenLineage
(the open standard used by Airflow, Spark, dbt) is a constrained profile of PROV-DM applied
to data pipeline lineage events.

Source: [W3C PROV family of specs — ACM DL](https://dl.acm.org/doi/10.1145/2452376.2452478)

---

## 2. Table-Level vs Column-Level Lineage

| Dimension | Table-level | Column-level |
|---|---|---|
| Unit of tracking | Table / dataset | Individual column / field |
| What it answers | "Which systems feed this table?" | "Which source columns feed this derived column, through which transformations?" |
| Audit grade (BCBS 239) | Partially — system mapping | Yes — attribute-level traceability |
| Parser complexity | Low (source/target tables) | High (must parse SELECT expressions, aliases, CASE logic, aggregations) |
| Tool examples | Informatica metadata, Airflow DAG view | sqllineage, sqlglot.lineage, Unity Catalog CLL, Snowflake lineage |

**The BCBS 239 cliff:** Principle 2 requires attribute-level lineage, which means column-level.
Table-level lineage is necessary but not sufficient for a regulatory audit. The ECB is now
explicitly rejecting institutions that present system-level maps without field-level traceability.

---

## 3. Impact Analysis vs Root-Cause Analysis

Two directions on the same DAG:

**Upstream trace (root-cause / "find my data path"):** Given a column in a downstream mart,
which source columns ultimately feed it? Implemented in river_fish as `trace_to_source()` —
walks the DAG backwards to all root nodes (in_degree = 0). This is the BCBS 239 audit query:
"Show me where `stressed_rwa` comes from, end to end."

**Downstream trace (impact analysis / "what does this column feed?"):** Given a source column,
which downstream columns, tables, and reports depend on it? Implemented via `nx.descendants()`.
Critical for change management: "If I rename `pd` in stg_credit, what breaks?"

In graph terms: the lineage DAG has edges pointing downstream (source → consumer). Upstream
trace reverses the traversal direction; downstream trace follows it forward.

**The DAG guarantee matters:** A lineage graph must be a DAG (directed acyclic graph) — no
cycles. Cycles would mean a column depends on itself, which is logically impossible in a SQL
pipeline. The DAG structure is what makes both traversal directions valid and the trace results
trustworthy.

---

## 4. The Hybrid Design: Why Deterministic Backbone + Governed LLM Assist

This is the central architectural decision in river_fish and the most important interview point.

### Deterministic backbone
The `lineage.py` engine parses SQL text (sqllineage → networkx DAG). It is:
- **Reproducible:** same SQL → same graph, always. No stochastic variation.
- **Auditable:** an auditor (or your BCBS 239 team) can inspect the parsed paths and verify
  them against the SQL source. The parsing logic is transparent code, not a black box.
- **Not LLM-dependent:** runs at $0 with no API key. Works on air-gapped infrastructure.

### Governed LLM assist
The `explain.py` module adds an LLM explanation layer. It is:
- **Fed metadata/SQL only.** The prompt contains column names, table names, derivation SQL
  expressions, and path structure — never data values or row contents.
- **Clearly labelled.** Every LLM-generated output carries the label
  "AI SUGGESTION — needs sign-off (not audit-grade)". This label is non-negotiable and
  hardcoded in `ExplainResult.__post_init__()`.
- **Gracefully fallback.** If ANTHROPIC_API_KEY is absent or the API call fails, the system
  returns a template-built deterministic explanation. The tool never fails silently or returns
  a blank.

### Why not LLM-only?
Spider 2.0 (ICLR 2025) shows frontier LLMs solve only 6–21% of real enterprise SQL problems.
An LLM generating lineage paths directly would invent plausible-looking but wrong derivations —
exactly the failure mode that makes it useless for an auditor. The deterministic engine
provides the verifiable claim; the LLM provides the readable explanation. Each layer does what
it is good at.

---

## 5. Concrete Engineering Lessons from This Repo

### 5.1 The `find_node` Bare-Suffix Bug and the Fix

**Bug:** An earlier version of `find_node()` matched any node where the search string appeared
as a substring. Searching for `'pd'` would match `'avg_pd'`, `'expected_pd'`, and
`'stg_credit.pd'` — ambiguous and wrong.

**Fix (exact/dotted-suffix logic):**
```python
cands = [n for n in g.nodes if n.lower() == name or n.lower().endswith("." + name)]
```
This accepts only an exact full-name match OR a dotted-suffix match (i.e., the search term
must be the column name part of a `table.column` qualified node). It rejects bare substring
matches. Ambiguity (multiple matches) raises `ValueError` and demands a fully-qualified name.

**Why this matters in production:** In a real banking pipeline with hundreds of columns, bare
substring matching generates false lineage paths — a BCBS 239 audit failure. The exact/dotted
fix is a precision/recall trade: you get fewer matches, but every match is correct.

### 5.2 Schema-Aware Validation + Abstain on SELECT * / Unknown Nodes

`schema.py` `validate_lineage_nodes()` cross-checks every node in the built graph against
`KNOWN_SCHEMA`. If a node is not in the schema, the engine emits an abstain message rather
than silently returning potentially wrong lineage. This is the "honest tool" design principle
articulated in `limitations.py`:

> "An honest tool that says 'I can't see this' is more trustworthy than one that silently
> returns partial results."

`SELECT *` is banned in the pipeline SQL (enforced by comment in `10_staging.sql`) because
sqllineage without a schema provider cannot resolve `SELECT *` to specific columns — it would
produce table-level lineage labeled as column-level, which is both wrong and misleading.

### 5.3 Parse the SQL Once

**Bug (pre-fix):** `build_graph()` called `_runner()` multiple times per invocation, causing
sqllineage to parse the full pipeline SQL string once per call to `column_paths()` inside the
loop — O(n) parses for O(n) path steps.

**Fix:** The `_runner()` helper function parses once and returns the `LineageRunner` object.
`build_graph()` calls `_runner()` once, passes the same runner to `column_paths()`, and
reuses it. Single parse per graph build regardless of pipeline size.

**Lesson:** SQL parsing is not free. Enterprise pipelines with thousands of lines, parsed
repeatedly in a loop, will hit wall-clock problems. Always parse once, cache the parse result,
and reuse.

### 5.4 sqllineage vs sqlglot.lineage — The ADR Choice

Both libraries parse SQL to column-level lineage, but the design decision differs:

| Dimension | sqllineage | sqlglot.lineage |
|---|---|---|
| API | `LineageRunner(sql).get_column_lineage()` | `lineage(column, sql, schema=...)` — per-column query |
| Schema-awareness | No built-in schema provider | Accepts `schema` dict; expands `SELECT *` |
| Maintained by | Community (less active) | Tobiko/SQLMesh team (actively maintained) |
| AST fidelity | High-level | Fine-grained — per-expression sub-lineage in CASE branches |
| v1 choice | Yes | Planned for M3/v2 migration |

**v1 chose sqllineage** because the explicit-SELECT pipeline needs no schema provider, setup
is zero (one pip install), and it correctly resolved 54 columns / 49 edges with zero wrong
edges on ground-truth audit. **The migration to sqlglot.lineage is planned for M3** when the
NL layer arrives and schema-awareness becomes load-bearing (LLM-generated SQL must be
validated against the known schema).

### 5.5 Gap Analysis as a Second Product

The `gap_analysis.py` module runs *after* the lineage DAG is built and asks a different
question: which source columns are loaded into the pipeline but never reach any mart or
reporting layer? This is operationally distinct from lineage tracing — it's a data coverage
and pipeline hygiene product.

This design pattern — derive a second analytics product from the same DAG — is common in
production data observability platforms (Monte Carlo, Bigeye, Soda). The DAG is an asset;
lineage tracing and gap detection are two queries over the same asset.

### 5.6 The Real-Public-Market-Data / Synthetic-Customer-Data Governance Boundary

`market_data.py` fetches live public reference data (FX rates, yields, VIX, NIFTY 50, S&P 500)
from Yahoo Finance. The governance boundary is explicit and enforced:

- **Real data:** public market reference data only (the kind banks legitimately ingest from
  Bloomberg/Reuters). No PII, no customer data, no counterparty data.
- **Synthetic data:** all customer, counterparty, exposure, and internal-rating data.
- **The LLM never sees rows.** The LLM prompt contains SQL expressions and column names only.
  DuckDB rows from market_data.py are for BA per-hop inspection in the UI, not for LLM input.

This boundary maps directly to the real bank architecture: public vendor data flows in from
external endpoints; customer data stays within the regulatory perimeter and is never exported.

---

## 6. Interview Talking Points

These are designed to be said aloud, not read. Each is one or two sentences.

**1. On why column-level lineage matters for banking:**
"Table-level lineage tells you which system a dataset came from. Column-level lineage tells
you exactly which source field — and through which transformation logic — produced a specific
value in your risk report. BCBS 239 Principle 2 requires the second, not the first, and the
ECB is now actively rejecting banks that deliver only the first."

**2. On the hybrid deterministic + LLM design:**
"The deterministic parser gives you audit-grade lineage paths — reproducible, inspectable,
what you show an auditor. The LLM gives you the readable explanation and the NL interface —
fed metadata only, never data, and clearly labelled as a suggestion that needs sign-off.
Each layer does what it's actually good at, and the two are never mixed."

**3. On Spider 2.0 and why LLM-only lineage is wrong:**
"The Spider 2.0 benchmark — ICLR 2025 — tested frontier LLMs on real enterprise SQL workflows.
GPT-4o solved 15% of tasks. That's the benchmark everyone misses when they say 'AI can
understand your SQL.' For a BCBS 239 audit, that error rate is catastrophic. The LLM is not
your lineage engine — it's your explanation and interface layer."

**4. On the find_node precision fix:**
"We caught a bug where searching for 'pd' matched 'avg_pd' — a false positive that would
produce a wrong lineage path. The fix was an exact or dotted-suffix match rule: the search
term must be the full column name or the column-name segment of a qualified table.column node.
That kind of precision engineering matters when the output is being shown to a regulator."

**5. On static vs runtime lineage:**
"Static parsing — what this engine does — reads the SQL text without running the pipeline.
It's air-gap compatible and needs no query execution. Runtime capture — what Databricks Unity
Catalog does — intercepts the query plan as it executes. Both are valid designs; the choice
depends on whether you can run the pipeline in the environment where you're capturing lineage."

**6. On the on-prem governance design:**
"The whole architecture is built around one constraint: data cannot leave the warehouse.
The LLM is fed SQL expressions and column names — metadata — never data rows. The lineage
engine reads no data at all; it parses SQL text only. That's the design you need in a bank
running credit-risk pipelines on-premises with customer data that can't touch a cloud API."

**7. On gap analysis as a leadership deliverable:**
"Once you have a lineage DAG, the second product is free: which source data did you bring into
the pipeline but never consume in any report or mart? That's a direct conversation with your
data owners about what to build next or what to retire — and it comes from the same graph
you already built."

**8. On the market trajectory:**
"The lineage market is at $1.7B in 2025 and growing at 24% CAGR. The governance catalog
vendors — Atlan, Collibra, Alation — are all racing toward active metadata and agentic
governance. The Gartner prediction is that by 2030, AI agents will be interpreting governance
policies into machine-verifiable data contracts automatically. The lineage DAG is the
dependency graph that all of that runs on top of."

---

## 7. Key Vocabulary for Interviews and Positioning

| Term | Crisp definition |
|---|---|
| **Data provenance** | The record of origins, transformations, and movements of a data value through a system. |
| **Where-provenance** | Which source cell/column a result cell came from — the formal term for column-level lineage. |
| **Lineage DAG** | Directed acyclic graph where nodes = columns, edges = "feeds into" relationships. |
| **Root node** | A source column with no upstream parents (in_degree = 0) — the origin point. |
| **Upstream trace** | Walking the DAG backwards from a derived column to its source columns. |
| **Downstream trace** | Walking the DAG forwards — all consumers of a given source column. |
| **Static lineage** | Derived from SQL text parsing without executing the pipeline. |
| **Runtime lineage** | Captured from query-plan hooks or event emission during actual pipeline execution. |
| **Active metadata** | Metadata that continuously monitors, enforces policies, and pushes context into tools. |
| **Data contract** | Machine-readable agreement between data producer and consumer on schema, quality, and SLA. |
| **OpenLineage** | Open event schema (LF AI & Data) for emitting lineage events from Airflow/Spark/dbt. |
| **BCBS 239 Principle 2** | Requires attribute (column)-level data traceability from source to risk report. |
| **MCP** | Model Context Protocol — open standard for LLMs to access tools and data sources inside a governance boundary. |

---

*Synthetic data only. No real firm data, no PII. This project derives lineage from SQL text
— the engine reads no data rows. The LLM explanation layer receives metadata/SQL only.*
