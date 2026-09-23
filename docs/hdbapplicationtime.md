# hdbapplicationtime — HANA HDI Application Time Period Artifact

## Overview
An `.hdbapplicationtime` file declares an **application-time period** on a table — enables bi-temporal queries using `FOR APPLICATION_TIME AS OF` / `BETWEEN`. The period is user-managed (unlike system versioning which is automatic).

## File Extension
`.hdbapplicationtime`

## File Path in Container
`src/<NAME>.hdbapplicationtime`

## Syntax
JSON file referencing the table and its VALID_FROM / VALID_TO columns.

```json
{
  "application_time": {
    "table": "<TABLE_NAME>",
    "from_column": "<VALID_FROM_COL>",
    "to_column": "<VALID_TO_COL>"
  }
}
```

## Required Companion Table
The table must have VALID_FROM and VALID_TO columns as part of its primary key:

```
COLUMN TABLE "PRODUCTS_APPTIME"(
    "PRODUCT_ID"   INTEGER NOT NULL,
    "PRICE"        DECIMAL(10,2),
    "VALID_FROM"   DATE NOT NULL,
    "VALID_TO"     DATE NOT NULL,
    PRIMARY KEY ("PRODUCT_ID", "VALID_FROM")
)
```

## Application Time Artifact
```json
{
  "application_time": {
    "table": "PRODUCTS_APPTIME",
    "from_column": "VALID_FROM",
    "to_column": "VALID_TO"
  }
}
```

## Querying with Application Time
```sql
-- Point-in-time query
SELECT * FROM "AAK_CONTAINER"."PRODUCTS_APPTIME"
FOR APPLICATION_TIME AS OF DATE '2024-06-01';

-- Period overlap query
SELECT * FROM "AAK_CONTAINER"."PRODUCTS_APPTIME"
FOR APPLICATION_TIME BETWEEN DATE '2024-01-01' AND DATE '2024-12-31';

-- All versions
SELECT * FROM "AAK_CONTAINER"."PRODUCTS_APPTIME";
```

## Inserting Time-Period Records
```sql
-- Insert price valid for first half of 2024
INSERT INTO "AAK_CONTAINER"."PRODUCTS_APPTIME"
VALUES (1, 999.99, '2024-01-01', '2024-06-30');

-- Insert updated price valid from July 2024
INSERT INTO "AAK_CONTAINER"."PRODUCTS_APPTIME"
VALUES (1, 1099.99, '2024-07-01', '2024-12-31');
```

## Notes
- Application-time periods are **user-managed** — you INSERT/UPDATE/DELETE records manually
- The from/to columns must be DATE, SECONDDATE, or TIMESTAMP
- Deploy the `.hdbapplicationtime` alongside the `.hdbtable` it references
- For system-managed time tracking, use `.hdbsystemversioning` instead