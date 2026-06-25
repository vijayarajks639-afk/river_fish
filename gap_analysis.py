"""Gap Analysis — Secondary Module (standalone add-on to the core lineage tool).

Primary product: lineage.py — traces a column from source to target.
This module: runs AFTER lineage is built and answers a different question:
"Which source data was brought into the pipeline but is NEVER consumed
by any downstream mart / report / analytical layer?"

Banking context: data arrives from many channel and product systems
(ATM, Core Banking, Mobile, Social Sentiment, Branch CRM, Campaign, Credit Card,
Loans, Retail, Consumer, Commercial Banking). Not all of it gets used.
Surfacing the gaps helps data owners and product owners have a conversation
with stakeholders about what to build next — or what to retire.

Run this standalone:  python gap_analysis.py
Or call gap_report(g) to get a structured report dict for embedding in the Streamlit UI.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import networkx as nx

import config
from lineage import build_graph


@dataclass
class SourceGap:
    column:         str          # fully-qualified source column
    source_system:  str          # key from config.SOURCE_SYSTEMS
    system_label:   str          # human-readable system name
    column_name:    str          # bare column name
    reaches_tables: list[str]    # intermediate tables it reaches (if any)
    status:         str          # "completely_unused" | "partial" | "join_key_only"
    note:           str          # stakeholder-facing explanation


@dataclass
class GapReport:
    total_source_columns: int
    used_columns:         int
    gap_columns:          list[SourceGap]
    coverage_pct:         float
    by_system:            dict[str, list[SourceGap]] = field(default_factory=dict)
    parser_limitations:   list[str] = field(default_factory=list)

    def summary_text(self) -> str:
        lines = [
            f"Source coverage: {self.used_columns}/{self.total_source_columns} columns "
            f"reach a mart/report layer ({self.coverage_pct:.0f}%).",
            f"Gap columns: {len(self.gap_columns)} source column(s) are loaded but not consumed.",
        ]
        if self.by_system:
            for sys_key, gaps in sorted(self.by_system.items()):
                label = config.SOURCE_SYSTEMS.get(sys_key, sys_key)
                lines.append(f"  {label}: {len(gaps)} unused column(s)")
        if self.parser_limitations:
            lines.append("")
            lines.append("Parser limitations that may hide additional gaps:")
            for lim in self.parser_limitations:
                lines.append(f"  - {lim}")
        return "\n".join(lines)


def _source_system_for(node: str) -> str:
    """Map a fully-qualified column node to its source system key."""
    node_lower = node.lower()
    for sys_key in config.SOURCE_SYSTEMS:
        if sys_key in node_lower:
            return sys_key
    return "unknown"


def _intermediate_tables(g: nx.DiGraph, source_node: str) -> list[str]:
    """Tables the source node reaches (not counting source-system tables and not mart_)."""
    descendants = nx.descendants(g, source_node)
    tables = sorted({
        n.split(".")[-2] for n in descendants
        if "mart_" not in n and not any(s in n for s in config.SOURCE_SYSTEMS)
    })
    return tables


def gap_report(g: Optional[nx.DiGraph] = None) -> GapReport:
    """Build a gap report from the lineage DAG.

    A 'gap' = source column (in_degree 0) that has no path to ANY mart_* table.
    """
    from limitations import check_sql_for_limitations
    from lineage import load_sql

    if g is None:
        g = build_graph()

    # Detect parser limitations that may hide additional gaps
    sql_text = load_sql()
    found_lims = check_sql_for_limitations(sql_text)
    lim_messages = []
    if "select_star" in found_lims:
        lim_messages.append("SELECT * detected — column-level gaps may be under-reported")
    if "dynamic_sql" in found_lims:
        lim_messages.append("Dynamic SQL detected — runtime transformations are not visible")
    if "stored_procedure" in found_lims:
        lim_messages.append("Stored procedures detected — procedural logic is not traced")
    lim_messages.append(
        "Non-SQL ETL (Ab Initio / Informatica) columns are NOT in this graph — "
        "register them in schema.py to include in gap analysis"
    )

    # All source nodes = root nodes (in_degree 0) that belong to a known source system
    all_nodes = list(g.nodes)
    source_nodes = [
        n for n in all_nodes
        if g.in_degree(n) == 0 and any(s in n.lower() for s in config.SOURCE_SYSTEMS)
    ]

    mart_nodes = {n for n in all_nodes if "mart_" in n}

    used, gaps = [], []
    for src in sorted(source_nodes):
        reaches_mart = any(nx.has_path(g, src, m) for m in mart_nodes)
        if reaches_mart:
            used.append(src)
        else:
            sys_key = _source_system_for(src)
            sys_label = config.SOURCE_SYSTEMS.get(sys_key, sys_key)
            col_name = src.split(".")[-1]
            intermediates = _intermediate_tables(g, src)

            if not intermediates:
                status = "completely_unused"
                note = (
                    f"'{col_name}' is extracted from {sys_label} but reaches NO downstream "
                    f"table — it is loaded and then discarded. Consider removing the extract "
                    f"or routing it to an analytical layer."
                )
            elif col_name in ("counterparty_id", "id", "key"):
                status = "join_key_only"
                note = (
                    f"'{col_name}' is used as a JOIN key (reaching: {', '.join(intermediates)}) "
                    f"but is not propagated to any mart column. This is expected for surrogate keys "
                    f"but worth confirming with the data owner."
                )
            else:
                status = "partial"
                note = (
                    f"'{col_name}' reaches intermediate table(s): {', '.join(intermediates)} "
                    f"but does NOT flow into any mart/report layer. It may be filtered out, "
                    f"or it may be a candidate for inclusion in the next mart iteration."
                )

            gaps.append(SourceGap(
                column=src,
                source_system=sys_key,
                system_label=sys_label,
                column_name=col_name,
                reaches_tables=intermediates,
                status=status,
                note=note,
            ))

    total = len(source_nodes)
    used_count = len(used)
    coverage = (used_count / total * 100) if total else 0

    by_system: dict[str, list[SourceGap]] = {}
    for gap in gaps:
        by_system.setdefault(gap.source_system, []).append(gap)

    return GapReport(
        total_source_columns=total,
        used_columns=used_count,
        gap_columns=gaps,
        coverage_pct=coverage,
        by_system=by_system,
        parser_limitations=lim_messages,
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("Building lineage graph ...")
    g = build_graph()
    report = gap_report(g)

    print("\n" + "=" * 60)
    print("  GAP ANALYSIS REPORT  (secondary module)")
    print("=" * 60)
    print(report.summary_text())

    if report.gap_columns:
        print("\nDetailed gaps:")
        for gap in report.gap_columns:
            print(f"\n  [{gap.status.upper()}]  {gap.column}")
            print(f"  {gap.note}")

    print("\n" + "=" * 60)
    print("  NOTE: This is a secondary add-on to the lineage tool.")
    print("  Primary use: run lineage.py or explain.py to trace a specific column.")
    print("  This report is for stakeholder conversations about data coverage.")
    print("=" * 60)
