# How an AI Agent Team Built river_fish

*A multi-agent software-delivery story — speed with governance intact. Companion to
`Agent_Team_Demo_river_fish.pptx`.*

## The challenge
Build a credible, **audit-grade column-level data-lineage prototype** for a multi-source banking
pipeline — with a natural-language interface and a live demo — in a single working session, **without
losing a single governance control** (BCBS 239 auditability, on-prem data boundary, honest QA).

## The team & operating model
| Role | Owns |
|---|---|
| **Product Owner** (human) | Vision, scope, sign-off, governance, credentials, push authority |
| **Orchestrator** (lead AI) | Architecture, integration, the NL interface, the QA gate, **all git commits** |
| **Data Generator** agent | Synthetic 11-system bank + DuckDB + extended SQL |
| **Research/Docs** agent | Cited market & future-of-data + learning/interview docs |
| **Reg-RAG UI** agent | Streamlit UI + deploy prep (sister project) |
| **QA + Deploy-prep** agents | Independent red-team review · HF deploy packaging |

Cadence: **Jira story-first**, live worklogs, an interim QA checkpoint, and a **sprint retro that
included the agents themselves**.

## How work was parallelized — without collisions
- **Partition by file surface.** Each agent owns distinct files; **no two writers per file** → true
  parallelism, zero merge conflicts.
- **One committer.** The orchestrator serializes git; agents just produce files in the working tree.
- **Cold-start, read-first briefs.** A mandatory STEP 0 to read the real code grounds every agent.
- **A living briefing log.** Charters are kept "continuously informed" as the design evolves.
- **Async execution.** Agents run in the background while the orchestrator does critical-path work.
- **Net effect: time compression** — four workstreams concurrent instead of sequential. The binding
  constraint was *clarity of brief*, not headcount.

## Governance under parallelism (the hard part)
- **Synthetic vs. real boundary held across every agent** — customer data 100% synthetic (DPDP-safe);
  only public market data is real.
- **Audit-grade backbone** — lineage is deterministic; the LLM only explains, labelled "suggestion —
  needs sign-off."
- **On-prem proven mechanically** — the eval harness asserts the engine reads SQL text only, imports no
  data engine, and no rows enter a prompt.
- **Human owns the irreversibles** — sign-off, pushes, and all credential handling.

## What the agents said (retro voices)
- **Reg-RAG UI agent** — *"clean briefing meant zero rework."* **Caught a real security risk:** a public
  demo Space with an API key lets anyone spend it → keep public demos $0/key-less.
- **Research/Docs agent** — read-first briefing gave exact repo vocabulary; flagged that vendor/Gartner
  claims age fast → "analysts suggest," not "Gartner says."
- **Data Generator agent** — flagged its own duplicate-key shortcut → the orchestrator merged it before
  commit.

## Outcomes
**7 milestones · 18/18 tests · 20/20 eval · 11 source systems · 18,742 synthetic rows · ~17 commits ·
5 agents · ~9.5h AI-actual in one session.** Quality gates green throughout; governance proven; failures
reported honestly.

## The repeatable method
Brief cold & read-first · partition by file surface · keep a living briefing log · run async + integrate
centrally · gate with honest independent QA · **retro with the agents** · human owns sign-off, pushes,
credentials, and the data boundary.

> **One team, not human-vs-AI.**
