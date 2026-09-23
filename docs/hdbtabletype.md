# hdbtabletype — HANA HDI Table Type Artifact

## Overview
An `.hdbtabletype` file defines a **table type** for use as parameters in stored procedures and functions.

## File Extension
`.hdbtabletype`

## File Path in Container
`src/<TYPE_NAME>.hdbtabletype`

## Syntax
```
TYPE "<TypeName>" AS TABLE (
    "<COL1>" <TYPE>,
    "<COL2>" <TYPE>,
    ...
)
```

## Rules
- Do **NOT** use `CREATE TYPE` — start directly with `TYPE`
- Table types are used as IN/OUT parameters in procedures and functions
- Must be deployed before the procedures/functions that reference them

## Examples

### Order table type
```
TYPE "ORDER_TYPE" AS TABLE (
    "ORDERNUMBER"    INTEGER,
    "ORDERDATE"      TIMESTAMP,
    "STATUS"         VARCHAR(15),
    "CUSTOMERNUMBER" INTEGER
)
```

### Product result type
```
TYPE "PRODUCT_RESULT_TYPE" AS TABLE (
    "PRODUCT_ID"   INTEGER,
    "PRODUCT_NAME" NVARCHAR(100),
    "PRICE"        DECIMAL(10,2),
    "STOCK"        INTEGER
)
```

### Employee record type
```
TYPE "EMPLOYEE_TYPE" AS TABLE (
    "EMPLOYEE_ID" INTEGER,
    "FIRST_NAME"  NVARCHAR(100),
    "LAST_NAME"   NVARCHAR(100),
    "DEPARTMENT"  NVARCHAR(50),
    "SALARY"      DECIMAL(15,2)
)
```

## Usage in Stored Procedures
```
PROCEDURE "GET_ORDERS" (
    IN  P_CUSTOMER_ID INTEGER,
    OUT P_ORDERS      "ORDER_TYPE"
)
LANGUAGE SQLSCRIPT AS
BEGIN
    P_ORDERS = SELECT ORDERNUMBER, ORDERDATE, STATUS, CUSTOMERNUMBER
               FROM "ORDERS"
               WHERE CUSTOMERNUMBER = :P_CUSTOMER_ID;
END
```

## Notes
- Table types are referenced inside procedures using the quoted type name
- Deploy table types **before** procedures/functions that use them
- To drop: use `drop_artifact` with `file_path = "src/<TYPE_NAME>.hdbtabletype"`