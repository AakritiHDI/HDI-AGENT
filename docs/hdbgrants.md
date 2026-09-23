# hdbgrants — HANA HDI External Grants Artifact

## Overview
An `.hdbgrants` file grants object privileges **FROM** an external schema/user **TO** the container's object owner (`#OO` user). Used when the container needs SELECT on objects in another schema (e.g., SDA remote sources, other containers, system views).

## File Extension
`.hdbgrants`

## File Path in Container
`src/<GRANTS_NAME>.hdbgrants`

## Syntax
JSON file declaring grantors and the privileges each grants to the OO user.

```json
{
  "<GRANTOR_USER_OR_SCHEMA>": {
    "object_owner": {
      "schema_privileges": [{
        "reference": "<EXTERNAL_SCHEMA>",
        "privileges": ["SELECT", "INSERT", ...]
      }]
    }
  }
}
```

## Rules
- The key in the JSON is the **GRANTOR** user/schema (who grants the privilege)
- `"object_owner"` means privileges go to the container's `#OO` user
- The GRANTOR must exist and have `GRANT OPTION` on the objects
- Required when container artifacts (views, CVs) reference objects in **external** schemas

## Examples

### Grant SELECT from an external schema
```json
{
  "CONTAINER_ADMIN": {
    "object_owner": {
      "schema_privileges": [{
        "reference": "EXTERNAL_SCHEMA",
        "privileges": ["SELECT", "SELECT METADATA"]
      }]
    }
  }
}
```

### Grant from a UPS/secondary container user
```json
{
  "SECONDARY_CONTAINER_ADMIN": {
    "object_owner": {
      "schema_privileges": [{
        "reference": "SECONDARY_SCHEMA",
        "privileges": ["SELECT", "INSERT", "UPDATE", "DELETE"]
      }]
    }
  }
}
```

### Grant access to SYS system views
```json
{
  "SYS": {
    "object_owner": {
      "schema_object_privileges": [{
        "name": "M_SERVICES",
        "privileges": ["SELECT"]
      }]
    }
  }
}
```

### Grant from HDI_USER for cross-container access
```json
{
  "HDI_USER": {
    "object_owner": {
      "schema_privileges": [{
        "reference": "OTHER_CONTAINER",
        "privileges": ["SELECT"]
      }]
    }
  }
}
```

## Notes
- `.hdbgrants` is needed when a view or CV in the container references tables in **another schema**
- Without this grant, deployment fails with "Insufficient Privilege" on the referenced object
- For SDA virtual tables: `GRANT CREATE VIRTUAL TABLE ON REMOTE SOURCE <RS> TO <CONT>#OO` must be done manually (not via hdbgrants)
- Deploy `.hdbgrants` **before** the views/CVs that depend on the external objects