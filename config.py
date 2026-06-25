"""Config for "Find My Data Path" — column-level data lineage + NL querying (learning project).

All content is SYNTHETIC. The lineage is derived from the SQL TEXT only (no data rows are read),
which is the on-prem / data-cannot-leave-the-warehouse design.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SQL_DIR = ROOT / "sql"
DATA_DIR = ROOT / "data"

# Source systems — two tiers:
#   ACTIVE:   systems wired into this synthetic pipeline (columns exist in the lineage graph)
#   CATALOG:  real-world banking sources registered for gap/coverage reporting (not yet wired in)
#
# In production this dict would be read from a data catalog (DataHub / Apache Atlas / Collibra).
SOURCE_SYSTEMS = {
    # ── ACTIVE in current pipeline ──────────────────────────────────────────
    "creditmart":      "CreditMart — credit-risk exposures",
    "marketriskhub":   "MarketRiskHub — market-risk positions",
    "goldensourcefdo": "GoldenSource FDO — counterparty reference data",

    # ── CATALOG: channel systems (not yet wired into pipeline) ──────────────
    "atm_channel":        "ATM — cash withdrawal & enquiry transactions",
    "internet_banking":   "Internet Banking — web session & transaction data",
    "mobile_banking":     "Mobile App — in-app activity & transaction data",
    "branch_crm":         "Branch / Walk-in — CRM interactions & teller data",
    "ivr_channel":        "IVR / Call Centre — voice interaction data",
    "social_sentiment":   "Social Media — sentiment feeds (Twitter/X, news NLP)",

    # ── CATALOG: product systems (not yet wired into pipeline) ──────────────
    "core_banking":       "Core Banking System — accounts, balances, transactions",
    "credit_card":        "Credit Card — spend, limit, delinquency, rewards",
    "loans":              "Loans & Lending — personal, auto, mortgage origination & servicing",
    "retail_banking":     "Retail Banking — savings, current accounts, FDs",
    "consumer_banking":   "Consumer Banking — mass-market product suite",
    "commercial_banking": "Commercial Banking — SME/corporate facilities & trade finance",
    "campaign_mgmt":      "Campaign Management — marketing offers, responses, attribution",
    "collections":        "Collections — delinquency, recovery, write-off data",
    "fraud_platform":     "Fraud Detection — alerts, confirmed fraud cases, device fingerprints",
}

DIALECT = "ansi"          # SQL dialect for the parser
REG_MULTIPLIER = 1.06     # regulatory multiplier used in the mart derivation (a constant, not a column)

# --- LLM (OPTIONAL; metadata/SQL only, never data rows). Runs $0 without a key. ---
AI_MODEL = "claude-haiku-4-5-20251001"   # cheap; switch to claude-sonnet-4-6 for richer explanations
AI_MAX_TOKENS = 600


def get_key() -> str:
    """Anthropic key via env only (never committed). Empty = $0 deterministic mode."""
    return os.environ.get("ANTHROPIC_API_KEY", "")
