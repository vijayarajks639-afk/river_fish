# Data Generator Agent — Charter & Briefing

> **Purpose of this file:** the standing brief handed to the dedicated Data Generator
> agent when it is spun (planned: M5, the river/fish visualization milestone). It is kept
> **continuously informed** — every architectural change that affects synthetic data is
> appended to the *Briefing Log* at the bottom. Read top-to-bottom before generating anything.

---

## 1. Mission

Generate **rich, multi-source synthetic banking data** that:
1. Makes the lineage (river/fish) demo visually compelling across many source systems.
2. Lets the gap-analysis module find *real, explainable* "loaded-but-unused" columns.
3. Is **consistent with the live market data** that `market_data.py` already ingests.
4. Loads into **DuckDB** so a Business Analyst can run inspect-SQL per lineage hop.

This agent owns the **customer/counterparty tier**. It does NOT touch market data.

---

## 2. THE HARD GOVERNANCE BOUNDARY (non-negotiable)

| Tier | Owner | Real or synthetic? | Rule |
|---|---|---|---|
| **Public market / reference data** (FX, yields, VIX, indices) | `market_data.py` (already built) | **REAL — live** | Do NOT generate or duplicate this. Reference it. |
| **Customer / counterparty data** (names, exposures, PD, LGD, accounts, channel events) | **THIS AGENT** | **SYNTHETIC only** | No PII. No real people. No real account numbers. DPDP-safe by construction. |

- **Never** scrape, fetch, or copy real customer data from anywhere.
- **Never** put a real person's name, PAN, Aadhaar, account number, card number, email, or phone.
- Use faker-style synthetic identities with obviously-synthetic markers (e.g. `CPTY_000123`, `Synthetic Corp 47 Ltd`).
- The lineage engine reads **SQL text only**; generated rows live in DuckDB for BA inspection and **never enter an LLM prompt**.

---

## 3. Align to the LIVE market basket (`market_data.py`)

The generator must make synthetic customer data that *plausibly consumes* the real feeds, so lineage from **real market data → synthetic exposure → risk number** is demonstrable:

| Real feed (live) | Synthetic data must align so that… |
|---|---|
| **FX**: EUR/INR, USD/INR, GBP/INR, EUR/USD | Every exposure has a `currency` in {INR, USD, EUR, GBP}; a base-currency conversion can JOIN to the real FX rate. (This **closes the `currency` gap** found by gap_analysis.) |
| **Yields**: ^TNX (10Y UST), ^IRX (13wk) | Provide a `tenor` / `maturity` so a risk-free discount rate can be looked up. |
| **Stress**: ^VIX | Provide a `stress_scenario` flag so a VIX-driven stress multiplier is traceable. |
| **Equity indices**: ^NSEI, ^GSPC | Give a subset of counterparties an `equity_ticker` so `market_value` can be marked from a real price. (This **closes the `market_value` gap**.) |

Keep the real values OUT of the generated tables — store only the **join keys** (currency code, ticker, tenor). The actual price/rate comes from `market_data.py` at query time. That is the whole point: lineage should show the JOIN to the external feed.

---

## 4. Source systems to generate (from `config.SOURCE_SYSTEMS`)

Currently ACTIVE (already in the SQL pipeline — keep consistent, don't break):
`creditmart`, `marketriskhub`, `goldensourcefdo`.

CATALOG systems to bring to life (priority order for demo richness):
1. `core_banking` — accounts, balances, daily transactions
2. `credit_card` — spend, limit, utilization, delinquency, rewards
3. `loans` — personal/auto/mortgage origination + servicing + EMI status
4. `atm_channel` — withdrawal/enquiry events (channel data)
5. `mobile_banking` — session + in-app transaction events
6. `retail_banking`, `consumer_banking`, `commercial_banking` — product holdings
7. `campaign_mgmt` — offers, responses, attribution
8. `social_sentiment` — **synthetic** sentiment scores per counterparty (NOT scraped social posts — generate a score 0–1 with a label)
9. `branch_crm`, `ivr_channel`, `collections`, `fraud_platform` — stretch

**Deliberately leave some generated columns unconsumed** so gap_analysis has true findings to report (that is a feature, not a bug — it's the secondary product).

---

## 5. Consistency contract with the existing pipeline

The current SQL pipeline (`sql/10..40`) and `schema.py` `KNOWN_SCHEMA` define the truth. The generator must:
- Match existing column names/types for the 3 active systems exactly.
- Register every new table/column in `schema.py` `KNOWN_SCHEMA` (or the generator emits an updated catalog the maintainer merges).
- Use `counterparty_id` as the universal join key (format `CPTY_%06d`).
- Produce a **referentially consistent** set: every `counterparty_id` in a product/channel table must exist in `goldensourcefdo.raw_counterparty`.

---

## 6. Output / deliverables

1. `generate_data.py` — deterministic (seeded) generator; `--rows N` flag; writes to DuckDB.
2. A DuckDB file (gitignored, regenerated on demand — `data/` is already in `.gitignore`).
3. New `sql/` transforms (or extend existing) that consume some — not all — new columns, so:
   - lineage spans 8–12 source systems,
   - gap_analysis reports realistic unused-data findings,
   - at least one path goes **real market feed → synthetic exposure → mart risk number**.
4. Update `schema.py` `KNOWN_SCHEMA` + this brief's Briefing Log.

---

## 7. Acceptance criteria

- [ ] `python generate_data.py` runs offline, deterministic, **zero PII**, < 30s for demo volume.
- [ ] Referential integrity holds (no orphan counterparty_id).
- [ ] `gap_analysis.py` reports ≥ 5 genuinely-unused columns across ≥ 3 systems, each explainable.
- [ ] At least one lineage path JOINs to a real `market_data.py` feed (FX or equity).
- [ ] `test_lineage.py` still 100% green after schema expansion.
- [ ] Governance banner present; brief's Briefing Log updated.

---

## 8. Briefing Log (kept continuously informed — newest first)

- **2026-06-25** — *SPUN — first generation complete.* `generate_data.py` created and
  executed (seed=42, 500 counterparties). DuckDB `data/warehouse.duckdb` populated with
  18,742 rows across 15 tables spanning 11 source systems. `sql_extended/` folder created
  with 4 SQL transform files (50–80) covering FX exposure, channel activity, product
  holdings, and campaign+sentiment+commercial marts. `schema.py` KNOWN_SCHEMA extended
  with 32 new table entries covering all new source and mart tables. `test_lineage.py`
  confirmed 18/18 green (core pipeline untouched: 54 columns, 49 edges). `gap_analysis.py`
  reports 6 gap columns across 3 core systems (57% coverage). Extended systems carry ~30%
  unconsumed columns by design (gap candidates: `cashback_earned_ytd`, `churn_score`,
  `bureau_score_at_origination`, `news_score`, `covenant_breach_flag`, `propensity_score`,
  `device_id_hash`, `failure_code`, etc.). FX lineage path operational:
  `creditmart.currency` (synthetic JOIN key) → `stg_fx_rates.spot_rate` (real
  market_data.py feed) → `stg_fx_exposure_inr.exposure_inr` (derived risk number).

- **2026-06-25** — *Real market data added.* `market_data.py` now ingests LIVE public market
  data (FX: EUR/USD/GBP-INR + EUR/USD; yields: ^TNX, ^IRX; stress: ^VIX; equity: ^NSEI, ^GSPC)
  with freshness TTL + cache fallback. **Action for generator:** align synthetic data to these
  via join keys only (currency code, equity_ticker, tenor) — do NOT embed real values. Aim to
  close the `currency` and `market_value` gaps via real-feed JOINs.
- **2026-06-25** — *Gap analysis is a secondary product.* `gap_analysis.py` finds loaded-but-unused
  source columns. **Action for generator:** intentionally leave a realistic fraction of generated
  columns unconsumed so the gap report has true, business-relevant findings.
- **2026-06-25** — *Source taxonomy expanded.* `config.SOURCE_SYSTEMS` now has 3 active + 14 catalog
  banking systems (ATM, mobile, branch, IVR, social, core banking, cards, loans, retail, consumer,
  commercial, campaign, collections, fraud). **Action for generator:** bring these to life per §4.
- **2026-06-25** — *P1 hardening done.* `find_node` exact/dotted-suffix only; `schema.py` catalog +
  `validate_lineage_nodes` + abstain; 18/18 tests green. **Action for generator:** every new table
  must be registered in `KNOWN_SCHEMA` or validation will flag its columns as unknown.

---

## 9. Status

**SPUN — first generation complete (2026-06-25).** `generate_data.py` is live; DuckDB
`data/warehouse.duckdb` is populated. Re-run anytime with `.venv\Scripts\python generate_data.py`.
Core test suite 18/18 green. `sql_extended/` transforms ready for the river/fish M5 visualization.
