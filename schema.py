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
    # NOTE: creditmart / marketriskhub / goldensourcefdo are defined ONCE in the extended
    # block below as supersets (original core columns + new synthetic join keys), so there
    # are no duplicate dict keys. The core columns required by sql/10..40 are preserved there.
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

    # ── Extended source systems (generate_data.py — SYNTHETIC, zero PII) ──
    # Added 2026-06-25 by Data Generator agent; duplicate-key originals merged in by
    # the orchestrator. These 3 entries are the single source of truth for the active
    # source tables (core columns + synthetic join keys for the market_data.py feeds).
    # goldensourcefdo extended columns
    "goldensourcefdo.raw_counterparty": [
        "counterparty_id", "counterparty_name", "legal_entity", "country",
        "incorporation_date", "sic_code", "group_parent_id",
    ],
    # creditmart extended columns (join keys for market_data.py feeds)
    "creditmart.raw_credit_exposures": [
        "counterparty_id", "exposure_amount", "pd", "lgd", "internal_rating", "currency",
        "equity_ticker", "tenor", "stress_scenario", "origination_date", "facility_type",
    ],
    # marketriskhub extended columns
    "marketriskhub.raw_market_positions": [
        "counterparty_id", "market_value", "var_1d", "currency",
        "desk_id", "book_id", "position_type", "as_of_date",
    ],
    # core_banking
    "core_banking.raw_accounts": [
        "account_id", "counterparty_id", "account_type", "balance", "currency",
        "open_date", "branch_code", "status",
        "interest_rate", "sweep_enabled", "nomination_flag",
    ],
    "core_banking.raw_daily_txns": [
        "txn_id", "counterparty_id", "account_id", "txn_type", "amount",
        "currency", "txn_date", "channel",
        "merchant_code", "narration",
    ],
    # credit_card
    "credit_card.raw_card_accounts": [
        "card_id", "counterparty_id", "card_product", "credit_limit",
        "outstanding_balance", "utilization_ratio", "delinquency_bucket",
        "reward_points", "cycle_date", "currency",
        "cashback_earned_ytd", "emi_converted_amount", "insurance_flag",
    ],
    # loans
    "loans.raw_loan_accounts": [
        "loan_id", "counterparty_id", "loan_type", "sanctioned_amount",
        "outstanding_principal", "interest_rate", "tenor_months",
        "emi_amount", "emi_status", "loan_status",
        "disbursement_date", "currency", "collateral_type",
        "bureau_score_at_origination", "co_applicant_flag", "insurance_linked",
    ],
    # atm_channel
    "atm_channel.raw_atm_events": [
        "atm_txn_id", "counterparty_id", "atm_id", "txn_type", "amount",
        "currency", "txn_datetime", "atm_location_code",
        "failure_code", "card_type_used", "bank_code",
    ],
    # mobile_banking
    "mobile_banking.raw_mobile_sessions": [
        "session_id", "counterparty_id", "session_date", "session_duration_sec",
        "txn_type", "amount", "currency", "os_type", "app_version",
        "login_method", "push_notif_clicked", "device_id_hash",
    ],
    # retail_banking
    "retail_banking.raw_product_holdings": [
        "holding_id", "counterparty_id", "product_type", "balance",
        "currency", "open_date", "maturity_date", "interest_rate",
        "auto_renewal_flag", "nominee_flag", "branch_code",
    ],
    # consumer_banking
    "consumer_banking.raw_consumer_profile": [
        "counterparty_id", "segment", "nrv", "total_products",
        "vintage_months", "primary_channel",
        "churn_score", "cross_sell_score", "kyc_status",
    ],
    # commercial_banking
    "commercial_banking.raw_commercial_facilities": [
        "facility_id", "counterparty_id", "facility_type", "sanctioned_limit",
        "utilised_amount", "currency", "sector", "tenor_months", "interest_rate",
        "collateral_value", "deal_team_id", "covenant_breach_flag",
    ],
    # campaign_mgmt
    "campaign_mgmt.raw_campaign_events": [
        "campaign_event_id", "counterparty_id", "campaign_id", "campaign_type",
        "offer_product", "offer_amount", "response", "response_date", "campaign_date",
        "channel_cost", "propensity_score", "segment_targeted",
    ],
    # social_sentiment (SYNTHETIC scores — NOT scraped posts)
    "social_sentiment.raw_sentiment_scores": [
        "sentiment_id", "counterparty_id", "sentiment_score", "sentiment_label",
        "score_date", "signal_volume",
        "news_score", "analyst_mention_flag",
    ],
    # ── sql_extended/ staging and mart tables ──────────────────────────────────
    # FX exposure staging (joins real market feed to synthetic exposure)
    "stg_fx_rates": [
        "symbol", "base_currency", "quote_currency", "spot_rate",
        "market_time", "loaded_at", "is_stale",
    ],
    "stg_fx_exposure_inr": [
        "counterparty_id", "exposure_amount", "exposure_currency",
        "fx_rate_to_inr", "exposure_inr", "rate_as_of", "rate_is_stale",
    ],
    "mart_fx_exposure_summary": [
        "exposure_currency", "counterparty_count", "total_local_exposure",
        "fx_rate_used", "total_exposure_inr", "rate_as_of", "any_rate_stale",
    ],
    # Channel activity staging and mart
    "stg_atm_activity": [
        "counterparty_id", "atm_txn_count", "total_withdrawal_amount",
        "last_atm_txn_datetime", "distinct_atms_used",
    ],
    "stg_mobile_activity": [
        "counterparty_id", "session_count", "total_mobile_txn_amount",
        "avg_session_duration_sec", "last_session_date", "distinct_os_types",
    ],
    "stg_core_txn_activity": [
        "counterparty_id", "txn_count", "total_credit_amount",
        "total_debit_amount", "last_txn_date",
    ],
    "mart_channel_activity": [
        "counterparty_id", "counterparty_name", "country",
        "atm_txn_count", "atm_withdrawal_amount",
        "mobile_session_count", "mobile_txn_amount",
        "core_txn_count", "core_credit_amount", "core_debit_amount",
        "total_channel_events",
    ],
    # Product holdings staging and mart
    "stg_card_summary": [
        "counterparty_id", "card_count", "total_credit_limit",
        "total_card_outstanding", "avg_utilization_ratio", "worst_delinquency_rank",
    ],
    "stg_loan_summary": [
        "counterparty_id", "loan_count", "total_loan_outstanding",
        "npa_outstanding", "avg_loan_interest_rate", "worst_emi_status_rank",
    ],
    "stg_retail_holdings": [
        "counterparty_id", "product_count", "total_deposit_balance", "term_deposit_balance",
    ],
    "mart_product_holdings": [
        "counterparty_id", "counterparty_name", "legal_entity", "country",
        "segment", "nrv", "vintage_months", "primary_channel",
        "card_count", "total_credit_limit", "card_outstanding",
        "avg_card_utilization", "worst_card_delinquency",
        "loan_count", "loan_outstanding", "npa_outstanding", "worst_emi_status",
        "total_deposit_balance", "term_deposit_balance",
        "liabilities_to_deposits_ratio",
    ],
    # Campaign + sentiment + commercial mart
    "stg_campaign_summary": [
        "counterparty_id", "total_campaigns_targeted", "campaigns_accepted",
        "campaigns_rejected", "acceptance_rate", "last_campaign_date",
    ],
    "stg_commercial_summary": [
        "counterparty_id", "facility_count", "total_sanctioned_limit",
        "total_utilised", "utilisation_ratio", "avg_facility_rate", "primary_sector",
    ],
    "mart_engagement_risk": [
        "counterparty_id", "counterparty_name", "legal_entity",
        "campaigns_targeted", "campaigns_accepted", "campaign_acceptance_rate",
        "sentiment_score", "sentiment_label", "signal_volume",
        "facility_count", "total_sanctioned_limit", "total_utilised",
        "commercial_utilisation_ratio", "primary_sector",
        "engagement_quality_index",
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
