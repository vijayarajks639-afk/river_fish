-- Integration layer: join credit + counterparty reference, and derive several columns of
-- INCREASING complexity (this is closer to a real pipeline than one clean formula).

CREATE TABLE int_exposure AS
SELECT
    c.counterparty_id,
    r.counterparty_name,
    r.legal_entity,
    r.country,
    c.exposure_amount,
    c.pd,
    c.lgd,
    c.internal_rating,
    -- (1) simple arithmetic derivation: EL = PD x LGD x EAD
    c.pd * c.lgd * c.exposure_amount AS expected_loss,
    -- (2) CASE business rule: stress the LGD for sub-investment-grade ratings
    CASE WHEN c.internal_rating IN ('CCC', 'CC', 'C', 'D') THEN c.lgd * 1.25
         ELSE c.lgd END AS stressed_lgd,
    -- (3) nested CASE x arithmetic: stressed EL depends on pd, lgd, internal_rating AND exposure_amount
    c.pd
        * (CASE WHEN c.internal_rating IN ('CCC', 'CC', 'C', 'D') THEN c.lgd * 1.25
                ELSE c.lgd END)
        * c.exposure_amount AS stressed_expected_loss,
    c.currency
FROM stg_credit c
JOIN ref_counterparty r
    ON c.counterparty_id = r.counterparty_id;
