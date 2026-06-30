# Jira Status — river_fish (project RF)

Single source of truth for the RF board, kept in-repo so it stays current even when no Jira API token
is in session. **Worklogs are AI-actual minutes** (not human-equivalent), per the team cadence
([[jira-story-first]]). Sync to Jira via UI, or provide a token and I'll push it via the REST API.

_Last updated: 2026-06-25_

## Epic
- **RF-1 — Epic: river_fish "Find My Data Path"** — *In Progress* (closes when deploy + push done)

## Stories (original M-plan)
| Key | Story | Status | AI worklog |
|---|---|---|---|
| RF-2 | Research (Spider 2.0, provenance theory, market scan) | ✅ Done | 60m |
| RF-3 | M1/M2 — synthetic SQL pipeline + column-level lineage engine | ✅ Done | 50m |
| RF-4 | Interim QA checkpoint (2 reviewers) | ✅ Done | 30m |
| RF-5 | P1 hardening — find_node, schema.py, ADR, 18/18 tests | ✅ Done | 45m |
| RF-6 | M3 — LLM derivation explanation ($0 fallback, sign-off label) | ✅ Done | 40m |
| RF-7 | M4 — NL "find my path" interface (+ helpful abstain) | ✅ Done | 50m |
| RF-8 | M5 — river/fish Streamlit visualization | ✅ Done | 50m |
| RF-9 | M7 — evaluation harness (20/20) + market/learning docs | ✅ Done | 45m |

## Stories to CREATE (work that exceeded the original plan — tracked honestly per the retro)
| Suggested key | Story | Status | AI worklog |
|---|---|---|---|
| RF-10 | Live market-data ingestion (market_data.py, real public feeds + freshness) | ✅ Done | 25m |
| RF-11 | Gap analysis secondary product (gap_analysis.py, limitations.py) | ✅ Done | 30m |
| RF-12 | Synthetic multi-source data generator + extended pipeline (generate_data.py, sql_extended/, DuckDB) | ✅ Done | 60m |
| RF-13 | HuggingFace deploy-prep (requirements.txt, README front-matter, DEPLOY_HF.md) | ✅ Done | 20m |
| RF-14 | Multi-agent retro record (Multi_Agent_Retro_Sprint1.docx + SPRINT_RETRO.md) | ✅ Done | 25m |
| RF-15 | Fix lstrip prefix bug (extended-name corruption) + abstain UX | ✅ Done | 20m |

## To Do (need a human action / external reset)
| Suggested key | Story | Status | Blocker |
|---|---|---|---|
| RF-16 | Push all commits to GitHub | ⏳ To Do | needs GitHub PAT (deliberately not stored) |
| RF-17 | Deploy the app to HuggingFace Spaces | ⏳ To Do | follows the push; keep public Space $0/key-less |
| RF-18 | Independent QA re-run (agent hit session limit) | ⏳ To Do | resets 10pm IST |
| RF-19 | End-of-project "How an AI Agent Team Built This" demo | ⏳ To Do | after deploy |

## Summary
- **Done:** 14 stories (RF-2…RF-15) · **AI-actual ≈ 9.5 hours** of work compressed into one session via the agent team.
- **Quality:** 18/18 regression + 20/20 eval green; governance proven (SQL-text-only).
- **Open:** push (RF-16), deploy (RF-17), independent QA re-run (RF-18), agent-method demo (RF-19).
