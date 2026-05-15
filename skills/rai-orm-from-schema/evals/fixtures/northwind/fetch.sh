#!/usr/bin/env bash
# Fetch the Northwind benchmark fixture. Idempotent — safe to re-run.
#
# Source: pthom/northwind_psql (Postgres port of MS Northwind)
# License: MIT (see https://github.com/pthom/northwind_psql/blob/master/LICENSE)
#
# Produces:
#   schema.sql       — DROP + CREATE TABLE + ALTER TABLE (PK / FK / UNIQUE)
#   sample_data.sql  — INSERT statements only

set -euo pipefail

REPO="pthom/northwind_psql"
COMMIT="cd0ef28d66369fbe177778e604e4be0f153c9e5c"
URL="https://raw.githubusercontent.com/${REPO}/${COMMIT}/northwind.sql"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAW="${DIR}/northwind_full.sql"
SCHEMA="${DIR}/schema.sql"
DATA="${DIR}/sample_data.sql"

echo "Fetching Northwind from ${URL}"
curl -sSL -o "${RAW}" "${URL}"
echo "  → wrote ${RAW} ($(wc -l <"${RAW}") lines)"

# Split: lines 1-247 are DDL (DROP + CREATE TABLE), lines 248-3691 are INSERTs,
# lines 3692-end are ALTER TABLE statements adding PK/FK/UNIQUE.
# schema.sql = DDL + ALTERs (concatenated); sample_data.sql = INSERTs only.
sed -n '1,247p' "${RAW}" > "${SCHEMA}"
echo "" >> "${SCHEMA}"
sed -n '3692,$p' "${RAW}" >> "${SCHEMA}"
sed -n '248,3691p' "${RAW}" > "${DATA}"

rm -f "${RAW}"

echo "  → schema.sql       ($(wc -l <"${SCHEMA}") lines)"
echo "  → sample_data.sql  ($(wc -l <"${DATA}") lines)"
echo "Done."
