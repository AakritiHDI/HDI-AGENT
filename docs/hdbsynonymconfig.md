# hdbsynonymconfig — HANA HDI Synonym Config Artifact

## Overview
An `.hdbsynonymconfig` file provides the **runtime configuration** that binds synonyms to their actual target objects. While `.hdbsynonym` defines the synonym structure, `.hdbsynonymconfig` specifies the physical target at deployment time.

## File Extension
`.hdbsynonymconfig`

## File Path in Container
`src/<NAME>.hdbsynonymconfig`

## Syntax
JSON file mapping synonym name → actual target object and schema.

```json
{
  "<SynonymName>": {
    "target": {
      "object": "<actual_object_name>",
      "schema": "<actual_schema_name>"
    }
  }
}
```

## Rules
- The synonym name in the config must match the synonym name in the corresponding `.hdbsynonym` file
- Both `.hdbsynonym` and `.hdbsynonymconfig` must be deployed together
- The target object and schema must exist at deployment time
- Use when the physical target differs across environments (dev/test/prod)

## Examples

### Binding to an external schema table
```json
{
  "SYN_PRODUCTS": {
    "target": {
      "object": "PRODUCTDETAILS",
      "schema": "PROD_SCHEMA"
    }
  }
}
```

### Binding to another HDI container's schema
```json
{
  "SYN_DWC_TABLE": {
    "target": {
      "object": "FACT_SALES",
      "schema": "DWC_CONTAINER"
    }
  }
}
```

### Multiple synonym bindings
```json
{
  "SYN_CUSTOMERS": {
    "target": { "object": "CUSTOMERS", "schema": "MASTER_DATA" }
  },
  "SYN_PRODUCTS": {
    "target": { "object": "PRODUCTS", "schema": "MASTER_DATA" }
  },
  "SYN_ORDERS": {
    "target": { "object": "ORDERS", "schema": "TRANSACT_DATA" }
  }
}
```

## Companion .hdbsynonym File
The `.hdbsynonym` file defines the synonym (logical layer):
```json
{
  "SYN_PRODUCTS": {
    "target": {
      "object": "PRODUCTDETAILS"
    }
  }
}
```

The `.hdbsynonymconfig` then provides the physical binding (runtime layer).

## Notes
- `hdbsynonymconfig` is optional if the synonym already specifies a complete, fixed target in `.hdbsynonym`
- Use config files to support environment-specific deployments without changing artifact source files
- Deploy the config file alongside its `.hdbsynonym` file
- The target schema must be accessible to the container's `#OO` user (grant via `.hdbgrants` if needed)