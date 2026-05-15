#!/usr/bin/env bash
# Fetch the TPC-H benchmark fixture. Idempotent — safe to re-run.
#
# Source: gregrahn/tpch-kit (community fork of TPC's dbgen)
# License: TPC EULA Version 2.2 (see ../../../../notes/phase4-tpch-eula-2026-05-04.txt)
#
# Note: the canonical dss.ddl declares only NOT NULL constraints. We append
# PK and FK ALTER TABLE statements per the TPC-H specification (Section 1.4)
# so the SRP's mechanical lift has the full constraint surface to work against.
#
# Produces:
#   schema.sql       — canonical DDL + spec-compliant PK/FK additions

set -euo pipefail

REPO="gregrahn/tpch-kit"
COMMIT="852ad0a5ee31ebefeed884cea4188781dd9613a3"
URL="https://raw.githubusercontent.com/${REPO}/${COMMIT}/dbgen/dss.ddl"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCHEMA="${DIR}/schema.sql"

echo "Fetching TPC-H DDL from ${URL}"
curl -sSL -o "${SCHEMA}" "${URL}"

# Append PK/FK constraints from the TPC-H specification Section 1.4.
cat >> "${SCHEMA}" << 'EOF'

-- ----------------------------------------------------------------------------
-- LOCAL MODIFICATION (rai-orm-from-schema):
-- The canonical TPC-H dbgen DDL omits PK and FK declarations; the TPC-H
-- specification (Section 1.4) defines them and we add them here so the SRP's
-- mechanical lift has the full constraint surface to work against.
-- See evals/fixtures/tpc_h/README.md for the rationale.
-- ----------------------------------------------------------------------------

ALTER TABLE REGION   ADD CONSTRAINT pk_region   PRIMARY KEY (R_REGIONKEY);
ALTER TABLE NATION   ADD CONSTRAINT pk_nation   PRIMARY KEY (N_NATIONKEY);
ALTER TABLE PART     ADD CONSTRAINT pk_part     PRIMARY KEY (P_PARTKEY);
ALTER TABLE SUPPLIER ADD CONSTRAINT pk_supplier PRIMARY KEY (S_SUPPKEY);
ALTER TABLE PARTSUPP ADD CONSTRAINT pk_partsupp PRIMARY KEY (PS_PARTKEY, PS_SUPPKEY);
ALTER TABLE CUSTOMER ADD CONSTRAINT pk_customer PRIMARY KEY (C_CUSTKEY);
ALTER TABLE ORDERS   ADD CONSTRAINT pk_orders   PRIMARY KEY (O_ORDERKEY);
ALTER TABLE LINEITEM ADD CONSTRAINT pk_lineitem PRIMARY KEY (L_ORDERKEY, L_LINENUMBER);

ALTER TABLE NATION   ADD CONSTRAINT fk_nation_region   FOREIGN KEY (N_REGIONKEY) REFERENCES REGION(R_REGIONKEY);
ALTER TABLE SUPPLIER ADD CONSTRAINT fk_supplier_nation FOREIGN KEY (S_NATIONKEY) REFERENCES NATION(N_NATIONKEY);
ALTER TABLE CUSTOMER ADD CONSTRAINT fk_customer_nation FOREIGN KEY (C_NATIONKEY) REFERENCES NATION(N_NATIONKEY);
ALTER TABLE PARTSUPP ADD CONSTRAINT fk_partsupp_part   FOREIGN KEY (PS_PARTKEY) REFERENCES PART(P_PARTKEY);
ALTER TABLE PARTSUPP ADD CONSTRAINT fk_partsupp_supp   FOREIGN KEY (PS_SUPPKEY) REFERENCES SUPPLIER(S_SUPPKEY);
ALTER TABLE ORDERS   ADD CONSTRAINT fk_orders_customer FOREIGN KEY (O_CUSTKEY) REFERENCES CUSTOMER(C_CUSTKEY);
ALTER TABLE LINEITEM ADD CONSTRAINT fk_lineitem_orders FOREIGN KEY (L_ORDERKEY) REFERENCES ORDERS(O_ORDERKEY);
ALTER TABLE LINEITEM ADD CONSTRAINT fk_lineitem_partsupp FOREIGN KEY (L_PARTKEY, L_SUPPKEY) REFERENCES PARTSUPP(PS_PARTKEY, PS_SUPPKEY);
EOF

echo "  → schema.sql ($(wc -l <"${SCHEMA}") lines)"
echo "Done."
