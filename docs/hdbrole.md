# hdbrole — HANA HDI Database Role Artifact

## Overview
An `.hdbrole` file defines a **database role** that grants SELECT/EXECUTE/INSERT privileges on container objects. Roles are assigned to users after deployment.

## File Extension
`.hdbrole`

## File Path in Container
`src/<ROLE_NAME>.hdbrole`

## Syntax
JSON file defining role name and schema privileges.

## Examples

### Default access role (SELECT + EXECUTE on entire schema)
```json
{
  "role": {
    "name": "default_access_role",
    "schema_privileges": [{
      "privileges": ["SELECT", "EXECUTE", "CREATE TEMPORARY TABLE"]
    }]
  }
}
```

### Named reporting role (SELECT only)
```json
{
  "role": {
    "name": "REPORTING_ROLE",
    "schema_privileges": [{"privileges": ["SELECT"]}]
  }
}
```

### Full DML role
```json
{
  "role": {
    "name": "DATA_EDITOR_ROLE",
    "schema_privileges": [{
      "privileges": ["SELECT", "INSERT", "UPDATE", "DELETE", "EXECUTE"]
    }]
  }
}
```

## Granting the Role
After deployment, grant to a user:
```sql
GRANT 'AAK_CONTAINER::default_access_role' TO MY_USER;
```

## Notes
- The `default_access_role` is a special name — it can be auto-assigned to users accessing the container
- Role name in JSON must match the file name (without extension)
- Deploy `.hdbrole` alongside the tables/views it should grant access to
- To drop a role: use `drop_artifact` with `file_path = "src/<ROLE_NAME>.hdbrole"`
- For object-level (not schema-level) privileges, use `.hdbgrants` instead