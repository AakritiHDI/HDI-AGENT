# hdbprocedure — HANA HDI Stored Procedure Artifact

## Overview
An `.hdbprocedure` file defines a **SQLScript stored procedure** with IN/OUT parameters as a design-time artifact in an HDI container.

## File Extension
`.hdbprocedure`

## File Path in Container
`src/<PROCEDURE_NAME>.hdbprocedure`

## Syntax
```
PROCEDURE "<Name>" (
    IN  <param> <type>,
    OUT <param> <type>
)
LANGUAGE SQLSCRIPT
[SQL SECURITY INVOKER|DEFINER]
AS
BEGIN
    -- body
END
```

## Rules
- Do **NOT** use `CREATE PROCEDURE` — start directly with `PROCEDURE`
- Always include `LANGUAGE SQLSCRIPT`
- Reference parameters inside body with `:param_name` (colon prefix)
- Use `SQL SECURITY INVOKER` (runs as calling user) or `SQL SECURITY DEFINER` (runs as OO user)
- OUT parameters for table results can use a table type (`.hdbtabletype`) or inline `TABLE(...)` syntax

## Examples

### Procedure with IN and OUT scalar parameters
```
PROCEDURE "PROC_EXAMPLE"(
    IN  P_ID    INTEGER,
    OUT P_NAME  NVARCHAR(100)
)
LANGUAGE SQLSCRIPT AS
BEGIN
    SELECT NAME INTO P_NAME FROM "INSTRUCTOR"
    WHERE INSTRUCTORID = :P_ID;
END
```

### Procedure with temporal query and table OUT parameter
```
PROCEDURE "getCurrentData"(
    IN  TIME_ST   TIMESTAMP,
    OUT OUT_TAB   "TYPES"
)
LANGUAGE SQLSCRIPT
SQL SECURITY INVOKER
AS
BEGIN
    OUT_TAB = SELECT * FROM "TYPES"
              FOR SYSTEM_TIME AS OF :TIME_ST;
END
```

### Procedure with cursor
```
PROCEDURE "PROC_TOP_EARNER"(
    IN  P_DEPT   NVARCHAR(50),
    OUT P_NAME   NVARCHAR(100),
    OUT P_SALARY DECIMAL(15,2)
)
LANGUAGE SQLSCRIPT AS
BEGIN
    SELECT FIRST_NAME || ' ' || LAST_NAME, SALARY
    INTO P_NAME, P_SALARY
    FROM "EMPLOYEES"
    WHERE DEPARTMENT = :P_DEPT
    ORDER BY SALARY DESC
    LIMIT 1;
END
```

### Data processing procedure (no OUT params)
```
PROCEDURE "PROC_CLEANUP_STAGING"()
LANGUAGE SQLSCRIPT AS
BEGIN
    DELETE FROM "STAGING_LOAD"
    WHERE LOADED_AT < ADD_DAYS(CURRENT_TIMESTAMP, -7);
END
```

## Calling a Procedure
```sql
DECLARE P_NAME NVARCHAR(100);
CALL "AAK_CONTAINER"."PROC_EXAMPLE"(1, P_NAME);
SELECT :P_NAME FROM DUMMY;
```

## Notes
- Procedures can be called by scheduler jobs (`.hdbschedulerjob`)
- For returning result sets, use table functions (`.hdbfunction`) instead
- Deploy table types (`.hdbtabletype`) before procedures that use them as OUT parameters
- To drop: use `drop_artifact` with `file_path = "src/<PROCEDURE_NAME>.hdbprocedure"`