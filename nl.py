"""M4 — Natural-language "Find My Data Path" interface.

A Business Analyst asks in plain English:
  - "where does stressed_rwa come from?"        -> upstream trace (sources + river paths)
  - "what is impacted if exposure_amount changes?" -> downstream impact
  - "how is regulatory_bucket calculated?"      -> derivation explanation (M3)
  - "trace expected_loss back to source"        -> upstream trace

…and gets: the resolved column, the source->target path(s), an explanation, and a
per-hop INSPECT-SQL a BA can run in DuckDB/PROD to check the data at each stage.

Design (Spider 2.0 lesson: ground + validate, never trust free-text blindly):
  - DETERMINISTIC intent + column extraction works with NO API key ($0 path).
  - The column is ALWAYS validated against the lineage graph/schema — if it isn't a
    real column we ABSTAIN (no hallucinated lineage). Ambiguous bare names ask for the
    qualified form.
  - An optional LLM step (metadata only — the question + the list of known column
    NAMES, never data rows) improves intent parsing; its pick is still validated against
    the graph, so the LLM can never invent a column.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

import networkx as nx

import config
from lineage import build_graph, find_node, trace_to_source
from explain import explain_column
import limitations


# ── Intent detection (deterministic keyword routing) ──────────────────────────

UPSTREAM_CUES = ("come from", "comes from", "source", "sources", "trace back",
                 "back to source", "origin", "upstream", "derived from", "where does",
                 "where do", "feed", "feeds", "made of", "based on", "find my path",
                 "find the path", "data path")
DOWNSTREAM_CUES = ("impact", "impacted", "downstream", "used", "used in", "consumed",
                   "depends on", "affect", "affected", "consumers", "where is", "feeds into",
                   "what uses", "who uses", "blast radius")
EXPLAIN_CUES = ("how is", "how does", "explain", "derivation", "calculated", "computed",
                "formula", "logic", "rule", "what does", "meaning")


def detect_intent(question: str) -> str:
    """Return one of: 'upstream' | 'downstream' | 'explain'. Defaults to 'upstream'."""
    q = question.lower()
    # Order matters: explicit explain/downstream cues win over the upstream default.
    if any(c in q for c in EXPLAIN_CUES) and not any(c in q for c in ("come from", "trace back", "upstream")):
        return "explain"
    if any(c in q for c in DOWNSTREAM_CUES) and not any(c in q for c in ("come from", "comes from", "trace back")):
        return "downstream"
    return "upstream"


# Words that signal an ANALYTICS request (compute a metric) rather than a lineage trace.
ANALYTICAL_CUES = ("total", "sum", "average", " avg", "count", "percent", "%", "top ",
                   "rank", "ratio", "region wise", "region-wise", "by region", "breakdown",
                   "distribution", "trend", "how many", "most ", "share of", "group by",
                   "highest", "lowest", "per ")

# Source systems that live ONLY in the extended pipeline (the app's toggle, default OFF).
EXTENDED_KEYWORDS = ("atm", "card", "loan", "mobile", "campaign", "sentiment", "branch",
                     "account", "deposit", "channel", "withdrawal", "transaction", "txn",
                     "consumer", "commercial", "retail", "holding")


def _short(node: str) -> str:
    """Strip sqllineage's '<default>.' schema prefix (proper prefix removal, not lstrip)."""
    return node[len("<default>."):] if node.startswith("<default>.") else node


def suggest_columns(question: str, g: nx.DiGraph, k: int = 6) -> list[str]:
    """Best-effort: columns whose name tokens overlap the question — for a helpful abstain."""
    noise = {"raw", "stg", "mart", "id", "the", "our", "find", "total", "wise"}
    q_tokens = set(re.findall(r"[a-z]+", question.lower())) - noise
    scored = []
    for n in g.nodes:
        if n.endswith(".*"):           # SELECT * placeholder — not a traceable column
            continue
        name_tokens = set(re.findall(r"[a-z]+", _short(n).lower())) - noise
        overlap = len(q_tokens & name_tokens)
        if overlap:
            scored.append((overlap, n))
    scored.sort(key=lambda x: (-x[0], len(x[1])))
    return [_short(n) for _, n in scored[:k]]


# ── Column extraction (schema-grounded) ───────────────────────────────────────

def _column_index(g: nx.DiGraph) -> dict[str, list[str]]:
    """Map bare column name -> [graph nodes that end in it]."""
    idx: dict[str, list[str]] = {}
    for n in g.nodes:
        col = n.split(".")[-1].lower()
        idx.setdefault(col, []).append(n)
    return idx


def extract_column(question: str, g: nx.DiGraph,
                   intent: str = "upstream") -> tuple[Optional[str], Optional[str]]:
    """Find the column the question is about.

    Returns (resolved_node, error_message). Exactly one is non-None:
      - (node, None)        column resolved unambiguously
      - (None, message)     not found, or ambiguous (message tells the user what to do)

    Intent-aware tie-breaking when a bare name exists in several tables:
      - upstream/explain → prefer the mart/target occurrence (trace its full history)
      - downstream       → prefer the source/root occurrence (impact of changing it at origin)
    """
    q = question.lower()
    idx = _column_index(g)

    # 1) qualified table.column mentioned verbatim?
    for token in re.findall(r"[a-z_][a-z0-9_]*\.[a-z0-9_]+", q):
        node = find_node(g, token)  # may raise ValueError (won't, token is qualified)
        if node:
            return node, None

    # 2) bare column names that appear as whole words in the question
    tokens = set(re.findall(r"[a-z_][a-z0-9_]+", q))
    hits = [col for col in idx if col in tokens]

    # Prefer the longest / most specific match (e.g. 'stressed_expected_loss' over 'expected_loss')
    hits.sort(key=len, reverse=True)

    # Drop hits that are substrings of a longer hit already chosen (avoid 'loss' when 'expected_loss' present)
    chosen: list[str] = []
    for h in hits:
        if not any(h in c and h != c for c in chosen):
            chosen.append(h)

    if not chosen:
        return None, ("No known column was recognised in the question. "
                      "Ask about a column in the pipeline, e.g. 'where does stressed_rwa come from?'.")

    col = chosen[0]
    nodes = idx[col]
    if len(nodes) == 1:
        return nodes[0], None

    # Ambiguous — same column name in several tables. Tie-break by intent.
    if intent == "downstream":
        root_nodes = [n for n in nodes if g.in_degree(n) == 0]
        if len(root_nodes) == 1:
            return root_nodes[0], None
    else:
        mart_nodes = [n for n in nodes if "mart_" in n]
        if len(mart_nodes) == 1:
            return mart_nodes[0], None

    options = ", ".join(sorted(_short(n) for n in nodes))
    return None, (f"'{col}' exists in several tables. Please qualify it. Options: {options}")


# ── Per-hop inspect SQL (what a BA runs to check data at each stage) ───────────

def inspect_sql_for_path(path: list[str]) -> list[dict]:
    """For each distinct table along the path, emit a SELECT to inspect that column's values."""
    seen = set()
    out = []
    for node in path:
        parts = _short(node).split(".")
        if len(parts) < 2:
            continue
        table = parts[-2]
        col = parts[-1]
        key = (table, col)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "stage": table,
            "column": col,
            "sql": f"SELECT counterparty_id, {col} FROM {table} LIMIT 20;",
        })
    return out


# ── LLM-assisted intent (optional, metadata-only, validated) ──────────────────

def _llm_parse(question: str, g: nx.DiGraph) -> Optional[tuple[str, str]]:
    """Use Claude to extract (intent, column) — metadata only. Returns None if unavailable/invalid.

    The LLM only sees the question and the list of known column NAMES. Its pick is
    validated against the graph by the caller, so it can never invent a column.
    """
    key = config.get_key()
    if not key:
        return None
    try:
        import anthropic
        col_names = sorted({n.split(".")[-1] for n in g.nodes})
        prompt = (
            "You route a data-lineage question. Return ONLY compact JSON: "
            '{\"intent\": \"upstream|downstream|explain\", \"column\": \"<one column name from the list>\"}.\n'
            f"Known columns: {', '.join(col_names)}\n"
            f"Question: {question}\n"
            "intent=upstream means trace to sources; downstream means find consumers/impact; "
            "explain means describe the derivation. JSON:"
        )
        client = anthropic.Anthropic(api_key=key)
        resp = client.messages.create(model=config.AI_MODEL, max_tokens=120,
                                       messages=[{"role": "user", "content": prompt}])
        text = resp.content[0].text.strip()
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return None
        data = json.loads(m.group(0))
        intent = data.get("intent", "upstream")
        column = data.get("column", "")
        if intent not in ("upstream", "downstream", "explain"):
            intent = "upstream"
        return intent, column
    except Exception:
        return None


# ── Result + main answer() ────────────────────────────────────────────────────

@dataclass
class NLAnswer:
    question:    str
    intent:      str
    column:      Optional[str]
    abstained:   bool
    message:     str                       # human-facing headline (abstain reason or summary)
    sources:     list[str] = field(default_factory=list)
    consumers:   list[str] = field(default_factory=list)
    paths:       list[list[str]] = field(default_factory=list)
    inspect_sql: list[dict] = field(default_factory=list)
    explanation: str = ""
    label:       str = ""
    used_llm:    bool = False

    def display(self) -> str:
        lines = [f"Q: {self.question}", f"   intent={self.intent}"
                 + ("  [LLM-assisted]" if self.used_llm else "  [$0 deterministic]")]
        if self.abstained:
            lines.append(f"\n⚠ ABSTAINED: {self.message}")
            return "\n".join(lines)

        lines.append(f"\nColumn: {self.column}")
        if self.intent == "downstream":
            lines.append(f"Used by ({len(self.consumers)} downstream column(s)):")
            for c in self.consumers[:20]:
                lines.append(f"   -> {_short(c)}")
        else:
            lines.append(f"Sources ({len(self.sources)}): "
                         + (", ".join(s.split('.')[-1] for s in self.sources) or "(this is a source)"))
            for p in self.paths[:6]:
                lines.append("   river ~>  " + "  ~>  ".join(_short(n) for n in p))

        if self.explanation:
            lines.append(f"\nExplanation:\n  {self.explanation}")
            lines.append(f"  [{self.label}]")

        if self.inspect_sql:
            lines.append("\nInspect-SQL per hop (run in DuckDB/PROD to check the data):")
            for hop in self.inspect_sql:
                lines.append(f"   [{hop['stage']}]  {hop['sql']}")
        return "\n".join(lines)


def answer(question: str, g: Optional[nx.DiGraph] = None) -> NLAnswer:
    if g is None:
        g = build_graph()

    intent = detect_intent(question)
    used_llm = False

    # Deterministic extraction first (the $0 path).
    node, err = extract_column(question, g, intent)

    # Optional LLM assist: only to refine intent/column when deterministic extraction failed.
    if node is None:
        llm = _llm_parse(question, g)
        if llm is not None:
            llm_intent, llm_col = llm
            cand = find_node(g, llm_col) if llm_col else None
            if cand is not None:           # validated against the graph — no hallucination
                node, err, intent, used_llm = cand, None, llm_intent, True

    if node is None:
        # Abstain — but make it HELPFUL, not a dead end. Explain the boundary, suggest columns,
        # and hint when the relevant data is in the extended pipeline (toggle off by default).
        q = question.lower()
        parts = [err or "I couldn't ground that question to a column in this pipeline."]

        if any(c in q for c in ANALYTICAL_CUES):
            parts.append(
                "This looks like an ANALYTICS question (a metric to compute). river_fish traces "
                "data LINEAGE — where a column comes from and what it feeds — it does not generate "
                "ad-hoc analytical SQL. Pick a column below and I'll show its lineage + the "
                "inspect-SQL you'd run to build the metric yourself.")

        graph_tables = " ".join(g.nodes).lower()
        missing_sys = [kw for kw in EXTENDED_KEYWORDS if kw in q and kw not in graph_tables]
        if missing_sys:
            parts.append(
                f"Note: terms like {sorted(set(missing_sys))} belong to the EXTENDED multi-source "
                "pipeline, which is off by default — turn on 'Include extended pipeline' to bring "
                "those systems (ATM, cards, loans, channels…) into the graph.")

        sugg = suggest_columns(question, g)
        if sugg:
            parts.append("Closest columns you can trace: " + ", ".join(sugg) + ".")

        return NLAnswer(question=question, intent=intent, column=None, abstained=True,
                        message="  ".join(parts), used_llm=used_llm)

    # We have a grounded column. Route by intent.
    if intent == "downstream":
        consumers = sorted(nx.descendants(g, node))
        paths = []
        # show a couple of representative downstream paths to mart targets
        mart_targets = [c for c in consumers if "mart_" in c]
        for t in mart_targets[:4]:
            paths.extend(nx.all_simple_paths(g, node, t))
        inspect = inspect_sql_for_path([node] + (paths[0] if paths else []))
        msg = (f"{node.split('.')[-1]} feeds {len(consumers)} downstream column(s)."
               if consumers else f"{node.split('.')[-1]} has no downstream consumers (it is a final output).")
        return NLAnswer(question=question, intent=intent, column=node, abstained=False,
                        message=msg, consumers=consumers, paths=paths,
                        inspect_sql=inspect, used_llm=used_llm)

    # upstream or explain → trace to source, and attach an explanation
    _, sources, paths = trace_to_source(g, node)
    exp = explain_column(node, g)
    inspect = inspect_sql_for_path(paths[0] if paths else [node])
    msg = (f"{node.split('.')[-1]} traces to {len(sources)} source column(s) across "
           f"{len({s.rsplit('.',1)[0] for s in sources})} system(s).")
    return NLAnswer(question=question, intent=("explain" if intent == "explain" else "upstream"),
                    column=node, abstained=False, message=msg,
                    sources=sources, paths=paths, inspect_sql=inspect,
                    explanation=exp.explanation, label=exp.label, used_llm=used_llm)


# ── CLI demo ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    g = build_graph()
    print(f"NL 'Find My Data Path'  —  mode: "
          f"{'LLM-assisted' if config.get_key() else '$0 deterministic'}\n")

    demo_questions = [
        "where does stressed_rwa come from?",
        "trace expected_loss back to source",
        "how is regulatory_bucket calculated?",
        "what is impacted if exposure_amount changes?",
        "where does the moon landing data come from?",   # out-of-scope → must ABSTAIN
    ]
    for q in demo_questions:
        print(answer(q, g).display())
        print("\n" + "-" * 70 + "\n")
