# hdbsystemversioning — HANA HDI System Versioning Artifact

## Overview
An `.hdbsystemversioning` file declares a **system-versioned table pair**: a main table and a history table. This enables `FOR SYSTEM_TIME` queries for point-in-time access to historical data (bi-temporal tables).

## File Extension
`.hdbsystemversioning`

## File Path in Container
`src/<NAME>.hdbsystemversioning`

## Syntax
JSON file declaring the history table and versioning settings.

```json
{
  "system_versioning": {
    "history_table": "<HISTORY_TABLE_NAME>",
    "data_consistency": "PHYSICAL",
    "public": true
  }
}
```

## Required Companion Tables

### Main table (must have PERIOD FOR SYSTEM_TIME)
```
COLUMN TABLE "TYPES"(
    "ID"           SMALLINT,
    "COUNTRY"      VARCHAR(30),
    "BOOLEAN_VAL"  BOOLEAN,
    "VALID_FROM"   TIMESTAMP NOT NULL GENERATED ALWAYS AS ROW START,
    "VALID_TO"     TIMESTAMP NOT NULL GENERATED ALWAYS AS ROW END,
    PERIOD FOR SYSTEM_TIME("VALID_FROM","VALID_TO")
) WITH SYSTEM VERSIONING
```

### History table (same structure without PERIOD clause)
```
COLUMN TABLE "TYPES_HISTORY"(
    "ID"           SMALLINT,
    "COUNTRY"      VARCHAR(30),
    "BOOLEAN_VAL"  BOOLEAN,
    "VALID_FROM"   TIMESTAMP NOT NULL,
    "VALID_TO"     TIMESTAMP NOT NULL
)
```

### System versioning artifact (links main to history)
```json
{
  "system_versioning": {
    "history_table": "TYPES_HISTORY",
    "data_consistency": "PHYSICAL",
    "public": true
  }
}
```

## Querying Historical Data
After deployment:
```sql
-- Point-in-time query
SELECT * FROM "AAK_CONTAINER"."TYPES"
FOR SYSTEM_TIME AS OF TIMESTAMP '2024-01-01 00:00:00';

-- Range query
SELECT * FROM "AAK_CONTAINER"."TYPES"
FOR SYSTEM_TIME BETWEEN '2024-01-01' AND '2024-12-31';

-- All versions including current
SELECT * FROM "AAK_CONTAINER"."TYPES"
FOR SYSTEM_TIME ALL;
```

## Deployment Order
Deploy all three artifacts together:
1. `src/TYPES.hdbtable` (main table with PERIOD FOR SYSTEM_TIME)
2. `src/TYPES_HISTORY.hdbtable` (history table)
3. `src/TYPES_SV.hdbsystemversioning` (linking artifact)

## Notes
- The main table must include `VALID_FROM` and `VALID_TO` columns with `GENERATED ALWAYS AS ROW START/END`
- The history table has the same columns but WITHOUT the PERIOD clause
- `data_consistency: "PHYSICAL"` ensures history is stored in the database (not just logically)
- System versioning is managed by HANA — no manual history inserts needed