# hdbsequence — HANA HDI Sequence Artifact

## Overview
An `.hdbsequence` file defines a **sequence** (auto-increment number generator).

## File Extension
`.hdbsequence`

## File Path in Container
`src/<SEQUENCE_NAME>.hdbsequence`

## Syntax

```
SEQUENCE "<NAME>"
[INCREMENT BY <n>]
[START WITH <n>]
[MINVALUE <n> | NO MINVALUE]
[MAXVALUE <n> | NO MAXVALUE]
[CYCLE | NO CYCLE]
[CACHE <n> | NO CACHE]
[RESET BY <SELECT statement>]
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `INCREMENT BY` | 1 | Step size between values |
| `START WITH` | 1 | First value generated |
| `MINVALUE` | 1 | Minimum allowed value |
| `NO MAXVALUE` | — | Unbounded maximum |
| `CYCLE` | NO CYCLE | Whether to wrap around at min/max |
| `CACHE` | 20 | Pre-allocated values in memory |
| `RESET BY` | — | SQL query to reset on server restart |

## Examples

### Simple sequence (defaults)
```
SEQUENCE "EMPLOYEE_ID_SEQ"
```

### Sequence starting at 1000, step 10
```
SEQUENCE "ORDER_ID_SEQ"
    INCREMENT BY 10
    START WITH 1000
    NO MAXVALUE
    NO CYCLE
    CACHE 50
```

### Sequence with RESET BY (persists across restarts)
```
SEQUENCE "INVOICE_SEQ"
    INCREMENT BY 1
    START WITH 1
    RESET BY SELECT IFNULL(MAX("INVOICE_NO"), 0) + 1 FROM "INVOICES"
```

## Usage in SQL
```sql
-- Get next value
SELECT "EMPLOYEE_ID_SEQ".NEXTVAL FROM DUMMY;

-- Use in INSERT
INSERT INTO "EMPLOYEES" ("EMPLOYEE_ID", "FIRST_NAME")
VALUES ("EMPLOYEE_ID_SEQ".NEXTVAL, 'John');

-- Get current value (same session)
SELECT "EMPLOYEE_ID_SEQ".CURRVAL FROM DUMMY;
```

## Rules
- Do **NOT** use `CREATE SEQUENCE` SQL syntax.
- Sequence names must use double-quote identifiers.
- `RESET BY` is useful for maintaining continuous numbering after system restarts.