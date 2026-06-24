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

# Source systems modelled (a realistic multi-source banking landscape)
SOURCE_SYSTEMS = {
    "creditmart": "CreditMart — credit-risk exposures",
    "marketriskhub": "MarketRiskHub — market-risk positions",
    "goldensourcefdo": "GoldenSource FDO — counterparty reference data",
}

DIALECT = "ansi"          # SQL dialect for the parser
REG_MULTIPLIER = 1.06     # regulatory multiplier used in the mart derivation (a constant, not a column)

# --- LLM (OPTIONAL; metadata/SQL only, never data rows). Runs $0 without a key. ---
AI_MODEL = "claude-haiku-4-5-20251001"   # cheap; switch to claude-sonnet-4-6 for richer explanations
AI_MAX_TOKENS = 600


def get_key() -> str:
    """Anthropic key via env only (never committed). Empty = $0 deterministic mode."""
    return os.environ.get("ANTHROPIC_API_KEY", "")
