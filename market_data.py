"""Live market-data ingestion for "Find My Data Path".

Sources REAL public market/reference data — the kind a bank legitimately ingests
from external vendors (Bloomberg/Reuters in production; here: free public endpoints).

CRITICAL boundary (keeps the project's data-governance principle intact):
  - REAL data here is PUBLIC MARKET DATA ONLY — FX rates, yields, indices, vol.
    No PII, no customer data. This data flows INTO the bank from vendors.
  - Customer / counterparty data stays SYNTHETIC (generate_*.py). Never sourced live.
  - The lineage engine still reads SQL TEXT only. This module populates the DuckDB
    warehouse with rows a BA can inspect per hop — the LLM never sees these rows.

"Not stale" enforcement:
  - Every data point carries `market_time` (when the market last traded) and
    `fetched_at` (when we pulled it). A freshness TTL forces a refetch.
  - Live fetch failure falls back to cache but loudly flags the data as STALE.

No third-party dependency — uses urllib so it runs anywhere (incl. HF Spaces).
"""
from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import config

# ── Freshness policy ──────────────────────────────────────────────────────────
TTL_SECONDS = 3600                       # refetch if cached data older than 1 hour
CACHE_FILE  = config.ROOT / ".market_cache.json"
_UA         = {"User-Agent": "Mozilla/5.0 (river_fish learning project)"}
_YH_CHART   = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"


# ── The curated banking-relevant basket ──────────────────────────────────────
# Each maps to a real input of a credit/market-risk pipeline.
BASKET: dict[str, dict[str, str]] = {
    # FX — feeds the `currency` columns (convert exposure_amount to a base ccy)
    "EURINR=X": {"label": "EUR/INR spot",          "category": "fx",     "source": "Yahoo Finance"},
    "USDINR=X": {"label": "USD/INR spot",          "category": "fx",     "source": "Yahoo Finance"},
    "GBPINR=X": {"label": "GBP/INR spot",          "category": "fx",     "source": "Yahoo Finance"},
    "EURUSD=X": {"label": "EUR/USD spot",          "category": "fx",     "source": "Yahoo Finance"},
    # Yields — risk-free rate for the capital / discounting calc
    "^TNX":     {"label": "US 10Y Treasury yield", "category": "rate",   "source": "Yahoo Finance (CBOE)"},
    "^IRX":     {"label": "US 13wk T-Bill yield",  "category": "rate",   "source": "Yahoo Finance (CBOE)"},
    # Stress / credit proxies — market-risk stress indicators
    "^VIX":     {"label": "CBOE Volatility Index", "category": "stress", "source": "Yahoo Finance (CBOE)"},
    # Equity index — market_value benchmarking
    "^NSEI":    {"label": "NIFTY 50 index",        "category": "equity", "source": "Yahoo Finance (NSE)"},
    "^GSPC":    {"label": "S&P 500 index",         "category": "equity", "source": "Yahoo Finance"},
}


@dataclass
class MarketDataPoint:
    symbol:       str
    label:        str
    category:     str
    value:        Optional[float]
    currency:     Optional[str]
    market_time:  Optional[str]   # ISO — when the market last traded (true "as of")
    fetched_at:   str             # ISO — when we pulled it
    source:       str
    is_stale:     bool            # True = cache fallback / older than TTL
    note:         str = ""

    def display(self) -> str:
        flag = "  ⚠ STALE" if self.is_stale else ""
        val = f"{self.value:,.4f}" if self.value is not None else "n/a"
        ccy = f" {self.currency}" if self.currency else ""
        return f"  {self.label:<28} {val}{ccy}   (as of {self.market_time}){flag}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _fetch_one(symbol: str, meta: dict[str, str]) -> Optional[MarketDataPoint]:
    """Fetch a single live quote from Yahoo's JSON chart endpoint. None on failure."""
    url = _YH_CHART.format(symbol=urllib.parse.quote(symbol))
    try:
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
        m = data["chart"]["result"][0]["meta"]
        mkt_epoch = m.get("regularMarketTime")
        mkt_time = (datetime.fromtimestamp(mkt_epoch, tz=timezone.utc).isoformat(timespec="seconds")
                    if mkt_epoch else None)
        return MarketDataPoint(
            symbol=symbol,
            label=meta["label"],
            category=meta["category"],
            value=m.get("regularMarketPrice"),
            currency=m.get("currency"),
            market_time=mkt_time,
            fetched_at=_now_iso(),
            source=meta["source"],
            is_stale=False,
        )
    except (urllib.error.URLError, KeyError, IndexError, TimeoutError, ValueError) as exc:
        return None


def _load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_cache(points: list[MarketDataPoint]) -> None:
    payload = {"saved_at": _now_iso(), "points": [asdict(p) for p in points]}
    CACHE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _cache_is_fresh(cache: dict) -> bool:
    saved = cache.get("saved_at")
    if not saved:
        return False
    try:
        saved_dt = datetime.fromisoformat(saved)
        age = (datetime.now(timezone.utc) - saved_dt).total_seconds()
        return age < TTL_SECONDS
    except Exception:
        return False


def fetch_market_snapshot(force: bool = False) -> list[MarketDataPoint]:
    """Return the banking basket as live market data points.

    - If cache is fresh (< TTL) and not forced, return cache (no network call).
    - Else fetch live; on per-symbol failure, fall back to that symbol's cached
      value flagged STALE; if no cache, return value=None flagged STALE.
    """
    cache = _load_cache()
    cached_by_symbol = {p["symbol"]: p for p in cache.get("points", [])}

    if not force and _cache_is_fresh(cache):
        pts = [MarketDataPoint(**p) for p in cache["points"]]
        return pts

    points: list[MarketDataPoint] = []
    for symbol, meta in BASKET.items():
        live = _fetch_one(symbol, meta)
        if live is not None:
            points.append(live)
        elif symbol in cached_by_symbol:
            stale = MarketDataPoint(**cached_by_symbol[symbol])
            stale.is_stale = True
            stale.note = "live fetch failed — showing last cached value"
            points.append(stale)
        else:
            points.append(MarketDataPoint(
                symbol=symbol, label=meta["label"], category=meta["category"],
                value=None, currency=None, market_time=None, fetched_at=_now_iso(),
                source=meta["source"], is_stale=True,
                note="live fetch failed and no cache available",
            ))

    # Only refresh cache if at least one live point succeeded
    if any(not p.is_stale for p in points):
        _save_cache([p for p in points if not p.is_stale]
                    + [p for p in points if p.is_stale and p.value is not None])
    return points


def snapshot_summary(points: list[MarketDataPoint]) -> str:
    fresh = sum(1 for p in points if not p.is_stale and p.value is not None)
    stale = sum(1 for p in points if p.is_stale)
    return (f"Market snapshot: {fresh} live / {len(points)} symbols"
            + (f"  ({stale} STALE — using cache)" if stale else "  (all fresh)"))


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("Fetching live market data (public reference data — no PII) ...\n")
    pts = fetch_market_snapshot(force="--force" in sys.argv)

    print(snapshot_summary(pts))
    print()
    by_cat: dict[str, list[MarketDataPoint]] = {}
    for p in pts:
        by_cat.setdefault(p.category, []).append(p)

    cat_titles = {"fx": "FX rates (feeds `currency` columns)",
                  "rate": "Yields (risk-free rate input)",
                  "stress": "Stress / credit proxies",
                  "equity": "Equity indices (market_value benchmark)"}
    for cat, title in cat_titles.items():
        if cat in by_cat:
            print(f"{title}:")
            for p in by_cat[cat]:
                print(p.display())
            print()

    print("=" * 64)
    print("  GOVERNANCE: public market data only — no customer/PII data.")
    print("  Customer & counterparty data remains SYNTHETIC (generate_*.py).")
    print("  Lineage engine reads SQL text only; these rows live in DuckDB for")
    print("  per-hop BA inspection — they never enter an LLM prompt.")
    print("=" * 64)
