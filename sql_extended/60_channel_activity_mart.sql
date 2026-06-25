-- ============================================================
-- sql_extended/60_channel_activity_mart.sql
-- MULTI-CHANNEL ACTIVITY STAGING + MART
-- ============================================================
--
-- PURPOSE: Brings ATM, Mobile Banking, and Core Banking
--          transaction data into a unified channel-activity view.
--          Demonstrates multi-source lineage across 3 new systems.
--
-- SOURCE SYSTEMS (all synthetic):
--   atm_channel.raw_atm_events
--   mobile_banking.raw_mobile_sessions
--   core_banking.raw_daily_txns
--
-- COLUMNS DELIBERATELY NOT CONSUMED (gap candidates for gap_analysis):
--   atm_channel:     failure_code, card_type_used, bank_code
--   mobile_banking:  login_method, push_notif_clicked, device_id_hash
--   core_banking:    merchant_code, narration
-- ============================================================

-- Stage ATM activity per counterparty (aggregate daily)
CREATE TABLE stg_atm_activity AS
SELECT
    counterparty_id,
    COUNT(*)                                    AS atm_txn_count,
    SUM(CASE WHEN txn_type = 'WITHDRAWAL' THEN amount ELSE 0 END)
                                                AS total_withdrawal_amount,
    MAX(txn_datetime)                           AS last_atm_txn_datetime,
    -- NOTE: atm_id, atm_location_code intentionally NOT forwarded to mart
    --       (gap candidates — useful for geo-risk but not yet wired up)
    COUNT(DISTINCT atm_id)                      AS distinct_atms_used
FROM atm_channel.raw_atm_events
GROUP BY counterparty_id;

-- Stage mobile session activity per counterparty
CREATE TABLE stg_mobile_activity AS
SELECT
    counterparty_id,
    COUNT(*)                                    AS session_count,
    SUM(CASE WHEN txn_type != 'BALANCE_ENQUIRY' THEN amount ELSE 0 END)
                                                AS total_mobile_txn_amount,
    AVG(session_duration_sec)                   AS avg_session_duration_sec,
    MAX(session_date)                           AS last_session_date,
    -- app_version intentionally not forwarded (gap candidate)
    COUNT(DISTINCT os_type)                     AS distinct_os_types
FROM mobile_banking.raw_mobile_sessions
GROUP BY counterparty_id;

-- Stage core banking transaction volume
CREATE TABLE stg_core_txn_activity AS
SELECT
    counterparty_id,
    COUNT(*)                                    AS txn_count,
    SUM(CASE WHEN txn_type = 'CREDIT' THEN amount ELSE 0 END)
                                                AS total_credit_amount,
    SUM(CASE WHEN txn_type = 'DEBIT' THEN amount ELSE 0 END)
                                                AS total_debit_amount,
    MAX(txn_date)                               AS last_txn_date
    -- channel, merchant_code intentionally not forwarded to mart (gap candidates)
FROM core_banking.raw_daily_txns
GROUP BY counterparty_id;

-- Unified channel activity mart
CREATE TABLE mart_channel_activity AS
SELECT
    cp.counterparty_id,
    cp.counterparty_name,
    cp.country,
    -- ATM dimension
    COALESCE(atm.atm_txn_count, 0)             AS atm_txn_count,
    COALESCE(atm.total_withdrawal_amount, 0)   AS atm_withdrawal_amount,
    -- Mobile dimension
    COALESCE(mob.session_count, 0)             AS mobile_session_count,
    COALESCE(mob.total_mobile_txn_amount, 0)   AS mobile_txn_amount,
    -- Core banking dimension
    COALESCE(core.txn_count, 0)                AS core_txn_count,
    COALESCE(core.total_credit_amount, 0)      AS core_credit_amount,
    COALESCE(core.total_debit_amount, 0)       AS core_debit_amount,
    -- Derived: total channel engagement score (simple sum of transaction counts)
    COALESCE(atm.atm_txn_count, 0)
        + COALESCE(mob.session_count, 0)
        + COALESCE(core.txn_count, 0)          AS total_channel_events
FROM goldensourcefdo.raw_counterparty cp
LEFT JOIN stg_atm_activity   atm  ON cp.counterparty_id = atm.counterparty_id
LEFT JOIN stg_mobile_activity mob  ON cp.counterparty_id = mob.counterparty_id
LEFT JOIN stg_core_txn_activity core ON cp.counterparty_id = core.counterparty_id;
