-- Portfolio mart: AGGREGATION lineage (SUM / AVG / COUNT, GROUP BY) — a different shape of derivation.
-- Each aggregate column traces back to the column it aggregates, through int_exposure to source.

CREATE TABLE mart_portfolio_concentration AS
SELECT
    legal_entity,
    COUNT(DISTINCT counterparty_id) AS counterparty_count,
    SUM(exposure_amount)            AS total_exposure,
    SUM(expected_loss)              AS total_expected_loss,
    AVG(pd)                         AS avg_pd
FROM int_exposure
GROUP BY legal_entity;
