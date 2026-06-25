-- ============================================================
-- sql_extended/50_fx_exposure_staging.sql
-- FX EXPOSURE STAGING — REAL MARKET FEED x SYNTHETIC EXPOSURE
-- ============================================================
--
-- PURPOSE:  Demonstrates lineage from a REAL market data feed
--           into a synthetic risk number. This is the key
--           data-governance showcase:
--
--             [synthetic] creditmart.raw_credit_exposures.currency
--                         (JOIN KEY — no real FX value stored here)
--               +
--             [REAL LIVE] stg_fx_rates.spot_rate
--                         (sourced from market_data.py → Yahoo Finance)
--               =
--             [derived]   stg_fx_exposure_inr.exposure_inr
--                         (exposure converted to INR base currency)
--
-- LINEAGE PATH:
--   creditmart.raw_credit_exposures.exposure_amount
--     → stg_fx_exposure_inr.exposure_inr          (via FX conversion)
--   stg_fx_rates.spot_rate (from market_data.py)
--     → stg_fx_exposure_inr.exposure_inr          (the rate used)
--
-- GOVERNANCE NOTE:
--   - creditmart side is SYNTHETIC (generate_data.py — zero PII)
--   - stg_fx_rates side is REAL PUBLIC MARKET DATA (market_data.py)
--   - No customer data touches the FX rate table (join is on currency code only)
-- ============================================================

-- Stage the FX-converted exposure for each counterparty.
-- Columns NOT selected here are gap candidates visible in gap_analysis:
--   creditmart: equity_ticker, tenor, stress_scenario, origination_date, facility_type
--   goldensourcefdo: incorporation_date, sic_code, group_parent_id
CREATE TABLE stg_fx_exposure_inr AS
SELECT
    ce.counterparty_id,
    ce.exposure_amount,
    ce.currency                                AS exposure_currency,
    -- JOIN to REAL market feed: spot_rate comes from stg_fx_rates (sourced via market_data.py)
    COALESCE(fx.spot_rate, 1.0)               AS fx_rate_to_inr,
    ce.exposure_amount * COALESCE(fx.spot_rate, 1.0)
                                               AS exposure_inr,
    fx.market_time                             AS rate_as_of,
    fx.is_stale                                AS rate_is_stale
FROM creditmart.raw_credit_exposures ce
LEFT JOIN stg_fx_rates fx
    ON  ce.currency    = fx.base_currency
    AND fx.quote_currency = 'INR';

-- ============================================================
-- Portfolio-level FX exposure summary
-- Shows total INR-equivalent exposure by currency — this
-- is the kind of table a treasury or credit-risk team uses
-- to monitor currency concentration.
-- ============================================================
CREATE TABLE mart_fx_exposure_summary AS
SELECT
    stg.exposure_currency,
    COUNT(DISTINCT stg.counterparty_id)        AS counterparty_count,
    SUM(stg.exposure_amount)                   AS total_local_exposure,
    MAX(stg.fx_rate_to_inr)                    AS fx_rate_used,
    SUM(stg.exposure_inr)                      AS total_exposure_inr,
    MAX(stg.rate_as_of)                        AS rate_as_of,
    BOOL_OR(stg.rate_is_stale)                 AS any_rate_stale
FROM stg_fx_exposure_inr stg
GROUP BY stg.exposure_currency;
