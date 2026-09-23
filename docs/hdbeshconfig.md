# hdbeshconfig — HANA HDI Enterprise Search Configuration Artifact

## Overview
An `.hdbeshconfig` file configures **Enterprise Search (ESH) / full-text / fuzzy search** on a view. It enables `@Search.searchable` annotation and marks which columns are searchable.

## File Extension
`.hdbeshconfig`

## File Path in Container
`src/<VIEW_NAME>.hdbeshconfig`

## Syntax
JSON configuration file.

## Examples

### Text search on book data
```json
{
  "com.sap.hana.di.eshconfig": {
    "@EndUserText.label": "Man Booker Prize Books",
    "@Search.searchable": true,
    "Elements": {
      "NAME":        { "@Search.defaultSearchElement": true },
      "AUTHOR":      { "@Search.defaultSearchElement": true },
      "NATIONALITY": { "@Search.defaultSearchElement": true },
      "PUBLISHER":   { "@Search.defaultSearchElement": true }
    }
  }
}
```

### Search with spatial column
```json
{
  "com.sap.hana.di.eshconfig": {
    "@EndUserText.label": "Booker Prize Locations",
    "@Search.searchable": true,
    "Elements": {
      "COUNTRY_NAME": { "@Search.defaultSearchElement": true },
      "CITY":         { "@Search.geoJson": true }
    }
  }
}
```

### Product search with multiple text fields
```json
{
  "com.sap.hana.di.eshconfig": {
    "@EndUserText.label": "Product Search",
    "@Search.searchable": true,
    "Elements": {
      "PRODUCT_NAME":  { "@Search.defaultSearchElement": true },
      "DESCRIPTION":   { "@Search.defaultSearchElement": true },
      "CATEGORY":      { "@Search.defaultSearchElement": true }
    }
  }
}
```

## Rules
- The `.hdbeshconfig` file is deployed **alongside** the view (`.hdbview`) it annotates
- The file name should match the view name
- `@Search.defaultSearchElement: true` marks columns included in full-text search
- `@Search.geoJson: true` marks spatial columns for geographic search
- The view must exist in the same container

## Notes
- Fuzzy search threshold is configured in the ESH service layer, not the artifact
- Enterprise Search requires the ESH service to be enabled on the HANA Cloud instance
- Deploy `.hdbeshconfig` together with its `.hdbview` in the same DI.MAKE call