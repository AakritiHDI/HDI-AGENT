YSDI_TABLE_TYPES = {
    "TT_PARAMETERS": {
        "columns": [("KEY", "NVARCHAR(256)"), ("VALUE", "NVARCHAR(256)")],
        "description": "Key-value pairs for API call parameters.",
        "common_keys": {
            "ignore_work": "Skip work-area check when dropping (true/false)",
            "ignore_deployed": "Skip deployed-objects check when dropping (true/false)",
            "target_container": "Target container name for cross-container operations",
        },
    },
    "TT_FILESFOLDERS_CONTENT": {
        "columns": [("PATH", "NVARCHAR(511)"), ("CONTENT", "NCLOB")],
        "description": "File paths and their text/binary content for DI.WRITE.",
        "notes": "Folders have NULL content. Path separator is '/'. Root is container root.",
    },
    "TT_FILESFOLDERS": {
        "columns": [("PATH", "NVARCHAR(511)")],
        "description": "File paths for DI.MAKE deploy/undeploy lists.",
    },
    "TT_API_PRIVILEGES": {
        "columns": [
            ("PRINCIPAL_NAME", "NVARCHAR(256)"),
            ("PRIVILEGE_NAME", "NVARCHAR(256)"),
            ("OBJECT_NAME", "NVARCHAR(256)"),
        ],
        "description": "API privilege assignments for container/group management.",
    },
    "TT_SCHEMA_PRIVILEGES": {
        "columns": [
            ("PRIVILEGE_NAME", "NVARCHAR(256)"),
            ("PRINCIPAL_SCHEMA_NAME", "NVARCHAR(256)"),
            ("PRINCIPAL_NAME", "NVARCHAR(256)"),
        ],
        "description": "SQL schema privilege grants on the deployed container schema.",
    },
}

SYSDI_PREDEFINED_TABLES = {
    "T_NO_PARAMETERS": "Empty TT_PARAMETERS – use when no parameters needed.",
    "T_NO_FILESFOLDERS": "Empty TT_FILESFOLDERS.",
    "T_NO_FILESFOLDERS_PARAMETERS": "Empty parameters for file-level options in MAKE.",
    "T_DEFAULT_LIBRARIES": "Default set of HDI system libraries to configure.",
    "T_DEFAULT_CONTAINER_GROUP_ADMIN_PRIVILEGES": "Full admin privilege set for container groups.",
    "T_DEFAULT_CONTAINER_ADMIN_PRIVILEGES": "Full admin privilege set for containers.",
    "M_ALL_CONTAINERS": "Monitoring view: all HDI containers. Columns: CONTAINER_NAME, ...",
    "M_ALL_CONTAINER_GROUPS": "Monitoring view: all container groups. Columns: CONTAINER_GROUP_NAME, ...",
}

