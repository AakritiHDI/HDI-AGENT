# hdbresultcache — HANA HDI Result Cache Artifact

## Overview
An `.hdbresultcache` file defines a **result cache** on a view — caches query results for a retention period to improve performance for frequently-accessed views.

## File Extension
`.hdbresultcache`

## File Path in Container
`src/<CACHE_NAME>.hdbresultcache`

## Syntax

### Variant 1: Time-based retention
```
RESULT CACHE "_SYS_CACHE#<ViewName>"
ON VIEW "<ViewName>"
WITH RETENTION <seconds> [OF <timestamp_column>]
```

### Variant 2: Force refresh on commit
```
RESULTCACHE "<CacheName>"
ENABLE REFRESH FORCE ON COMMIT
VIEW "<ViewName>"
```

## Rules
- Cache name for Variant 1 must use `_SYS_CACHE#` prefix
- Retention is in **seconds**
- `OF <col>` ties cache invalidation to a timestamp column — cache is refreshed when the column value changes
- `ENABLE REFRESH FORCE ON COMMIT` invalidates cache on every commit — ensures freshness for hierarchy views
- The view being cached must be deployed in the same container

## Examples

### Retention-based cache with column binding
```
RESULT CACHE "_SYS_CACHE#CIS_COURSES"
ON VIEW "CIS_COURSES"
WITH RETENTION 30 OF STARTDATE
```

### Time-based cache (1 hour)
```
RESULT CACHE "_SYS_CACHE#V_PRODUCTS"
ON VIEW "V_PRODUCTS"
WITH RETENTION 3600
```

### Force refresh on commit (for hierarchy views)
```
RESULTCACHE "HIERARCHY_CACHE"
ENABLE REFRESH FORCE ON COMMIT
VIEW "HIERARCHY"
```

## Notes
- Result caches significantly improve performance for expensive aggregation views
- Deploy the result cache **after** the view it caches (or together)
- To drop a result cache: use `drop_artifact` with `file_path = "src/<CACHE_NAME>.hdbresultcache"`
- Check cache status: `SELECT * FROM _SYS_STATISTICS.HOST_RESULT_CACHE`