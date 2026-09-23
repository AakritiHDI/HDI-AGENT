# hdblogicalschema — HANA HDI Logical Schema Artifact

## Overview
An `.hdblogicalschema` file declares a **logical schema reference** — a named placeholder for a physical schema. It allows artifacts to reference external schemas by logical name, with the actual schema binding configured at deployment time.

## File Extension
`.hdblogicalschema`

## File Path in Container
`src/<NAME>.hdblogicalschema`

## Syntax
JSON file that declares the logical schema name.

```json
{
  "default_logical_schema": ""
}
```

## Examples

### Simple logical schema declaration
```json
{
  "default_logical_schema": ""
}
```

### Named logical schema
```json
{
  "default_logical_schema": "EXTERNAL_DATA_SCHEMA"
}
```

## Using in a View
Reference the logical schema in a view:
```
VIEW "MY_VIEW" AS
SELECT * FROM "LOGICAL_SCHEMA_NAME"."SOME_TABLE"
```

## Notes
- Logical schemas **decouple** artifact definitions from physical schema names
- The physical binding is provided via `.hdbsynonymconfig` or deployment parameters
- Use logical schemas when the same artifact set needs to target different schemas across dev/test/prod
- Deploy `.hdblogicalschema` before the artifacts that reference it