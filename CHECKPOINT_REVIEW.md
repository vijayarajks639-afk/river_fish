# Interim Quality Checkpoint — "Find My Data Path" (after M1/M2)

Two independent reviewer agents red-teamed the analysis + build so far (research/plan, the synthetic
SQL pipeline, and `lineage.py` — the deterministic column-level lineage backbone). The LLM/NL layers
(`explain.py`/`nl.py`/`app.py`) and `MARKET_AND_FUTURE.md` are **not yet built** — those claims are
still aspirational, not code-verified.

---

## Reviewer A — Technical QA · Verdict: **CONDITIONAL PASS**
**Verified correct:** every column→column edge matches hand-derived ground truth; `stressed_rwa` → 5
sources incl. `internal_rating`; `regulatory_bucket` correctly *excludes* `internal_rating`; SUM-aggregation
lineage right; DAG valid/acyclic; deterministic (stable 3×); **on-prem claim TRUE** (reads only SQL text,
zero data access); docstrings honest.

| Sev | Issue | Fix |
|---|---|---|
| **High** | `find_node` bare `.endswith(name)` mis-matches (`"loss"`→expected_loss, `"pd"`→avg_pd). Harmless to qualified targets; **bites the free-text NL layer (M4)**. | Keep only exact + `endswith("."+name)`; surface ambiguity, don't silently pick. |
| Med | Ambiguous matches silently take `cands[0]`. | Prefer most-downstream node / return candidate list. |
| Med | `column_paths()` parses SQL twice per run. | Compute once, pass into `build_graph()`. |
| Low | glob ordering contract; dead `DATA_DIR`; `all_simple_paths` exponential on dense graphs. | Document / remove / note as scale caveat. |

## Reviewer B — Analysis & Design · Verdict: **SOUND-WITH-GAPS**
**Fact-check:** all headline research claims **VERIFIED** (Spider 2.0 ~6–30% vs 91%; Cortex "no data
leaves"; UC column lineage; Gartner 2026 data-contracts; Iceberg; BCBS 239). Caveats to add:
- Cortex "no data/metadata leaves" is **conditional on Snowflake-hosted models** (changes if routed to Anthropic/OpenAI).
- Databricks UC lineage is **runtime (query-plan) capture**, architecturally different from our **static AST parse** — name it as a trade-off, don't blur.
- Strengthen BCBS 239 (2013) with the **ECB May 2024 RDARR guide** (explicit attribute-level lineage).

| Sev | Issue | Fix |
|---|---|---|
| **High** | `LineageRunner` is called **without a schema/metadata provider** — the exact fragility the plan claims to solve. `SELECT *` can't expand; the pipeline *dodges* this via explicit columns. The hard case isn't actually tested. | Feed schema metadata (e.g. DuckDB `information_schema`) into the parser, **and** add a `SELECT *` / ambiguous-join test that shows graceful degradation or **abstain**. |
| **High** | Tool choice under-justified: DataHub's `sqlglot`-based parser claims **97–99% CLL** ("outperforms sqllineage by a wide margin"); we name-drop sqlglot but build on the higher-level `sqllineage.LineageRunner`. | Move backbone to **`sqlglot.lineage`** (finer-grained, schema-aware) **or** write an ADR defending sqllineage for v1. |
| Med | OpenLineage / DataHub not positioned. | **Emit the DAG as OpenLineage events** + a one-page ADR — biggest credibility/standards upgrade. |
| Med | Non-SQL ETL blind spot (Ab Initio / Informatica / PySpark / stored procs). | Add a **"known boundaries"** paragraph (static SQL parsing covers the SQL-expressed portion; non-SQL needs runtime capture or manual stitching). |
| Med | LLM role is the weakest-specified part — the deterministic layer already nails every built case. | Make the LLM do something deterministic **cannot** (reconcile ambiguous/non-parseable transforms, labelled "suggestion — needs sign-off") **or** honestly downgrade its billing to "NL interface + explanation." |
| Low | `find_node` endswith false matches at 1000s of columns (echoes Reviewer A High). | Name as a scaling limitation. |

**Positioning gaps:** add an **interoperability module (OpenLineage)**; beef up **M7 eval with adversarial
cases that report where the engine *fails*** (a green check on a pipeline you wrote is weak evidence); add
**scale honesty**; be ready to speak to **Iceberg/dbt** (table-stakes for the target roles).

**Honesty risks (would not survive a senior interview):** (1) marketing column-level robustness while running
without schema metadata + avoiding `SELECT *`; (2) implying the LLM does heavy lifting; (3) implicit "open
version of Cortex/Unity Catalog" when those do **runtime** capture across non-SQL workloads, ours does static SQL.

---

## Consolidated action plan (priority order)

**P1 — before the NL layer (M4):**
1. Fix `find_node` (exact + dotted-suffix only; surface ambiguity). *(A-High, B-Low)*
2. Feed **schema metadata** into the parser **+ add a `SELECT *` / ambiguous-join test** showing graceful
   degradation/abstain — converts a hidden failure into a demonstrated boundary. *(B-High)*
3. **ADR**: `sqllineage` vs `sqlglot.lineage` vs DataHub vs OpenLineage → decide/justify the backbone
   (lean toward moving to `sqlglot.lineage`). *(B-High)*

**P2 — strengthen + positioning:**
4. Emit lineage as **OpenLineage events** + interoperability note. *(B-Med)*
5. Add **"Known boundaries"** section (non-SQL ETL; runtime vs static; scale). *(B-Med)*
6. Make the **LLM load-bearing** in the demo, or downgrade its billing honestly. *(B-Med)*
7. **M7 eval**: adversarial cases; report failures, not just passes. *(B)*

**P3 — perf/polish:** single-parse `column_paths`; glob ordering contract; remove dead `DATA_DIR`. *(A-Med/Low)*

**Docs:** add **ECB May 2024 RDARR** citation; add the **Cortex/UC caveats** to `MARKET_AND_FUTURE.md`.

**Both verdicts agree:** the deterministic-backbone + governed-LLM-assist architecture is the **correct call**
and is validated by the academic frontier and the vendor market; it's a ship-worthy learning/portfolio
artifact **once the `find_node` fix and the schema-metadata gap are addressed.**
