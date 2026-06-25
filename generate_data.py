"""Synthetic Banking Data Generator for "Find My Data Path".

GOVERNANCE BANNER (NON-NEGOTIABLE)
===================================
- Generates SYNTHETIC data ONLY. Zero PII. No real names, PAN, Aadhaar,
  account/card numbers, email, or phone.
- All identities use obviously-synthetic markers: CPTY_000123, "Synthetic Corp 47 Ltd".
- Market/reference data (FX rates, yields, VIX, equity prices) is NOT generated here.
  It comes from market_data.py (real public data). This module aligns to it via
  JOIN KEYS ONLY (currency code, equity_ticker, tenor).
- Generated rows live in DuckDB for BA inspection and NEVER enter an LLM prompt.

Run:
    .venv\\Scripts\\python generate_data.py              (default 500 counterparties)
    .venv\\Scripts\\python generate_data.py --rows 200   (smaller demo set)
    .venv\\Scripts\\python generate_data.py --rows 1000  (larger stress test)
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# ── project imports ───────────────────────────────────────────────────────────
import config

# ── constants ─────────────────────────────────────────────────────────────────
SEED = 42          # deterministic — same seed = same data every run

# Join-key domains that align to market_data.py feeds (no real values stored here)
CURRENCIES      = ["INR", "USD", "EUR", "GBP"]          # aligns to EURINR, USDINR, GBPINR, EURUSD
TENORS          = ["3M", "6M", "1Y", "2Y", "5Y", "10Y"] # aligns to ^IRX (13wk), ^TNX (10Y UST)
EQUITY_TICKERS  = ["^NSEI", "^GSPC", None, None, None]  # ~40% have an equity mark (aligns to basket)
STRESS_FLAGS    = ["BASE", "VIX_STRESS", "SEVERE"]       # VIX_STRESS => ^VIX-driven multiplier

# Internal-rating buckets (Basel III / credit-risk taxonomy)
INTERNAL_RATINGS = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "CC", "C", "D"]
RATING_PD_RANGE = {
    "AAA": (0.0001, 0.0005),
    "AA":  (0.0003, 0.001),
    "A":   (0.001,  0.003),
    "BBB": (0.003,  0.01),
    "BB":  (0.01,   0.05),
    "B":   (0.05,   0.10),
    "CCC": (0.10,   0.30),
    "CC":  (0.20,   0.50),
    "C":   (0.40,   0.70),
    "D":   (0.70,   1.00),
}
RATING_LGD_RANGE = {   # senior unsecured typical LGD by grade
    "AAA": (0.20, 0.35),
    "AA":  (0.25, 0.40),
    "A":   (0.30, 0.45),
    "BBB": (0.35, 0.50),
    "BB":  (0.40, 0.55),
    "B":   (0.45, 0.60),
    "CCC": (0.50, 0.70),
    "CC":  (0.55, 0.75),
    "C":   (0.60, 0.80),
    "D":   (0.65, 0.90),
}

LEGAL_ENTITIES  = [
    "Synthetic Holdings APAC Ltd",
    "Synthetic Corp EMEA Ltd",
    "Synthetic Capital Americas Corp",
    "Synthetic FinServ India Pvt Ltd",
    "Synthetic SME Ventures Ltd",
    "Synthetic Trade Finance PLC",
]
COUNTRIES = ["IND", "USA", "GBR", "DEU", "SGP", "ARE", "AUS", "CAN"]

# Channel / product taxonomy
ATM_TXN_TYPES    = ["WITHDRAWAL", "BALANCE_ENQUIRY", "MINI_STATEMENT", "PIN_CHANGE"]
MOBILE_TXN_TYPES = ["FUND_TRANSFER", "BILL_PAY", "RECHARGE", "UPI_PUSH", "UPI_PULL", "INVESTMENT"]
LOAN_TYPES       = ["PERSONAL", "AUTO", "MORTGAGE", "EDUCATION"]
LOAN_STATUS      = ["ACTIVE", "CLOSED", "NPA", "WRITTEN_OFF", "RESTRUCTURED"]
EMI_STATUS       = ["CURRENT", "30_DPD", "60_DPD", "90_DPD", "OVER_90_DPD"]
PRODUCT_TYPES    = ["SAVINGS", "CURRENT", "FIXED_DEPOSIT", "RECURRING_DEPOSIT"]
CAMPAIGN_TYPES   = ["EMAIL", "SMS", "PUSH_NOTIFICATION", "BRANCH_OFFER", "IVR_CALL"]
RESPONSE_TYPES   = ["ACCEPTED", "REJECTED", "NO_RESPONSE", "BOUNCED"]
SENTIMENT_LABELS = ["POSITIVE", "NEUTRAL", "NEGATIVE", "MIXED"]

# SME/corporate sectors for commercial banking
SECTORS = [
    "MANUFACTURING", "RETAIL_TRADE", "FINANCIAL_SERVICES",
    "REAL_ESTATE", "IT_SERVICES", "PHARMA", "AGRI", "TRANSPORT",
]


def _rng(seed: int = SEED) -> random.Random:
    return random.Random(seed)


def _synth_name(rng: random.Random, idx: int) -> str:
    """Synthetic company name — obviously not real, no PII."""
    adjectives = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta", "Theta",
                  "Iota", "Kappa", "Lambda", "Mu", "Nu", "Xi", "Omicron", "Pi", "Rho",
                  "Sigma", "Tau", "Upsilon", "Phi", "Chi", "Psi", "Omega"]
    nouns = ["Corp", "Holdings", "Ventures", "Capital", "Industries", "Enterprises",
             "Solutions", "Group", "Partners", "Associates"]
    suffixes = ["Ltd", "Pvt Ltd", "PLC", "Inc", "LLC", "SA"]
    adj = adjectives[idx % len(adjectives)]
    noun = nouns[rng.randint(0, len(nouns) - 1)]
    suf = suffixes[rng.randint(0, len(suffixes) - 1)]
    return f"Synthetic {adj} {noun} {suf}"


def _random_date(rng: random.Random, start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=rng.randint(0, delta))


def _iso(d: date) -> str:
    return d.isoformat()


# ── Generator functions (one per source system) ──────────────────────────────

def gen_goldensourcefdo_counterparty(n: int, rng: random.Random) -> list[dict]:
    """goldensourcefdo.raw_counterparty — master counterparty reference.

    This is the 'spine' table: every counterparty_id used in any other table
    MUST exist here first (referential integrity root).
    """
    rows = []
    for i in range(1, n + 1):
        cpty_id = f"CPTY_{i:06d}"
        rows.append({
            "counterparty_id":   cpty_id,
            "counterparty_name": _synth_name(rng, i),
            "legal_entity":      rng.choice(LEGAL_ENTITIES),
            "country":           rng.choice(COUNTRIES),
            # --- columns deliberately left out of sql_extended/ mart (gap candidates) ---
            "incorporation_date": _iso(_random_date(rng, date(1980, 1, 1), date(2020, 12, 31))),
            "sic_code":           f"SIC{rng.randint(1000, 9999)}",
            "group_parent_id":    f"CPTY_{rng.randint(1, max(1, n // 10)):06d}" if rng.random() < 0.3 else None,
        })
    return rows


def gen_creditmart_exposures(cpty_ids: list[str], rng: random.Random) -> list[dict]:
    """creditmart.raw_credit_exposures — active source in core pipeline."""
    rows = []
    for cid in cpty_ids:
        rating = rng.choice(INTERNAL_RATINGS)
        pd_lo, pd_hi = RATING_PD_RANGE[rating]
        lgd_lo, lgd_hi = RATING_LGD_RANGE[rating]
        currency = rng.choice(CURRENCIES)
        equity_ticker = rng.choice(EQUITY_TICKERS)  # join key to market_data.py ^NSEI / ^GSPC
        tenor = rng.choice(TENORS)                  # join key to ^TNX / ^IRX
        rows.append({
            "counterparty_id":  cid,
            "exposure_amount":  round(rng.uniform(50_000, 50_000_000), 2),
            "pd":               round(rng.uniform(pd_lo, pd_hi), 6),
            "lgd":              round(rng.uniform(lgd_lo, lgd_hi), 4),
            "internal_rating":  rating,
            "currency":         currency,
            # extra columns — partially consumed (gap candidates)
            "equity_ticker":    equity_ticker,   # join key → market price (closes market_value gap)
            "tenor":            tenor,            # join key → yield curve (closes discount-rate gap)
            "stress_scenario":  rng.choice(STRESS_FLAGS),   # join key → ^VIX stress multiplier
            "origination_date": _iso(_random_date(rng, date(2018, 1, 1), date(2025, 12, 31))),
            "facility_type":    rng.choice(["TERM_LOAN", "REVOLVING", "LETTER_OF_CREDIT", "BOND"]),
        })
    return rows


def gen_marketriskhub_positions(cpty_ids: list[str], rng: random.Random) -> list[dict]:
    """marketriskhub.raw_market_positions — active source in core pipeline."""
    rows = []
    for cid in cpty_ids:
        currency = rng.choice(CURRENCIES)
        rows.append({
            "counterparty_id": cid,
            "market_value":    round(rng.uniform(100_000, 20_000_000), 2),
            "var_1d":          round(rng.uniform(1_000, 500_000), 2),
            "currency":        currency,
            # extra columns — NOT consumed downstream (gap candidates)
            "desk_id":         f"DESK_{rng.randint(1, 20):03d}",
            "book_id":         f"BOOK_{rng.randint(1, 100):04d}",
            "position_type":   rng.choice(["EQUITY", "BOND", "FX_FORWARD", "SWAP", "OPTION"]),
            "as_of_date":      _iso(date.today() - timedelta(days=rng.randint(0, 3))),
        })
    return rows


def gen_core_banking_accounts(cpty_ids: list[str], rng: random.Random) -> list[dict]:
    """core_banking.raw_accounts — current/savings account master."""
    rows = []
    for cid in cpty_ids:
        n_accounts = rng.randint(1, 3)
        for acc_idx in range(n_accounts):
            acc_type = rng.choice(PRODUCT_TYPES)
            open_date = _random_date(rng, date(2005, 1, 1), date(2024, 12, 31))
            rows.append({
                "account_id":      f"ACC_{cid}_{acc_idx:02d}",   # synthetic ID, not real
                "counterparty_id": cid,
                "account_type":    acc_type,
                "balance":         round(rng.uniform(1_000, 5_000_000), 2),
                "currency":        rng.choice(CURRENCIES),
                "open_date":       _iso(open_date),
                "branch_code":     f"BR{rng.randint(1, 500):04d}",
                "status":          rng.choices(["ACTIVE", "DORMANT", "CLOSED"], weights=[80, 15, 5])[0],
                # gap candidates (rich but not yet consumed in sql_extended/)
                "interest_rate":   round(rng.uniform(0.02, 0.085), 4),
                "sweep_enabled":   rng.choice([True, False]),
                "nomination_flag": rng.choice([True, False]),
            })
    return rows


def gen_core_banking_transactions(cpty_ids: list[str], rng: random.Random) -> list[dict]:
    """core_banking.raw_daily_txns — daily debit/credit transactions."""
    rows = []
    txn_types = ["CREDIT", "DEBIT", "INTEREST_CREDIT", "CHARGES_DEBIT", "EMI_DEBIT"]
    ref_date = date.today()
    for cid in cpty_ids:
        n_txns = rng.randint(3, 20)
        for t in range(n_txns):
            txn_date = ref_date - timedelta(days=rng.randint(0, 30))
            rows.append({
                "txn_id":          f"TXN_{cid}_{t:04d}",
                "counterparty_id": cid,
                "account_id":      f"ACC_{cid}_00",
                "txn_type":        rng.choice(txn_types),
                "amount":          round(rng.uniform(100, 500_000), 2),
                "currency":        rng.choice(CURRENCIES),
                "txn_date":        _iso(txn_date),
                "channel":         rng.choice(["BRANCH", "ATM", "MOBILE", "NET", "CHEQUE"]),
                # gap candidates
                "merchant_code":   f"MCC{rng.randint(1000, 9999)}" if rng.random() < 0.4 else None,
                "narration":       f"Synthetic txn reference {t:06d}",  # never a real narration
            })
    return rows


def gen_credit_card(cpty_ids: list[str], rng: random.Random) -> list[dict]:
    """credit_card.raw_card_accounts — spend, limit, utilization, delinquency."""
    rows = []
    card_products = ["CLASSIC", "GOLD", "PLATINUM", "SIGNATURE", "INFINITE"]
    for cid in cpty_ids:
        if rng.random() < 0.65:   # ~65% of counterparties have a card
            credit_limit = rng.choice([50_000, 100_000, 200_000, 500_000, 1_000_000])
            outstanding = round(rng.uniform(0, credit_limit * 0.9), 2)
            utilization = round(outstanding / credit_limit, 4)
            rows.append({
                "card_id":           f"CARD_{cid}_01",    # synthetic token, not real PAN
                "counterparty_id":   cid,
                "card_product":      rng.choice(card_products),
                "credit_limit":      credit_limit,
                "outstanding_balance": outstanding,
                "utilization_ratio": utilization,
                "delinquency_bucket": rng.choices(
                    ["CURRENT", "30_DPD", "60_DPD", "90_DPD", "WRITE_OFF"],
                    weights=[75, 10, 7, 5, 3]
                )[0],
                "reward_points":     rng.randint(0, 150_000),
                "cycle_date":        rng.randint(1, 28),
                "currency":          rng.choice(CURRENCIES),
                # gap candidates (not consumed in sql_extended/ mart)
                "cashback_earned_ytd": round(rng.uniform(0, 10_000), 2),
                "emi_converted_amount": round(rng.uniform(0, outstanding), 2) if rng.random() < 0.3 else 0.0,
                "insurance_flag":    rng.choice([True, False]),
            })
    return rows


def gen_loans(cpty_ids: list[str], rng: random.Random) -> list[dict]:
    """loans.raw_loan_accounts — personal/auto/mortgage origination + servicing."""
    rows = []
    for cid in cpty_ids:
        n_loans = rng.choices([0, 1, 2, 3], weights=[30, 45, 18, 7])[0]
        for l_idx in range(n_loans):
            loan_type = rng.choice(LOAN_TYPES)
            sanction_amt = rng.choice([100_000, 250_000, 500_000, 1_000_000, 5_000_000, 10_000_000])
            tenor_months = {"PERSONAL": 36, "AUTO": 60, "MORTGAGE": 240, "EDUCATION": 84}[loan_type]
            tenor_months += rng.randint(-12, 12)
            disbursement_date = _random_date(rng, date(2015, 1, 1), date(2024, 6, 30))
            emi = round(sanction_amt * 0.01 * rng.uniform(0.8, 1.2), 2)
            rows.append({
                "loan_id":           f"LN_{cid}_{l_idx:02d}",  # synthetic ID
                "counterparty_id":   cid,
                "loan_type":         loan_type,
                "sanctioned_amount": sanction_amt,
                "outstanding_principal": round(sanction_amt * rng.uniform(0.05, 0.95), 2),
                "interest_rate":     round(rng.uniform(0.07, 0.18), 4),
                "tenor_months":      tenor_months,
                "emi_amount":        emi,
                "emi_status":        rng.choices(EMI_STATUS, weights=[75, 8, 6, 5, 6])[0],
                "loan_status":       rng.choices(LOAN_STATUS, weights=[65, 15, 8, 5, 7])[0],
                "disbursement_date": _iso(disbursement_date),
                "currency":          rng.choice(CURRENCIES),
                "collateral_type":   rng.choice(["PROPERTY", "VEHICLE", "FD", "NONE"]) if loan_type != "PERSONAL" else "NONE",
                # gap candidates
                "bureau_score_at_origination": rng.randint(550, 850),
                "co_applicant_flag": rng.choice([True, False]),
                "insurance_linked":  rng.choice([True, False]),
            })
    return rows


def gen_atm_channel(cpty_ids: list[str], rng: random.Random) -> list[dict]:
    """atm_channel.raw_atm_events — withdrawal/enquiry events."""
    rows = []
    ref_date = date.today()
    for cid in cpty_ids:
        n_events = rng.randint(0, 8)
        for e_idx in range(n_events):
            txn_date = ref_date - timedelta(days=rng.randint(0, 90))
            txn_type = rng.choice(ATM_TXN_TYPES)
            rows.append({
                "atm_txn_id":      f"ATM_{cid}_{e_idx:04d}",
                "counterparty_id": cid,
                "atm_id":          f"ATM_{rng.randint(1, 5000):05d}",
                "txn_type":        txn_type,
                "amount":          round(rng.uniform(500, 50_000), 2) if txn_type == "WITHDRAWAL" else 0.0,
                "currency":        "INR",   # ATM is local-currency
                "txn_datetime":    f"{_iso(txn_date)}T{rng.randint(0,23):02d}:{rng.randint(0,59):02d}:00Z",
                "atm_location_code": f"LOC_{rng.randint(1, 200):03d}",
                # gap candidates (not consumed in any sql_extended/ mart)
                "failure_code":    rng.choice(["00", "51", "61", "91", None]),
                "card_type_used":  rng.choice(["DEBIT", "CREDIT"]),
                "bank_code":       rng.choice(["OWN_BANK", "INTER_BANK"]),
            })
    return rows


def gen_mobile_banking(cpty_ids: list[str], rng: random.Random) -> list[dict]:
    """mobile_banking.raw_mobile_sessions — in-app sessions + transactions."""
    rows = []
    ref_date = date.today()
    os_types = ["ANDROID", "IOS"]
    for cid in cpty_ids:
        n_sessions = rng.randint(1, 15)
        for s_idx in range(n_sessions):
            session_date = ref_date - timedelta(days=rng.randint(0, 30))
            txn_type = rng.choice(MOBILE_TXN_TYPES)
            rows.append({
                "session_id":      f"MOB_{cid}_{s_idx:04d}",
                "counterparty_id": cid,
                "session_date":    _iso(session_date),
                "session_duration_sec": rng.randint(10, 1800),
                "txn_type":        txn_type,
                "amount":          round(rng.uniform(10, 1_000_000), 2) if txn_type not in ["BALANCE_ENQUIRY"] else 0.0,
                "currency":        rng.choice(CURRENCIES),
                "os_type":         rng.choice(os_types),
                "app_version":     f"{rng.randint(4,7)}.{rng.randint(0,9)}.{rng.randint(0,9)}",
                # gap candidates
                "login_method":    rng.choice(["MPIN", "BIOMETRIC", "OTP"]),
                "push_notif_clicked": rng.choice([True, False, None]),
                "device_id_hash":  f"DEV_{rng.randint(100000, 999999):06d}",  # hashed, not real
            })
    return rows


def gen_retail_banking(cpty_ids: list[str], rng: random.Random) -> list[dict]:
    """retail_banking.raw_product_holdings — savings/current/FD holdings."""
    rows = []
    for cid in cpty_ids:
        n_products = rng.randint(1, 4)
        for p_idx in range(n_products):
            prod_type = rng.choice(PRODUCT_TYPES)
            rows.append({
                "holding_id":      f"RB_{cid}_{p_idx:02d}",
                "counterparty_id": cid,
                "product_type":    prod_type,
                "balance":         round(rng.uniform(5_000, 10_000_000), 2),
                "currency":        rng.choice(CURRENCIES),
                "open_date":       _iso(_random_date(rng, date(2000, 1, 1), date(2024, 12, 31))),
                "maturity_date":   _iso(_random_date(rng, date(2025, 1, 1), date(2030, 12, 31))) if prod_type in ["FIXED_DEPOSIT", "RECURRING_DEPOSIT"] else None,
                "interest_rate":   round(rng.uniform(0.03, 0.09), 4) if prod_type in ["FIXED_DEPOSIT", "RECURRING_DEPOSIT"] else None,
                # gap candidates
                "auto_renewal_flag": rng.choice([True, False]),
                "nominee_flag":    rng.choice([True, False]),
                "branch_code":     f"BR{rng.randint(1, 500):04d}",
            })
    return rows


def gen_consumer_banking(cpty_ids: list[str], rng: random.Random) -> list[dict]:
    """consumer_banking.raw_consumer_profile — mass-market product suite."""
    rows = []
    segments = ["MASS_MARKET", "MASS_AFFLUENT", "PREMIUM", "BURGUNDY"]
    for cid in cpty_ids:
        rows.append({
            "counterparty_id":  cid,
            "segment":          rng.choice(segments),
            "nrv":              round(rng.uniform(10_000, 50_000_000), 2),  # net relationship value
            "total_products":   rng.randint(1, 8),
            "vintage_months":   rng.randint(1, 240),
            "primary_channel":  rng.choice(["BRANCH", "MOBILE", "NET", "IVR"]),
            # gap candidates (not consumed in sql_extended/)
            "churn_score":      round(rng.uniform(0.0, 1.0), 4),
            "cross_sell_score": round(rng.uniform(0.0, 1.0), 4),
            "kyc_status":       rng.choice(["COMPLETED", "PENDING", "EXPIRED"]),
        })
    return rows


def gen_commercial_banking(cpty_ids: list[str], rng: random.Random) -> list[dict]:
    """commercial_banking.raw_commercial_facilities — SME/corporate credit facilities."""
    rows = []
    # Only a subset of counterparties have commercial facilities
    commercial_cptys = [c for c in cpty_ids if int(c.split("_")[1]) % 5 == 0]   # ~20%
    facility_types = ["TERM_LOAN", "WORKING_CAPITAL", "LETTER_OF_CREDIT", "BANK_GUARANTEE", "EXPORT_FINANCE"]
    for cid in commercial_cptys:
        n_facilities = rng.randint(1, 3)
        for f_idx in range(n_facilities):
            sector = rng.choice(SECTORS)
            sanction = round(rng.uniform(1_000_000, 500_000_000), 2)
            rows.append({
                "facility_id":     f"CF_{cid}_{f_idx:02d}",
                "counterparty_id": cid,
                "facility_type":   rng.choice(facility_types),
                "sanctioned_limit": sanction,
                "utilised_amount": round(sanction * rng.uniform(0.1, 0.95), 2),
                "currency":        rng.choice(CURRENCIES),
                "sector":          sector,
                "tenor_months":    rng.choice([12, 24, 36, 60, 120]),
                "interest_rate":   round(rng.uniform(0.06, 0.14), 4),
                # gap candidates
                "collateral_value":  round(rng.uniform(sanction * 0.5, sanction * 2.0), 2),
                "deal_team_id":      f"DT_{rng.randint(1, 50):03d}",
                "covenant_breach_flag": rng.choices([True, False], weights=[5, 95])[0],
            })
    return rows


def gen_campaign_mgmt(cpty_ids: list[str], rng: random.Random) -> list[dict]:
    """campaign_mgmt.raw_campaign_events — marketing offers and responses."""
    rows = []
    ref_date = date.today()
    for cid in cpty_ids:
        n_campaigns = rng.randint(0, 5)
        for c_idx in range(n_campaigns):
            campaign_date = ref_date - timedelta(days=rng.randint(0, 180))
            rows.append({
                "campaign_event_id":  f"CAMP_{cid}_{c_idx:04d}",
                "counterparty_id":    cid,
                "campaign_id":        f"CMP_{rng.randint(1000, 9999)}",
                "campaign_type":      rng.choice(CAMPAIGN_TYPES),
                "offer_product":      rng.choice(["CREDIT_CARD", "PERSONAL_LOAN", "INVESTMENT", "INSURANCE"]),
                "offer_amount":       round(rng.uniform(10_000, 1_000_000), 2),
                "response":           rng.choices(RESPONSE_TYPES, weights=[25, 15, 55, 5])[0],
                "response_date":      _iso(campaign_date + timedelta(days=rng.randint(0, 30))),
                "campaign_date":      _iso(campaign_date),
                # gap candidates (not consumed downstream)
                "channel_cost":       round(rng.uniform(10, 500), 2),
                "propensity_score":   round(rng.uniform(0.0, 1.0), 4),
                "segment_targeted":   rng.choice(["MASS", "PREMIUM", "HNI"]),
            })
    return rows


def gen_social_sentiment(cpty_ids: list[str], rng: random.Random) -> list[dict]:
    """social_sentiment.raw_sentiment_scores — SYNTHETIC scores (NOT scraped posts).

    Generates a sentiment score (0.0=very negative, 1.0=very positive) per
    counterparty with a label. NO real social media posts are stored.
    """
    rows = []
    ref_date = date.today()
    for cid in cpty_ids:
        # ~70% of counterparties have a sentiment signal (some are private/unknown)
        if rng.random() < 0.70:
            score = round(rng.betavariate(5, 3), 4)   # slightly right-skewed (mostly neutral/positive)
            if score >= 0.70:
                label = "POSITIVE"
            elif score >= 0.45:
                label = "NEUTRAL"
            elif score >= 0.25:
                label = "MIXED"
            else:
                label = "NEGATIVE"
            rows.append({
                "sentiment_id":       f"SENT_{cid}",
                "counterparty_id":    cid,
                "sentiment_score":    score,
                "sentiment_label":    label,
                "score_date":         _iso(ref_date - timedelta(days=rng.randint(0, 7))),
                "signal_volume":      rng.randint(0, 1000),  # synthetic signal count, NOT real posts
                # gap candidates (not consumed by any mart — pure gap signal)
                "news_score":         round(rng.uniform(0.0, 1.0), 4),   # sub-score from news channel
                "analyst_mention_flag": rng.choice([True, False]),
            })
    return rows


# ── FX rates staging helper ───────────────────────────────────────────────────

def write_fx_rates_to_duckdb(conn) -> int:
    """Write the current market_data.py snapshot into a DuckDB fx_rates table.

    This makes the JOIN in sql_extended/50_fx_exposure_staging.sql runnable:
      synthetic exposure.currency -> fx_rates.currency_pair -> real spot rate.
    The actual rate comes from market_data.py (real public data).
    Returns number of FX rows written.
    """
    from market_data import fetch_market_snapshot

    print("  Fetching FX rates from market_data.py (live public data)...")
    pts = fetch_market_snapshot()
    fx_pts = [p for p in pts if p.category == "fx" and p.value is not None]

    # Map Yahoo symbol to currency pair key that synthetic data can JOIN on
    symbol_to_pair = {
        "EURINR=X": ("EUR", "INR"),
        "USDINR=X": ("USD", "INR"),
        "GBPINR=X": ("GBP", "INR"),
        "EURUSD=X": ("EUR", "USD"),
    }
    rows = []
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for p in fx_pts:
        if p.symbol in symbol_to_pair:
            base, quote = symbol_to_pair[p.symbol]
            rows.append((
                p.symbol,
                base,
                quote,
                p.value,
                p.market_time,
                now_iso,
                p.is_stale,
            ))

    conn.execute("""
        CREATE OR REPLACE TABLE stg_fx_rates (
            symbol           VARCHAR,
            base_currency    VARCHAR,
            quote_currency   VARCHAR,
            spot_rate        DOUBLE,
            market_time      VARCHAR,
            loaded_at        VARCHAR,
            is_stale         BOOLEAN
        )
    """)
    conn.executemany("INSERT INTO stg_fx_rates VALUES (?,?,?,?,?,?,?)", rows)
    return len(rows)


# ── DuckDB loader ─────────────────────────────────────────────────────────────

def load_to_duckdb(tables: dict[str, list[dict]], db_path: Path) -> dict[str, int]:
    """Write all generated tables into DuckDB. Returns {table_name: row_count}."""
    import duckdb

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path))

    row_counts: dict[str, int] = {}

    for table_name, rows in tables.items():
        if not rows:
            print(f"  [SKIP] {table_name} — 0 rows, skipping")
            continue

        # Infer CREATE TABLE columns from first row
        keys = list(rows[0].keys())
        col_defs = []
        for k in keys:
            # Infer type from first non-None value
            sample = next((r[k] for r in rows if r.get(k) is not None), None)
            if isinstance(sample, bool):
                dtype = "BOOLEAN"
            elif isinstance(sample, int):
                dtype = "INTEGER"
            elif isinstance(sample, float):
                dtype = "DOUBLE"
            else:
                dtype = "VARCHAR"
            col_defs.append(f"{k} {dtype}")

        # Schema prefix → DuckDB schema
        if "." in table_name:
            schema, tbl = table_name.split(".", 1)
            conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
            full_name = f"{schema}.{tbl}"
        else:
            full_name = table_name

        conn.execute(f"DROP TABLE IF EXISTS {full_name}")
        conn.execute(f"CREATE TABLE {full_name} ({', '.join(col_defs)})")

        placeholders = ", ".join(["?" for _ in keys])
        data = [[r.get(k) for k in keys] for r in rows]
        conn.executemany(f"INSERT INTO {full_name} VALUES ({placeholders})", data)

        row_counts[table_name] = len(rows)
        print(f"  Loaded {len(rows):>6,} rows -> {full_name}")

    # FX rates from live market feed
    fx_rows = write_fx_rates_to_duckdb(conn)
    row_counts["stg_fx_rates"] = fx_rows
    print(f"  Loaded {fx_rows:>6,} rows -> stg_fx_rates (from market_data.py)")

    conn.close()
    return row_counts


# ── Main orchestrator ─────────────────────────────────────────────────────────

def generate(n_counterparties: int = 500, seed: int = SEED) -> dict[str, list[dict]]:
    """Generate all synthetic tables. Returns {qualified_table_name: [row_dicts]}."""
    rng = _rng(seed)
    print(f"\n[DATA GENERATOR] Generating {n_counterparties} synthetic counterparties (seed={seed})")
    print("  GOVERNANCE: SYNTHETIC data only. Zero PII. No real names/accounts/cards.")

    # Step 1: Master counterparty spine (every other table FKs to this)
    counterparties = gen_goldensourcefdo_counterparty(n_counterparties, rng)
    cpty_ids = [r["counterparty_id"] for r in counterparties]
    print(f"  Generated {len(counterparties)} counterparties (CPTY_000001 .. CPTY_{n_counterparties:06d})")

    tables: dict[str, list[dict]] = {}

    # Step 2: Active pipeline source systems (match existing sql/10..40 schema exactly)
    tables["goldensourcefdo.raw_counterparty"]      = counterparties
    tables["creditmart.raw_credit_exposures"]       = gen_creditmart_exposures(cpty_ids, rng)
    tables["marketriskhub.raw_market_positions"]    = gen_marketriskhub_positions(cpty_ids, rng)

    # Step 3: New catalog source systems (for sql_extended/ and gap analysis)
    tables["core_banking.raw_accounts"]             = gen_core_banking_accounts(cpty_ids, rng)
    tables["core_banking.raw_daily_txns"]           = gen_core_banking_transactions(cpty_ids, rng)
    tables["credit_card.raw_card_accounts"]         = gen_credit_card(cpty_ids, rng)
    tables["loans.raw_loan_accounts"]               = gen_loans(cpty_ids, rng)
    tables["atm_channel.raw_atm_events"]            = gen_atm_channel(cpty_ids, rng)
    tables["mobile_banking.raw_mobile_sessions"]    = gen_mobile_banking(cpty_ids, rng)
    tables["retail_banking.raw_product_holdings"]   = gen_retail_banking(cpty_ids, rng)
    tables["consumer_banking.raw_consumer_profile"] = gen_consumer_banking(cpty_ids, rng)
    tables["commercial_banking.raw_commercial_facilities"] = gen_commercial_banking(cpty_ids, rng)
    tables["campaign_mgmt.raw_campaign_events"]     = gen_campaign_mgmt(cpty_ids, rng)
    tables["social_sentiment.raw_sentiment_scores"] = gen_social_sentiment(cpty_ids, rng)

    return tables


def main():
    parser = argparse.ArgumentParser(description="Synthetic banking data generator (zero PII)")
    parser.add_argument("--rows", type=int, default=500,
                        help="Number of counterparties to generate (default: 500)")
    parser.add_argument("--seed", type=int, default=SEED,
                        help=f"Random seed for determinism (default: {SEED})")
    parser.add_argument("--db", type=str, default=str(config.DATA_DIR / "warehouse.duckdb"),
                        help="DuckDB output path")
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    tables = generate(n_counterparties=args.rows, seed=args.seed)

    db_path = Path(args.db)
    print(f"\n[DuckDB] Writing to {db_path} ...")
    row_counts = load_to_duckdb(tables, db_path)

    total_rows = sum(row_counts.values())
    print(f"\n[SUMMARY] {len(row_counts)} tables, {total_rows:,} total rows loaded.")
    print(f"  DuckDB: {db_path}")
    print("\n  Table row counts:")
    for tbl, cnt in sorted(row_counts.items()):
        print(f"    {tbl:<50} {cnt:>8,} rows")

    print("\n[DONE] Data generation complete. DuckDB is ready for BA inspection.")
    print("       data/ is gitignored — regenerate anytime with: python generate_data.py")


if __name__ == "__main__":
    main()
