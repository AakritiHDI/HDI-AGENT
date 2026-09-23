# hdbtabledata — HANA HDI Table Data (CSV Load) Artifact

## Overview
An `.hdbtabledata` file declares **CSV data to load into a table at deployment time** (DI.MAKE). The data is loaded automatically when the table is deployed or redeployed and the table is empty.

## File Extension
`.hdbtabledata`

## File Path in Container
`src/<NAME>.hdbtabledata`

## Syntax
JSON file referencing a `.csv` file and target table mapping.

```json
{
  "format_version": 1,
  "imports": [{
    "target_table": "<TABLE_NAME>",
    "source_data": {
      "data_type": "CSV",
      "file_name": "<name>.csv",
      "has_header": true,
      "dialect": "HANA",
      "type_config": { "delimiter": "," }
    },
    "import_settings": {
      "import_columns": ["<COL1>", "<COL2>", ...]
    },
    "column_mappings": {
      "<COL1>": 1,
      "<COL2>": 2
    }
  }]
}
```

## Rules
- The `.hdbtabledata` file references a `.csv` file in the **same container folder** — both must be deployed together
- Data is loaded at DI.MAKE time **only if the table is empty**
- The target table must be deployed in the same container
- `column_mappings` maps column name → CSV column position (1-based)

## Example

### Products table data
**File: `src/PRODUCTS.hdbtabledata`**
```json
{
  "format_version": 1,
  "imports": [{
    "target_table": "PRODUCTS",
    "source_data": {
      "data_type": "CSV",
      "file_name": "products.csv",
      "has_header": true,
      "dialect": "HANA",
      "type_config": { "delimiter": "," }
    },
    "import_settings": {
      "import_columns": ["PRODUCT_ID", "PRODUCT_NAME", "PRICE", "CATEGORY"]
    },
    "column_mappings": {
      "PRODUCT_ID":   1,
      "PRODUCT_NAME": 2,
      "PRICE":        3,
      "CATEGORY":     4
    }
  }]
}
```

**File: `src/products.csv`**
```
PRODUCT_ID,PRODUCT_NAME,PRICE,CATEGORY
1,Laptop,999.99,Electronics
2,Mouse,29.99,Accessories
3,Keyboard,79.99,Accessories
```

### Multiple table imports in one file
```json
{
  "format_version": 1,
  "imports": [
    {
      "target_table": "COUNTRIES",
      "source_data": {
        "data_type": "CSV",
        "file_name": "countries.csv",
        "has_header": true,
        "dialect": "HANA",
        "type_config": { "delimiter": "," }
      },
      "import_settings": {
        "import_columns": ["CODE", "NAME"]
      },
      "column_mappings": { "CODE": 1, "NAME": 2 }
    }
  ]
}
```

## Notes
- Both the `.hdbtabledata` and `.csv` files must be included in the DI.MAKE deploy paths
- CSV file path is relative to the container root (same folder as the `.hdbtabledata` file)
- Data is NOT re-loaded on subsequent deploys if the table already has rows
- For tables that should be repopulated on every deploy, use `.hdbdropcreatetable` + `.hdbtabledata`