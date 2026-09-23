# hdbdropcreatetable — HANA HDI Drop-Create Table Artifact

## Overview
An `.hdbdropcreatetable` file uses a **DROP + CREATE deployment strategy** — the table is always dropped and recreated on every DI.MAKE. Use only for staging/temp tables where data loss on redeploy is acceptable.

## File Extension
`.hdbdropcreatetable`

## File Path in Container
`src/<TABLE_NAME>.hdbdropcreatetable`

## Syntax
Identical DDL syntax to `.hdbtable`:
```
COLUMN TABLE "<TableName>" (
    "<COL>" <TYPE> [NOT NULL] [DEFAULT <val>],
    ...
    [PRIMARY KEY ("<COL>")]
)
```

## Rules
- Do **NOT** use `CREATE TABLE` — start directly with `COLUMN TABLE`
- **ALL data is LOST on every redeploy** — never use for user or transactional data
- Suitable for ETL staging areas, config snapshots, or test fixtures repopulated via `.hdbtabledata`

## Examples

### ETL staging table
```
COLUMN TABLE "STAGING_LOAD"(
    "BATCH_ID"    INTEGER NOT NULL,
    "SRC_ROW"     NCLOB,
    "LOADED_AT"   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY ("BATCH_ID")
)
```

### Configuration snapshot table
```
COLUMN TABLE "CONFIG_SNAPSHOT"(
    "KEY"   NVARCHAR(256) NOT NULL,
    "VALUE" NVARCHAR(1024),
    PRIMARY KEY ("KEY")
)
```

### Temporary calculation table
```
COLUMN TABLE "TEMP_AGGREGATES"(
    "PERIOD"    VARCHAR(7),
    "REGION"    NVARCHAR(50),
    "TOTAL"     DECIMAL(15,2),
    "ROW_COUNT" INTEGER
)
```

## When to Use vs Alternatives

| Use Case | Artifact Type |
|----------|---------------|
| Production table (keep data) | `.hdbtable` |
| Production table (schema changes needed) | `.hdbmigrationtable` |
| Staging/temp table (data loss OK) | `.hdbdropcreatetable` |

## Notes
- Combine with `.hdbtabledata` to repopulate the table with seed data after each deploy
- Great for test fixtures that need a clean state on every deployment
- The DROP + CREATE happens transparently — no manual DROP statement needed