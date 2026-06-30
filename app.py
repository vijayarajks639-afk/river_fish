"""M5 — "Find My Data Path" — river/fish lineage visualization (Streamlit).

The capstone UI over the deterministic lineage engine. A Business Analyst:
  - asks in natural language OR picks a column,
  - sees the river (the lineage DAG) with the fish (the queried column) traced to source,
  - reads the derivation explanation (labelled deterministic vs AI-suggested),
  - gets inspect-SQL per hop to check data quality in the warehouse,
  - and can switch to the Gap view (loaded-but-unused data) and the live Market Data feed.

On-prem by design: the engine reads SQL TEXT only; data rows live in DuckDB for BA
inspection and never enter an LLM prompt. Synthetic customer data; real public market data.
"""
from __future__ import annotations

import streamlit as st

import config
from lineage import build_graph, find_node, trace_to_source
from explain import explain_column
from nl import answer as nl_answer
from gap_analysis import gap_report
import market_data

st.set_page_config(page_title="Find My Data Path", page_icon="🐟", layout="wide")

# ── palette ───────────────────────────────────────────────────────────────────
FISH   = "#F4D03F"   # the queried column
SOURCE = "#AED6F1"   # headwaters (source columns)
MART   = "#A9DFBF"   # marts / outputs
MID    = "#FFFFFF"   # intermediate


@st.cache_resource(show_spinner=False)
def get_graph(extended: bool):
    return build_graph(include_extended=extended)


@st.cache_data(ttl=900, show_spinner=False)
def get_market():
    pts = market_data.fetch_market_snapshot()
    return [p.__dict__ for p in pts]


def _short(node: str) -> str:
    """Strip sqllineage's '<default>.' schema prefix (proper prefix removal, not lstrip)."""
    return node[len("<default>."):] if node.startswith("<default>.") else node


def dot_for_trace(g, node, paths) -> str:
    """Build a Graphviz DOT string for the river: every node on a path to `node`."""
    nodes_in = {node}
    for p in paths:
        nodes_in.update(p)
    lines = ['digraph G {', 'rankdir=LR;', 'bgcolor="transparent";',
             'node [shape=box style="rounded,filled" fontname="Helvetica" fontsize=10];',
             'edge [color="#5D6D7E" arrowsize=0.7];']
    for n in nodes_in:
        label = _short(n).replace(".", ".\\n")   # table on one line, column on next
        if n == node:
            fill, extra = FISH, ' penwidth=2 color="#B7950B"'
        elif g.in_degree(n) == 0:
            fill, extra = SOURCE, ""
        elif "mart_" in n:
            fill, extra = MART, ""
        else:
            fill, extra = MID, ""
        lines.append(f'"{n}" [label="{label}" fillcolor="{fill}"{extra}];')
    for p in paths:
        for a, b in zip(p, p[1:]):
            lines.append(f'"{a}" -> "{b}";')
    lines.append("}")
    return "\n".join(lines)


def render_trace(g, node):
    """Render the full trace block for a resolved column node."""
    _, sources, paths = trace_to_source(g, node)
    systems = sorted({_short(s).split(".")[0] for s in sources})

    c1, c2, c3 = st.columns(3)
    c1.metric("Source columns", len(sources))
    c2.metric("Source systems", len(systems))
    c3.metric("Max hops", max((len(p) - 1 for p in paths), default=0))

    st.markdown(f"#### 🌊 The river — lineage of `{_short(node)}`")
    st.caption("🐟 gold = your column · 🔵 blue = source columns (headwaters) · 🟢 green = marts/outputs")
    if paths:
        st.graphviz_chart(dot_for_trace(g, node, paths), use_container_width=True)
    else:
        st.info("This column is a source (headwater) — nothing upstream feeds it.")

    exp = explain_column(node, g)
    st.markdown("#### 🧠 How it's derived")
    st.write(exp.explanation)
    badge = "✅ " if "DETERMINISTIC" in exp.label else "🟠 "
    st.caption(f"{badge}{exp.label}")
    if exp.derivation_sql:
        st.code(exp.derivation_sql, language="sql")

    st.markdown("#### 🔎 Inspect-SQL per hop")
    st.caption("Run these in the DuckDB warehouse / PROD to check the data at each stage.")
    from nl import inspect_sql_for_path
    for hop in inspect_sql_for_path(paths[0] if paths else [node]):
        st.code(hop["sql"], language="sql")


# ══════════════════════════════════════════════════════════════════════════════
# Header
# ══════════════════════════════════════════════════════════════════════════════
st.title("🐟 Find My Data Path")
st.markdown("**Column-level data lineage** for a multi-source banking pipeline — "
            "trace any value from source to usage, on-prem-safe.")
st.info("🔒 **On-prem by design:** the engine reads **SQL text only** — no data rows are read by the "
        "lineage engine or sent to any LLM. Synthetic customer data; real public market data.", icon="🔒")

tab_path, tab_graph, tab_gap, tab_market, tab_about = st.tabs(
    ["🐟 Find My Path", "🌊 Full Lineage", "🔍 Gap Analysis", "📈 Market Data", "ℹ️ About"])

# ── Tab 1: Find My Path ───────────────────────────────────────────────────────
with tab_path:
    extended = st.toggle("Include extended multi-source pipeline (11 systems)", value=False,
                         help="Off = core risk pipeline (stable demo). On = full synthetic bank.")
    g = get_graph(extended)
    st.caption(f"Graph: {g.number_of_nodes()} columns · {g.number_of_edges()} edges "
               f"({'extended' if extended else 'core'} pipeline)")

    mode = st.radio("Ask by", ["Natural language", "Pick a column"], horizontal=True)

    if mode == "Natural language":
        q = st.text_input("Ask in plain English",
                          placeholder="e.g. where does stressed_rwa come from?")
        if q:
            ans = nl_answer(q, g)
            st.caption(f"intent = **{ans.intent}**  ·  "
                       + ("🟠 LLM-assisted" if ans.used_llm else "✅ $0 deterministic"))
            if ans.abstained:
                st.warning(f"**Abstained.** {ans.message}", icon="⚠️")
            elif ans.column:
                st.success(ans.message)
                if ans.intent == "downstream":
                    st.markdown(f"#### `{_short(ans.column)}` is used by {len(ans.consumers)} downstream column(s)")
                    st.dataframe({"downstream column": [_short(c) for c in ans.consumers]},
                                 use_container_width=True, hide_index=True)
                else:
                    render_trace(g, ans.column)
    else:
        targets = sorted(n for n in g.nodes if g.out_degree(n) == 0) or sorted(g.nodes)
        pick = st.selectbox("Target column", [_short(t) for t in targets])
        if pick:
            node = find_node(g, pick)
            if node:
                render_trace(g, node)

# ── Tab 2: Full Lineage ───────────────────────────────────────────────────────
with tab_graph:
    ext2 = st.toggle("Extended pipeline", value=False, key="graph_ext")
    g2 = get_graph(ext2)
    st.caption(f"{g2.number_of_nodes()} columns · {g2.number_of_edges()} edges")
    sources = sorted(n for n in g2.nodes if g2.in_degree(n) == 0)
    marts = sorted(n for n in g2.nodes if "mart_" in n)
    cols = st.columns(2)
    cols[0].markdown("**Source columns (headwaters)**")
    cols[0].dataframe({"source": [_short(s) for s in sources]},
                      use_container_width=True, hide_index=True, height=300)
    cols[1].markdown("**Mart / output columns**")
    cols[1].dataframe({"mart column": [_short(m) for m in marts]},
                      use_container_width=True, hide_index=True, height=300)

# ── Tab 3: Gap Analysis ───────────────────────────────────────────────────────
with tab_gap:
    st.markdown("### 🔍 Gap Analysis — *secondary product*")
    st.caption("Source data that is **loaded but never consumed** by any mart/report — "
               "the conversation starter with data owners and stakeholders.")
    ext3 = st.toggle("Scan extended multi-source pipeline", value=True, key="gap_ext",
                     help="On = include the 11-system synthetic bank (richer findings).")
    g3 = get_graph(ext3)
    rep = gap_report(g3)
    c1, c2, c3 = st.columns(3)
    c1.metric("Source coverage", f"{rep.coverage_pct:.0f}%")
    c2.metric("Used columns", f"{rep.used_columns}/{rep.total_source_columns}")
    c3.metric("Gap columns", len(rep.gap_columns))
    if rep.gap_columns:
        st.dataframe(
            {"source system": [gp.system_label.split(" — ")[0] for gp in rep.gap_columns],
             "column": [gp.column_name for gp in rep.gap_columns],
             "status": [gp.status for gp in rep.gap_columns],
             "note": [gp.note for gp in rep.gap_columns]},
            use_container_width=True, hide_index=True)

# ── Tab 4: Market Data ────────────────────────────────────────────────────────
with tab_market:
    st.markdown("### 📈 Live market data — *real public reference data*")
    st.caption("FX, yields, vol, indices ingested from Yahoo Finance. Feeds the `currency` / "
               "`market_value` join keys. Customer data stays synthetic.")
    pts = get_market()
    any_stale = any(p["is_stale"] for p in pts)
    if any_stale:
        st.warning("⚠️ Some values are **STALE** (live fetch failed — showing cache, or offline). "
                   "On an offline demo machine the FX rate falls back and INR exposure equals local exposure.",
                   icon="⚠️")
    st.dataframe(
        {"instrument": [p["label"] for p in pts],
         "value": [p["value"] for p in pts],
         "ccy": [p["currency"] for p in pts],
         "as of (market)": [p["market_time"] for p in pts],
         "stale": ["⚠️ STALE" if p["is_stale"] else "✅ fresh" for p in pts]},
        use_container_width=True, hide_index=True)

# ── Tab 5: About ──────────────────────────────────────────────────────────────
with tab_about:
    st.markdown("""
### The mental model
- A **column** is a **fish** 🐟; the **pipeline** is the **river** 🌊; where transformations merge
  inputs (`C + XYZ = D`) are **tributaries**. The tool traces a value's journey through them.

### Architecture — a governed hybrid
- **Deterministic backbone** (sqllineage → networkx DAG): auditable, reproducible — the part you
  show a **BCBS 239** auditor. This is the certified lineage.
- **Governed LLM layer**: explains derivations and powers the natural-language interface, fed
  **metadata/SQL only, never data rows**. Always labelled *"suggestion — needs sign-off."*
- **Guardrails**: columns validated against the real schema; **abstain** when a question can't be grounded.

### Why this design
- Spider 2.0 (ICLR 2025): frontier LLMs solve only ~6–30% of *real* enterprise text-to-SQL.
  So the lineage must be deterministic; the LLM assists, it does not certify.

### Governance
- **Synthetic** customer/counterparty data (zero PII, DPDP-safe). **Real** public market data only.
- The lineage engine reads **SQL text**; rows never enter an LLM prompt.

*Learning + portfolio project. See `MARKET_AND_FUTURE.md`, `LEARNING_LINEAGE.md`, `ADR_backbone.md`.*
""")
