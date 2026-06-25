# river_fish — Sprint Retrospectives

> Recurring cadence (ONE team: Vijay + Claude). Run a retro at each sprint boundary or
> major checkpoint. Newest sprint on top. Keep it honest — friction and misses included.

---

## Sprint 1 — Foundation, Hardening & First Agent Team
**Window:** through 2026-06-25 · **Theme:** deterministic lineage backbone + governed LLM layer

### Delivered
| Story | Item | Status |
|---|---|---|
| RF-2 | Research (Spider 2.0, provenance theory, vendor/market scan) | ✅ Done |
| RF-3 | M1/M2 — synthetic SQL pipeline + column-level lineage engine (54 cols / 49 edges) | ✅ Done |
| RF-4 | Interim QA checkpoint (2 independent reviewers) | ✅ Done |
| RF-5 | P1 hardening — find_node fix, schema.py catalog + abstain, ADR, **18/18 tests** | ✅ Done |
| RF-6 | M3 — LLM derivation explanation (sqlglot extractor, $0 fallback, "needs sign-off") | ✅ Done |
| *bonus* | limitations.py (9 named parser boundaries, business-language + BCBS 239) | ✅ Done |
| *bonus* | gap_analysis.py (secondary product — loaded-but-unused columns) | ✅ Done |
| *bonus* | market_data.py — **live real** public market data (9/9 symbols, freshness TTL) | ✅ Done |
| *bonus* | DATA_GENERATOR_BRIEF.md — agent charter | ✅ Done |
| *infra* | Spun a 3-agent parallel team (data gen · docs · reg-rag UI) | ▶ Running |

### What went well 👍
- **Architecture held under scrutiny.** Two independent QA reviewers validated the hybrid (deterministic backbone + governed LLM). P1 found the `find_node` false-match *before* the NL layer depended on it — cheap fix, right time.
- **Deterministic core is solid.** 18/18 tests green; `stressed_rwa` correctly includes `internal_rating` (CASE key) while `regulatory_bucket` correctly excludes it — genuine column-level discrimination, not hand-waving.
- **Real data, clean governance.** Live market data integrated dependency-free (urllib only → runs on HF Spaces) with the right boundary: **public market data real, customer data synthetic.** That distinction is itself a senior talking point.
- **Smart reframes from the product owner (Vijay).** "Lineage primary, gap analysis secondary" and "source real market data, not stale" both sharpened the product. Gap analysis surfaced *genuine* findings (`market_value`, `currency` loaded-but-unused) — the stakeholder story writes itself.

### What didn't go well 👎 / friction
- **🔴 Security incident (OPEN).** Live credentials were pasted into `settings.json` and backed up to `settings.json.bak`. **Action overdue:** rotate all (GitHub PATs, Google app passwords, YouTube API key, Jira tokens, HF admin pwd) and delete the `.bak`.
- **Scope creep — untracked.** limitations/gap/market-data/agent-brief all exceeded the M3 estimate. Good ideas, but they went in without their own stories/estimates. Velocity is therefore understated and the board doesn't reflect reality.
- **Jira cadence lagged.** No API token in-session → worklogs for RF-5/RF-6 still manual/pending; RF-5 wasn't tagged to a sprint initially. We preach story-first + live worklogs; this sprint we batched.
- **Commits unpushed.** 6 commits ready on `main`; auto-mode blocks push to the default branch → they sit local until Vijay pushes.
- **Environment fragility.** `.venv` had to be rebuilt after the folder rename; Windows cp1252 encoding broke a test print (≥ char). Minor rework, avoidable.

### Actions (carry into Sprint 2)
- [ ] **Rotate exposed credentials + delete `settings.json.bak`** (overdue — do first).
- [ ] Push the 6 commits to GitHub (`git push origin main`).
- [ ] Back-fill Jira: RF-5/RF-6 → Done + worklogs; create stories for the bonus work (gap analysis, limitations, market data) so velocity is honest.
- [ ] Keep estimating *before* building — even for "quick" additions (flag-prereqs habit).
- [ ] Retro stays a standing cadence (this file, every sprint).

### Metrics
- Stories closed: **5** (RF-2..6) + 4 bonus deliverables.
- Tests: **18/18** green. Live data: **9/9** symbols fresh.
- Commits: **6** on `main` (unpushed). New modules: 6 `.py` + 4 `.md`.
- Defects found by QA before downstream impact: **1 HIGH** (`find_node`) + 1 Med (double-parse) — both fixed.

### Agent voices 🗣️ (the specialist agents' own retro)
*Full executive write-up: [`Multi_Agent_Retro_Sprint1.docx`](Multi_Agent_Retro_Sprint1.docx) — for stakeholder presentations.*

- **Data Generator agent** — *Went well:* clean pipeline contract (explicit SELECTs, schema catalog, exact-shape tests) made extension safe; `sql_extended/` kept the core graph stable; SEED=42 + FX join-key landed first try. *Risk:* appended **duplicate KNOWN_SCHEMA keys** for the 3 active tables (last-wins, correct today, latent foot-gun) → merge before commit; `gap_analysis.py` only globs `sql/` so extended-system gaps are invisible; offline FX falls back to 1.0 (needs a "STALE" caption on stage).
- **Research/Docs agent** — *Went well:* read-first briefing gave exact repo vocabulary; web-verification high-yield (Spider 2.0 ICLR, Snowflake verbatim). *Risk:* vendor/Gartner claims age fast and two are vendor-blog "directional" — say "analysts suggest," not "Gartner says."
- **Reg-RAG UI agent** — *Went well:* import-don't-modify kept the UI a thin layer; explicit Streamlit-1.41 rule prevented a broken Space. *Risk:* a **public Space with an API key lets anyone spend it** — keep public demos $0/key-less.

**Common themes:** read-first briefs → near-zero rework · explicit constraints prevented broken output · the gaps were all *unstated judgment calls* (extend-vs-append, as-of dates, requirements rewrite) — fix with a brief house-style. **Top risk across all three: never put a live key on a public demo.**

---

## Planned end-of-project deliverable — "How an AI Agent Team Built This"
*(captured 2026-06-25 at Vijay's request — not yet built; suggest tracking as RF-10)*

A demonstration/showcase of the **multi-agent development method** itself — strong portfolio + interview material for a senior data/AI leadership audience:
- **The org chart & cadence** — product owner (Vijay) + orchestrator (main Claude) + specialist agents (Data Generator, Research/Docs, Reg-RAG UI), run on agile cadence with Jira, QA gates, and retros.
- **How work was partitioned** to avoid collisions (file-surface ownership; only the orchestrator commits the shared repo; isolated project dirs).
- **How agents were briefed cold** (durable charter docs like DATA_GENERATOR_BRIEF.md + a continuously-updated Briefing Log) — the "keep agents informed" pattern.
- **Governance under parallelism** — synthetic-vs-real data boundary preserved across all agents.
- **Outcome view** — what ran in parallel, time compression vs sequential, and the human-in-the-loop control points (sign-off, push, credential handling).
- **Format** — a section in the portfolio PPT + a short MARKDOWN/one-pager; optional architecture diagram. "One team, not human-vs-AI" framing throughout.

---

### Retro template (copy for next sprint)
```
## Sprint N — <theme>
Window: · Theme:
### Delivered            (table: story | item | status)
### What went well 👍
### What didn't go well 👎 / friction
### Actions (carry into Sprint N+1)
### Metrics
```
