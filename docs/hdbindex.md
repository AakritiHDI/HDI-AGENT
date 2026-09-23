# hdbindex — HANA HDI Index Artifact

## Overview
An `.hdbindex` file defines a **secondary index** on a deployed HDI table.
Indexes improve query performance by providing faster data access paths.

## File Extension
`.hdbindex`

## File Path in Container
`src/<INDEX_NAME>.hdbindex`

## Syntax

```
INDEX "<INDEX_NAME>" ON "<TABLE_NAME>" (
    "<COLUMN_1>" [ASC | DESC],
    "<COLUMN_2>" [ASC | DESC],
    ...
)
[UNIQUE]
[INVERTED VALUE | INVERTED HASH | INVERTED INDIVIDUAL]
```

## Index Types

| Type | Best For |
|------|----------|
| `INVERTED VALUE` (default) | Range queries, ORDER BY, column-store |
| `INVERTED HASH` | Equality queries (=, IN), high cardinality |
| `INVERTED INDIVIDUAL` | Per-column individual hash |
| `UNIQUE` | Enforce uniqueness constraint |
| `CPBTREE` | Row-store tables (B-tree) |

## Examples

### Basic non-unique index
```
INDEX "IDX_EMPLOYEES_DEPT" ON "EMPLOYEES" (
    "DEPARTMENT_ID"
)
```

### Composite index
```
INDEX "IDX_ORDERS_DATE_STATUS" ON "ORDERS" (
    "ORDER_DATE" DESC,
    "STATUS"
)
```

### Unique index (enforces uniqueness)
```
INDEX "UX_EMPLOYEES_EMAIL" ON "EMPLOYEES" (
    "EMAIL"
)
UNIQUE
```

### Hash index (for equality lookups)
```
INDEX "IDX_PRODUCTS_SKU" ON "PRODUCTS" (
    "SKU_CODE"
)
INVERTED HASH
```

## Rules
- Do **NOT** use `CREATE INDEX` SQL syntax.
- The referenced table must be **deployed first** before the index can be deployed.
- Deploy the table, then deploy the index in a separate or subsequent MAKE call.
- `UNIQUE` indexes will fail deployment if duplicate values already exist.
- Column-store tables (COLUMN TABLE) use INVERTED indexes.
- Row-store tables (ROW TABLE) use `CPBTREE`.