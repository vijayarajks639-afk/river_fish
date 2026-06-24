"""Schema metadata layer for "Find My Data Path".

Provides the KNOWN_SCHEMA for the synthetic banking pipeline and tools to validate
the lineage graph against it. This is the answer to the QA P1-2 finding: the lineage
backbone should be schema-aware, not purely SQL-text-parsing-in-the-dark.

Design:
- Schema is derived from the SQL text (column lists in each CREATE TABLE AS SELECT).
  In a real deployment this would be read from DuckDB information_schema or a data catalog.
- Kept here as a static dict so the engine runs $0 / offline and makes zero network calls.
- validate_lineage_nodes() checks the DAG against this dict and surfaces any node that
  has no corresponding schema column — the earliest signal of a SELECT * or parse gap.

On-prem note: schema metadata (table/column names, types) is NOT sensitive data and CAN
leave the warehouse boundary. Only row-level data is restricted.
"""
from __future__ import annotations

from typing import Optional

import networkx as nx


# ── Known schema for the 4-stage synthetic pipeline ──────────────────────────
# Source: extracted from sql/10_staging.sql → 20_integration.sql → 30_mart.sql → 40_portfolio.sql
# In production: replace with `duckdb.execute("SELECT table_name, column_name FROM information_schema.columns").fetchall()`

KNOWN_SCHEMA: dict[str, list[str]] = {
    # ── raw source tables (virtual — in real life these live in the source system) ──
    "creditmart.raw_credit_exposures": [
        "counterparty_id", "exposure_amount", "pd", "lgd", "internal_rating", "currency",
    ],
    "marketriskhub.raw_market_positions": [
        "counterparty_id", "market_value", "var_1d", "currency",
    ],
    "goldensourcefdo.raw_counterparty": [
        "counterparty_id", "counterparty_name", "legal_entity", "country",
    ],
    # ── staging ──
    "stg_credit": [
        "counterparty_id", "exposure_amount", "pd", "lgd", "internal_rating", "currency",
    ],
    "stg_market": [
        "counterparty_id", "market_value", "var_1d", "currency",
    ],
    "ref_counterparty": [
        "counterparty_id", "counterparty_name", "legal_entity", "country",
    ],
    # ── integration ──
    "int_exposure": [
        "counterparty_id", "counterparty_name", "legal_entity", "country",
        "exposure_amount", "pd", "lgd", "internal_rating",
        "expected_loss", "stressed_lgd", "stressed_expected_loss", "currency",
    ],
    # ── mart ──
    "mart_risk_summary": [
        "counterparty_id", "counterparty_name", "legal_entity",
        "expected_loss", "stressed_expected_loss", "var_1d",
        "risk_weighted_amount", "stressed_rwa", "regulatory_bucket",
    ],
    "mart_portfolio_concentration": [
        "legal_entity", "counterparty_count",
        "total_exposure", "total_expected_loss", "avg_pd",
    ],
}

# Flat set of all qualified column names (table.column) — fast membership test
_ALL_COLUMNS: frozenset[str] = frozenset(
    f"{tbl}.{col}"
    for tbl, cols in KNOWN_SCHEMA.items()
    for col in cols
)


def known_column(table: str, column: str) -> bool:
    """True if <table>.<column> is in the known schema."""
    return f"{table}.{column}" in _ALL_COLUMNS


def columns_for_table(table: str) -> list[str]:
    """Return the column list for a table, or [] if unknown."""
    return KNOWN_SCHEMA.get(table, [])


def validate_lineage_nodes(g: nx.DiGraph) -> dict[str, list[str]]:
    """Check every node in the lineage DAG against the known schema.

    Returns a dict with two keys:
      'valid'   — nodes that exist in KNOWN_SCHEMA
      'unknown' — nodes NOT in KNOWN_SCHEMA (parse gap, SELECT *, or spurious sqllineage node)

    A non-empty 'unknown' list is the signal that the parser hit a boundary and the
    result should be treated as PARTIAL (table-level only) — the auditable backbone
    abstains from certifying column-level lineage for those nodes.
    """
    valid, unknown = [], []
    for node in g.nodes:
        # sqllineage uses '<default>.table.column' for local tables, 'schema.table.column' for sources
        clean = node.lower()
        if clean.startswith("<default>."):
            clean = clean[len("<default>."):]
        parts = clean.split(".")
        if len(parts) >= 2:
            col = parts[-1]
            tbl_short = parts[-2]              # e.g. raw_credit_exposures
            tbl_full  = ".".join(parts[:-1])   # e.g. creditmart.raw_credit_exposures
            found = known_column(tbl_full, col) or known_column(tbl_short, col)
            (valid if found else unknown).append(node)
        else:
            unknown.append(node)
    return {"valid": valid, "unknown": unknown}


def abstain_message(unknown_nodes: list[str]) -> Optional[str]:
    """Return a user-facing abstain message if the DAG has unresolvable nodes, else None."""
    if not unknown_nodes:
        return None
    return (
        f"Column-level lineage is PARTIAL — {len(unknown_nodes)} node(s) could not be "
        f"resolved against the known schema: {unknown_nodes}.\n"
        "This typically means the SQL uses SELECT *, a computed alias the parser can't bind, "
        "or a source table not registered in the schema. "
        "Lineage for these columns is TABLE-LEVEL only (not audit-grade at column level).\n"
        "Action: replace SELECT * with explicit column lists, or register the missing table in schema.py."
    )
