# hdbflowgraph — HANA HDI Flowgraph Artifact

## Overview
An `.hdbflowgraph` file defines an **XML-based data transformation pipeline** — a series of data sources, transformations, and targets. Executed as a stored procedure by the SAP HANA Smart Data Integration (SDI) flowgraph engine.

## File Extension
`.hdbflowgraph`

## File Path in Container
`src/<FLOWGRAPH_NAME>.hdbflowgraph`

## Syntax
XML file with `flowgraph:Flowgraph` root element defining DataSource, Projection, Filter, Join, and DataSink nodes.

## DataSink Modes

| Mode | Description |
|------|-------------|
| `truncate` | Clear target before loading (full refresh) |
| `append` | Insert only — never delete existing rows |
| `upsert` | Insert new, update existing (requires key) |

## Examples

### Simple copy (source → target)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<flowgraph:Flowgraph
    xmlns:flowgraph="http://www.sap.com/ndb/BiModelFlowgraph.ecore"
    id="FG_COPY_PRODUCTS"
    schemaVersion="1.0">
  <descriptions defaultDescription="Copy PRODUCTDETAILS to PRODUCTS_COPY"/>
  <nodes xsi:type="flowgraph:DataSource"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      id="SOURCE" tableName="PRODUCTDETAILS">
    <outputPort id="output">
      <column id="PRODUCT_ID"   columnType="int"/>
      <column id="PRODUCT_NAME" columnType="nvarchar" length="100"/>
      <column id="PRICE"        columnType="decimal"  length="15" scale="2"/>
    </outputPort>
  </nodes>
  <nodes xsi:type="flowgraph:DataSink"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      id="TARGET" tableName="PRODUCTS_COPY" mode="truncate">
    <inputPort id="input">
      <column id="PRODUCT_ID"   columnType="int"/>
      <column id="PRODUCT_NAME" columnType="nvarchar" length="100"/>
      <column id="PRICE"        columnType="decimal"  length="15" scale="2"/>
    </inputPort>
  </nodes>
  <edges sourceNode="SOURCE" sourcePort="output"
         targetNode="TARGET" targetPort="input"/>
</flowgraph:Flowgraph>
```

### With filter (source → filter → target)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<flowgraph:Flowgraph
    xmlns:flowgraph="http://www.sap.com/ndb/BiModelFlowgraph.ecore"
    id="FG_FILTERED_PRODUCTS">
  <descriptions defaultDescription="Copy only products with PRICE > 100"/>
  <nodes xsi:type="flowgraph:DataSource"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      id="SRC" tableName="PRODUCTDETAILS">
    <outputPort id="out">
      <column id="PRODUCT_ID" columnType="int"/>
      <column id="PRICE"      columnType="decimal" length="15" scale="2"/>
    </outputPort>
  </nodes>
  <nodes xsi:type="flowgraph:Filter"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      id="FILT" expression="PRICE &gt; 100">
    <inputPort  id="input">
      <column id="PRODUCT_ID" columnType="int"/>
      <column id="PRICE"      columnType="decimal" length="15" scale="2"/>
    </inputPort>
    <outputPort id="output">
      <column id="PRODUCT_ID" columnType="int"/>
      <column id="PRICE"      columnType="decimal" length="15" scale="2"/>
    </outputPort>
  </nodes>
  <nodes xsi:type="flowgraph:DataSink"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      id="TGT" tableName="EXPENSIVE_PRODUCTS" mode="truncate">
    <inputPort id="input">
      <column id="PRODUCT_ID" columnType="int"/>
      <column id="PRICE"      columnType="decimal" length="15" scale="2"/>
    </inputPort>
  </nodes>
  <edges sourceNode="SRC"  sourcePort="out"    targetNode="FILT" targetPort="input"/>
  <edges sourceNode="FILT" sourcePort="output" targetNode="TGT"  targetPort="input"/>
</flowgraph:Flowgraph>
```

## Running the Flowgraph
After deployment, the flowgraph creates a stored procedure. Call it to execute:
```sql
CALL "AAK_CONTAINER"."FG_COPY_PRODUCTS"();
```

## Rules
- Flowgraph execution creates a **stored procedure** in the container schema
- All source and target tables must be deployed in the same container
- Filter `expression` attribute uses SQL syntax with XML-escaped operators (`&gt;`, `&lt;`, `&amp;`)
- Each `<edges>` element connects one output port to one input port

## Notes
- Requires SDI flowgraph engine — not available in all HANA Cloud configurations
- Source and target columns must have matching names and compatible types
- Use `mode="append"` for incremental loads, `mode="truncate"` for full refresh