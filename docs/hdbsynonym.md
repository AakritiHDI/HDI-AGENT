# hdbsynonym — HANA HDI Synonym Artifact

## Overview
An `.hdbsynonym` file maps **local alias names** to objects in other schemas or
HDI containers. This is the standard way to reference objects outside your container.

## File Extension
`.hdbsynonym`

## File Path in Container
`src/<FILE_NAME>.hdbsynonym`

> One `.hdbsynonym` file can define **multiple** synonyms.

## Format (JSON)

```json
{
    "<SYNONYM_NAME>": {
        "target": {
            "object": "<TARGET_OBJECT_NAME>",
            "schema": "<TARGET_SCHEMA>"
        }
    }
}
```

## Examples

### Single synonym
```json
{
    "PRODUCTS": {
        "target": {
            "object": "PRODUCTS",
            "schema": "PRODUCT_SCHEMA"
        }
    }
}
```

### Multiple synonyms in one file
```json
{
    "EXT_CUSTOMERS": {
        "target": { "object": "CUSTOMERS",  "schema": "CRM_SCHEMA" }
    },
    "EXT_PRODUCTS": {
        "target": { "object": "PRODUCTS",   "schema": "PRODUCT_SCHEMA" }
    },
    "EXT_PRICE_LIST": {
        "target": { "object": "PRICE_LIST", "schema": "PRICING_SCHEMA" }
    }
}
```

### Synonym for a calculation view (_SYS_BIC)
```json
{
    "CV_SALES": {
        "target": {
            "object": "sap.analytics/CV_SALES",
            "schema": "_SYS_BIC"
        }
    }
}
```

## Rules
- File format is **JSON**, NOT SQL — do NOT use `CREATE SYNONYM`.
- The synonym name (key) is what your views/procedures use inside the container.
- The `target` is the actual object in another schema.
- The HDI technical user must have appropriate privileges on the target object.
- One file can hold any number of synonyms.