# Sprint 1 Execution Report — river_fish (Project RF)

**Prepared for:** stakeholder / delivery review  ·  **Source:** live Jira (REST API)  ·  **Date:** 2026-06-30
**Companion deck:** `Sprint1_Review_river_fish.pptx`

> **Sprint 1 is now formally closed in Jira** — native velocity **43 SP** / 46 committed (93%),
> burndown available on board 6. The figures below match the live closed-sprint data.

> Honest, metrics-first review. Where Jira's raw rollup is misleading (epic double-counting), the
> correction is shown. Methodology and caveats are stated at the end.

---

## 1. Executive summary
A full audit-grade column-level data-lineage prototype (milestones M1–M7) was delivered in a single
working session by a human-led **AI agent team**. **43 of 46 story points completed (93%)**; the two
open items (deploy, independent QA re-run) are blocked on **external inputs**, not capacity. Quality
gates were green throughout (**18/18** tests, **20/20** eval), **zero defects escaped**, and the
data-governance controls held.

---

## 2. Delivery & scope
| Metric | Value |
|---|---|
| Issues | 19 (1 Epic + 18 Stories) |
| Stories Done | **16 / 18 (89%)** |
| Story points — total scope | **46 SP** |
| Story points — completed | **43 SP (93%)** |
| Baseline commitment (M1–M7, RF-2…9) | 30 SP — **100% delivered** |
| Scope added mid-sprint (RF-10…19) | **+16 SP (+53%)** |
| Carried over | 3 SP — RF-17 (deploy), RF-18 (QA re-run) |
| Status mix | Done 16 · In Progress 1 (epic) · To Do 2 |

---

## 3. Velocity, estimation & throughput
| Metric | Value |
|---|---|
| **Velocity (Sprint 1)** | **43 SP** |
| Planned-equivalent effort (43 SP × 4 h) | 172 human-hours |
| **AI-actual logged effort** | **9.8 h** (590 min) |
| **Throughput acceleration** | **~18×** (172 h ÷ 9.8 h) |
| Baseline-only view | 30 SP est. 120 h → 6.2 h actual = **19.4×** |

**Estimation accuracy:** baseline estimates (RF-2…9) were directionally sound and fully delivered. The
gap is the **unestimated added scope** (RF-10…19) — quantified below, carried to the retro.

---

## 4. Per-story detail (from Jira)
| Key | Story | SP | Est (h) | AI-actual | Status |
|---|---|---:|---:|---:|---|
| RF-2 | Research & plan | 5 | 20 | 60 m | Done |
| RF-3 | M1/M2 lineage engine | 5 | 20 | 50 m | Done |
| RF-4 | Interim QA checkpoint | 3 | 12 | 30 m | Done |
| RF-5 | P1 hardening | 3 | 12 | 45 m | Done |
| RF-6 | M3 LLM explanation | 3 | 12 | 40 m | Done |
| RF-7 | M4 NL interface | 5 | 20 | 50 m | Done |
| RF-8 | M5 visualization | 3 | 12 | 50 m | Done |
| RF-9 | M7 eval + docs | 3 | 12 | 45 m | Done |
| RF-10 | Live market data | 2* | 8* | 25 m | Done |
| RF-11 | Gap analysis | 2* | 8* | 30 m | Done |
| RF-12 | Synthetic data generator | 3* | 12* | 60 m | Done |
| RF-13 | HF deploy-prep | 1* | 4* | 20 m | Done |
| RF-14 | Multi-agent retro doc | 1* | 4* | 25 m | Done |
| RF-15 | lstrip fix + abstain UX | 1* | 4* | 20 m | Done |
| RF-16 | Push to GitHub | 1* | 4* | 10 m | Done |
| RF-17 | HuggingFace deploy | 2* | 8* | — | **To Do** |
| RF-18 | Independent QA re-run | 1* | 4* | — | **To Do** |
| RF-19 | Agent-method demo | 2* | 8* | 30 m | Done |

`*` = estimate proposed in this report for completeness (these stories were created mid-sprint without
points; **not yet written back to Jira** — pending approval).

---

## 5. Quality & engineering health
| Metric | Value |
|---|---|
| Regression tests | **18 / 18** green |
| Evaluation harness (correctness, governance, guardrails, adversarial) | **20 / 20** green |
| Defects found pre-release | 3 (1 High: `find_node` false-match · 2 Med: `lstrip` name-corruption, double-parse) |
| **Defect escape rate** | **0** (all fixed before release) |
| QA gates | interim independent checkpoint + self-review + eval harness (RF-18 independent re-run pending) |

---

## 6. Where the effort went (590 min AI-actual)
| Workstream | Minutes |
|---|---:|
| Research & planning | 60 |
| Lineage engine + hardening | 95 |
| LLM / NL + visualization | 140 |
| Data platform (synthetic / market / gap) | 115 |
| Eval, docs & QA | 75 |
| Infra, deploy, retro & reporting | 105 |

---

## 7. Cycle / lead time
- **Lead time (created → Done):** ~6 days calendar (issues created across ~1 week).
- **Effort:** ~9.8 h AI-actual.
- **Caveat:** lead time here reflects *calendar wait*, not work — execution was **bursty/compressed**
  into one session (continuous-flow, not a daily-cadence sprint). Cycle time is therefore **not a
  meaningful velocity signal** for this sprint.

---

## 8. Scope-change analysis
- Baseline 30 SP → final 46 SP = **+53% scope growth**, all added **mid-sprint without estimates**.
- Added scope was high-value (live data, the synthetic data platform, gap analysis, deploy-prep, retro,
  the agent-method demo) but **invisible to the original plan** — the central predictability finding.

---

## 9. Process findings (for the retrospective)
1. **Estimate scope additions up front** — even "quick" additions get a point value before work starts.
2. **Run sprints formally** — two sprints exist but sit in `future`; nothing was started/closed, so Jira
   has **no native burndown/velocity**. Formalizing Sprint 1 (below) fixes this.
3. **Spread cadence** — delivery concentrated in one session; distribute for resilience.
4. **Automation governance** — automated Jira board writes are gated by a safety guardrail and need
   explicit approval (a healthy control, noted for planning).

---

## 10. Risks & impediments
| Risk | Severity | Note |
|---|---|---|
| API tokens exposed in chat | **High** | Rotate Jira + GitHub tokens now |
| RF-17 deploy blocked | Medium | Needs HuggingFace account/token (external) |
| RF-18 QA re-run blocked | Low | Usage-limit reset (10pm IST) |
| Single-session concentration | Low | Resilience/continuity risk |

---

## 11. Governance & compliance
- **Synthetic** customer data only (DPDP-safe); **real** data is public market data only.
- **On-prem proven mechanically** — engine reads SQL text only; no rows enter an LLM prompt.
- **Audit-grade** deterministic backbone; LLM labelled "suggestion — needs sign-off."
- **BCBS 239**-aligned attribute-level traceability; human owns sign-off, pushes, credentials.

---

## 12. Recommended actions
1. **Rotate the two exposed API tokens** (High, owner).
2. **Approve the Jira formalization** — back-fill SP on RF-10…19 + close Sprint 1 → native velocity/burndown.
3. **Deploy to HuggingFace** (RF-17) once the HF token is available; keep the public Space $0/key-less.
4. **Independent QA re-run** (RF-18) after reset.
5. **Adopt "estimate-before-build"** for scope additions (retro action).

---

## Methodology & caveats
- Data pulled live via Jira REST (`/search/jql`, fields incl. `customfield_10052` Story Points,
  `timeoriginalestimate`, `aggregatetimespent`).
- **Epic excluded from time/point totals** — its aggregate equals the sum of its children, so including
  it double-counts (the raw rollup showed 1,180 min; the true figure is **590 min**).
- AI-actual = Jira worklogs = orchestrator + agent-team time (not human-equivalent).
- `*` story points for RF-10…19 are **proposed in this report**, not yet written to Jira.
- "1 SP = 4 h" is the team's planning convention, used only to express a human-equivalent baseline.
