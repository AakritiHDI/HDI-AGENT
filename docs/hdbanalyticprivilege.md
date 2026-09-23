# hdbanalyticprivilege — HANA HDI Analytic Privilege Artifact

## Overview
An `.hdbanalyticprivilege` file defines an **XML-based analytic privilege** that controls row-level access to Calculation Views. It restricts which rows a user can see when querying a CV via SELECT or SDA virtual table.

## File Extension
`.hdbanalyticprivilege`

## File Path in Container
`src/<PRIVILEGE_NAME>.hdbanalyticprivilege`

## Syntax
XML file with `Privilege:analyticPrivilege` root element.

## Rules
- The CV must have `applyPrivilegeType="ANALYTIC_PRIVILEGE"` in its scenario element to enforce the AP
- Default CV setting is `applyPrivilegeType="NONE"` (no AP enforcement)
- Multiple CVs can be secured by a single AP via multiple `<modelUri>` entries
- Grant with: `GRANT ANALYTIC PRIVILEGE '<container>::<ap_id>' TO <user>`
- `modelUri` format: `<container_name>/<cv_id>` — no schema prefix

## Examples

### Unrestricted access (grants access to all rows)
```xml
<?xml version="1.0" encoding="utf-8"?>
<Privilege:analyticPrivilege
    xmlns:Privilege="http://www.sap.com/ndb/BiModelPrivilege.ecore"
    id="AP_FULL_ACCESS"
    privilegeType="SQL_ANALYTIC_PRIVILEGE">
  <descriptions defaultDescription="Full unrestricted access to CV"/>
  <securedModels>
    <modelUri>AAK_CONTAINER/CV_SALES</modelUri>
  </securedModels>
  <restrictions/>
</Privilege:analyticPrivilege>
```

### With dimension filter (restrict by COUNTRY)
```xml
<?xml version="1.0" encoding="utf-8"?>
<Privilege:analyticPrivilege
    xmlns:Privilege="http://www.sap.com/ndb/BiModelPrivilege.ecore"
    id="AP_REGION_FILTER"
    privilegeType="SQL_ANALYTIC_PRIVILEGE">
  <descriptions defaultDescription="Restrict access by COUNTRY dimension"/>
  <securedModels>
    <modelUri>AAK_CONTAINER/CV_SALES</modelUri>
  </securedModels>
  <restrictions>
    <restriction>
      <dimension>COUNTRY</dimension>
      <attributeName>COUNTRY</attributeName>
      <operatorCode>EQ</operatorCode>
      <value>India</value>
    </restriction>
  </restrictions>
</Privilege:analyticPrivilege>
```

### Multi-model (secures multiple CVs)
```xml
<?xml version="1.0" encoding="utf-8"?>
<Privilege:analyticPrivilege
    xmlns:Privilege="http://www.sap.com/ndb/BiModelPrivilege.ecore"
    id="AP_MULTI_CV"
    privilegeType="SQL_ANALYTIC_PRIVILEGE">
  <descriptions defaultDescription="Grant access to multiple CVs"/>
  <securedModels>
    <modelUri>AAK_CONTAINER/CV_SALES</modelUri>
    <modelUri>AAK_CONTAINER/CV_COURSES</modelUri>
  </securedModels>
  <restrictions/>
</Privilege:analyticPrivilege>
```

## Granting the Privilege
After deployment, grant to a user:
```sql
GRANT ANALYTIC PRIVILEGE "AAK_CONTAINER::AP_FULL_ACCESS" TO MY_USER;
```

## Notes
- Analytic privileges enforce row-level security on Calculation Views
- Without granting the AP, the user cannot query the CV at all (if AP enforcement is enabled)
- For structured row-level filters without CVs, use `.hdbstructuredprivilege` instead