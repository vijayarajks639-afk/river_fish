# Deploying "Find My Data Path" to HuggingFace Spaces

## Prerequisites
- A HuggingFace account (free tier is sufficient)
- Git installed locally
- The `river_fish` repo checked out

## Steps

### 1. Create a new Space
1. Go to https://huggingface.co/spaces
2. Click **Create new Space**
3. Name it (e.g. `find-my-data-path`)
4. **SDK**: select **Streamlit**
5. **Visibility**: Public (or Private)
6. Click **Create Space** — HF creates a bare git repo for the Space

### 2. Add the HF Space as a git remote
```bash
git remote add hf https://huggingface.co/spaces/<your-username>/find-my-data-path
```

### 3. Push the working tree
```bash
git push hf main
```
HF Spaces reads `requirements.txt` automatically and installs deps, then launches `app_file: app.py`
(declared in the YAML front-matter at the top of `README.md`).

### 4. Verify the build
- Go to your Space URL: `https://huggingface.co/spaces/<your-username>/find-my-data-path`
- Watch the **Logs** tab while the build runs (takes ~2–3 minutes first time)
- App should start and show all 5 tabs with zero errors

---

## What the deployed app needs — and does NOT need

**Needed on a fresh checkout (no local files required):**
- `sql/*.sql` — the core pipeline SQL (committed, lineage reads text only)
- `sql_extended/*.sql` — extended pipeline SQL (committed)
- `requirements.txt` — pip installs these on Space startup

**NOT needed (do not add to the Space):**
- `data/warehouse.duckdb` — this file is in `.gitignore` and is intentionally absent.
  The running app reads SQL TEXT only; it never opens a DuckDB connection.
  The "Inspect-SQL per hop" shown in the UI are display strings, not live queries.
- `.market_cache.json` — regenerated on first fetch; gitignored.

---

## CRITICAL GOVERNANCE NOTE — Public Spaces and API keys

**Do NOT set `ANTHROPIC_API_KEY` as a secret on a PUBLIC HuggingFace Space.**

Anyone who visits a public Space can trigger the app to run, which would make LLM API
calls against your key and accumulate charges you cannot control.

The app is designed for this: when `ANTHROPIC_API_KEY` is absent, it runs in
**$0 deterministic mode** — all lineage, gap analysis, and NL queries work fully using
only the sqllineage DAG and rule-based logic. The LLM layer (explanation + NL assist)
gracefully degrades and is labelled accordingly in the UI.

To enable LLM features for your own private use:
- Set `ANTHROPIC_API_KEY` only on a **Private** Space, or
- Run locally: `export ANTHROPIC_API_KEY=<your-key> && streamlit run app.py`

---

## Dependency note
`sqllineage` pulls in `sqlfluff`, `sqlalchemy`, and `rustworkx` as transitive deps —
these are resolved automatically by pip from `requirements.txt`. No manual action needed.
