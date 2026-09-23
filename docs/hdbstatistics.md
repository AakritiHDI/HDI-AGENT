# hdbstatistics — HANA HDI Column Statistics Artifact

## Overview
An `.hdbstatistics` file instructs the HANA query optimizer about **data distribution in table columns**. Can significantly improve join and filter plan quality for columns with non-uniform distributions.

## File Extension
`.hdbstatistics`

## File Path in Container
`src/<NAME>.hdbstatistics`

## Syntax
JSON file declaring target tables, columns, and statistic types.

```json
{
  "statistics": [{
    "table":  "<TABLE_NAME>",
    "column": "<COLUMN_NAME>",
    "type":   "HISTOGRAM|SIMPLE"
  }]
}
```

## Statistic Types

| Type | Description | Use When |
|------|-------------|----------|
| `SIMPLE` | Min, max, count, distinct count | Basic selectivity estimation |
| `HISTOGRAM` | Full frequency distribution | Skewed data, range queries, joins |

## Examples

### Single column histogram
```json
{
  "statistics": [{
    "table":  "PRODUCTDETAILS",
    "column": "PRICE",
    "type":   "HISTOGRAM"
  }]
}
```

### Multiple columns (mixed types)
```json
{
  "statistics": [
    { "table": "COURSES", "column": "STARTDATE",    "type": "HISTOGRAM" },
    { "table": "COURSES", "column": "FEES",          "type": "HISTOGRAM" },
    { "table": "COURSES", "column": "INSTRUCTORID",  "type": "SIMPLE"    }
  ]
}
```

### Statistics for join key columns
```json
{
  "statistics": [
    { "table": "ORDERS",    "column": "CUSTOMER_ID", "type": "HISTOGRAM" },
    { "table": "CUSTOMERS", "column": "CUSTOMER_ID", "type": "HISTOGRAM" },
    { "table": "ORDERS",    "column": "ORDER_DATE",  "type": "HISTOGRAM" }
  ]
}
```

## Notes
- Statistics are **refreshed on every DI.MAKE** deployment
- Most useful for **large tables** with skewed distributions where the optimizer makes suboptimal decisions
- Without statistics, the optimizer uses default selectivity estimates (often 10%)
- Deploy the statistics artifact after the table it references
- Statistics improve performance for: range filters, JOIN order decisions, GROUP BY queries
- For small tables (<10k rows), statistics have minimal impact