---
title: Find My Data Path
emoji: 🐟
colorFrom: blue
colorTo: indigo
sdk: streamlit
sdk_version: 1.41.0
app_file: app.py
pinned: false
license: mit
---

# river_fish — "Find My Data Path"

Column-level **data lineage discovery** for a complex, multi-source banking data pipeline, with a
natural-language ("find my data path") way in — built for an **on-prem / data-cannot-leave-the-warehouse**
setting. The mental model: a column is a **fish**; the pipeline is the **river**; where transformations
merge inputs (`C + XYZ = D`) are **tributaries** — and the tool traces a value's journey through them.

> **Learning + portfolio project. Synthetic data only** — no real firm data, no PII. Lineage is derived
> from the **SQL text** (the engine reads *no data rows*), which is the on-prem design.

## Why this is hard (and why it's built this way)
Naive text-to-SQL fails on real enterprise schemas (Spider 2.0: frontier LLMs ~6–30% vs 91% on toy
benchmarks). So the architecture is a **hybrid**:
- **Deterministic backbone** — parse the pipeline SQL → a **column-level lineage DAG** (auditable,
  reproducible; the part you'd show a BCBS 239 auditor).
- **Governed LLM assist** *(in progress)* — explains derivations and powers the NL interface, fed
  **metadata/SQL only, never data**; clearly labelled "suggestion — needs sign-off," never audit-grade.

## Status (work in progress)
- ✅ **M1/M2** — synthetic multi-source SQL pipeline (`sql/`) + deterministic column-level lineage
  engine (`lineage.py`): 54 columns / 49 edges; e.g. `risk_weighted_amount` traces across **2 source
  systems and 2 hops** to `pd, lgd, exposure_amount, var_1d`, including `internal_rating` via a nested CASE.
- 🔎 **Interim QA checkpoint** complete — see [`CHECKPOINT_REVIEW.md`](CHECKPOINT_REVIEW.md) (two
  independent reviewers; known gaps + fix plan tracked there).
- ⏭️ Next: harden free-text resolution + schema-metadata, LLM explanation, NL interface, river/fish viz, eval.

## Run
```bash
python -m venv .venv && .venv/Scripts/activate     # Python 3.12
pip install sqlglot sqllineage duckdb networkx fastembed streamlit anthropic
python lineage.py                                  # prints the column-level lineage + traces
```

## Layout
```
sql/   10_staging · 20_integration (EL = PD×LGD×EAD) · 30_mart ((EL+VaR)×1.06) · 40_portfolio (aggregations)
lineage.py   deterministic column-level lineage (sqllineage → networkx DAG) + trace_to_source()
config.py    paths, source systems, LLM model (optional; $0 without a key)
```
