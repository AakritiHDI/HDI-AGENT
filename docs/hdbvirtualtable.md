# hdbvirtualtable — HANA HDI Virtual Table Artifact

## Overview
An `.hdbvirtualtable` file creates a **virtual table** pointing to a remote data source via SAP Smart Data Access (SDA). Virtual tables let you query remote data as if it were local.

## File Extension
`.hdbvirtualtable`

## File Path in Container
`src/<VT_NAME>.hdbvirtualtable`

## Syntax
```
VIRTUAL TABLE "<Name>" AT "<RemoteSource>"."<Database>"."<Schema>"."<Table>"
```

## Rules
- Do **NOT** use `CREATE VIRTUAL TABLE` — start directly with `VIRTUAL TABLE`
- The remote source must exist and the container's `#OO` user must have `CREATE VIRTUAL TABLE ON REMOTE SOURCE <RS>` privilege
- Use `<NULL>` for the database part when not applicable (most HANA Cloud scenarios)

## Examples

### SDA virtual table (HANA-to-HANA)
```
VIRTUAL TABLE "VT_REMOTE_SALES" AT "FED_SDA_HC"."<NULL>"."REMOTE_SCHEMA"."SALES"
```

### Virtual table pointing to another HDI container
```
VIRTUAL TABLE "VT_CV_DIRECT" AT "FED_SDA_HC"."<NULL>"."OTHER_CONTAINER"."CV_DIRECT"
```

### Virtual table for Amazon Athena
```
VIRTUAL TABLE "VT_ATHENA" AT "FED_SDA_ATHENA"."<NULL>"."demo"."agriculture_cost_yield"
```

### Virtual table for calculation view (with input parameters)
```
VIRTUAL TABLE "VT_CV_COURSES" AT "FED_SDA_HC"."<NULL>"."AAK_CONTAINER"."CV_COURSES"
```

## Prerequisites
Before deploying, grant the required privilege:
```sql
GRANT CREATE VIRTUAL TABLE ON REMOTE SOURCE FED_SDA_HC TO AAK_CONTAINER#OO;
```

## Querying a Virtual Table with CV Input Parameters
```sql
-- Get CV input parameters first
CALL SYS.GET_REMOTE_SOURCE_VIEW_PARAMETERS(
    'FED_SDA_HC',
    '<NULL>' || CHAR(127) || 'AAK_CONTAINER' || CHAR(127) || 'CV_COURSES',
    'GET_CV_INPUT_PARAMETER_TYPE_INFO'
);

-- Query with placeholder values
SELECT * FROM "AAK_CONTAINER"."VT_CV_COURSES"(
    placeholder."$$IP_FEES$$"=>500
);
```

## Notes
- Virtual tables expose Calculation View input parameters via `VIRTUAL_TABLE_PARAMETERS` system view
- For runtime target overrides, use `.hdbvirtualtableconfig` alongside the virtual table
- Deploy virtual tables **after** the remote source is configured
- To drop: use `drop_artifact` with `file_path = "src/<VT_NAME>.hdbvirtualtable"`