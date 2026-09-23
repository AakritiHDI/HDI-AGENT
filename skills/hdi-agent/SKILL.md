---
name: hdi-agent
description: >
  Use when creating, deploying, or managing SAP HANA HDI (HANA Deployment Infrastructure)
  artifacts programmatically via the _SYS_DI SQL API, or when working with ANY of the
  18+ HDI design-time artifact types: .hdbtable, .hdbmigrationtable, .hdbview,
  .hdbcalculationview, .hdbprocedure, .hdbfunction, .hdbsequence, .hdbsynonym,
  .hdbsynonymconfig, .hdbrole, .hdbgrants, .hdbstructuredprivilege, .hdbindex,
  .hdbconstraint, .hdbtabletype, .hdbtabledata, .hdbvirtualtable, .hdblibrary,
  .hdbgraphworkspace, .hdbschedulerjob, .hdbapplicationtime, .hdbeshconfig,
  .hdbtrigger, .hdblogicalschema, .hdbanalyticprivilege. Also use for: HDI container
  lifecycle (create, grant, drop), multi-user HDI setups, cross-container synonyms,
  remote source virtual tables, structured privilege + role companion pattern, and
  migration table-based schema evolution.
metadata:
  version: "1.0.0"
  keywords:
    - SAP HANA Cloud
    - HDI
    - HDI container
    - _SYS_DI
    - hdbtable
    - hdbmigrationtable
    - hdbcalculationview
    - hdbprocedure
    - hdbfunction
    - hdbsequence
    - hdbsynonym
    - hdbrole
    - hdbgrants
    - hdbstructuredprivilege
    - hdbvirtualtable
    - hdbgraphworkspace
    - hdblibrary
    - SQLScript
    - column store
    - hdi-deploy
    - DI.WRITE
    - DI.MAKE
    - DI.DELETE
    - multi-user HDI
    - cross-container synonym
    - remote source
    - migration table
  related:
    hana-cloud-native: basic HDI best practices and common artifact types
    btp-deployment: HDI container service binding in mta.yaml
    performance: query tuning and column-store optimization
    cds-modeling: how CAP CDS entities compile to HANA tables
    multitenancy: one HDI container per tenant pattern
---

# SAP HANA HDI Agent — Complete Artifact & Container Reference

> **HDI Reference**: https://help.sap.com/docs/HANA_CLOUD_DATABASE/c2cc2e43458d4abda6788049c58143dc
> **_SYS_DI API**: https://help.sap.com/docs/HANA_CLOUD_DATABASE/c2b99f19e9264c4d9ae9221b22f6f589
> **SQLScript Reference**: https://help.sap.com/docs/HANA_CLOUD_DATABASE/d1cb63c8dd8e4c35a0f18aef632687f0

SAP HANA HDI (HANA Deployment Infrastructure) deploys design-time source files
**transactionally** into isolated **HDI containers** via the `_SYS_DI` SQL API.
Objects are created by name in a container — never via raw `CREATE TABLE` DDL.

---

## HDI Container Lifecycle (via `_SYS_DI` SQL API)

For programmatic / agent-driven setups (no BTP service binding), create containers
manually through the `_SYS_DI` stored procedures.

### 1. Create container group
```sql
CALL _SYS_DI.CREATE_CONTAINER_GROUP('MY_GROUP', _SYS_DI.T_NO_PARAMETERS, ?, ?, ?);
```

### 2. Grant group admin to a user
```sql
CALL _SYS_DI.GRANT_CONTAINER_GROUP_API_PRIVILEGES(
  'MY_GROUP',
  SELECT * FROM _SYS_DI.T_DEFAULT_CONTAINER_GROUP_ADMIN_PRIVILEGES,
  _SYS_DI.T_NO_PARAMETERS, ?, ?, ?
);
```

### 3. Create container in the group
```sql
CALL _SYS_DI#MY_GROUP.CREATE_CONTAINER('MY_CONTAINER', _SYS_DI.T_NO_PARAMETERS, ?, ?, ?);
```

### 4. Grant DI API access to the container user
```sql
CALL _SYS_DI#MY_GROUP.GRANT_CONTAINER_API_PRIVILEGES(
  'MY_CONTAINER',
  SELECT * FROM _SYS_DI.T_DEFAULT_CONTAINER_ADMIN_PRIVILEGES WHERE PRIVILEGE_NAME NOT IN ('CREATE ANY','DROP','ALTER'),
  _SYS_DI.T_NO_PARAMETERS, ?, ?, ?
);
```

### 5. Write, deploy, and drop artifacts
```sql
-- Stage a file
CALL _SYS_DI#MY_CONTAINER.WRITE(
  SELECT 'src/BOOK.hdbtable' AS PATH, TO_BLOB('<DDL>') AS CONTENT FROM DUMMY,
  _SYS_DI.T_NO_PARAMETERS, ?, ?, ?
);
-- Deploy everything staged
CALL _SYS_DI#MY_CONTAINER.MAKE(
  _SYS_DI.T_NO_DELTA_DEPLOY_FILES, _SYS_DI.T_NO_UNDEPLOY_FILES,
  _SYS_DI.T_NO_PARAMETERS, ?, ?, ?
);
-- Delete a file from the work area then MAKE to undeploy
CALL _SYS_DI#MY_CONTAINER.DELETE(
  SELECT 'src/BOOK.hdbtable' AS PATH FROM DUMMY,
  _SYS_DI.T_NO_PARAMETERS, ?, ?, ?
);
```

### Multi-user setup
In multi-user setups distinguish two roles:
- **HANA_USER** (`HDI_USER`) — the database connection user; owns the DI API calls.
- **HDI_USERNAME** (e.g. `AAK`, `SUSHANT`) — the business user doing data preview in DBX.

Grant schema privileges to **both** so each user can query the runtime schema directly
without switching to `HDI_USER`:
```sql
GRANT SELECT, INSERT, UPDATE, DELETE, EXECUTE, CREATE TEMPORARY TABLE
  ON SCHEMA "MY_CONTAINER"
  TO "AAK";
```

---

## Artifact Reference

### `.hdbtable` — Column table (default)

```sql
COLUMN TABLE "BOOK" (
  "ID"        INTEGER NOT NULL,
  "TITLE"     NVARCHAR(200) NOT NULL,
  "AUTHOR_ID" INTEGER,
  "PRICE"     DECIMAL(9,2),
  PRIMARY KEY ("ID")
)
```
Always use `COLUMN TABLE` unless you have a high-write, single-row-lookup case.
Never use `SELECT *` in views or procedures over column tables.

---

### `.hdbmigrationtable` — Schema-evolution table

Use instead of `.hdbtable` when you need to **alter columns** across deploys.
HDI blocks data-losing changes on `.hdbtable`; migration tables allow controlled DDL.

```sql
== version = 1
COLUMN TABLE "ORDERS" (
  "ID"     INTEGER NOT NULL,
  "STATUS" NVARCHAR(20),
  PRIMARY KEY ("ID")
);

== version = 2
ALTER TABLE "ORDERS" ADD ("TOTAL" DECIMAL(12,2));
```
Each `== version` block runs exactly once in sequence. Never edit past versions.

---

### `.hdbview` — SQL view

```sql
VIEW "BOOK_DETAILS" AS
  SELECT b."ID", b."TITLE", a."NAME" AS AUTHOR
  FROM "BOOK" b
  JOIN "AUTHOR" a ON b."AUTHOR_ID" = a."ID"
```

---

### `.hdbcalculationview` — Analytical calculation view

Calculation views model analytical logic (star joins, aggregations). Types:
- **Dimension** — master data; no measure node.
- **Cube** — facts with aggregatable measures.

Authored as XML in SAP Business Application Studio. Key rules:
- Push filters down to the lowest join node.
- Join only on indexed key columns.
- Use `KEEP FLAG` for nullable outer-join attributes.

---

### `.hdbprocedure` — SQLScript stored procedure

```sql
PROCEDURE "GET_ORDERS" (
  IN  p_status  NVARCHAR(20),
  OUT orders    TABLE ("ID" INTEGER, "TOTAL" DECIMAL(12,2))
)
LANGUAGE SQLSCRIPT
SQL SECURITY INVOKER
AS
BEGIN
  orders = SELECT "ID", "TOTAL"
           FROM "ORDERS"
           WHERE "STATUS" = :p_status;
END;
```
Use declarative table variables (`orders = SELECT …`) not cursor loops — the optimizer
parallelizes set-based assignments.

---

### `.hdbfunction` — Scalar or table function

```sql
FUNCTION "DISCOUNT_PRICE"(p_price DECIMAL(9,2), p_pct INTEGER)
RETURNS DECIMAL(9,2)
LANGUAGE SQLSCRIPT
SQL SECURITY INVOKER AS
BEGIN
  RETURN :p_price * (1 - :p_pct / 100.0);
END;
```

---

### `.hdbtrigger` — DML trigger

```sql
TRIGGER "ORDERS_AUDIT_INSERT"
AFTER INSERT ON "ORDERS"
REFERENCING NEW ROW AS new_row
FOR EACH ROW
BEGIN
  INSERT INTO "ORDERS_AUDIT"("ORDER_ID","ACTION","TS")
  VALUES(:new_row."ID", 'INSERT', CURRENT_TIMESTAMP);
END
```

---

### `.hdbsequence` — Sequence

```sql
SEQUENCE "ORDER_SEQ"
  START WITH 1
  INCREMENT BY 1
  MAXVALUE 9999999
  NO CYCLE
  CACHE 20
```

---

### `.hdbindex` — Secondary index

```sql
INDEX "IDX_ORDERS_STATUS" ON "ORDERS" ("STATUS" ASC)
```
Add indexes only on columns used in `WHERE` / `JOIN` predicates. Column store already
organizes data by column — over-indexing wastes storage.

---

### `.hdbconstraint` — Table constraint (referential integrity)

```sql
ALTER TABLE "ORDER_ITEM"
  ADD CONSTRAINT "FK_ORDER"
  FOREIGN KEY ("ORDER_ID") REFERENCES "ORDERS"("ID")
  ON DELETE CASCADE
```

---

### `.hdbtabletype` — Reusable TABLE type

```sql
TABLE TYPE "TT_ORDERS" (
  "ORDER_ID" INTEGER,
  "TOTAL"    DECIMAL(12,2)
)
```
Use as parameter types in procedures to avoid repeating the schema inline.

---

### `.hdbtabledata` — Static seed / reference data

```sql
IMPORT INTO "STATUS_CODES"
(
  "CODE", "LABEL"
)
VALUES
(
  'OPEN',   'Open',
  'CLOSED', 'Closed',
  'VOID',   'Void'
)
```
Runs on every deploy; use for static lookup tables. Use `UPDATE` mode for mutable data.

---

### `.hdbsynonym` — Cross-container object alias

Never hardcode another container's schema name. Use a synonym resolved at deploy time.

```json
{
  "ExternalOrders": {
    "target": { "object": "ORDERS", "schema": "SALES_CONTAINER" }
  }
}
```

**Grant prerequisites** — before deploying:
```sql
-- Grant SELECT on source schema to the target container's technical users
GRANT SELECT, EXECUTE ON SCHEMA "SALES_CONTAINER" TO "MY_CONTAINER#OO";
GRANT SELECT, EXECUTE ON SCHEMA "SALES_CONTAINER" TO "MY_CONTAINER#DI";
-- Also grant to end-user who will query via the synonym
GRANT SELECT, EXECUTE ON SCHEMA "SALES_CONTAINER" TO "AAK";
```
Without the `#OO`/`#DI` grants, `DI.MAKE` fails with *object not found*.

---

### `.hdbsynonymconfig` — Synonym configuration (env-specific)

Maps synonym logical names to environment-specific targets (schema/remote source).
Used with `hdiconfig` to keep artifact files environment-agnostic.

---

### `.hdbrole` — Design-time role

Grant access through roles, never to individual users at design time.

```json
{
  "role": {
    "name": "APP_USER_ROLE",
    "object_privileges": [
      { "name": "BOOK",  "type": "TABLE",     "privileges": ["SELECT"] },
      { "name": "ORDERS","type": "TABLE",     "privileges": ["SELECT","INSERT","UPDATE"] }
    ],
    "schema_analytic_privileges": [
      { "privilege_name": "EMPLOYEE_DEPT_FILTER" }
    ]
  }
}
```

---

### `.hdbgrants` — External privilege grants to the container's owner

Grants privileges on **external objects** (outside the container) to the container's
`#OO` technical user so it can reference them during `MAKE`.

```json
{
  "Grants": {
    "remote_sources": [
      {
        "name": "FED_SDA_HC",
        "privileges": ["CREATE VIRTUAL TABLE"]
      }
    ],
    "schema_privileges": [
      {
        "name": "EXTERNAL_SCHEMA",
        "privileges": ["SELECT", "EXECUTE"]
      }
    ]
  }
}
```

---

### `.hdbstructuredprivilege` — Row-level analytic privilege

Controls row-level visibility in calculation views.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<StructuredPrivilege:structuredPrivilege
    xmlns:StructuredPrivilege="http://www.sap.com/ndb/BiModelStructuredPrivilege.ecore">
  <attributes name="DEPT_ID" operatorCode="EQ">
    <value type="static">10</value>
  </attributes>
</StructuredPrivilege:structuredPrivilege>
```

**Companion role pattern** — after deploying an SP, create and deploy an `.hdbrole`
that references it via `schema_analytic_privileges`, then grant the role:
```sql
CALL _SYS_DI#MY_CONTAINER.GRANT_CONTAINER_SCHEMA_ROLE(
  'MY_FILTER_ROLE', '', 'HDI_USER', _SYS_DI.T_NO_PARAMETERS, ?, ?, ?
);
```

---

### `.hdbanalyticprivilege` — SQL-based analytic privilege (deprecated path)

Older approach; prefer `.hdbstructuredprivilege` for new development.

---

### `.hdbvirtualtable` — Virtual table over a remote source

```sql
VIRTUAL TABLE "VT_REMOTE_SALES"
  AT "FED_SDA_HC"."REMOTE_SCHEMA"."SALES_FACT"
```

**Setup sequence**:
1. Grant `CREATE VIRTUAL TABLE ON REMOTE SOURCE` to `HDI_USER` (requires privileged user).
2. Deploy `.hdbgrants` referencing the remote source.
3. Deploy `.hdbvirtualtable`.

---

### `.hdblibrary` — SQLScript reusable library

```sql
LIBRARY "DATE_UTILS"
LANGUAGE SQLSCRIPT
AS
BEGIN
  PUBLIC FUNCTION fiscal_year(p_date DATE) RETURNS INTEGER AS
  BEGIN
    RETURN YEAR(:p_date) + CASE WHEN MONTH(:p_date) >= 4 THEN 1 ELSE 0 END;
  END;
END;
```
Requires the container to have default HDI libraries configured (`.hdiconfig` with
`com.sap.hana.di.library` plugin) and default db libraries enabled, otherwise `MAKE`
fails with *"the file requires db://DOUBLE which is not provided"*.

---

### `.hdbgraphworkspace` — Graph workspace

```sql
GRAPH WORKSPACE "SUPPLY_CHAIN"
  EDGE TABLE "SHIPMENT"
    SOURCE COLUMN  "FROM_ID"
    TARGET COLUMN  "TO_ID"
    KEY COLUMN     "ID"
  VERTEX TABLE "LOCATION"
    KEY COLUMN "ID"
```

---

### `.hdbschedulerjob` — Scheduled job

```json
{
  "job": {
    "description": "Nightly ETL",
    "action": "CALL \"ETL_PROCEDURE\"()",
    "schedules": [
      { "description": "Every night at 02:00", "cron": "* * * 2 0 0 0" }
    ]
  }
}
```

---

### `.hdblogicalschema` — Logical schema mapping

Maps a logical schema name used in `.hdbsynonym` to a physical schema, resolved by the
`logicalschema` service binding at deploy time (BTP pattern).

---

### `.hdbapplicationtime` — Application-time (bitemporal) table

Adds an `APPLICATION_TIME` period for bitemporal / valid-time history.

```sql
COLUMN TABLE "CONTRACT" (
  "ID"         INTEGER NOT NULL,
  "VALUE"      DECIMAL(12,2),
  "VALID_FROM" DATE NOT NULL,
  "VALID_TO"   DATE NOT NULL,
  PRIMARY KEY("ID", "VALID_FROM", "VALID_TO"),
  PERIOD FOR APPLICATION_TIME("VALID_FROM", "VALID_TO")
)
```

---

### `.hdbeshconfig` — Enterprise Search configuration

Configures SAP HANA Enterprise Search for full-text / search-UI scenarios.

---

## Common mistakes to avoid

| ❌ Anti-pattern | ✅ Correct approach |
|---|---|
| Raw `CREATE TABLE` in the schema | Deploy `.hdbtable` via HDI — changes are transactional |
| Altering columns in `.hdbtable` | Use `.hdbmigrationtable` for controlled column changes |
| `SELECT *` in views / procedures | Project only needed columns — column store rewards narrow reads |
| Row-by-row cursor loops | Declarative table variables — optimizer parallelizes set ops |
| `ROW TABLE` for analytics | `COLUMN TABLE` (HANA default) unless single-row high-write |
| Hardcoding another container's schema | `.hdbsynonym` resolved at deploy time |
| Granting to individual users at design time | Bundle in `.hdbrole`, grant the role |
| Deploying synonym without grants | Grant `SELECT` on source schema to `#OO` and `#DI` first |
| Editing objects directly in the runtime schema | All changes through HDI design-time source |
| Missing `#DI` / `#OO` grants for synonyms | Both technical users need access for `MAKE` to succeed |
| Deploying `.hdblibrary` without default lib config | Enable default db libraries in `.hdiconfig` first |
| Structured privilege without companion role | Create and deploy `.hdbrole` with `schema_analytic_privileges`, then grant it |

---

## Artifact → file extension quick reference

| Artifact | Extension |
|---|---|
| Column table | `.hdbtable` |
| Schema-evolution table | `.hdbmigrationtable` |
| SQL view | `.hdbview` |
| Calculation view | `.hdbcalculationview` |
| Stored procedure | `.hdbprocedure` |
| Scalar / table function | `.hdbfunction` |
| DML trigger | `.hdbtrigger` |
| Sequence | `.hdbsequence` |
| Secondary index | `.hdbindex` |
| Referential constraint | `.hdbconstraint` |
| TABLE type | `.hdbtabletype` |
| Seed / reference data | `.hdbtabledata` |
| Synonym | `.hdbsynonym` |
| Synonym config (env) | `.hdbsynonymconfig` |
| Design-time role | `.hdbrole` |
| External privilege grants | `.hdbgrants` |
| Structured privilege (row-level) | `.hdbstructuredprivilege` |
| SQL analytic privilege | `.hdbanalyticprivilege` |
| Virtual table (remote source) | `.hdbvirtualtable` |
| SQLScript library | `.hdblibrary` |
| Graph workspace | `.hdbgraphworkspace` |
| Scheduler job | `.hdbschedulerjob` |
| Logical schema mapping | `.hdblogicalschema` |
| Application-time (bitemporal) | `.hdbapplicationtime` |
| Enterprise Search config | `.hdbeshconfig` |
