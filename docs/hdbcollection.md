# hdbcollection — HANA HDI Document Store Collection Artifact

## Overview
An `.hdbcollection` file defines a **JSON document store collection** — a schema-flexible JSON storage container in SAP HANA Cloud. Unlike tables, collections don't require a fixed schema.

## File Extension
`.hdbcollection`

## File Path in Container
`src/<COLLECTION_NAME>.hdbcollection`

## Syntax
```
COLLECTION "<CollectionName>"
```

## Examples

### Basic collection
```
COLLECTION "COLLECTION"
```

### Named collection for customer documents
```
COLLECTION "CUSTOMER_DOCS"
```

### Named collection for product catalog
```
COLLECTION "PRODUCT_CATALOG"
```

## Working with Collections (after deployment)

### Insert a JSON document
```sql
INSERT INTO "AAK_CONTAINER"."CUSTOMER_DOCS"
VALUES ('{"customerId": 1, "name": "Alice", "region": "EU", "tier": "Gold"}');
```

### Query with JSON functions
```sql
-- Get all gold tier customers
SELECT JSON_VALUE(DOCUMENT, '$.name') AS NAME,
       JSON_VALUE(DOCUMENT, '$.region') AS REGION
FROM "AAK_CONTAINER"."CUSTOMER_DOCS"
WHERE JSON_VALUE(DOCUMENT, '$.tier') = 'Gold';
```

### Full-text search on collection
```sql
SELECT * FROM "AAK_CONTAINER"."CUSTOMER_DOCS"
WHERE CONTAINS(DOCUMENT, 'Alice');
```

## Notes
- Collections are **SAP HANA Cloud only** (not available in on-premise HANA)
- No fixed schema — each document can have different fields
- Use `JSON_VALUE()` and `JSON_QUERY()` to access nested JSON fields
- For indexed access, deploy an `.hdbcollectionindex` alongside the collection
- For hierarchical/graph JSON queries, deploy an `.hdbcollectionadjindex`
- To drop a collection: use `drop_artifact` with `file_path = "src/<COLLECTION_NAME>.hdbcollection"`