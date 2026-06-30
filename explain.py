"""M3 — LLM derivation explanation for "Find My Data Path".

Explains HOW a target column is derived, in plain English, using ONLY:
  - SQL text (pipeline SQL files — no data rows ever read)
  - Schema metadata (column names, table names)
  - The deterministic lineage DAG (roots, paths from M1/M2)

On-prem guarantee: the LLM prompt contains SQL expressions and column names only.
No data values, no row contents, no PII cross the process boundary.

Output contract:
  - Every LLM response is labelled "AI SUGGESTION — needs sign-off (not audit-grade)".
  - The deterministic fields (sources, hop_count, derivation_type) come from the
    sqllineage DAG and are ALWAYS present, regardless of whether the LLM is called.
  - $0 fallback fires when ANTHROPIC_API_KEY is absent — returns the deterministic
    fields + a template-built explanation with no LLM call.
"""
from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass, field
from typing import Optional

import networkx as nx

import config
from lineage import build_graph, find_node, load_sql, trace_to_source


# ── Derivation type classifier (from lineage structure — deterministic) ────────

def _strip_default(s: str) -> str:
    """Remove sqllineage's '<default>.' schema prefix (proper prefix removal, not lstrip)."""
    return s[len("<default>."):] if s.startswith("<default>.") else s


def _classify_derivation(derivation_sql: Optional[str]) -> str:
    """Rule-based derivation type from SQL expression text."""
    if not derivation_sql:
        return "pass-through"
    s = derivation_sql.upper()
    if "CASE" in s and ("*" in s or "+" in s or "-" in s or "/" in s):
        return "conditional-arithmetic"
    if "CASE" in s:
        return "conditional-lookup"
    if any(agg in s for agg in ("SUM(", "COUNT(", "AVG(", "MIN(", "MAX(")):
        return "aggregation"
    if any(op in s for op in ("*", "+", "-", "/")):
        return "arithmetic"
    return "pass-through"


# ── SQL fragment extractor (sqlglot AST — no data, metadata only) ─────────────

def extract_derivation_sql(table_name: str, column_name: str,
                           all_sql: str) -> Optional[str]:
    """Return the SQL expression that produces <column_name> in <table_name>.

    Uses sqlglot to parse each CREATE TABLE AS SELECT and find the SELECT
    expression whose alias matches column_name. Returns None for pass-throughs
    (plain column references with no derivation logic) or SELECT *.
    """
    try:
        import sqlglot
        import sqlglot.expressions as exp

        tbl_lower = _strip_default(table_name.lower())
        col_lower = column_name.lower()

        for stmt in sqlglot.parse(all_sql):         # no dialect="ansi" — sqlglot doesn't recognise it
            if not isinstance(stmt, exp.Create):
                continue
            # stmt.this is the target table for CREATE TABLE <name> AS SELECT
            if stmt.this.name.lower() != tbl_lower:
                continue
            select = stmt.find(exp.Select)
            if select is None:
                continue
            for expr in select.expressions:
                # Alias node  → expr.alias is the column alias ("expected_loss")
                # Column node → expr.alias is "" but expr.name gives column name
                alias = (expr.alias or getattr(expr, "name", "")).lower()
                if alias != col_lower:
                    continue
                # For Alias nodes: inner expression is expr.this (the derivation)
                # For plain Column: no interesting derivation — return None
                if isinstance(expr, exp.Alias):
                    # Strip SQL block comments (/* ... */) that sqlglot echoes back
                    raw = expr.this.sql()
                    clean = re.sub(r"/\*.*?\*/", "", raw, flags=re.DOTALL).strip()
                    clean = re.sub(r"\s+", " ", clean)
                    return clean if clean else None
                return None  # plain pass-through — no derivation SQL to show
    except Exception:
        pass
    return None


# ── Fallback explanation (deterministic — $0, no LLM) ────────────────────────

def _fallback_explanation(column: str, sources: list[str], paths: list[list[str]],
                          derivation_sql: Optional[str],
                          derivation_type: str) -> str:
    """Template-built explanation from lineage data. No LLM, always correct."""
    tbl, col = (column.split(".")[-2], column.split(".")[-1]) if "." in column else ("", column)
    source_cols = [s.split(".")[-1] for s in sources]
    source_tbls = sorted({s.rsplit(".", 1)[0] for s in sources})

    lines = [f"'{col}' in table '{tbl}' is derived from {len(sources)} source column(s): "
             f"{', '.join(source_cols)}."]

    if source_tbls:
        lines.append(f"Source systems: {', '.join(source_tbls)}.")

    if len(paths) == 1:
        hops = len(paths[0]) - 1
        lines.append(f"It flows through {hops} transformation hop(s) to reach this column.")
    elif len(paths) > 1:
        hop_counts = sorted({len(p) - 1 for p in paths})
        lines.append(f"Multiple paths exist with {min(hop_counts)}–{max(hop_counts)} hops.")

    if derivation_sql:
        clean = derivation_sql.strip()
        lines.append(f"Derivation expression: {clean}")

    type_descs = {
        "arithmetic":            "This is a pure arithmetic derivation (multiply/add/divide).",
        "conditional-arithmetic":"This derivation combines a business rule (CASE) with arithmetic — "
                                 "the CASE selects a branch, then arithmetic is applied.",
        "conditional-lookup":    "This is a CASE-based lookup that maps input values to output categories.",
        "aggregation":           "This is an aggregate function (SUM/COUNT/AVG) applied across a GROUP BY.",
        "pass-through":          "This column passes through unchanged from its source.",
    }
    if derivation_type in type_descs:
        lines.append(type_descs[derivation_type])

    return " ".join(lines)


# ── LLM prompt builder (metadata/SQL only) ────────────────────────────────────

def _build_prompt(column: str, sources: list[str], paths: list[list[str]],
                  derivation_sql: Optional[str], derivation_type: str) -> str:
    source_lines = "\n".join(f"  - {s}" for s in sources)
    path_lines   = "\n".join("  " + " -> ".join(p) for p in paths[:5])
    sql_block    = f"\nDerivation SQL:\n  {derivation_sql}" if derivation_sql else ""

    return textwrap.dedent(f"""
        You are a banking data engineer explaining a column derivation to a business analyst.
        Explain in 3–5 plain-English sentences how the column '{column}' is produced.

        IMPORTANT:
        - You have only SQL expressions and column/table names — NO data values.
        - Be specific about the business logic (why the formula makes sense in a credit-risk context).
        - Do not invent column meanings; stick to what the SQL shows.
        - End with one sentence about what a BA should verify in PROD data (a data quality check).

        === Lineage metadata (deterministic — from SQL parser) ===
        Target column : {column}
        Derivation type: {derivation_type}
        Source columns ({len(sources)}):
        {source_lines}

        Transformation paths:
        {path_lines}{sql_block}
        =========================================================
        Explanation (plain English, 3–5 sentences):
    """).strip()


# ── Main entry point ──────────────────────────────────────────────────────────

@dataclass
class ExplainResult:
    column:          str
    resolved_node:   Optional[str]
    sources:         list[str]
    hop_count:       int
    derivation_type: str
    derivation_sql:  Optional[str]
    explanation:     str
    is_llm:          bool          # True = LLM response; False = $0 fallback
    label:           str = field(init=False)

    def __post_init__(self):
        self.label = (
            "AI SUGGESTION — needs sign-off (not audit-grade)"
            if self.is_llm else
            "DETERMINISTIC — from SQL parser (audit-grade backbone)"
        )

    def display(self) -> str:
        src_short = [s.split(".")[-1] for s in self.sources]
        hdr = f"{'='*60}\nColumn : {self.column}\n{'='*60}"
        meta = (f"  Resolved node  : {self.resolved_node}\n"
                f"  Sources ({len(self.sources)})    : {', '.join(src_short)}\n"
                f"  Hops           : {self.hop_count}\n"
                f"  Derivation type: {self.derivation_type}\n"
                f"  SQL expression : {self.derivation_sql or '(pass-through / no alias)'}")
        body = f"\nExplanation:\n  {self.explanation}\n\n  [{self.label}]"
        return f"{hdr}\n{meta}{body}\n"


def explain_column(column: str, g: Optional[nx.DiGraph] = None) -> ExplainResult:
    """Explain the derivation of `column` end-to-end.

    Parameters
    ----------
    column : str
        Fully- or partially-qualified column name (e.g. 'stressed_rwa' or
        'mart_risk_summary.stressed_rwa').
    g : nx.DiGraph, optional
        Pre-built lineage graph. Built fresh if not provided.
    """
    if g is None:
        g = build_graph()

    node, sources, paths = trace_to_source(g, column)
    if node is None:
        return ExplainResult(
            column=column, resolved_node=None, sources=[], hop_count=0,
            derivation_type="unknown", derivation_sql=None,
            explanation=f"Column '{column}' was not found in the lineage graph. "
                        "Check the spelling or use the fully-qualified form table.column.",
            is_llm=False,
        )

    # Extract table + column name from the resolved node
    parts = _strip_default(node).split(".")
    tbl_name = parts[-2] if len(parts) >= 2 else ""
    col_name = parts[-1]

    all_sql       = load_sql()
    deriv_sql     = extract_derivation_sql(tbl_name, col_name, all_sql)
    deriv_type    = _classify_derivation(deriv_sql)
    hop_count     = max((len(p) - 1 for p in paths), default=0)

    key = config.get_key()
    if not key:
        # $0 path — deterministic fallback, no LLM call
        explanation = _fallback_explanation(node, sources, paths, deriv_sql, deriv_type)
        return ExplainResult(column=column, resolved_node=node, sources=sources,
                             hop_count=hop_count, derivation_type=deriv_type,
                             derivation_sql=deriv_sql, explanation=explanation, is_llm=False)

    # LLM path — metadata/SQL only, no data values
    try:
        import anthropic
        prompt = _build_prompt(node, sources, paths, deriv_sql, deriv_type)
        client = anthropic.Anthropic(api_key=key)
        response = client.messages.create(
            model=config.AI_MODEL,
            max_tokens=config.AI_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        explanation = response.content[0].text.strip()
        is_llm = True
    except Exception as exc:
        # Any LLM failure → fall back to deterministic; never surface a broken state
        explanation = (
            _fallback_explanation(node, sources, paths, deriv_sql, deriv_type)
            + f"  [LLM call failed: {exc}]"
        )
        is_llm = False

    return ExplainResult(column=column, resolved_node=node, sources=sources,
                         hop_count=hop_count, derivation_type=deriv_type,
                         derivation_sql=deriv_sql, explanation=explanation, is_llm=is_llm)


# ── CLI demo ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    g = build_graph()
    targets = [
        "mart_risk_summary.stressed_rwa",           # conditional-arithmetic (nested CASE × arithmetic)
        "mart_risk_summary.regulatory_bucket",      # conditional-lookup (CASE on derived expr)
        "int_exposure.expected_loss",               # arithmetic (PD × LGD × EAD)
        "mart_portfolio_concentration.avg_pd",      # aggregation (AVG)
        "stg_credit.exposure_amount",               # pass-through
    ]

    key_present = bool(config.get_key())
    print(f"Mode: {'LLM (Claude)' if key_present else '$0 deterministic fallback'}\n")

    for col in targets:
        result = explain_column(col, g)
        print(result.display())
