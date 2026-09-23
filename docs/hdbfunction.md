# hdbfunction — HANA HDI SQLScript Function Artifact

## Overview
An `.hdbfunction` file defines a **SQLScript table function (TUDF) or scalar function** as a design-time artifact in an HDI container.

## File Extension
`.hdbfunction`

## File Path in Container
`src/<FUNCTION_NAME>.hdbfunction`

## Syntax

### Scalar Function (multiple return values)
```
FUNCTION "<Name>" (IN <param> <type>, ...)
RETURNS <result1> <type>, <result2> <type>
LANGUAGE SQLSCRIPT
AS
BEGIN
  <result1> := <expr>;
  <result2> := <expr>;
END
```

### Table Function (TUDF)
```
FUNCTION "<Name>" (IN <param> <type>, ...)
RETURNS TABLE (<col1> <type>, <col2> <type>, ...)
LANGUAGE SQLSCRIPT
SQL SECURITY INVOKER
AS
BEGIN
    RETURN SELECT ...;
END;
```

## Rules
- Do **NOT** use `CREATE FUNCTION` — start directly with `FUNCTION`
- Always include `LANGUAGE SQLSCRIPT`
- Reference parameters inside body with `:param_name` (colon prefix)
- Use `SQL SECURITY INVOKER` (recommended) or `SQL SECURITY DEFINER`
- Add `READS SQL DATA` for read-only table functions

## Examples

### Scalar function — arithmetic
```
FUNCTION "ADD" (X DOUBLE, Y DOUBLE)
RETURNS RESULT_ADD DOUBLE, RESULT_MUL DOUBLE
LANGUAGE SQLSCRIPT
AS
BEGIN
  RESULT_ADD := :X + :Y;
  RESULT_MUL := :X * :Y;
END
```

### Table function — temporal query
```
FUNCTION "returnDataBetween"(START_TIME TIMESTAMP, END_TIME TIMESTAMP)
RETURNS TABLE(
    ID           SMALLINT,
    COUNTRY      VARCHAR(30),
    BOOLEAN_VAL  BOOLEAN,
    VALID_FROM   TIMESTAMP,
    VALID_TO     TIMESTAMP
)
LANGUAGE SQLSCRIPT
SQL SECURITY INVOKER AS
BEGIN
    RETURN SELECT ID, COUNTRY, BOOLEAN_VAL, VALID_FROM, VALID_TO
           FROM "TYPES"
           FOR SYSTEM_TIME BETWEEN :START_TIME AND :END_TIME;
END
```

### Table function — simple SELECT
```
FUNCTION "UDF" (IN A INTEGER, IN B BIGINT)
RETURNS TABLE (C INTEGER)
LANGUAGE SQLSCRIPT AS
BEGIN
    RETURN SELECT 1 AS C FROM "ALL_TYPES_TABLE";
END;
```

## Notes
- Table functions can be used as data sources in Calculation Views (`type="TABLE_FUNCTION"`)
- Scalar functions can return multiple named values
- Use cursor syntax for row-by-row processing