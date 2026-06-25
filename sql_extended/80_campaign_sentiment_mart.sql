-- ============================================================
-- sql_extended/80_campaign_sentiment_mart.sql
-- CAMPAIGN + COMMERCIAL + SENTIMENT MART
-- ============================================================
--
-- PURPOSE: Campaign attribution, commercial banking exposure,
--          and synthetic sentiment scoring — three systems
--          that rarely appear in textbook lineage demos but
--          are common in enterprise banking platforms.
--
-- SOURCE SYSTEMS (all synthetic):
--   campaign_mgmt.raw_campaign_events
--   commercial_banking.raw_commercial_facilities
--   social_sentiment.raw_sentiment_scores
--   goldensourcefdo.raw_counterparty
--
-- GAP CANDIDATES (deliberately not consumed):
--   campaign_mgmt:        channel_cost, propensity_score, segment_targeted
--   commercial_banking:   collateral_value, deal_team_id, covenant_breach_flag
--   social_sentiment:     news_score, analyst_mention_flag
--   goldensourcefdo:      incorporation_date, sic_code, group_parent_id
-- ============================================================

-- Campaign response summary per counterparty
CREATE TABLE stg_campaign_summary AS
SELECT
    counterparty_id,
    COUNT(*)                                    AS total_campaigns_targeted,
    SUM(CASE WHEN response = 'ACCEPTED' THEN 1 ELSE 0 END)
                                                AS campaigns_accepted,
    SUM(CASE WHEN response = 'REJECTED' THEN 1 ELSE 0 END)
                                                AS campaigns_rejected,
    ROUND(
        SUM(CASE WHEN response = 'ACCEPTED' THEN 1 ELSE 0 END) * 1.0
        / NULLIF(COUNT(*), 0)
    , 4)                                        AS acceptance_rate,
    MAX(campaign_date)                          AS last_campaign_date
    -- offer_amount, channel_cost, propensity_score NOT forwarded (gap candidates)
FROM campaign_mgmt.raw_campaign_events
GROUP BY counterparty_id;

-- Commercial facilities summary (only ~20% of counterparties have these)
CREATE TABLE stg_commercial_summary AS
SELECT
    counterparty_id,
    COUNT(*)                                    AS facility_count,
    SUM(sanctioned_limit)                       AS total_sanctioned_limit,
    SUM(utilised_amount)                        AS total_utilised,
    ROUND(SUM(utilised_amount) / NULLIF(SUM(sanctioned_limit), 0), 4)
                                                AS utilisation_ratio,
    AVG(interest_rate)                          AS avg_facility_rate,
    -- sector is forwarded for concentration analysis
    MAX(sector)                                 AS primary_sector
    -- collateral_value, deal_team_id, covenant_breach_flag NOT forwarded (gap candidates)
FROM commercial_banking.raw_commercial_facilities
GROUP BY counterparty_id;

-- Campaign + sentiment + commercial combined mart
CREATE TABLE mart_engagement_risk AS
SELECT
    cp.counterparty_id,
    cp.counterparty_name,
    cp.legal_entity,
    -- Campaign effectiveness
    COALESCE(camp.total_campaigns_targeted, 0) AS campaigns_targeted,
    COALESCE(camp.campaigns_accepted, 0)        AS campaigns_accepted,
    COALESCE(camp.acceptance_rate, 0)           AS campaign_acceptance_rate,
    -- Synthetic sentiment signal (score 0=negative, 1=positive)
    sent.sentiment_score,
    sent.sentiment_label,
    sent.signal_volume,
    -- Commercial exposure (nullable — only corporate counterparties)
    comm.facility_count,
    comm.total_sanctioned_limit,
    comm.total_utilised,
    comm.utilisation_ratio                      AS commercial_utilisation_ratio,
    comm.primary_sector,
    -- Derived: engagement quality index
    --   Combines campaign acceptance and sentiment — a simple heuristic
    --   showing how lineage can span campaign + sentiment + reference systems
    ROUND(
        COALESCE(camp.acceptance_rate, 0.5) * 0.6
        + COALESCE(sent.sentiment_score, 0.5)  * 0.4
    , 4)                                        AS engagement_quality_index
FROM goldensourcefdo.raw_counterparty cp
LEFT JOIN stg_campaign_summary    camp ON cp.counterparty_id = camp.counterparty_id
LEFT JOIN social_sentiment.raw_sentiment_scores sent ON cp.counterparty_id = sent.counterparty_id
LEFT JOIN stg_commercial_summary  comm ON cp.counterparty_id = comm.counterparty_id;
