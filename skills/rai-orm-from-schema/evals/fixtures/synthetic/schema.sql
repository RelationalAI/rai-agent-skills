-- Synthetic representative schema — e-commerce + fulfilment domain.
-- Built per notes/phase1-synthetic-schema-spec.md. 21 tables with deliberately
-- placed antipatterns and constraint-inference targets.
--
-- Antipatterns planted (see notes/phase1-synthetic-schema-spec.md table for the
-- per-antipattern rationale and the SRP's expected resolution):
--   - Denormalized address    : CUSTOMER + WAREHOUSE
--   - Encoded enum in VARCHAR : ORDERS.STATUS, SHIPMENT_EVENT.EVENT_TYPE,
--                               RETURN_REQUEST.REASON, PAYMENT.METHOD,
--                               CUSTOMER.TIER, PRODUCT.TYPE
--   - Ambiguous junction      : ORDER_ITEM_TAG (no extras) + ORDER_PROMOTION (with applied_at)
--   - TYPE-column subtype     : PRODUCT.TYPE + 3 *_PRODUCT_DETAILS tables
--
-- Constraint-inference targets:
--   - Common-sense ring (acyclic) : PRODUCT_CATEGORY.parent_category_id self-FK
--   - Common-sense ring (irreflexive) : INVENTORY_TRANSFER from/to_warehouse
--   - Common-sense temporal       : ORDERS placed_at <= shipped_at <= delivered_at
--   - LLM-inferred subset         : RETURN_REQUEST → ORDERS with STATUS='DELIVERED'
--
-- Explicit constraints declared in DDL (per spec):
--   - PKs on every table
--   - FKs on relationship columns
--   - NOT NULL on most columns
--   - UNIQUE on WAREHOUSE.code and PROMOTION_CODE.code (composite key for the latter — see PK)
-- CHECKs are deliberately omitted on the encoded-enum columns so Step 5 sample
-- probing has work to do. Numeric ranges (quantity, discount, etc.) likewise
-- ride on sample probing rather than DDL-declared CHECKs.

-- ============================================================================
-- DDL
-- ============================================================================

CREATE TABLE PRODUCT_CATEGORY (
    CATEGORY_ID         INTEGER PRIMARY KEY,
    NAME                VARCHAR(100) NOT NULL,
    PARENT_CATEGORY_ID  INTEGER REFERENCES PRODUCT_CATEGORY(CATEGORY_ID)
);

CREATE TABLE PRODUCT (
    PRODUCT_ID    INTEGER       PRIMARY KEY,
    SKU           VARCHAR(50)   NOT NULL,
    NAME          VARCHAR(200)  NOT NULL,
    UNIT_PRICE    DECIMAL(10,2) NOT NULL,
    TYPE          VARCHAR(20)   NOT NULL,                         -- encoded enum + TYPE-column subtype antipattern
    CATEGORY_ID   INTEGER       REFERENCES PRODUCT_CATEGORY(CATEGORY_ID)
);

CREATE TABLE PHYSICAL_PRODUCT_DETAILS (
    PRODUCT_ID    INTEGER       PRIMARY KEY REFERENCES PRODUCT(PRODUCT_ID),
    WEIGHT_KG     DECIMAL(8,3)  NOT NULL,
    LENGTH_CM     DECIMAL(8,2)  NOT NULL,
    WIDTH_CM      DECIMAL(8,2)  NOT NULL,
    HEIGHT_CM     DECIMAL(8,2)  NOT NULL
);

CREATE TABLE DIGITAL_PRODUCT_DETAILS (
    PRODUCT_ID     INTEGER       PRIMARY KEY REFERENCES PRODUCT(PRODUCT_ID),
    DOWNLOAD_URL   VARCHAR(500)  NOT NULL,
    FILE_SIZE_MB   DECIMAL(10,2) NOT NULL
);

CREATE TABLE SUBSCRIPTION_PRODUCT_DETAILS (
    PRODUCT_ID          INTEGER PRIMARY KEY REFERENCES PRODUCT(PRODUCT_ID),
    PERIOD_DAYS         INTEGER NOT NULL,
    AUTO_RENEW_DEFAULT  BOOLEAN NOT NULL
);

CREATE TABLE CUSTOMER (
    CUSTOMER_ID     INTEGER       PRIMARY KEY,
    NAME            VARCHAR(200)  NOT NULL,
    EMAIL           VARCHAR(200)  NOT NULL,                       -- common-sense uniqueness inferred
    TIER            VARCHAR(10)   NOT NULL,                       -- encoded enum antipattern
    ADDRESS_LINE1   VARCHAR(200)  NOT NULL,                       -- denormalized address antipattern
    ADDRESS_LINE2   VARCHAR(200),
    CITY            VARCHAR(100)  NOT NULL,
    STATE           VARCHAR(100),
    ZIP             VARCHAR(20)   NOT NULL,
    COUNTRY         VARCHAR(100)  NOT NULL
);

CREATE TABLE CUSTOMER_ADDRESS (
    ADDRESS_ID      INTEGER       PRIMARY KEY,
    CUSTOMER_ID     INTEGER       NOT NULL REFERENCES CUSTOMER(CUSTOMER_ID),
    LABEL           VARCHAR(50)   NOT NULL,
    LINE1           VARCHAR(200)  NOT NULL,
    LINE2           VARCHAR(200),
    CITY            VARCHAR(100)  NOT NULL,
    STATE           VARCHAR(100),
    ZIP             VARCHAR(20)   NOT NULL,
    COUNTRY         VARCHAR(100)  NOT NULL
);

CREATE TABLE WAREHOUSE (
    WAREHOUSE_ID    INTEGER       PRIMARY KEY,
    CODE            VARCHAR(20)   NOT NULL UNIQUE,                -- explicit external-unique
    NAME            VARCHAR(200)  NOT NULL,
    ADDRESS_LINE1   VARCHAR(200)  NOT NULL,                       -- denormalized address antipattern
    ADDRESS_LINE2   VARCHAR(200),
    CITY            VARCHAR(100)  NOT NULL,
    STATE           VARCHAR(100),
    ZIP             VARCHAR(20)   NOT NULL,
    COUNTRY         VARCHAR(100)  NOT NULL
);

CREATE TABLE INVENTORY (
    WAREHOUSE_ID       INTEGER NOT NULL REFERENCES WAREHOUSE(WAREHOUSE_ID),
    PRODUCT_ID         INTEGER NOT NULL REFERENCES PRODUCT(PRODUCT_ID),
    QUANTITY_ON_HAND   INTEGER NOT NULL,                          -- range constraint via sample probe
    PRIMARY KEY (WAREHOUSE_ID, PRODUCT_ID)
);

CREATE TABLE INVENTORY_TRANSFER (
    TRANSFER_ID         INTEGER PRIMARY KEY,
    FROM_WAREHOUSE_ID   INTEGER NOT NULL REFERENCES WAREHOUSE(WAREHOUSE_ID),
    TO_WAREHOUSE_ID     INTEGER NOT NULL REFERENCES WAREHOUSE(WAREHOUSE_ID),
    PRODUCT_ID          INTEGER NOT NULL REFERENCES PRODUCT(PRODUCT_ID),
    QUANTITY            INTEGER NOT NULL,
    TRANSFERRED_AT      TIMESTAMP NOT NULL
);
-- Note: irreflexive "from != to" constraint is intended to come from the
-- common-sense library matching "transfer between same-FK-target" semantics.

CREATE TABLE ORDERS (
    ORDER_ID         INTEGER       PRIMARY KEY,
    CUSTOMER_ID      INTEGER       NOT NULL REFERENCES CUSTOMER(CUSTOMER_ID),
    STATUS           VARCHAR(20)   NOT NULL,                      -- encoded enum antipattern
    PLACED_AT        TIMESTAMP     NOT NULL,
    SHIPPED_AT       TIMESTAMP,                                   -- nullable; populated when STATUS in (SHIPPED, DELIVERED)
    DELIVERED_AT     TIMESTAMP,                                   -- nullable; populated when STATUS = DELIVERED
    TOTAL_AMOUNT     DECIMAL(10,2) NOT NULL
);

CREATE TABLE ORDER_ITEM (
    ORDER_ID    INTEGER       NOT NULL REFERENCES ORDERS(ORDER_ID),
    LINE_NO     INTEGER       NOT NULL,
    PRODUCT_ID  INTEGER       NOT NULL REFERENCES PRODUCT(PRODUCT_ID),
    QUANTITY    INTEGER       NOT NULL,
    UNIT_PRICE  DECIMAL(10,2) NOT NULL,
    DISCOUNT    DECIMAL(4,3)  NOT NULL,                           -- 0..1 range via sample probe
    PRIMARY KEY (ORDER_ID, LINE_NO)
);

CREATE TABLE TAG (
    TAG_ID    INTEGER       PRIMARY KEY,
    NAME      VARCHAR(50)   NOT NULL                              -- could be external-unique; not declared
);

-- Ambiguous junction (no extras) — pure m:n candidate
CREATE TABLE ORDER_ITEM_TAG (
    ORDER_ID    INTEGER  NOT NULL,
    LINE_NO     INTEGER  NOT NULL,
    TAG_ID      INTEGER  NOT NULL REFERENCES TAG(TAG_ID),
    PRIMARY KEY (ORDER_ID, LINE_NO, TAG_ID),
    FOREIGN KEY (ORDER_ID, LINE_NO) REFERENCES ORDER_ITEM(ORDER_ID, LINE_NO)
);

CREATE TABLE CARRIER (
    CARRIER_ID  INTEGER       PRIMARY KEY,
    NAME        VARCHAR(100)  NOT NULL
);

CREATE TABLE SHIPMENT (
    SHIPMENT_ID    INTEGER       PRIMARY KEY,
    ORDER_ID       INTEGER       NOT NULL REFERENCES ORDERS(ORDER_ID),
    WAREHOUSE_ID   INTEGER       NOT NULL REFERENCES WAREHOUSE(WAREHOUSE_ID),
    CARRIER_ID     INTEGER       NOT NULL REFERENCES CARRIER(CARRIER_ID),
    TRACKING_NO    VARCHAR(100)  NOT NULL,                        -- could be external-unique; not declared
    SHIPPED_AT     TIMESTAMP     NOT NULL
);

CREATE TABLE SHIPMENT_EVENT (
    EVENT_ID      INTEGER       PRIMARY KEY,
    SHIPMENT_ID   INTEGER       NOT NULL REFERENCES SHIPMENT(SHIPMENT_ID),
    EVENT_TYPE    VARCHAR(30)   NOT NULL,                         -- encoded enum antipattern
    OCCURRED_AT   TIMESTAMP     NOT NULL,
    NOTE          VARCHAR(500)
);

CREATE TABLE RETURN_REQUEST (
    RETURN_ID       INTEGER       PRIMARY KEY,
    ORDER_ID        INTEGER       NOT NULL,
    LINE_NO         INTEGER       NOT NULL,
    REASON          VARCHAR(30)   NOT NULL,                       -- encoded enum antipattern
    REFUND_AMOUNT   DECIMAL(10,2) NOT NULL,
    REQUESTED_AT    TIMESTAMP     NOT NULL,
    FOREIGN KEY (ORDER_ID, LINE_NO) REFERENCES ORDER_ITEM(ORDER_ID, LINE_NO)
);
-- Note: the alethic subset "RETURN_REQUEST → only DELIVERED orders" is meant to
-- come from LLM inference (Step 6c) — not declared in DDL.

CREATE TABLE PAYMENT (
    PAYMENT_ID     INTEGER       PRIMARY KEY,
    ORDER_ID       INTEGER       NOT NULL REFERENCES ORDERS(ORDER_ID),
    METHOD         VARCHAR(20)   NOT NULL,                        -- encoded enum antipattern
    AMOUNT         DECIMAL(10,2) NOT NULL,
    PROCESSED_AT   TIMESTAMP     NOT NULL
);

CREATE TABLE PROMOTION_CODE (
    CODE          VARCHAR(50)   PRIMARY KEY,                      -- explicit external-unique via PK
    DISCOUNT_PCT  DECIMAL(5,2)  NOT NULL,                          -- 0..100 range via sample probe
    VALID_FROM    DATE          NOT NULL,
    VALID_TO      DATE          NOT NULL                           -- temporal ordering valid_from <= valid_to via common-sense
);

-- Ambiguous junction (with extras) — objectified candidate (carries APPLIED_AT)
CREATE TABLE ORDER_PROMOTION (
    ORDER_ID         INTEGER      NOT NULL REFERENCES ORDERS(ORDER_ID),
    PROMOTION_CODE   VARCHAR(50)  NOT NULL REFERENCES PROMOTION_CODE(CODE),
    APPLIED_AT       TIMESTAMP    NOT NULL,
    PRIMARY KEY (ORDER_ID, PROMOTION_CODE)
);

-- ============================================================================
-- Sample data (sized per spec — small enough to read, large enough to probe)
-- ============================================================================

-- Product categories (3-deep tree, no cycles)
INSERT INTO PRODUCT_CATEGORY (CATEGORY_ID, NAME, PARENT_CATEGORY_ID) VALUES
    (1,  'Electronics',          NULL),
    (2,  'Computing',             1),
    (3,  'Laptops',               2),
    (4,  'Accessories',           2),
    (5,  'Audio',                 1),
    (6,  'Headphones',            5),
    (7,  'Software',              NULL),
    (8,  'Productivity',          7),
    (9,  'Subscriptions',         NULL),
    (10, 'Cloud Services',        9);

-- Products (5 physical, 5 digital, 5 subscription = 15)
INSERT INTO PRODUCT (PRODUCT_ID, SKU, NAME, UNIT_PRICE, TYPE, CATEGORY_ID) VALUES
    ( 1, 'PHY-001', 'Laptop Pro 15"',         1899.00, 'PHYSICAL',     3),
    ( 2, 'PHY-002', 'USB-C Hub',                49.99, 'PHYSICAL',     4),
    ( 3, 'PHY-003', 'Wireless Headphones',     249.00, 'PHYSICAL',     6),
    ( 4, 'PHY-004', 'Mechanical Keyboard',     159.00, 'PHYSICAL',     4),
    ( 5, 'PHY-005', 'External SSD 1TB',        129.00, 'PHYSICAL',     4),
    ( 6, 'DIG-001', 'OfficeSuite License',     199.00, 'DIGITAL',      8),
    ( 7, 'DIG-002', 'Photo Editor Pro',         89.00, 'DIGITAL',      8),
    ( 8, 'DIG-003', 'Audio Mixing Pack',        49.00, 'DIGITAL',      8),
    ( 9, 'DIG-004', 'Font Bundle 2026',         29.00, 'DIGITAL',      8),
    (10, 'DIG-005', 'Stock Photo Pack',         19.00, 'DIGITAL',      8),
    (11, 'SUB-001', 'Cloud Backup 1TB/yr',     119.00, 'SUBSCRIPTION', 10),
    (12, 'SUB-002', 'Cloud Compute Plus',      299.00, 'SUBSCRIPTION', 10),
    (13, 'SUB-003', 'Productivity Suite/yr',   149.00, 'SUBSCRIPTION', 10),
    (14, 'SUB-004', 'Streaming Premium/yr',     99.00, 'SUBSCRIPTION', 10),
    (15, 'SUB-005', 'Antivirus Pro/yr',         59.00, 'SUBSCRIPTION', 10);

-- Subtype detail rows correlate with PRODUCT.TYPE values
INSERT INTO PHYSICAL_PRODUCT_DETAILS (PRODUCT_ID, WEIGHT_KG, LENGTH_CM, WIDTH_CM, HEIGHT_CM) VALUES
    (1, 2.000, 35.00, 24.00,  2.00),
    (2, 0.090, 12.00,  4.00,  1.00),
    (3, 0.260, 18.00, 16.00,  8.00),
    (4, 1.100, 45.00, 14.00,  4.00),
    (5, 0.075,  9.00,  6.00,  1.00);

INSERT INTO DIGITAL_PRODUCT_DETAILS (PRODUCT_ID, DOWNLOAD_URL, FILE_SIZE_MB) VALUES
    ( 6, 'https://cdn.example.com/dl/officesuite.zip',    410.00),
    ( 7, 'https://cdn.example.com/dl/photoeditor.zip',    980.50),
    ( 8, 'https://cdn.example.com/dl/audiomix.zip',       640.00),
    ( 9, 'https://cdn.example.com/dl/fonts.zip',           75.20),
    (10, 'https://cdn.example.com/dl/stockphotos.zip',   1850.00);

INSERT INTO SUBSCRIPTION_PRODUCT_DETAILS (PRODUCT_ID, PERIOD_DAYS, AUTO_RENEW_DEFAULT) VALUES
    (11, 365, TRUE),
    (12, 365, FALSE),
    (13, 365, TRUE),
    (14, 365, TRUE),
    (15, 365, FALSE);

-- Customers (10, all 3 tiers represented)
INSERT INTO CUSTOMER (CUSTOMER_ID, NAME, EMAIL, TIER, ADDRESS_LINE1, ADDRESS_LINE2, CITY, STATE, ZIP, COUNTRY) VALUES
    ( 1, 'Alice Brown',     'alice.brown@example.com',     'GOLD',   '123 Maple St',     'Apt 4',  'Seattle',     'WA', '98101', 'USA'),
    ( 2, 'Bob Carlsen',     'bob.carlsen@example.com',     'SILVER', '45 Oak Ave',       NULL,     'Portland',    'OR', '97201', 'USA'),
    ( 3, 'Cora Diaz',       'cora.diaz@example.com',       'BRONZE', '78 Pine Rd',       NULL,     'San Diego',   'CA', '92101', 'USA'),
    ( 4, 'Dimitri Kalas',   'dimitri.kalas@example.com',   'GOLD',   '90 Elm Blvd',      'Unit 2', 'Athens',      NULL, '10557', 'Greece'),
    ( 5, 'Eva Fischer',     'eva.fischer@example.com',     'SILVER', '12 Linden Str',    NULL,     'Berlin',      NULL, '10115', 'Germany'),
    ( 6, 'Farah Ahmed',     'farah.ahmed@example.com',     'BRONZE', '33 Cedar Ln',      NULL,     'Toronto',     'ON', 'M5H 2N2','Canada'),
    ( 7, 'Grace Park',      'grace.park@example.com',      'GOLD',   '5 Birch Park',     NULL,     'Vancouver',   'BC', 'V5K 0A1','Canada'),
    ( 8, 'Hugo Martins',    'hugo.martins@example.com',    'SILVER', '88 Cypress Rd',    NULL,     'Lisbon',      NULL, '1100',  'Portugal'),
    ( 9, 'Ines Vega',       'ines.vega@example.com',       'BRONZE', '2 Olive Way',      NULL,     'Madrid',      NULL, '28013', 'Spain'),
    (10, 'Jonas Westin',    'jonas.westin@example.com',    'GOLD',   '7 Aspen Crescent', NULL,     'Stockholm',   NULL, '11122', 'Sweden');

-- Customer addresses (alternate shipping addresses — demonstrates the canonical 1:N opposition)
INSERT INTO CUSTOMER_ADDRESS (ADDRESS_ID, CUSTOMER_ID, LABEL, LINE1, LINE2, CITY, STATE, ZIP, COUNTRY) VALUES
    (1, 1, 'work',    '500 Industrial Way',    'Suite 12', 'Seattle',  'WA', '98109', 'USA'),
    (2, 1, 'mom',     '88 Birch Hill',         NULL,       'Tacoma',   'WA', '98401', 'USA'),
    (3, 4, 'office',  '1 Syntagma Sq',         NULL,       'Athens',   NULL, '10563', 'Greece'),
    (4, 7, 'parents', '12 Granville St',       NULL,       'Victoria', 'BC', 'V8W 2J1','Canada');

-- Warehouses (3 — all denormalized addresses)
INSERT INTO WAREHOUSE (WAREHOUSE_ID, CODE, NAME, ADDRESS_LINE1, ADDRESS_LINE2, CITY, STATE, ZIP, COUNTRY) VALUES
    (1, 'WH-WEST', 'West Coast DC',  '1000 Logistics Pkwy',  NULL,         'Reno',    'NV', '89501', 'USA'),
    (2, 'WH-EAST', 'East Coast DC',  '2200 Distribution Rd', 'Bldg B',     'Edison',  'NJ', '08817', 'USA'),
    (3, 'WH-EU',   'EU Hub',         '15 Logistik Allee',    NULL,         'Frankfurt', NULL, '60311', 'Germany');

-- Inventory (every product in 1-2 warehouses)
INSERT INTO INVENTORY (WAREHOUSE_ID, PRODUCT_ID, QUANTITY_ON_HAND) VALUES
    (1,  1, 240), (1,  2, 1800), (1,  3, 410), (1,  4, 320), (1,  5, 980),
    (2,  1, 180), (2,  3, 250),  (2,  4, 410), (2,  5, 720),
    (3,  1, 120), (3,  2, 1100), (3,  3, 180), (3,  4, 200), (3,  5, 540);
-- Digital and subscription products have no physical inventory rows.

-- Inventory transfers (5 rows, all distinct from/to)
INSERT INTO INVENTORY_TRANSFER (TRANSFER_ID, FROM_WAREHOUSE_ID, TO_WAREHOUSE_ID, PRODUCT_ID, QUANTITY, TRANSFERRED_AT) VALUES
    (1, 1, 2, 1, 30, '2026-04-01 09:30:00'),
    (2, 1, 3, 3, 50, '2026-04-08 11:15:00'),
    (3, 2, 1, 4, 40, '2026-04-12 14:00:00'),
    (4, 3, 1, 5, 20, '2026-04-18 10:45:00'),
    (5, 3, 2, 1, 25, '2026-04-22 16:20:00');

-- Orders (20 rows spanning all five STATUS values; timestamps respect placed <= shipped <= delivered)
INSERT INTO ORDERS (ORDER_ID, CUSTOMER_ID, STATUS, PLACED_AT, SHIPPED_AT, DELIVERED_AT, TOTAL_AMOUNT) VALUES
    ( 1, 1, 'DELIVERED', '2026-03-01 10:00:00', '2026-03-02 14:00:00', '2026-03-05 11:30:00', 2148.00),
    ( 2, 2, 'DELIVERED', '2026-03-03 09:15:00', '2026-03-04 10:00:00', '2026-03-08 13:00:00',  408.99),
    ( 3, 3, 'DELIVERED', '2026-03-05 16:30:00', '2026-03-06 09:00:00', '2026-03-10 11:00:00',  267.99),
    ( 4, 4, 'DELIVERED', '2026-03-07 11:00:00', '2026-03-08 10:30:00', '2026-03-12 09:00:00',  389.00),
    ( 5, 5, 'SHIPPED',   '2026-04-15 13:00:00', '2026-04-16 14:00:00', NULL,                   349.00),
    ( 6, 6, 'SHIPPED',   '2026-04-16 09:30:00', '2026-04-17 11:00:00', NULL,                   159.00),
    ( 7, 7, 'PAID',      '2026-04-25 10:00:00', NULL,                  NULL,                   199.00),
    ( 8, 8, 'PAID',      '2026-04-26 12:00:00', NULL,                  NULL,                    89.00),
    ( 9, 9, 'PAID',      '2026-04-28 15:30:00', NULL,                  NULL,                   178.00),
    (10, 1, 'PENDING',   '2026-05-01 08:30:00', NULL,                  NULL,                    49.99),
    (11, 2, 'PENDING',   '2026-05-02 10:00:00', NULL,                  NULL,                   119.00),
    (12, 3, 'CANCELLED', '2026-04-10 14:00:00', NULL,                  NULL,                   299.00),
    (13, 4, 'CANCELLED', '2026-04-20 11:00:00', NULL,                  NULL,                    99.00),
    (14, 5, 'DELIVERED', '2026-03-12 09:30:00', '2026-03-13 12:00:00', '2026-03-17 09:00:00',  219.00),
    (15, 6, 'DELIVERED', '2026-03-15 14:00:00', '2026-03-16 11:00:00', '2026-03-19 13:00:00',  149.00),
    (16, 7, 'DELIVERED', '2026-03-18 10:30:00', '2026-03-19 13:00:00', '2026-03-22 10:00:00',  398.00),
    (17, 8, 'DELIVERED', '2026-03-20 12:00:00', '2026-03-21 09:00:00', '2026-03-25 11:30:00',   59.00),
    (18, 9, 'SHIPPED',   '2026-04-20 13:00:00', '2026-04-21 11:00:00', NULL,                   249.00),
    (19, 10, 'PAID',     '2026-04-29 09:00:00', NULL,                  NULL,                  1899.00),
    (20, 10, 'PENDING',  '2026-05-03 10:00:00', NULL,                  NULL,                    19.00);

-- Order items (1-5 per order; quantities and discounts within sensible ranges)
INSERT INTO ORDER_ITEM (ORDER_ID, LINE_NO, PRODUCT_ID, QUANTITY, UNIT_PRICE, DISCOUNT) VALUES
    -- Order 1 (Alice — laptop + accessories)
    ( 1, 1,  1, 1, 1899.00, 0.000),
    ( 1, 2,  2, 1,   49.99, 0.000),
    ( 1, 3,  4, 1,  199.00, 0.000),
    -- Order 2 (Bob — small bundle)
    ( 2, 1,  2, 4,   49.99, 0.100),
    ( 2, 2,  9, 1,   29.00, 0.000),
    ( 2, 3, 10, 1,   19.00, 0.000),
    -- Order 3 (Cora — accessories + software)
    ( 3, 1,  2, 2,   49.99, 0.000),
    ( 3, 2,  7, 1,   89.00, 0.050),
    ( 3, 3,  8, 1,   49.00, 0.000),
    ( 3, 4,  9, 1,   29.00, 0.000),
    -- Order 4 (Dimitri — software bundle)
    ( 4, 1,  6, 1,  199.00, 0.100),
    ( 4, 2,  7, 2,   89.00, 0.000),
    -- Order 5 (Eva — single headphones)
    ( 5, 1,  3, 1,  249.00, 0.000),
    ( 5, 2, 11, 1,  119.00, 0.150),
    -- Order 6 (Farah — keyboard)
    ( 6, 1,  4, 1,  159.00, 0.000),
    -- Order 7 (Grace — software)
    ( 7, 1,  6, 1,  199.00, 0.000),
    -- Order 8 (Hugo — single digital)
    ( 8, 1,  7, 1,   89.00, 0.000),
    -- Order 9 (Ines — small bundle)
    ( 9, 1,  3, 1,  249.00, 0.300),
    ( 9, 2, 10, 5,   19.00, 0.000),
    -- Order 10 (Alice — pending USB hub)
    (10, 1,  2, 1,   49.99, 0.000),
    -- Order 11 (Bob — pending cloud backup)
    (11, 1, 11, 1,  119.00, 0.000),
    -- Order 12 (Cora — cancelled compute plus)
    (12, 1, 12, 1,  299.00, 0.000),
    -- Order 13 (Dimitri — cancelled subscription)
    (13, 1, 14, 1,   99.00, 0.000),
    -- Order 14 (Eva — delivered productivity)
    (14, 1, 13, 1,  149.00, 0.000),
    (14, 2,  9, 1,   29.00, 0.000),
    (14, 3, 10, 1,   19.00, 0.250),
    -- Order 15 (Farah — delivered keyboard)
    (15, 1,  4, 1,  159.00, 0.000),
    -- Order 16 (Grace — delivered bundle)
    (16, 1,  3, 1,  249.00, 0.000),
    (16, 2,  9, 5,   29.00, 0.100),
    -- Order 17 (Hugo — delivered antivirus)
    (17, 1, 15, 1,   59.00, 0.000),
    -- Order 18 (Ines — shipped headphones)
    (18, 1,  3, 1,  249.00, 0.000),
    -- Order 19 (Jonas — paid laptop)
    (19, 1,  1, 1, 1899.00, 0.000),
    -- Order 20 (Jonas — pending stock photo)
    (20, 1, 10, 1,   19.00, 0.000);

-- Tags
INSERT INTO TAG (TAG_ID, NAME) VALUES
    (1, 'gift'),
    (2, 'urgent'),
    (3, 'fragile'),
    (4, 'pre-order'),
    (5, 'bulk');

-- Order-item tags (pure m:n; no extras)
INSERT INTO ORDER_ITEM_TAG (ORDER_ID, LINE_NO, TAG_ID) VALUES
    ( 1, 1, 3),
    ( 1, 3, 1),
    ( 2, 1, 5),
    ( 5, 1, 2),
    ( 5, 1, 3),
    ( 6, 1, 1),
    ( 9, 1, 2),
    (16, 1, 1),
    (16, 2, 5),
    (18, 1, 2);

-- Carriers
INSERT INTO CARRIER (CARRIER_ID, NAME) VALUES
    (1, 'GlobalShip'),
    (2, 'FastBox'),
    (3, 'Eurodelivery'),
    (4, 'PacificFreight');

-- Shipments (one per order with STATUS in (SHIPPED, DELIVERED) — 11 shipments)
INSERT INTO SHIPMENT (SHIPMENT_ID, ORDER_ID, WAREHOUSE_ID, CARRIER_ID, TRACKING_NO, SHIPPED_AT) VALUES
    ( 1,  1, 1, 1, 'GS-1000001', '2026-03-02 14:00:00'),
    ( 2,  2, 1, 2, 'FB-2000001', '2026-03-04 10:00:00'),
    ( 3,  3, 1, 1, 'GS-1000002', '2026-03-06 09:00:00'),
    ( 4,  4, 3, 3, 'EU-3000001', '2026-03-08 10:30:00'),
    ( 5,  5, 1, 4, 'PF-4000001', '2026-04-16 14:00:00'),
    ( 6,  6, 2, 2, 'FB-2000002', '2026-04-17 11:00:00'),
    ( 7, 14, 1, 1, 'GS-1000003', '2026-03-13 12:00:00'),
    ( 8, 15, 2, 2, 'FB-2000003', '2026-03-16 11:00:00'),
    ( 9, 16, 1, 1, 'GS-1000004', '2026-03-19 13:00:00'),
    (10, 17, 3, 3, 'EU-3000002', '2026-03-21 09:00:00'),
    (11, 18, 3, 3, 'EU-3000003', '2026-04-21 11:00:00');

-- Shipment events (2-3 per shipment)
INSERT INTO SHIPMENT_EVENT (EVENT_ID, SHIPMENT_ID, EVENT_TYPE, OCCURRED_AT, NOTE) VALUES
    ( 1,  1, 'PICKED_UP',         '2026-03-02 14:00:00', NULL),
    ( 2,  1, 'IN_TRANSIT',        '2026-03-03 08:00:00', NULL),
    ( 3,  1, 'OUT_FOR_DELIVERY',  '2026-03-05 09:30:00', NULL),
    ( 4,  1, 'DELIVERED',         '2026-03-05 11:30:00', NULL),
    ( 5,  2, 'PICKED_UP',         '2026-03-04 10:00:00', NULL),
    ( 6,  2, 'IN_TRANSIT',        '2026-03-05 12:00:00', NULL),
    ( 7,  2, 'DELIVERED',         '2026-03-08 13:00:00', NULL),
    ( 8,  3, 'PICKED_UP',         '2026-03-06 09:00:00', NULL),
    ( 9,  3, 'IN_TRANSIT',        '2026-03-07 11:00:00', 'transferred via West hub'),
    (10,  3, 'DELIVERED',         '2026-03-10 11:00:00', NULL),
    (11,  4, 'PICKED_UP',         '2026-03-08 10:30:00', NULL),
    (12,  4, 'EXCEPTION',         '2026-03-10 15:00:00', 'customs hold'),
    (13,  4, 'DELIVERED',         '2026-03-12 09:00:00', NULL),
    (14,  5, 'PICKED_UP',         '2026-04-16 14:00:00', NULL),
    (15,  5, 'IN_TRANSIT',        '2026-04-17 09:00:00', NULL),
    (16,  6, 'PICKED_UP',         '2026-04-17 11:00:00', NULL),
    (17,  6, 'OUT_FOR_DELIVERY',  '2026-04-19 08:00:00', NULL),
    (18,  7, 'PICKED_UP',         '2026-03-13 12:00:00', NULL),
    (19,  7, 'DELIVERED',         '2026-03-17 09:00:00', NULL),
    (20,  9, 'PICKED_UP',         '2026-03-19 13:00:00', NULL),
    (21,  9, 'DELIVERED',         '2026-03-22 10:00:00', NULL),
    (22, 10, 'PICKED_UP',         '2026-03-21 09:00:00', NULL),
    (23, 10, 'DELIVERED',         '2026-03-25 11:30:00', NULL),
    (24, 11, 'PICKED_UP',         '2026-04-21 11:00:00', NULL),
    (25, 11, 'IN_TRANSIT',        '2026-04-22 09:00:00', NULL);

-- Returns (only against DELIVERED orders — supports the LLM-inferred subset)
INSERT INTO RETURN_REQUEST (RETURN_ID, ORDER_ID, LINE_NO, REASON, REFUND_AMOUNT, REQUESTED_AT) VALUES
    (1, 1, 2, 'DEFECTIVE',     49.99, '2026-03-08 10:00:00'),
    (2, 3, 1, 'CHANGED_MIND',  99.98, '2026-03-12 14:00:00'),
    (3, 4, 1, 'WRONG_ITEM',   199.00, '2026-03-14 09:00:00'),
    (4, 14, 3, 'NOT_AS_DESCRIBED', 14.25, '2026-03-19 11:00:00'),
    (5, 16, 2, 'DAMAGED',     145.00, '2026-03-23 10:00:00');

-- Payments (most orders have a payment; cancelled ones don't)
INSERT INTO PAYMENT (PAYMENT_ID, ORDER_ID, METHOD, AMOUNT, PROCESSED_AT) VALUES
    ( 1,  1, 'CARD',   2148.00, '2026-03-01 10:01:00'),
    ( 2,  2, 'PAYPAL',  408.99, '2026-03-03 09:16:00'),
    ( 3,  3, 'CARD',    267.99, '2026-03-05 16:31:00'),
    ( 4,  4, 'BANK',    389.00, '2026-03-07 11:01:00'),
    ( 5,  5, 'CARD',    349.00, '2026-04-15 13:02:00'),
    ( 6,  6, 'CARD',    159.00, '2026-04-16 09:31:00'),
    ( 7,  7, 'PAYPAL',  199.00, '2026-04-25 10:01:00'),
    ( 8,  8, 'CARD',     89.00, '2026-04-26 12:01:00'),
    ( 9,  9, 'GIFT',    178.00, '2026-04-28 15:31:00'),
    (10, 14, 'CARD',    219.00, '2026-03-12 09:31:00'),
    (11, 15, 'CARD',    149.00, '2026-03-15 14:01:00'),
    (12, 16, 'PAYPAL',  398.00, '2026-03-18 10:31:00'),
    (13, 17, 'BANK',     59.00, '2026-03-20 12:01:00'),
    (14, 18, 'CARD',    249.00, '2026-04-20 13:01:00'),
    (15, 19, 'CARD',   1899.00, '2026-04-29 09:01:00');

-- Promotion codes
INSERT INTO PROMOTION_CODE (CODE, DISCOUNT_PCT, VALID_FROM, VALID_TO) VALUES
    ('SPRING26',  10.00, '2026-03-01', '2026-05-31'),
    ('GOLD15',    15.00, '2026-01-01', '2026-12-31'),
    ('NEWUSER5',   5.00, '2026-01-01', '2026-12-31'),
    ('FLASH50',   50.00, '2026-04-15', '2026-04-22'),
    ('BACKTO20',  20.00, '2026-08-01', '2026-09-15');

-- Order promotions (objectified candidate — applied_at as the extra)
INSERT INTO ORDER_PROMOTION (ORDER_ID, PROMOTION_CODE, APPLIED_AT) VALUES
    ( 2, 'NEWUSER5',  '2026-03-03 09:15:30'),
    ( 4, 'GOLD15',    '2026-03-07 11:00:30'),
    ( 5, 'SPRING26',  '2026-04-15 13:00:30'),
    ( 9, 'FLASH50',   '2026-04-28 15:30:30'),
    (16, 'GOLD15',    '2026-03-18 10:30:30'),
    (19, 'GOLD15',    '2026-04-29 09:00:30');
