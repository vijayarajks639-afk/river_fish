-- ============================================================
-- sql_extended/70_product_holdings_mart.sql
-- PRODUCT HOLDINGS + CREDIT PORTFOLIO MART
-- ============================================================
--
-- PURPOSE: Integrates credit card, loans, retail banking, and
--          consumer profile data into a product-holdings view.
--          Typical use: 360-degree customer product view for
--          cross-sell / relationship deepening.
--
-- SOURCE SYSTEMS (all synthetic):
--   credit_card.raw_card_accounts
--   loans.raw_loan_accounts
--   retail_banking.raw_product_holdings
--   consumer_banking.raw_consumer_profile
--   goldensourcefdo.raw_counterparty
--
-- COLUMNS DELIBERATELY NOT CONSUMED (gap candidates):
--   credit_card:   cashback_earned_ytd, emi_converted_amount, insurance_flag
--   loans:         bureau_score_at_origination, co_applicant_flag, insurance_linked
--   retail_banking: auto_renewal_flag, nominee_flag, branch_code
--   consumer_banking: churn_score, cross_sell_score, kyc_status
-- ============================================================

-- Credit card staging: one row per counterparty (worst delinquency bucket)
CREATE TABLE stg_card_summary AS
SELECT
    counterparty_id,
    COUNT(*)                                    AS card_count,
    SUM(credit_limit)                           AS total_credit_limit,
    SUM(outstanding_balance)                    AS total_card_outstanding,
    AVG(utilization_ratio)                      AS avg_utilization_ratio,
    -- worst delinquency drives the risk view
    MAX(CASE delinquency_bucket
        WHEN 'WRITE_OFF' THEN 5
        WHEN '90_DPD'    THEN 4
        WHEN '60_DPD'    THEN 3
        WHEN '30_DPD'    THEN 2
        WHEN 'CURRENT'   THEN 1
        ELSE 0 END)                             AS worst_delinquency_rank
    -- reward_points, cashback intentionally not forwarded (gap candidates)
FROM credit_card.raw_card_accounts
GROUP BY counterparty_id;

-- Loans staging: active loan exposure per counterparty
CREATE TABLE stg_loan_summary AS
SELECT
    counterparty_id,
    COUNT(*)                                    AS loan_count,
    SUM(outstanding_principal)                  AS total_loan_outstanding,
    SUM(CASE WHEN loan_status = 'NPA' THEN outstanding_principal ELSE 0 END)
                                                AS npa_outstanding,
    AVG(interest_rate)                          AS avg_loan_interest_rate,
    MAX(CASE emi_status
        WHEN 'OVER_90_DPD' THEN 5
        WHEN '90_DPD'      THEN 4
        WHEN '60_DPD'      THEN 3
        WHEN '30_DPD'      THEN 2
        WHEN 'CURRENT'     THEN 1
        ELSE 0 END)                             AS worst_emi_status_rank
    -- bureau_score_at_origination NOT forwarded (gap candidate: risk use-case pending)
FROM loans.raw_loan_accounts
GROUP BY counterparty_id;

-- Retail banking: total deposit base per counterparty
CREATE TABLE stg_retail_holdings AS
SELECT
    counterparty_id,
    COUNT(*)                                    AS product_count,
    SUM(balance)                                AS total_deposit_balance,
    SUM(CASE WHEN product_type IN ('FIXED_DEPOSIT', 'RECURRING_DEPOSIT')
             THEN balance ELSE 0 END)           AS term_deposit_balance
    -- interest_rate, auto_renewal_flag NOT forwarded (gap candidates)
FROM retail_banking.raw_product_holdings
GROUP BY counterparty_id;

-- Full product holdings mart
CREATE TABLE mart_product_holdings AS
SELECT
    cp.counterparty_id,
    cp.counterparty_name,
    cp.legal_entity,
    cp.country,
    -- Consumer profile
    cb.segment,
    cb.nrv,
    cb.vintage_months,
    cb.primary_channel,
    -- Credit card
    COALESCE(cd.card_count, 0)                 AS card_count,
    COALESCE(cd.total_credit_limit, 0)         AS total_credit_limit,
    COALESCE(cd.total_card_outstanding, 0)     AS card_outstanding,
    COALESCE(cd.avg_utilization_ratio, 0)      AS avg_card_utilization,
    COALESCE(cd.worst_delinquency_rank, 0)     AS worst_card_delinquency,
    -- Loans
    COALESCE(ln.loan_count, 0)                 AS loan_count,
    COALESCE(ln.total_loan_outstanding, 0)     AS loan_outstanding,
    COALESCE(ln.npa_outstanding, 0)            AS npa_outstanding,
    COALESCE(ln.worst_emi_status_rank, 0)      AS worst_emi_status,
    -- Retail deposits
    COALESCE(rb.total_deposit_balance, 0)      AS total_deposit_balance,
    COALESCE(rb.term_deposit_balance, 0)       AS term_deposit_balance,
    -- Derived: total liabilities-to-assets ratio (simple heuristic)
    CASE WHEN COALESCE(rb.total_deposit_balance, 0) > 0
         THEN (COALESCE(ln.total_loan_outstanding, 0)
               + COALESCE(cd.total_card_outstanding, 0))
              / COALESCE(rb.total_deposit_balance, 0)
         ELSE NULL END                          AS liabilities_to_deposits_ratio
FROM goldensourcefdo.raw_counterparty cp
LEFT JOIN consumer_banking.raw_consumer_profile cb ON cp.counterparty_id = cb.counterparty_id
LEFT JOIN stg_card_summary  cd  ON cp.counterparty_id = cd.counterparty_id
LEFT JOIN stg_loan_summary  ln  ON cp.counterparty_id = ln.counterparty_id
LEFT JOIN stg_retail_holdings rb ON cp.counterparty_id = rb.counterparty_id;
