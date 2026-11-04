# `schema.json` reference

`rai explore schema` writes this document (`-o schema.json`, or `--out -` for stdout). Two properties are load-bearing:

1. **Constant shape across `--depth`.** Every key exists at every depth. Keys a shallower depth did not compute are `null` — **never omitted**. Do not write code that treats an absent key as meaningful; absence does not occur.
2. **Deterministic output.** Byte-identical across runs on unchanged data. `generated_at` is `null` unless you pass `--stamp`, because a timestamp would break that.

`schema_version` gates breaking shape changes — if it is not `1`, this reference may not describe what you are holding. `tool_version` tracks the implementation and moves independently.

## Top-level fields

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | int | Wire-contract version. Currently `1`. |
| `tool_version` | string | Implementation version; moves independently of `schema_version`. |
| `depth` | `"structure"` / `"profile"` / `"full"` | Which depth produced this document. Tells you which fields could have been populated. |
| `database` | string | Source database. |
| `schema` | string | Source schema within the database. |
| `generated_at` | ISO-8601 string or null | `null` unless `--stamp` was passed. |
| `warnings` | array of `Warning` | In-band degradations and undecidable inferences. **Always read these** — see [Reading `warnings[]`](#reading-warnings). |
| `tables` | array of `Table` | One entry per table or view (or per `--table` whitelist entry). |
| `fk_candidates` | array of `FKCandidate` | Cross-table edges, declared or inferred. |
| `graph_topology` | `GraphTopology` or null | Populated at `--depth full` when the edge-table heuristic fires. |

## `Table`

| Field | Type | Meaning |
|---|---|---|
| `table_name` | string | Unqualified name, in the catalog's stored spelling. |
| `row_count` | int or null | Approximate metadata count at `structure` depth (`null` for views); a **live, exact `COUNT(*)` at `profile`+, populated for views and empty tables too**. |
| `pk_candidates` | array of string | Single-column PK candidates in ordinal order. The first is almost always the real PK; later entries are unique *by coincidence* (`EMAIL`, `PHONE`). Composite uniqueness is out of scope — an empty list on a junction table is expected, not a failure. |
| `columns` | array of `Column` | Column list in ordinal order. |

## `Column`

Every key below is always present. `null` means "not computed at this depth" or "not applicable" — never "missing".

| Field | Type | Meaning |
|---|---|---|
| `column_name` | string | Stored spelling, not case-folded. |
| `data_type` | string | Source type as reported by the catalog. |
| `ordinal_position` | int | 1-based position in the table. |
| `is_nullable` | bool | Declared nullability (distinct from observed `null_rate`). |
| `numeric_precision` | int or null | For numeric types. |
| `numeric_scale` | int or null | For numeric types. `> 0` is why a `NUMBER` maps to `Float`. |
| `rai_type` | string or null | **The RAI type to declare.** One of `String`, `Integer`, `Float`, `Date`, `DateTime`, `Boolean`. `null` means the mapper did not recognize `data_type` (VARIANT, OBJECT, ARRAY, GEOGRAPHY, VECTOR, …) — a real signal, not a gap; the column still exists. Fall back to the type mapping table in `SKILL.md` § Data Mapping Guidance. |
| `distinct_count` | int or null | Distinct non-null values. `null` below `profile`. |
| `null_rate` | float or null | Observed fraction of NULL rows. `null` below `profile` and for an empty table (0/0 is undefined). |
| `numeric_range` | `{min, max}` or null | Observed range for numeric columns. **`min` and `max` only — there is no `avg`.** Use it to set thresholds against the real data scale. |
| `value_distribution` | object `{value: count}` or null | Populated for low-cardinality columns (`distinct_count <= 20`). **Keys are sorted alphabetically on the wire — sort by count descending yourself to rank values.** Keys are stringified. For a share-of-rows figure, divide by the table's `row_count`. |

## `FKCandidate`

| Field | Type | Meaning |
|---|---|---|
| `source_table`, `source_column` | string | The FK column (the child side). |
| `target_table`, `target_column` | string | What it points at (the parent side). |
| `multiplicity_class` | `"1:1"` / `"N:1"` / `"M:N"` / null | Source-to-target cardinality. `M:N` means the source is a junction. `null` means there was nothing to classify from — `structure` depth, an empty source table, or an all-NULL FK column — so establish multiplicity yourself before choosing Property vs. Relationship. |

There is no `inference_source` field: an edge that survives to this array is one you should model, and declared-vs-inferred provenance implied no different action. Per-FK cardinality counts (`avg_rows_per_fk`, `max_rows_per_fk`) and `broken_fk_count` are likewise absent — `multiplicity_class` is the verdict they existed to support, and the null-FK count you would act on is `graph_topology.broken_edges`.

## `GraphTopology` (at `--depth full`)

| Field | Type | Meaning |
|---|---|---|
| `edge_type_pairs` | array of `{entity_type, count}` | One entry per co-targeted FK pair. `entity_type` is the **target table name** shared by both FKs — one field captures both endpoints, which is why a self-edge reads naturally. `count` is the edge-table row count. |
| `broken_edges` | int | Rows on those edge tables where at least one FK column is NULL — the graph has invisible gaps. Surface a non-zero count to the user before generating code. |

This block counts edges **between tables**. It cannot tell you which node *TYPE column values* connect to which; for that, run the query in [discovery-queries.md](discovery-queries.md).

Presence of the block is a strong hint to model the edge table as a `Relationship` rather than a concept — the endpoints are the real entities. If several edge tables thread through the same node concept (A → B, B → C), an intermediate concept may be needed to bridge tiers.

## Reading `warnings[]`

Each entry is `{code, message, subject}`. `subject` names the table, column, or schema the warning is about, and is `null` when it concerns the whole run — it is what distinguishes several warnings sharing one `code`. A warning means the document is **usable but incomplete**; anything that would make it wrong is an error exit instead, so a document in your hands is trustworthy as far as it goes.

### `fk_candidate_ambiguous` — three tiers, three different responses

A column matched the PK candidate of two or more tables. The link is real, but its target is not decidable from the name, so **no edge was inferred**. Read the `message` to tell the tiers apart:

| What the message says | What it means | What to do |
|---|---|---|
| The candidates are **1:1 with each other** | The two targets are a perfect bijection, so containment can never separate them — either choice yields an equivalent model | Pick the target that names the entity in your ontology and move on. **Do not investigate** — there is no evidence that would decide it. |
| A **spread of containment fractions** (e.g. `ORDERS (0.998), ARCHIVE (0.412)`) | One target is far better supported than the others | Take the highest fraction. |
| Anything else — no fractions, or fractions that do not separate | The inference is genuinely unresolved | Investigate the join by hand, or scope the relationship out of this version. |

Do not silently drop an ambiguous column: without the edge, dropping it is indistinguishable from the column referencing nothing.

### The other six codes

| Code | Meaning | What to do |
|---|---|---|
| `empty_schema` | The schema exists and is readable but has no tables | Check the `--database` / `--schema` values before concluding the source is empty. |
| `declared_foreign_keys_unavailable` | The role could not read declared FK constraints; edges came from inference only | Expect fewer edges than the DDL declares. Verify any FK the model depends on. |
| `table_scan_failed` | One table's aggregate scan failed; its data-derived fields stay `null` | That table has no PK candidates, multiplicity, or distributions. Re-run scoped with `--table`, or design it from `data_type` alone. |
| `value_distribution_failed` | The low-cardinality probe failed for a column | No subtype or enum evidence for it. Do not conclude the column has no repeated values. |
| `graph_topology_failed` | The `--depth full` topology probe failed | `graph_topology` is unreliable or absent. Re-run at `--depth full`, scoped with `--table` to the edge tables; if it fails again, count edges by hand — one `COUNT(*)` per edge table, plus a `COUNT(*)` filtered to either FK column `IS NULL` for the broken-edge figure. `fk_candidates` still names which tables carry co-targeted FKs. |
| `containment_check_failed` | The probe that tie-breaks ambiguous FK matches failed | Every affected column falls back to reporting as ambiguous rather than being guessed at — treat those as the third tier above. |

## Sample — illustrative dump

A **synthesized** document for an illustrative `BOOKSTORE_DEMO.PUBLIC` schema (not a real dataset), at `--depth full`. Trimmed to two tables to stay readable; note that every key is present on every column, including the `null`s.

```json
{
  "schema_version": 1,
  "tool_version": "1.0.0",
  "depth": "full",
  "database": "BOOKSTORE_DEMO",
  "schema": "PUBLIC",
  "generated_at": null,
  "warnings": [
    {
      "code": "fk_candidate_ambiguous",
      "message": "RECOMMENDATIONS.BOOK_ID matches the PK candidate of BOOKS and EDITIONS, which are 1:1 with each other; either target yields an equivalent model.",
      "subject": "RECOMMENDATIONS.BOOK_ID"
    }
  ],
  "tables": [
    {
      "table_name": "AUTHORS",
      "row_count": 250,
      "pk_candidates": ["AUTHOR_ID"],
      "columns": [
        {"column_name": "AUTHOR_ID", "data_type": "TEXT", "ordinal_position": 1, "is_nullable": false, "numeric_precision": null, "numeric_scale": null, "rai_type": "String", "distinct_count": 250, "null_rate": 0.0, "numeric_range": null, "value_distribution": null},
        {"column_name": "BIRTH_YEAR", "data_type": "NUMBER", "ordinal_position": 2, "is_nullable": true, "numeric_precision": 38, "numeric_scale": 0, "rai_type": "Integer", "distinct_count": 132, "null_rate": 0.072, "numeric_range": {"min": 1832.0, "max": 1994.0}, "value_distribution": null},
        {"column_name": "DECEASED", "data_type": "BOOLEAN", "ordinal_position": 3, "is_nullable": false, "numeric_precision": null, "numeric_scale": null, "rai_type": "Boolean", "distinct_count": 2, "null_rate": 0.0, "numeric_range": null, "value_distribution": {"false": 198, "true": 52}}
      ]
    },
    {
      "table_name": "BOOKS",
      "row_count": 1800,
      "pk_candidates": ["BOOK_ID", "ISBN"],
      "columns": [
        {"column_name": "BOOK_ID", "data_type": "TEXT", "ordinal_position": 1, "is_nullable": false, "numeric_precision": null, "numeric_scale": null, "rai_type": "String", "distinct_count": 1800, "null_rate": 0.0, "numeric_range": null, "value_distribution": null},
        {"column_name": "AUTHOR_ID", "data_type": "TEXT", "ordinal_position": 2, "is_nullable": false, "numeric_precision": null, "numeric_scale": null, "rai_type": "String", "distinct_count": 245, "null_rate": 0.0, "numeric_range": null, "value_distribution": null},
        {"column_name": "GENRE", "data_type": "TEXT", "ordinal_position": 3, "is_nullable": false, "numeric_precision": null, "numeric_scale": null, "rai_type": "String", "distinct_count": 4, "null_rate": 0.0, "numeric_range": null, "value_distribution": {"FICTION": 920, "NON_FICTION": 540, "POETRY": 220, "REFERENCE": 120}},
        {"column_name": "PUBLISHED", "data_type": "TIMESTAMP_NTZ", "ordinal_position": 4, "is_nullable": true, "numeric_precision": null, "numeric_scale": null, "rai_type": "DateTime", "distinct_count": 1240, "null_rate": 0.004, "numeric_range": null, "value_distribution": null},
        {"column_name": "PRICE_USD", "data_type": "NUMBER", "ordinal_position": 5, "is_nullable": false, "numeric_precision": 18, "numeric_scale": 2, "rai_type": "Float", "distinct_count": 312, "null_rate": 0.0, "numeric_range": {"min": 4.99, "max": 129.5}, "value_distribution": null},
        {"column_name": "COVER_META", "data_type": "VARIANT", "ordinal_position": 6, "is_nullable": true, "numeric_precision": null, "numeric_scale": null, "rai_type": null, "distinct_count": 1795, "null_rate": 0.02, "numeric_range": null, "value_distribution": null}
      ]
    }
  ],
  "fk_candidates": [
    {"source_table": "BOOKS", "source_column": "AUTHOR_ID", "target_table": "AUTHORS", "target_column": "AUTHOR_ID", "multiplicity_class": "N:1"}
  ],
  "graph_topology": {
    "edge_type_pairs": [{"entity_type": "BOOKS", "count": 4200}],
    "broken_edges": 30
  }
}
```

What the sample demonstrates: `generated_at: null` (no `--stamp`); a `value_distribution` in **alphabetical** key order (`FICTION` leads alphabetically, but `FICTION` also happens to be the largest — do not rely on that coincidence, sort by count); `GENRE` as a subtype candidate; a multi-PK-candidate table (`BOOKS` — `ISBN` is unique by coincidence, so `BOOK_ID` is the identity); `PUBLISHED` as `TIMESTAMP_NTZ` → `DateTime`, not `Date`, despite reading like a date; `PRICE_USD` as `NUMBER` with `numeric_scale: 2` → `Float`; `COVER_META` as an unmapped VARIANT with `rai_type: null` but still listed; and a tier-1 `fk_candidate_ambiguous` warning whose message says the targets are 1:1 with each other — pick one and move on.

## Reading-order tips

- **PKs first.** Take the first `pk_candidates` entry per table; treat later entries as coincidence. An empty list on a junction table means compound identity, which is yours to establish.
- **Then `warnings[]`.** Cheaper to read seven warnings than to rediscover an undecidable FK by hand.
- **Categoricals via `value_distribution`.** A low-`distinct_count` column naming a kind or category is an enumeration-concept or subtype candidate: SKILL.md § Categorical values decides concept vs `String`; use `extends` only when each kind carries distinct properties.
- **Trust `multiplicity_class`.** `N:1` → Property on the source. `M:N` → Relationship, source is a junction. `null` → nothing to classify from; decide yourself.
- **Watch `null_rate`.** Close to 1.0 is a sparse column — model it as optional or scope it out.
- **`numeric_range` before any threshold.** Type alone cannot distinguish percentage points from a 0–1 fraction, or cents from dollars.
