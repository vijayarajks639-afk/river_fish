-- Mart layer: multiple "C + XYZ = D" derivations + a CASE that depends on a derived expression.

CREATE TABLE mart_risk_summary AS
SELECT
    e.counterparty_id,
    e.counterparty_name,
    e.legal_entity,
    e.expected_loss,
    e.stressed_expected_loss,
    m.var_1d,
    -- base regulatory capital charge: D = (C + X) * Y   (multi-hop, multi-source)
    (e.expected_loss + m.var_1d) * 1.06 AS risk_weighted_amount,
    -- stressed variant: reuses the stressed EL tributary
    (e.stressed_expected_loss + m.var_1d) * 1.06 AS stressed_rwa,
    -- CASE on a DERIVED expression -> regulatory bucket
    CASE WHEN (e.expected_loss + m.var_1d) * 1.06 > 1000000 THEN 'High'
         WHEN (e.expected_loss + m.var_1d) * 1.06 > 250000 THEN 'Medium'
         ELSE 'Low' END AS regulatory_bucket
FROM int_exposure e
JOIN stg_market m
    ON e.counterparty_id = m.counterparty_id;
