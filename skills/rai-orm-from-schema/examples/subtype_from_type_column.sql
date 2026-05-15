-- examples/subtype_from_type_column.sql
-- Demonstrates Step 7's TYPE-column subtype detection. The schema has:
--   - VEHICLE: a parent entity with a TYPE discriminator column
--   - CAR_DETAILS, TRUCK_DETAILS, MOTORCYCLE_DETAILS: side tables FK'd from VEHICLE
--     whose presence correlates with specific TYPE values
-- The SRP must:
--   1. Detect the TYPE-column subtype-split antipattern (Step 7).
--   2. Propose subtypes Car / Truck / Motorcycle as `extends=[Vehicle]` with derivation rules.
--   3. Emit a subtype-partition constraint with exclusive=true, exhaustive=true (TYPE is NOT NULL).
--   4. Translate to PyRel via mechanical (subtype membership) + verbose (partition) tiers.

CREATE TABLE VEHICLE (
    VEHICLE_ID  INTEGER       PRIMARY KEY,
    MAKE        VARCHAR(100)  NOT NULL,
    MODEL       VARCHAR(100)  NOT NULL,
    TYPE        VARCHAR(20)   NOT NULL CHECK (TYPE IN ('CAR', 'TRUCK', 'MOTORCYCLE'))
);

-- Side table — only present when VEHICLE.TYPE = 'CAR'
CREATE TABLE CAR_DETAILS (
    VEHICLE_ID   INTEGER  PRIMARY KEY REFERENCES VEHICLE(VEHICLE_ID),
    NUM_SEATS    INTEGER  NOT NULL CHECK (NUM_SEATS BETWEEN 1 AND 9),
    BODY_STYLE   VARCHAR(20) NOT NULL CHECK (BODY_STYLE IN ('SEDAN','HATCHBACK','SUV','COUPE','WAGON'))
);

-- Side table — only present when VEHICLE.TYPE = 'TRUCK'
CREATE TABLE TRUCK_DETAILS (
    VEHICLE_ID         INTEGER       PRIMARY KEY REFERENCES VEHICLE(VEHICLE_ID),
    PAYLOAD_CAPACITY   INTEGER       NOT NULL CHECK (PAYLOAD_CAPACITY > 0),
    BED_LENGTH         DECIMAL(5,2)  NOT NULL CHECK (BED_LENGTH > 0)
);

-- Side table — only present when VEHICLE.TYPE = 'MOTORCYCLE'
CREATE TABLE MOTORCYCLE_DETAILS (
    VEHICLE_ID  INTEGER  PRIMARY KEY REFERENCES VEHICLE(VEHICLE_ID),
    ENGINE_CC   INTEGER  NOT NULL CHECK (ENGINE_CC > 0)
);

-- Sample data so Step 5 can correlate side-table presence with TYPE values.
INSERT INTO VEHICLE (VEHICLE_ID, MAKE, MODEL, TYPE) VALUES
  (1, 'Toyota',     'Camry',         'CAR'),
  (2, 'Ford',       'F-150',         'TRUCK'),
  (3, 'Honda',      'CBR600RR',      'MOTORCYCLE'),
  (4, 'Tesla',      'Model 3',       'CAR'),
  (5, 'Chevrolet',  'Silverado',     'TRUCK'),
  (6, 'Yamaha',     'YZF-R3',        'MOTORCYCLE');

INSERT INTO CAR_DETAILS (VEHICLE_ID, NUM_SEATS, BODY_STYLE) VALUES
  (1, 5, 'SEDAN'),
  (4, 5, 'SEDAN');

INSERT INTO TRUCK_DETAILS (VEHICLE_ID, PAYLOAD_CAPACITY, BED_LENGTH) VALUES
  (2, 1500, 6.50),
  (5, 2000, 5.75);

INSERT INTO MOTORCYCLE_DETAILS (VEHICLE_ID, ENGINE_CC) VALUES
  (3, 599),
  (6, 321);
