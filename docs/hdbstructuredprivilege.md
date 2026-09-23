# hdbstructuredprivilege — HANA HDI Structured Privilege Artifact

## Overview
An `.hdbstructuredprivilege` file defines a **row-level security filter** applied to a view. It restricts which rows a specific user can see when querying the view. Unlike analytic privileges (which target CVs), structured privileges work on regular SQL views.

## File Extension
`.hdbstructuredprivilege`

## File Path in Container
`src/<PRIVILEGE_NAME>.hdbstructuredprivilege`

## Syntax
```
STRUCTURED PRIVILEGE "<Name>"
FOR SELECT ON "<ViewName>"
WHERE <filter_expression>
```

## Rules
- Do **NOT** use `CREATE STRUCTURED PRIVILEGE` — start directly with `STRUCTURED PRIVILEGE`
- The view must be deployed in the same container
- The WHERE clause defines which rows are visible
- `SESSION_CONTEXT()` and `SESSION_USER` can be used for dynamic per-session filtering
- Grant to users with: `GRANT STRUCTURED PRIVILEGE "<CONT>::<Name>" TO <user>`

## Examples

### Filter by salary threshold
```
STRUCTURED PRIVILEGE "CIS_INSTRUCTOR_SP"
FOR SELECT ON "CIS_INSTRUCTOR"
WHERE "SALARY" > 30000
```

### Filter by session user (self-service row filter)
```
STRUCTURED PRIVILEGE "EMP_SELF_ACCESS"
FOR SELECT ON "EMPLOYEE"
WHERE "EMAIL" = SESSION_USER
```

### Filter by session context variable
```
STRUCTURED PRIVILEGE "REGIONAL_ACCESS"
FOR SELECT ON "VIEW_SALES"
WHERE "REGION" = SESSION_CONTEXT('REGION')
```

### Filter by department
```
STRUCTURED PRIVILEGE "DEPT_FILTER"
FOR SELECT ON "VIEW_EMPLOYEES"
WHERE "DEPARTMENT_ID" = TO_INTEGER(SESSION_CONTEXT('DEPARTMENT'))
```

## Granting the Privilege
After deployment, grant to a user:
```sql
GRANT STRUCTURED PRIVILEGE "AAK_CONTAINER::CIS_INSTRUCTOR_SP" TO MY_USER;
```

## ⚠️ Important — Data Preview for Structured Privilege Views

Per the SAP HDI specification: **`WITH STRUCTURED PRIVILEGE CHECK` is mandatory on any view referenced by a structured privilege.** It cannot be omitted.

```sql
-- ✅ CORRECT — WITH STRUCTURED PRIVILEGE CHECK is required:
VIEW "SALES_ORDER_VIEW" AS
SELECT "ORDERID", "STATUS" FROM "SALES_ORDER"
WITH STRUCTURED PRIVILEGE CHECK
```

### Why the agent's data preview shows "Insufficient Privilege"

The agent connects to HANA as a service user (`HDI_USER`). HANA does not allow a user to grant a privilege to itself — so `HDI_USER` cannot hold a structured privilege. Querying a view with `WITH STRUCTURED PRIVILEGE CHECK` as `HDI_USER` fails with "insufficient privilege."

**This is expected and correct HANA security behaviour — not a bug.**

### How to preview data from a structured privilege view

Use `execute_sql` in the agent with the session context set first:

```sql
-- Step 1: set the session context variable
SET 'SALES_STATUS' = 'CONFIRMED';

-- Step 2: query the view — returns only rows matching the filter
SELECT * FROM "AAK_CONTAINER"."SALES_ORDER_VIEW";
```

The structured privilege `WHERE "STATUS" = SESSION_CONTEXT('SALES_STATUS')` will return:
- Rows where STATUS = 'CONFIRMED' ✅
- If SESSION_CONTEXT is not set (NULL), returns 0 rows — this is by design

### Prompts to use in the agent for preview

```
run SQL: SET 'SALES_STATUS' = 'CONFIRMED'; SELECT * FROM "AAK_CONTAINER"."SALES_ORDER_VIEW"
```

Or to see all statuses one at a time:
```
run SQL: SET 'SALES_STATUS' = 'PENDING'; SELECT * FROM "AAK_CONTAINER"."SALES_ORDER_VIEW"
```

## Notes
- Structured privileges enforce **row-level security** on SQL views
- They are always active for the granted user — no explicit per-query activation needed
- `SESSION_CONTEXT('KEY')` reads session variables set by the application layer
- For Calculation View row-level security, use `.hdbanalyticprivilege` instead
- Deploy the structured privilege **after** the view it references