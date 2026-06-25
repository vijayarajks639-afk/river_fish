"""Limitations registry for "Find My Data Path".

Every time the lineage engine hits a boundary it calls surface_message() from
here so the user — BA, data steward, or auditor — gets a clear, jargon-free
explanation of WHAT was missed, WHY, and WHAT to do next.

Design principle: an honest tool that says "I can't see this" is more
trustworthy than one that silently returns partial results.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Limitation:
    id: str
    trigger: str             # what causes this limitation
    impact: str              # HIGH / MEDIUM / LOW + description
    business_message: str    # plain-English message for a BA / stakeholder
    action: str              # what to do next
    bcbs239_note: Optional[str] = None   # regulatory callout if relevant


REGISTRY: list[Limitation] = [
    Limitation(
        id="select_star",
        trigger="SELECT * in the SQL",
        impact="HIGH",
        business_message=(
            "This SQL uses SELECT * — the engine cannot determine which specific columns "
            "flow from the source. Only the table-level link is visible; column-level traceability "
            "is unavailable. The lineage shown here is PARTIAL and not audit-grade."
        ),
        action=(
            "Ask the pipeline developer to replace SELECT * with explicit column names "
            "(e.g. SELECT col_a, col_b FROM ...). Each column must be named for BCBS 239 "
            "attribute-level traceability."
        ),
        bcbs239_note="BCBS 239 Principle 2 requires attribute (column)-level lineage. "
                     "SELECT * prevents this and will fail a RDARR audit.",
    ),
    Limitation(
        id="etl_non_sql",
        trigger="Non-SQL ETL tool (Ab Initio, Informatica, SSIS, Talend, DataStage)",
        impact="HIGH",
        business_message=(
            "This transformation is performed inside an ETL tool whose logic is NOT expressed "
            "as SQL text. The lineage engine reads SQL only — it cannot see inside Ab Initio "
            "graphs, Informatica mappings, SSIS packages, or similar tools. "
            "The column shown has a LINEAGE GAP at this step."
        ),
        action=(
            "Export the ETL tool's column-level metadata (Ab Initio: EME/MFS metadata API; "
            "Informatica: PowerCenter repository API; SSIS: BIML export). Stitch it to this DAG "
            "as an external lineage segment, or re-express the logic as SQL views/CTEs."
        ),
        bcbs239_note="Most enterprise banking pipelines use Ab Initio or Informatica for "
                     "critical data. This gap is the most common BCBS 239 audit finding.",
    ),
    Limitation(
        id="stored_procedure",
        trigger="Stored procedure / PL/SQL / T-SQL procedural block",
        impact="HIGH",
        business_message=(
            "This step is implemented as a stored procedure. The engine can trace SQL SELECT/INSERT/UPDATE "
            "statements, but procedural logic (IF blocks, cursors, dynamic EXEC inside a proc) "
            "is not parsed. Column derivations inside the procedure are invisible to this tool."
        ),
        action=(
            "Decompose stored procedures into SQL views or CTEs where possible. "
            "For procs that cannot be changed, add OpenLineage instrumentation at the proc boundary "
            "to emit a runtime lineage event."
        ),
    ),
    Limitation(
        id="dynamic_sql",
        trigger="Dynamic SQL (EXEC, sp_executesql, or column lists built at runtime)",
        impact="HIGH",
        business_message=(
            "The SQL text for this transformation is built and executed at runtime — the column names "
            "are not visible in any static file. This engine cannot trace dynamic SQL. "
            "There is a LINEAGE GAP here."
        ),
        action=(
            "Log the dynamic SQL to a metadata table at execution time, then feed that log "
            "into the lineage parser as if it were static SQL. Alternatively, rewrite as static SQL."
        ),
        bcbs239_note="Dynamic SQL is a common source of BCBS 239 traceability failures.",
    ),
    Limitation(
        id="pyspark_dataframe",
        trigger="PySpark / pandas / DataFrame transformation (non-SQL)",
        impact="MEDIUM",
        business_message=(
            "This step is a Python/Spark DataFrame transformation — column lineage is expressed "
            "in code, not SQL. The static SQL parser cannot trace it. "
            "Table-level lineage may be available but column-level is not."
        ),
        action=(
            "Use the OpenLineage Spark integration (ol-spark listener) or Marquez to capture "
            "runtime column-level lineage from Spark jobs automatically."
        ),
    ),
    Limitation(
        id="ambiguous_column",
        trigger="Column name is ambiguous across multiple tables",
        impact="MEDIUM",
        business_message=(
            "The column name you searched for exists in more than one table. "
            "The engine cannot decide which one you mean without a fully-qualified name "
            "(table.column_name). No lineage has been returned to avoid returning the wrong path."
        ),
        action=(
            "Use the fully-qualified form: table_name.column_name. "
            "For example, use 'stg_credit.pd' instead of just 'pd'."
        ),
    ),
    Limitation(
        id="unregistered_source",
        trigger="Source table not registered in the schema catalog",
        impact="MEDIUM",
        business_message=(
            "One or more source tables in the lineage path are not registered in the schema catalog. "
            "The columns from these tables are shown as 'unknown source' — "
            "the link exists but cannot be validated against the known schema."
        ),
        action=(
            "Register the missing table in schema.py (KNOWN_SCHEMA) or your data catalog. "
            "In production this would connect to DataHub / Apache Atlas / Collibra."
        ),
    ),
    Limitation(
        id="runtime_vs_static",
        trigger="Runtime lineage vs static SQL lineage",
        impact="LOW",
        business_message=(
            "This tool traces lineage from SQL TEXT only — it does not execute the pipeline. "
            "If the actual data has been filtered, repartitioned, or enriched at runtime in ways "
            "not visible in the SQL (e.g. via config-driven exclusions, masking, dynamic filters), "
            "those transformations will NOT appear in this lineage view."
        ),
        action=(
            "Complement static lineage (this tool) with runtime lineage capture "
            "(OpenLineage events from your orchestrator: dbt, Airflow, Spark, etc.)."
        ),
    ),
    Limitation(
        id="scale_traversal",
        trigger="Very large lineage DAG (1000s of columns, dense fan-in/fan-out)",
        impact="LOW",
        business_message=(
            "For very large pipelines the all-paths traversal used here can be slow. "
            "Paths shown may be capped. The source columns (roots) are always complete "
            "even when path enumeration is limited."
        ),
        action="Switch to depth-limited traversal or use a graph database (Neo4j) for production scale.",
    ),
]

# Fast lookup by id
_BY_ID: dict[str, Limitation] = {lim.id: lim for lim in REGISTRY}


def get(limitation_id: str) -> Optional[Limitation]:
    return _BY_ID.get(limitation_id)


def surface_message(limitation_id: str, context: str = "") -> str:
    """Return a formatted, user-facing message for a known limitation."""
    lim = get(limitation_id)
    if lim is None:
        return f"[Unknown limitation id '{limitation_id}']"

    lines = [
        f"⚠  LINEAGE BOUNDARY — {lim.trigger}",
        f"   Impact : {lim.impact}",
        f"   What this means : {lim.business_message}",
        f"   Action : {lim.action}",
    ]
    if lim.bcbs239_note:
        lines.append(f"   BCBS 239 : {lim.bcbs239_note}")
    if context:
        lines.append(f"   Context : {context}")
    return "\n".join(lines)


def check_sql_for_limitations(sql_text: str) -> list[str]:
    """Scan SQL text and return limitation IDs that apply.

    Used by the lineage engine to proactively warn before the user even asks.
    """
    found = []
    upper = sql_text.upper()
    if "SELECT *" in upper or "SELECT\n*" in upper:
        found.append("select_star")
    if any(kw in upper for kw in ("EXEC ", "EXECUTE ", "SP_EXECUTESQL")):
        found.append("dynamic_sql")
    if any(kw in upper for kw in ("CREATE PROCEDURE", "CREATE PROC", "BEGIN\n", "DECLARE @")):
        found.append("stored_procedure")
    return found
