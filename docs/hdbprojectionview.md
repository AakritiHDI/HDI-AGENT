# hdbprojectionview — HANA HDI Projection View Artifact

## Overview
An `.hdbprojectionview` file creates a **cross-schema projection view** — a view in the container's schema that projects columns from a table or view in another schema. It acts as a secure, schema-local alias for external objects.

## File Extension
`.hdbprojectionview`

## File Path in Container
`src/<VIEW_NAME>.hdbprojectionview`

## Syntax
```
PROJECTION VIEW "<Name>"
AS SELECT <cols> FROM "<ExternalSchema>"."<Object>"
```

## Rules
- Do **NOT** use `CREATE PROJECTION VIEW` — start directly with `PROJECTION VIEW`
- The external schema must be accessible to the container's `#OO` user
- Grant access via `.hdbgrants` or explicit `GRANT SELECT ON SCHEMA ... TO <CONT>#OO`
- Pair with `.hdbprojectionviewconfig` when using logical schema references

## Examples

### Full projection (all columns)
```
PROJECTION VIEW "PV_EXTERNAL_PRODUCTS"
AS SELECT * FROM "EXTERNAL_SCHEMA"."PRODUCTDETAILS"
```

### Column subset projection
```
PROJECTION VIEW "PV_INSTRUCTOR_NAMES"
AS SELECT INSTRUCTORID, INSTRUCTORNAME, EMAIL
FROM "SHARED_SCHEMA"."INSTRUCTOR"
```

### Projection with filter
```
PROJECTION VIEW "PV_ACTIVE_COURSES"
AS SELECT COURSEID, SUBJECTID, STARTDATE, FEES
FROM "SHARED_SCHEMA"."COURSES"
WHERE FEES > 0
```

### Using a logical schema reference
```
PROJECTION VIEW "PV_ORDERS"
AS SELECT ORDER_ID, CUSTOMER_ID, AMOUNT
FROM "LOGICAL_SCHEMA_REF"."ORDERS"
```

## Projection View Config (optional)
When using logical schema names, provide a `.hdbprojectionviewconfig` to bind the logical name to a physical schema:

**File: `src/PV_ORDERS.hdbprojectionviewconfig`**
```json
{
  "PV_ORDERS": {
    "target": {
      "schema": "PROD_ORDER_SCHEMA"
    }
  }
}
```

## Prerequisites
Grant SELECT on the external schema to the container's OO user:
```sql
GRANT SELECT ON SCHEMA EXTERNAL_SCHEMA TO AAK_CONTAINER#OO;
```

Or use `.hdbgrants`:
```json
{
  "EXTERNAL_SCHEMA_ADMIN": {
    "object_owner": {
      "schema_privileges": [{
        "reference": "EXTERNAL_SCHEMA",
        "privileges": ["SELECT"]
      }]
    }
  }
}
```

## Notes
- Projection views are useful for cross-container data access patterns
- They expose external data within the container's schema namespace
- Unlike synonyms, projection views can filter and subset columns
- Deploy `.hdbgrants` before the projection view that depends on the external schema