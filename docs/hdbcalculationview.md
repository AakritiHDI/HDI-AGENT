# hdbcalculationview — HANA HDI Calculation View Artifact

## Overview
An `.hdbcalculationview` file defines an **XML-based analytical model** (Calculation View / CV). CVs support CUBE (with measures) and DIMENSION (attributes only) data categories, input parameters, calculated columns, joins, unions, and more.

## File Extension
`.hdbcalculationview`

## File Path in Container
`src/<CV_NAME>.hdbcalculationview`

## Syntax
XML file with `Calculation:scenario` root element.

## Key Concepts

| Term | Description |
|------|-------------|
| `dataCategory` | `CUBE` (has measures) or `DIMENSION` (attributes only) |
| `outputViewType` | `Aggregation` (CUBE) or `Projection` (DIMENSION/fuzzy) |
| Input Parameter | Filter value passed at query time via `$$IP_NAME$$` |
| `logicalModel` | Always references the **top-most** calculation node |
| `dataSources` | Raw tables/views/functions only — never other CV nodes |
| `calculationViews` | Intermediate nodes (Projection, Join, Aggregation, Union) |

## Basic Structure

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Calculation:scenario
    xmlns:Calculation="http://www.sap.com/ndb/BiModelCalculation.ecore"
    id="CV_NAME"
    applyPrivilegeType="NONE"
    dataCategory="CUBE"
    schemaVersion="3.0"
    outputViewType="Aggregation"
    enforceSqlExecution="true">
  <descriptions defaultDescription="CV_NAME"/>
  <localVariables>
    <!-- Input parameters here -->
  </localVariables>
  <variableMappings/>
  <dataSources>
    <DataSource id="MY_TABLE">
      <resourceUri>MY_TABLE</resourceUri>
    </DataSource>
  </dataSources>
  <snapshotProcedures/>
  <calculationViews/>
  <logicalModel id="MY_TABLE">
    <attributes>
      <attribute id="COL_NAME" order="1" displayAttribute="false" attributeHierarchyActive="false">
        <descriptions defaultDescription="COL_NAME"/>
        <keyMapping columnObjectName="MY_TABLE" columnName="COL_NAME"/>
      </attribute>
    </attributes>
    <calculatedAttributes/>
    <baseMeasures>
      <measure id="AMOUNT" order="2" aggregationType="sum" measureType="simple">
        <descriptions defaultDescription="AMOUNT"/>
        <measureMapping columnObjectName="MY_TABLE" columnName="AMOUNT"/>
        <exceptionAggregationMetadata/>
      </measure>
    </baseMeasures>
    <calculatedMeasures/>
    <restrictedMeasures/>
    <localDimensions/>
  </logicalModel>
</Calculation:scenario>
```

## Input Parameter Block
```xml
<variable id="IP_COUNTRY" parameter="true">
  <descriptions defaultDescription=""/>
  <variableProperties datatype="NVARCHAR" length="30" mandatory="true">
    <valueDomain type="empty"/>
    <selection multiLine="false" type="SingleValue"/>
  </variableProperties>
</variable>
```

## Filter Expression (using input parameter)
Add inside `<logicalModel>` after measures:
```xml
<filter>&quot;COUNTRY&quot; = &apos;$$IP_COUNTRY$$&apos;</filter>
```

**Filter encoding rules:**
- String values: `&apos;$$IP_NAME$$&apos;`
- Numeric values: `$$IP_NAME$$`
- Double quotes for column names: `&quot;COLUMN&quot;`

## Multi-Stack Pattern (Projection → Aggregation)
```xml
<dataSources>
  <DataSource id="COURSES"><resourceUri>COURSES</resourceUri></DataSource>
</dataSources>
<calculationViews>
  <!-- Bottom node: Projection -->
  <calculationView xsi:type="Calculation:ProjectionView" id="Projection_1"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <viewAttributes>
      <viewAttribute id="COURSEID"/>
      <viewAttribute id="FEES"/>
    </viewAttributes>
    <calculatedViewAttributes/>
    <input node="COURSES">
      <mapping xsi:type="Calculation:AttributeMapping" targetAttribute="COURSEID" sourceAttribute="COURSEID"/>
      <mapping xsi:type="Calculation:AttributeMapping" targetAttribute="FEES" sourceAttribute="FEES"/>
    </input>
  </calculationView>
  <!-- Top node: Aggregation -->
  <calculationView xsi:type="Calculation:AggregationView" id="Aggregation_1"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <viewAttributes>
      <viewAttribute id="COURSEID"/>
      <viewAttribute id="FEES" aggregationType="sum"/>
    </viewAttributes>
    <calculatedViewAttributes/>
    <input node="Projection_1">
      <mapping xsi:type="Calculation:AttributeMapping" targetAttribute="COURSEID" sourceAttribute="COURSEID"/>
      <mapping xsi:type="Calculation:AttributeMapping" targetAttribute="FEES" sourceAttribute="FEES"/>
    </input>
  </calculationView>
</calculationViews>
<!-- logicalModel references TOP node -->
<logicalModel id="Aggregation_1">...</logicalModel>
```

## ⚠️ CRITICAL RULE: aggregationType placement

`aggregationType` is **ONLY valid** inside `AggregationView` `<viewAttribute>` elements.

| Node type | `aggregationType` on `<viewAttribute>`? |
|---|---|
| `AggregationView` | ✅ **VALID** — required for measures |
| `JoinView` | ❌ **INVALID** — HANA rejects with error |
| `ProjectionView` | ❌ **INVALID** — HANA rejects with error |
| `logicalModel` `<baseMeasures>` | ✅ **VALID** — required for measures |

**Never** put `aggregationType="sum"` (or any aggregationType) on `<viewAttribute>` inside a JoinView or ProjectionView.  
HANA will report **5+ cascading errors** when this appears in a JoinView.

## Join Node (Minimal Syntax)
```xml
<calculationView xsi:type="Calculation:JoinView" id="Join_1"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    cardinality="C1_N" joinType="inner">
  <viewAttributes>
    <viewAttribute id="KEY_COL"/>          <!-- NO aggregationType here -->
    <viewAttribute id="OTHER_COL"/>        <!-- NO aggregationType here -->
    <viewAttribute id="MEASURE_COL"/>      <!-- NO aggregationType here — even for measures -->
  </viewAttributes>
  <calculatedViewAttributes/>
  <input node="LEFT_TABLE">
    <mapping xsi:type="Calculation:AttributeMapping" targetAttribute="KEY_COL" sourceAttribute="KEY_COL"/>
  </input>
  <input node="RIGHT_TABLE">
    <mapping xsi:type="Calculation:AttributeMapping" targetAttribute="OTHER_COL" sourceAttribute="OTHER_COL"/>
    <mapping xsi:type="Calculation:AttributeMapping" targetAttribute="MEASURE_COL" sourceAttribute="MEASURE_COL"/>
    <!-- Do NOT re-map KEY_COL from the right side — it is owned by the left side -->
  </input>
  <joinAttribute name="KEY_COL"/>
</calculationView>
```

**Join key mapping rule:**
- The `<joinAttribute name="X"/>` column must appear in BOTH inputs' data, but in the output it should be mapped from **only ONE side** (the key-preserving/left side).
- The right side should NOT map the join key into the join output again — this causes ambiguity errors.

**Join types:** `inner`, `leftOuter`, `rightOuter`, `fullOuter`, `referential`, `temporal`, `textTable`, `dynamic`

## Complete Join CV Pattern (Projection → Projection → Join → Aggregation)

Use this pattern when source tables have **different column names** for the join key (e.g., `TABLE_A.ID` joins `TABLE_B.FOREIGN_ID`).

**Step 1:** Two ProjectionViews to normalize the join key name.  
**Step 2:** JoinView consuming both projections.  
**Step 3:** AggregationView (this is where `aggregationType` goes).  
**Step 4:** LogicalModel references the AggregationView.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Calculation:scenario
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:Calculation="http://www.sap.com/ndb/BiModelCalculation.ecore"
    id="CV_JOIN_EXAMPLE" applyPrivilegeType="NONE"
    dataCategory="CUBE" schemaVersion="3.0"
    outputViewType="Aggregation" enforceSqlExecution="true">
  <descriptions defaultDescription="Join Example"/>
  <localVariables/>
  <variableMappings/>
  <dataSources>
    <DataSource id="TABLE_A"><resourceUri>TABLE_A</resourceUri></DataSource>
    <DataSource id="TABLE_B"><resourceUri>TABLE_B</resourceUri></DataSource>
  </dataSources>
  <snapshotProcedures/>
  <calculationViews>

    <!-- 1. ProjectionView for TABLE_A — expose join key as JOIN_KEY -->
    <calculationView xsi:type="Calculation:ProjectionView" id="Proj_A">
      <viewAttributes>
        <viewAttribute id="JOIN_KEY"/>
      </viewAttributes>
      <calculatedViewAttributes/>
      <input node="TABLE_A">
        <mapping xsi:type="Calculation:AttributeMapping" targetAttribute="JOIN_KEY" sourceAttribute="ID"/>
      </input>
    </calculationView>

    <!-- 2. ProjectionView for TABLE_B — rename FOREIGN_ID to JOIN_KEY + pass other columns -->
    <calculationView xsi:type="Calculation:ProjectionView" id="Proj_B">
      <viewAttributes>
        <viewAttribute id="JOIN_KEY"/>
        <viewAttribute id="LABEL"/>
        <viewAttribute id="AMOUNT"/>
      </viewAttributes>
      <calculatedViewAttributes/>
      <input node="TABLE_B">
        <mapping xsi:type="Calculation:AttributeMapping" targetAttribute="JOIN_KEY" sourceAttribute="FOREIGN_ID"/>
        <mapping xsi:type="Calculation:AttributeMapping" targetAttribute="LABEL" sourceAttribute="LABEL"/>
        <mapping xsi:type="Calculation:AttributeMapping" targetAttribute="AMOUNT" sourceAttribute="AMOUNT"/>
      </input>
    </calculationView>

    <!-- 3. JoinView — NO aggregationType on any viewAttribute -->
    <calculationView xsi:type="Calculation:JoinView" id="Join_1" cardinality="C1_N" joinType="inner">
      <viewAttributes>
        <viewAttribute id="JOIN_KEY"/>   <!-- NO aggregationType -->
        <viewAttribute id="LABEL"/>      <!-- NO aggregationType -->
        <viewAttribute id="AMOUNT"/>     <!-- NO aggregationType — even though it is a measure -->
      </viewAttributes>
      <calculatedViewAttributes/>
      <input node="Proj_A">
        <!-- Left side owns the join key -->
        <mapping xsi:type="Calculation:AttributeMapping" targetAttribute="JOIN_KEY" sourceAttribute="JOIN_KEY"/>
      </input>
      <input node="Proj_B">
        <!-- Right side: map non-key columns only — do NOT re-map JOIN_KEY here -->
        <mapping xsi:type="Calculation:AttributeMapping" targetAttribute="LABEL" sourceAttribute="LABEL"/>
        <mapping xsi:type="Calculation:AttributeMapping" targetAttribute="AMOUNT" sourceAttribute="AMOUNT"/>
      </input>
      <joinAttribute name="JOIN_KEY"/>
    </calculationView>

    <!-- 4. AggregationView — aggregationType goes HERE only -->
    <calculationView xsi:type="Calculation:AggregationView" id="Aggregation_1">
      <viewAttributes>
        <viewAttribute id="JOIN_KEY"/>
        <viewAttribute id="LABEL"/>
        <viewAttribute id="AMOUNT" aggregationType="sum"/>  <!-- aggregationType ONLY here -->
      </viewAttributes>
      <calculatedViewAttributes/>
      <input node="Join_1">
        <mapping xsi:type="Calculation:AttributeMapping" targetAttribute="JOIN_KEY" sourceAttribute="JOIN_KEY"/>
        <mapping xsi:type="Calculation:AttributeMapping" targetAttribute="LABEL" sourceAttribute="LABEL"/>
        <mapping xsi:type="Calculation:AttributeMapping" targetAttribute="AMOUNT" sourceAttribute="AMOUNT"/>
      </input>
    </calculationView>

  </calculationViews>

  <!-- LogicalModel references the TOP node (AggregationView) -->
  <logicalModel id="Aggregation_1">
    <attributes>
      <attribute id="JOIN_KEY" order="1" displayAttribute="false" attributeHierarchyActive="false">
        <descriptions defaultDescription="JOIN_KEY"/>
        <keyMapping columnObjectName="Aggregation_1" columnName="JOIN_KEY"/>
      </attribute>
      <attribute id="LABEL" order="2" displayAttribute="false" attributeHierarchyActive="false">
        <descriptions defaultDescription="LABEL"/>
        <keyMapping columnObjectName="Aggregation_1" columnName="LABEL"/>
      </attribute>
    </attributes>
    <calculatedAttributes/>
    <baseMeasures>
      <measure id="AMOUNT" order="3" aggregationType="sum" measureType="simple">
        <descriptions defaultDescription="AMOUNT"/>
        <measureMapping columnObjectName="Aggregation_1" columnName="AMOUNT"/>
        <exceptionAggregationMetadata/>
      </measure>
    </baseMeasures>
    <calculatedMeasures/>
    <restrictedMeasures/>
    <localDimensions/>
  </logicalModel>
</Calculation:scenario>
```

**Node order in `calculationViews`:** Bottom nodes (ProjectionViews) first, then JoinView, then AggregationView (top). The `logicalModel` always references the top node.

## Rules
- `dataSources` always reference raw tables/views/functions — **never** other CV nodes
- CV nodes in `calculationViews` reference each other by node id
- `logicalModel id` **MUST** reference the top-most node
- Input parameter filter: use `$$IP_NAME$$` (no quotes for numeric, `&apos;` for strings)
- For TABLE_FUNCTION datasources, add `type="TABLE_FUNCTION"` on the DataSource element
- For CV-on-CV, add `type="CALCULATION_VIEW"` on the DataSource element

## Variable Mappings (for PSV/TUDF/CV sources)
```xml
<variableMappings>
  <mapping xsi:type="Variable:VariableMapping"
      xmlns:Variable="http://www.sap.com/ndb/BiModelVariable.ecore"
      dataSource="PSV1">
    <targetVariable name="IP_FEES" resourceUri="PSV1"/>
    <localVariable>IP_FEES</localVariable>
  </mapping>
</variableMappings>
```

## Notes
- Always set `enforceSqlExecution="true"` unless using dynamic joins
- For fuzzy search CVs, set `outputViewType="Projection"`
- Calculation views can be queried directly or via SDA virtual tables
- File path: `src/<CV_NAME>.hdbcalculationview`