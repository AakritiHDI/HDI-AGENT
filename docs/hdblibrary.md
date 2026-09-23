# hdblibrary — HANA HDI SQLScript Library Artifact

## Overview
An `.hdblibrary` file defines a **reusable SQLScript library** — a named collection of functions and procedures that can be imported by other SQLScript artifacts using the `USING` clause. Avoids code duplication across procedures and functions.

## File Extension
`.hdblibrary`

## File Path in Container
`src/<LIBRARY_NAME>.hdblibrary`

## Syntax
```
LIBRARY "<Name>"
LANGUAGE SQLSCRIPT AS
BEGIN
    PUBLIC FUNCTION <func_name>(<params>) RETURNS <type> AS
    BEGIN
        ...
    END;

    PUBLIC PROCEDURE <proc_name>(<params>) AS
    BEGIN
        ...
    END;
END
```

## Rules
- Do **NOT** use `CREATE LIBRARY` — start directly with `LIBRARY`
- Functions/procedures must be declared `PUBLIC` to be accessible from outside
- Consumer (procedure/function) uses: `USING "<LibraryName>" AS <alias>;` then calls `<alias>:<function_name>(<args>)`
- Deploy library **before** the procedures/functions that use it

## Examples

### Math utilities library
```
LIBRARY "MathUtils"
LANGUAGE SQLSCRIPT AS
BEGIN
    PUBLIC FUNCTION round_2dp(val DOUBLE)
    RETURNS DOUBLE AS
    BEGIN
        RETURN ROUND(:val, 2);
    END;

    PUBLIC FUNCTION percentage(part DOUBLE, total DOUBLE)
    RETURNS DOUBLE AS
    BEGIN
        IF :total = 0 THEN RETURN 0; END IF;
        RETURN ROUND((:part / :total) * 100, 2);
    END;
END
```

### String utilities library
```
LIBRARY "StringUtils"
LANGUAGE SQLSCRIPT AS
BEGIN
    PUBLIC FUNCTION pad_left(val NVARCHAR(500), width INT, pad_char NVARCHAR(1))
    RETURNS NVARCHAR(500) AS
    BEGIN
        DECLARE result NVARCHAR(500);
        result := LPAD(:val, :width, :pad_char);
        RETURN :result;
    END;

    PUBLIC FUNCTION normalize_name(val NVARCHAR(500))
    RETURNS NVARCHAR(500) AS
    BEGIN
        RETURN UPPER(TRIM(:val));
    END;
END
```

### Date utilities library
```
LIBRARY "DateUtils"
LANGUAGE SQLSCRIPT AS
BEGIN
    PUBLIC FUNCTION fiscal_year(d DATE)
    RETURNS INTEGER AS
    BEGIN
        DECLARE m INTEGER;
        m := MONTH(:d);
        IF :m >= 4 THEN RETURN YEAR(:d);
        ELSE RETURN YEAR(:d) - 1;
        END IF;
    END;
END
```

## Using a Library in a Procedure
```
PROCEDURE "CALC_DISCOUNT"(IN price DOUBLE, OUT discounted DOUBLE)
LANGUAGE SQLSCRIPT AS
BEGIN
    USING "MathUtils" AS mu;
    discounted := mu:round_2dp(:price * 0.9);
END
```

## Using a Library in a Function
```
FUNCTION "GET_PERCENTAGE"(IN part DOUBLE, IN total DOUBLE)
RETURNS DOUBLE
LANGUAGE SQLSCRIPT AS
BEGIN
    USING "MathUtils" AS mu;
    RETURN mu:percentage(:part, :total);
END
```

## Notes
- Libraries are compiled as separate artifacts — changes to a library trigger recompilation of all dependents
- Only `PUBLIC` members are accessible outside the library
- Deploy order: library → procedures/functions that use it
- To drop: use `drop_artifact` with `file_path = "src/<LIBRARY_NAME>.hdblibrary"`