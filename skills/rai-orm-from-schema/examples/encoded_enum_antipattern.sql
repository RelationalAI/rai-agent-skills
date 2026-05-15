-- examples/encoded_enum_antipattern.sql
-- Demonstrates Step 5 (sample probing) and Step 7 (antipattern detection) for the
-- encoded-enum-in-VARCHAR antipattern. The schema declares STATUS / TIER as plain
-- VARCHAR, with no CHECK constraint to constrain values. The SRP must:
--   1. Probe sample data (Step 5) to discover the small set of distinct values.
--   2. Flag the columns as encoded-enum-in-varchar antipatterns (Step 7).
--   3. Propose value enumeration constraints (status: confirmed via sample saturation).
--   4. Translate to model.Enum (mechanical tier) at Step 10.
--
-- Sample data is included at the bottom so live-SQL probing has rows to scan.

CREATE TABLE CUSTOMER (
    CUSTOMER_ID  INTEGER       PRIMARY KEY,
    NAME         VARCHAR(200)  NOT NULL,
    TIER         VARCHAR(20)   NOT NULL          -- encoded enum, no CHECK
);

CREATE TABLE ORDERS (
    ORDER_ID     INTEGER       PRIMARY KEY,
    CUSTOMER_ID  INTEGER       NOT NULL REFERENCES CUSTOMER(CUSTOMER_ID),
    STATUS       VARCHAR(20)   NOT NULL          -- encoded enum, no CHECK
);

-- Sample inserts so Step 5 probes find a saturated set of distinct values.
INSERT INTO CUSTOMER (CUSTOMER_ID, NAME, TIER) VALUES
  (1, 'Alice',    'GOLD'),
  (2, 'Bob',      'SILVER'),
  (3, 'Cora',     'BRONZE'),
  (4, 'Diane',    'GOLD'),
  (5, 'Esteban',  'SILVER'),
  (6, 'Farah',    'BRONZE'),
  (7, 'Grace',    'GOLD'),
  (8, 'Hugo',     'SILVER');

INSERT INTO ORDERS (ORDER_ID, CUSTOMER_ID, STATUS) VALUES
  ( 1, 1, 'PENDING'),
  ( 2, 1, 'PAID'),
  ( 3, 2, 'SHIPPED'),
  ( 4, 3, 'DELIVERED'),
  ( 5, 4, 'CANCELLED'),
  ( 6, 5, 'PAID'),
  ( 7, 6, 'PENDING'),
  ( 8, 7, 'SHIPPED'),
  ( 9, 8, 'DELIVERED'),
  (10, 1, 'PAID');
