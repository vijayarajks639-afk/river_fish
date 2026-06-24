-- Staging layer: thin extracts from each SOURCE SYSTEM (one model per source).
-- Explicit column lists on purpose: "SELECT *" would break column-level lineage (a key lesson).

CREATE TABLE stg_credit AS
SELECT
    counterparty_id,
    exposure_amount,
    pd,
    lgd,
    internal_rating,
    currency
FROM creditmart.raw_credit_exposures;

CREATE TABLE stg_market AS
SELECT
    counterparty_id,
    market_value,
    var_1d,
    currency
FROM marketriskhub.raw_market_positions;

CREATE TABLE ref_counterparty AS
SELECT
    counterparty_id,
    counterparty_name,
    legal_entity,
    country
FROM goldensourcefdo.raw_counterparty;
