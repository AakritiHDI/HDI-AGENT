"""
Tool definitions and dispatcher for the HANA HDI Agent.

Each tool:
  1. Has a TOOL_DEFINITIONS entry (Bedrock toolSpec format)
  2. Has a handler function called by dispatch()

Multi-user design:
  - The `username` parameter passed to each handler is the HDI_USERNAME
    (the actual person using the agent, e.g. "AAK", "SUSHANT").
  - This is DIFFERENT from HANA_USER (the database connection user, e.g. "HDI_USER").
  - All privilege grants target the HDI_USERNAME so each user can do data preview
    in DBX without manually switching to HDI_USER.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.hana_client import HANAClient


# ──────────────────────────────────────────────────────────────────────────────
# Tool definitions (Bedrock / OpenAI function-calling format)
# ──────────────────────────────────────────────────────────────────────────────

TOOL_DEFINITIONS = [
    # 1. Read artifact documentation
    {
        "toolSpec": {
            "name": "read_artifact_doc",
            "description": (
                "Read the HDI documentation for a specific artifact type from the local docs/ directory. "
                "ALWAYS call this first before generating any artifact content."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "artifact_type": {
                            "type": "string",
                            "description": (
                                "Artifact type to look up. One of: "
                                "hdbtable, hdbmigrationtable, hdbview, hdbprocedure, hdbsequence, "
                                "hdbsynonym, hdbsynonymconfig, hdbindex, hdbrole, hdbgrants, "
                                "hdbfunction, hdbtrigger, hdbtabletype, hdbconstraint, hdbflowgraph, "
                                "hdbcalculationview, hdbprojectionview, hdbvirtualtable"
                            ),
                        }
                    },
                    "required": ["artifact_type"],
                }
            },
        }
    },

    # 2. List objects in a specific schema (for synonym target discovery)
    {
        "toolSpec": {
            "name": "list_schema_objects",
            "description": (
                "List all tables, views, and procedures in a specific HANA schema or HDI container. "
                "Use this BEFORE creating a synonym to see what objects are available in the target schema. "
                "Returns object names and types grouped by TABLE / VIEW / PROCEDURE."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "schema_name": {
                            "type": "string",
                            "description": "Schema or HDI container name to inspect (e.g. 'OTHER_CONTAINER', 'SHARED_DATA').",
                        }
                    },
                    "required": ["schema_name"],
                }
            },
        }
    },

    # 2b. Grant synonym access — SELECT on source schema to container #OO and #DI
    {
        "toolSpec": {
            "name": "grant_synonym_access",
            "description": (
                "Grant SELECT (and EXECUTE for procedures) on the SOURCE schema to the TARGET container's "
                "#OO (object owner) and #DI (DI API) technical users. "
                "This is REQUIRED before deploying an .hdbsynonym — without it, DI.MAKE fails with "
                "'object not found' or 'insufficient privilege'. "
                "Call this ONCE before deploying synonyms that reference the source schema."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "source_schema": {
                            "type": "string",
                            "description": "The schema/container whose objects will be referenced via synonym (e.g. 'OTHER_CONTAINER').",
                        },
                        "target_container": {
                            "type": "string",
                            "description": "The HDI container that will own the synonym (e.g. 'AAK_CONTAINER'). Defaults to HDI_CONTAINER env var.",
                        },
                    },
                    "required": ["source_schema"],
                }
            },
        }
    },

    # 2c. List HDI containers and accessible schemas
    {
        "toolSpec": {
            "name": "list_hdi_containers",
            "description": (
                "List all HDI containers and HANA schemas visible to the current connection user. "
                "Use this to discover what containers/schemas are available as synonym targets "
                "before creating an .hdbsynonym to access external objects. "
                "Returns: HDI containers (from _SYS_DI.M_ALL_CONTAINERS) and "
                "schemas (from SYS.SCHEMAS) with their object counts."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "filter": {
                            "type": "string",
                            "description": (
                                "Optional name filter (case-insensitive substring). "
                                "e.g. 'CONTAINER' to show only container-related schemas."
                            ),
                        }
                    },
                    "required": [],
                }
            },
        }
    },

    # 3. Grant SP role — deploy companion .hdbrole + grant to HDI_USER & HANA_PRIV_USER
    {
        "toolSpec": {
            "name": "grant_sp_role",
            "description": (
                "For a structured privilege (.hdbstructuredprivilege) that is already deployed, "
                "create and deploy a companion .hdbrole that bundles the SP via schema_analytic_privileges "
                "and auto-detected views via schema_object_privileges, then grant the role to "
                "HDI_USER and HANA_PRIV_USER via GRANT_CONTAINER_SCHEMA_ROLE. "
                "Use this when data preview fails with 'insufficient privilege' after an SP is deployed."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "container_name": {
                            "type": "string",
                            "description": "HDI container name (e.g. 'AAK_CONTAINER').",
                        },
                        "privilege_name": {
                            "type": "string",
                            "description": "Structured privilege name (e.g. 'EMPLOYEE_DEPT_FILTER').",
                        },
                    },
                    "required": ["container_name", "privilege_name"],
                }
            },
        }
    },

    # 3. Create HDI container group
    {
        "toolSpec": {
            "name": "create_container_group",
            "description": (
                "Create a new HDI container group via _SYS_DI.CREATE_CONTAINER_GROUP. "
                "This is step 1 when setting up a fresh HDI environment. "
                "Requires _SYS_DI admin privileges on HANA."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "group_name": {
                            "type": "string",
                            "description": "Name of the container group to create (e.g. 'MY_GROUP'). Use UPPERCASE.",
                        }
                    },
                    "required": ["group_name"],
                }
            },
        }
    },

    # 3. Create HDI container
    {
        "toolSpec": {
            "name": "create_hdi_container",
            "description": (
                "Create a new HDI container inside a container group. "
                "This is step 2 after creating the container group. "
                "The container will be used to store and deploy HDI artifacts."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "group_name": {
                            "type": "string",
                            "description": "Name of the container group (must already exist).",
                        },
                        "container_name": {
                            "type": "string",
                            "description": "Name of the new container to create (e.g. 'MY_CONTAINER'). Use UPPERCASE.",
                        },
                    },
                    "required": ["group_name", "container_name"],
                }
            },
        }
    },

    # 4. Grant container group API
    {
        "toolSpec": {
            "name": "grant_container_group_api",
            "description": (
                "Grant the HDI container group admin API privileges to the current user "
                "using _SYS_DI.GRANT_CONTAINER_GROUP_API_PRIVILEGES with T_DEFAULT_CONTAINER_GROUP_ADMIN_PRIVILEGES. "
                "Call this after creating a container group so the current user can manage containers in it."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "group_name": {
                            "type": "string",
                            "description": "Name of the container group.",
                        },
                        "username": {
                            "type": "string",
                            "description": "HANA username to grant access to (leave blank to use current user).",
                        },
                    },
                    "required": ["group_name"],
                }
            },
        }
    },

    # 5. Grant container API privileges (DI access for a specific container)
    {
        "toolSpec": {
            "name": "grant_container_api_privileges",
            "description": (
                "Grant HDI DI API privileges for a specific container to the current user "
                "using _SYS_DI#<CG>.GRANT_CONTAINER_API_PRIVILEGES with T_DEFAULT_CONTAINER_ADMIN_PRIVILEGES. "
                "Call this after creating a container so the user can call WRITE, MAKE, DELETE, STATUS on it."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "group_name": {
                            "type": "string",
                            "description": "Name of the container group that owns this container.",
                        },
                        "container_name": {
                            "type": "string",
                            "description": "Name of the HDI container.",
                        },
                        "username": {
                            "type": "string",
                            "description": "HANA username to grant DI API access to (leave blank to use current user).",
                        },
                    },
                    "required": ["group_name", "container_name"],
                }
            },
        }
    },

    # 6. Write artifact file to HDI container
    {
        "toolSpec": {
            "name": "create_artifact_file",
            "description": (
                "Write an HDI design-time artifact file to a container via DI.WRITE. "
                "The file is staged (not yet active) until deploy_artifact is called."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "container_name": {
                            "type": "string",
                            "description": (
                                "HDI container name. If not specified, uses the HDI_CONTAINER env var. "
                                "Example: 'MY_CONTAINER'"
                            ),
                        },
                        "file_path": {
                            "type": "string",
                            "description": "Artifact path inside the container, e.g. 'src/MY_TABLE.hdbtable'",
                        },
                        "content": {
                            "type": "string",
                            "description": "Complete content of the artifact file.",
                        },
                    },
                    "required": ["file_path", "content"],
                }
            },
        }
    },

    # 7. Deploy artifact
    {
        "toolSpec": {
            "name": "deploy_artifact",
            "description": (
                "Deploy (compile and activate) all staged artifacts in an HDI container via DI.MAKE. "
                "Call this after create_artifact_file."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "container_name": {
                            "type": "string",
                            "description": (
                                "HDI container name. If not specified, uses the HDI_CONTAINER env var."
                            ),
                        }
                    },
                    "required": [],
                }
            },
        }
    },

    # 8. List artifacts
    {
        "toolSpec": {
            "name": "list_artifacts",
            "description": "List all deployed artifacts in an HDI container.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "container_name": {
                            "type": "string",
                            "description": "HDI container name. Defaults to HDI_CONTAINER env var.",
                        }
                    },
                    "required": [],
                }
            },
        }
    },

    # 9. Drop a single artifact
    {
        "toolSpec": {
            "name": "drop_artifact",
            "description": (
                "Delete a single deployed HDI artifact from a container and undeploy it via DI.DELETE + DI.MAKE. "
                "Use this to remove a specific table, view, procedure, or any artifact by its file path."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "container_name": {
                            "type": "string",
                            "description": "HDI container name. Defaults to HDI_CONTAINER env var.",
                        },
                        "file_path": {
                            "type": "string",
                            "description": "Artifact path inside the container, e.g. 'src/MY_TABLE.hdbtable'",
                        },
                    },
                    "required": ["file_path"],
                }
            },
        }
    },

    # 10. Drop ALL artifacts
    {
        "toolSpec": {
            "name": "drop_all_artifacts",
            "description": (
                "Drop (delete and undeploy) ALL artifacts from an HDI container at once. "
                "This lists all deployed artifacts, deletes them all via DI.DELETE, "
                "then runs DI.MAKE to undeploy everything. "
                "Use this when you want to completely clean a container. "
                "⚠️ This removes ALL tables, views, procedures, indexes etc. from the container."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "container_name": {
                            "type": "string",
                            "description": "HDI container name. Defaults to HDI_CONTAINER env var.",
                        }
                    },
                    "required": [],
                }
            },
        }
    },

    # 11. Drop HDI container
    {
        "toolSpec": {
            "name": "drop_container",
            "description": (
                "Drop (delete) an entire HDI container from its container group via _SYS_DI#<CG>.DROP_CONTAINER. "
                "Uses ignore_work=true and ignore_deployed=true to force-drop even if artifacts are present. "
                "This permanently removes all artifacts and the container itself. "
                "⚠️ Use with caution — this is irreversible."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "container_name": {
                            "type": "string",
                            "description": "Name of the HDI container to drop (e.g. 'AAK_CONTAINER'). Use UPPERCASE.",
                        },
                        "group_name": {
                            "type": "string",
                            "description": (
                                "Name of the container group that owns this container "
                                "(e.g. 'AAK_CONTAINER_GROUP'). If omitted, derived from username."
                            ),
                        },
                    },
                    "required": ["container_name"],
                }
            },
        }
    },

    # 12. Grant container schema privileges (for DBX data preview)
    {
        "toolSpec": {
            "name": "grant_schema_privileges",
            "description": (
                "Grant SELECT, INSERT, UPDATE, DELETE, EXECUTE and CREATE TEMPORARY TABLE "
                "on the container's runtime schema to the current user AND to HDI_USER. "
                "ALWAYS call this after deployment so the user can do data preview in HANA Database Explorer (DBX) "
                "and call procedures WITHOUT needing to manually connect as HDI_USER or set schema. "
                "This works for ALL users: AAK, SUSHANT, or any other HDI_USERNAME."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "container_name": {
                            "type": "string",
                            "description": "HDI container name. Defaults to HDI_CONTAINER env var.",
                        },
                        "username": {
                            "type": "string",
                            "description": (
                                "Specific HANA username to grant privileges to. "
                                "Leave blank to use the current user's HDI_USERNAME automatically."
                            ),
                        },
                    },
                    "required": [],
                }
            },
        }
    },

    # 13. Preview artifact data
    {
        "toolSpec": {
            "name": "preview_artifact_data",
            "description": (
                "Preview data from a deployed table or view in an HDI container. "
                "Runs SELECT TOP <row_limit> * FROM \"<container>\".\"<object_name>\". "
                "The container acts as the runtime schema. "
                "Use this to verify data after INSERT, or to inspect table contents."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "container_name": {
                            "type": "string",
                            "description": "HDI container name (runtime schema). Defaults to HDI_CONTAINER env var.",
                        },
                        "object_name": {
                            "type": "string",
                            "description": "Table or view name to preview (e.g. 'BOOK', 'ORDERS_VIEW'). Use UPPERCASE.",
                        },
                        "row_limit": {
                            "type": "integer",
                            "description": "Maximum number of rows to return (default 100).",
                        },
                    },
                    "required": ["object_name"],
                }
            },
        }
    },

    # 14. Read artifact file content
    {
        "toolSpec": {
            "name": "read_artifact_file",
            "description": (
                "Read the raw source content of a deployed artifact from the HDI container's work area via DI.READ. "
                "Use this to retrieve the XML of a calculation view, DDL of a table, body of a procedure, etc. "
                "The file_path must match the path as stored (e.g. 'src/CV_SALES.hdbcalculationview')."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "container_name": {
                            "type": "string",
                            "description": "HDI container name. Defaults to HDI_CONTAINER env var.",
                        },
                        "file_path": {
                            "type": "string",
                            "description": "Artifact path in the container, e.g. 'src/CV_SALES.hdbcalculationview'",
                        },
                    },
                    "required": ["file_path"],
                }
            },
        }
    },

    # 15. Execute SQL
    {
        "toolSpec": {
            "name": "execute_sql",
            "description": (
                "Execute a SQL statement directly on HANA and return the results. "
                "Useful for DML operations (INSERT, UPDATE, DELETE), verification queries, "
                "listing objects, or administrative queries."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "SQL statement to execute.",
                        }
                    },
                    "required": ["sql"],
                }
            },
        }
    },

    # 16. Grant remote source privilege (auto-connects as HANA_PRIV_USER)
    {
        "toolSpec": {
            "name": "grant_remote_source_privilege",
            "description": (
                "Automatically grant CREATE VIRTUAL TABLE on a remote source to a HANA user. "
                "Connects as the privileged user (HANA_PRIV_USER from HANA_PRIV_USER env var), "
                "runs GRANT CREATE VIRTUAL TABLE ON REMOTE SOURCE '<RS>' TO '<grantee>' WITH GRANT OPTION, "
                "then closes the privileged connection immediately. "
                "Call this BEFORE deploying the first .hdbgrants + .hdbvirtualtable for a new remote source. "
                "No manual SQL console step required — the agent handles the grant automatically."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "remote_source": {
                            "type": "string",
                            "description": "Remote source name (e.g. 'FED_SDA_HC').",
                        },
                        "grantee": {
                            "type": "string",
                            "description": "HANA user to receive the privilege (default: 'HDI_USER').",
                        },
                    },
                    "required": ["remote_source"],
                }
            },
        }
    },
]


# ──────────────────────────────────────────────────────────────────────────────
# Tool handlers
# ──────────────────────────────────────────────────────────────────────────────

def _default_container() -> str:
    return os.environ.get("HDI_CONTAINER", "")


def _resolve_container(args: dict, username: str) -> str:
    """
    Resolve the container name from:
      1. Tool argument 'container_name'
      2. HDI_CONTAINER env var
      3. Username-derived name: <USERNAME>_CONTAINER
    """
    container = args.get("container_name", "").strip() or _default_container()
    if username:
        uname = username.strip().upper()
        if not container or not container.upper().startswith(f"{uname}_"):
            container = f"{uname}_CONTAINER"
    return container


def _read_artifact_doc(hana: "HANAClient", args: dict, username: str = "") -> str:
    artifact_type = args.get("artifact_type", "").lower().strip()
    docs_dir = Path(__file__).parent.parent / "docs"
    doc_file = docs_dir / f"{artifact_type}.md"
    if doc_file.exists():
        return doc_file.read_text()
    for f in docs_dir.glob("*.md"):
        if artifact_type in f.stem.lower():
            return f.read_text()
    return (
        f"No documentation found for artifact type '{artifact_type}'. "
        f"Available: {[f.stem for f in docs_dir.glob('*.md')]}"
    )


def _create_container_group(hana: "HANAClient", args: dict, username: str = "") -> str:
    group_name = args.get("group_name", "").strip().upper()
    if not group_name:
        return json.dumps({"error": "group_name is required"})
    if username:
        uname = username.strip().upper()
        if not group_name.startswith(f"{uname}_"):
            group_name = f"{uname}_CONTAINER_GROUP"
    result = hana.create_container_group(group_name)
    return json.dumps(result)


def _create_hdi_container(hana: "HANAClient", args: dict, username: str = "") -> str:
    group_name = args.get("group_name", "").strip().upper()
    container_name = args.get("container_name", "").strip().upper()
    if not group_name or not container_name:
        return json.dumps({"error": "group_name and container_name are required"})
    if username:
        uname = username.strip().upper()
        if not group_name.startswith(f"{uname}_"):
            group_name = f"{uname}_CONTAINER_GROUP"
        if not container_name.startswith(f"{uname}_"):
            container_name = f"{uname}_CONTAINER"
    result = hana.create_hdi_container(group_name, container_name)
    return json.dumps(result)


def _grant_container_group_api(hana: "HANAClient", args: dict, username: str = "") -> str:
    group_name = args.get("group_name", "").strip().upper()
    # Target user: explicit arg > agent username (HDI_USERNAME) > env var
    hana_user = args.get("username", "").strip() or username or os.environ.get("HDI_USERNAME", "")
    if username:
        uname = username.strip().upper()
        if not group_name.startswith(f"{uname}_"):
            group_name = f"{uname}_CONTAINER_GROUP"
    if not group_name:
        return json.dumps({"error": "group_name is required"})
    result = hana.grant_container_group_api(group_name, hana_user or None)
    return json.dumps(result)


def _grant_container_api_privileges(hana: "HANAClient", args: dict, username: str = "") -> str:
    group_name = args.get("group_name", "").strip().upper()
    container_name = args.get("container_name", "").strip().upper()
    # Target user: explicit arg > agent username (HDI_USERNAME) > env var
    hana_user = args.get("username", "").strip() or username or os.environ.get("HDI_USERNAME", "")
    if username:
        uname = username.strip().upper()
        if not group_name.startswith(f"{uname}_"):
            group_name = f"{uname}_CONTAINER_GROUP"
        if not container_name.startswith(f"{uname}_"):
            container_name = f"{uname}_CONTAINER"
    if not group_name or not container_name:
        return json.dumps({"error": "group_name and container_name are required"})
    result = hana.grant_container_api_privileges(group_name, container_name, hana_user or None)
    return json.dumps(result)


def _create_artifact_file(hana: "HANAClient", args: dict, username: str = "") -> str:
    container = _resolve_container(args, username)
    file_path = args.get("file_path", "").strip()
    content = args.get("content", "")
    if not container:
        return json.dumps({"error": "container_name is required (or set HDI_CONTAINER env var)"})
    if not file_path:
        return json.dumps({"error": "file_path is required"})
    result = hana.write_artifact(container, file_path, content, username=username or None)
    return json.dumps(result)


def _deploy_artifact(hana: "HANAClient", args: dict, username: str = "") -> str:
    container = _resolve_container(args, username)
    if not container:
        return json.dumps({"error": "container_name is required (or set HDI_CONTAINER env var)"})
    result = hana.deploy(container, username=username or None)
    return json.dumps(result)


def _list_artifacts(hana: "HANAClient", args: dict, username: str = "") -> str:
    """
    List deployed artifacts by querying SYS.TABLES / SYS.VIEWS / SYS.PROCEDURES.

    WHY NOT DI.LIST FOR TABLES/VIEWS/PROCS:
      DI.LIST reads the HDI work area (staged files). The work area is session-volatile —
      it appears empty on every fresh session restart even when tables/views are deployed.
      This caused the agent to say "container is empty" on restart, which then triggered
      the cascade undeploy bug when the user asked to deploy a new artifact.

    SYS catalog reflects the ACTUAL deployed runtime state and is session-independent.

    CVs in _SYS_BIC are not visible to HDI_USER via SYS.VIEWS (privilege filtered), so
    DI.LIST is used as a fallback for calculation views only.
    """
    container = _resolve_container(args, username)
    if not container:
        return json.dumps({"error": "container_name is required (or set HDI_CONTAINER env var)"})
    c = container.strip().upper()
    sql = (
        f"SELECT TABLE_NAME AS OBJECT_NAME, 'TABLE' AS OBJECT_TYPE "
        f"FROM SYS.TABLES WHERE SCHEMA_NAME = '{c}' "
        f"UNION ALL "
        f"SELECT VIEW_NAME, 'VIEW' "
        f"FROM SYS.VIEWS WHERE SCHEMA_NAME = '{c}' "
        f"UNION ALL "
        f"SELECT PROCEDURE_NAME, 'PROCEDURE' "
        f"FROM SYS.PROCEDURES WHERE SCHEMA_NAME = '{c}' "
        f"ORDER BY OBJECT_TYPE, OBJECT_NAME"
    )
    rows = hana.execute_sql(sql)
    if not rows:
        rows = []
    # Surface a clear "error" key if execute_sql returned an error dict
    if len(rows) == 1 and "error" in rows[0]:
        return json.dumps(rows)

    # Calculation views: use DI.LIST as the authoritative source.
    # In this HANA Cloud instance CVs land in the container schema (SYS.VIEWS) rather than
    # _SYS_BIC.  Using DI.LIST avoids duplicates and doesn't require _SYS_BIC privileges.
    di_files = None
    cv_names_upper: set = set()
    try:
        di_files = hana.list_artifacts(c)
        if di_files and not (len(di_files) == 1 and "error" in di_files[0]):
            from pathlib import Path as _CVPath
            cv_di = [
                {"OBJECT_NAME": _CVPath(f["PATH"]).stem, "OBJECT_TYPE": "CALCULATION_VIEW"}
                for f in di_files
                if "PATH" in f and f["PATH"].endswith(".hdbcalculationview")
            ]
            cv_names_upper = {r["OBJECT_NAME"].upper() for r in cv_di}
            # Remove CV names from VIEW rows (they appear in SYS.VIEWS too)
            rows = [r for r in rows if not (r.get("OBJECT_TYPE") == "VIEW" and r.get("OBJECT_NAME", "").upper() in cv_names_upper)]
            rows = rows + cv_di
    except Exception:
        pass

    # SQLScript libraries: SYS.LIBRARIES; fall back to DI.LIST if not accessible.
    try:
        lib_rows = hana.execute_sql(
            f"SELECT LIBRARY_NAME AS OBJECT_NAME, 'LIBRARY' AS OBJECT_TYPE "
            f"FROM SYS.LIBRARIES WHERE SCHEMA_NAME = '{c}' ORDER BY LIBRARY_NAME"
        )
        if lib_rows and not (len(lib_rows) == 1 and "error" in lib_rows[0]):
            rows = rows + lib_rows
        else:
            # DI.LIST fallback
            if di_files is None:
                try:
                    di_files = hana.list_artifacts(c)
                except Exception:
                    di_files = []
            if di_files and not (len(di_files) == 1 and "error" in di_files[0]):
                from pathlib import Path as _LibPath
                lib_di = [
                    {"OBJECT_NAME": _LibPath(f["PATH"]).stem, "OBJECT_TYPE": "LIBRARY"}
                    for f in di_files
                    if "PATH" in f and f["PATH"].endswith(".hdblibrary")
                ]
                rows = rows + lib_di
    except Exception:
        pass

    return json.dumps(rows)


def _drop_artifact(hana: "HANAClient", args: dict, username: str = "") -> str:
    container = _resolve_container(args, username)
    file_path = args.get("file_path", "").strip()
    if not container:
        return json.dumps({"error": "container_name is required (or set HDI_CONTAINER env var)"})
    if not file_path:
        return json.dumps({"error": "file_path is required"})
    result = hana.drop_artifact(container, file_path)
    return json.dumps(result)


def _drop_all_artifacts(hana: "HANAClient", args: dict, username: str = "") -> str:
    """
    Drop ALL artifacts from the user's HDI container.
    Lists everything in the container, deletes via DI.DELETE, then runs DI.MAKE to undeploy.
    """
    container = _resolve_container(args, username)
    if not container:
        return json.dumps({"error": "container_name is required (or set HDI_CONTAINER env var)"})
    result = hana.drop_all_artifacts(container)
    return json.dumps(result)


def _drop_container(hana: "HANAClient", args: dict, username: str = "") -> str:
    container_name = args.get("container_name", "").strip().upper()
    group_name = args.get("group_name", "").strip().upper()
    if not container_name:
        return json.dumps({"error": "container_name is required"})
    if not group_name:
        if username:
            group_name = f"{username.strip().upper()}_CONTAINER_GROUP"
        else:
            return json.dumps({"error": "group_name is required (or provide username)"})
    result = hana.drop_container(group_name, container_name)
    return json.dumps(result)


def _configure_libraries(hana: "HANAClient", args: dict, username: str = "") -> str:
    """
    Configure the default HDI libraries for a container.

    Required for .hdblibrary deployment — without it the HDI compiler cannot resolve
    built-in SQL types (db://DOUBLE, db://INTEGER, etc.) and fails with:
      "the file requires db://DOUBLE which is not provided by any file"

    Idempotent: safe to call on an already-configured container.
    """
    container = _resolve_container(args, username)
    if not container:
        return json.dumps({"error": "container_name is required (or set HDI_CONTAINER env var)"})
    result = hana.configure_libraries(container)
    return json.dumps(result)


def _grant_schema_privileges(hana: "HANAClient", args: dict, username: str = "") -> str:
    """
    Grant schema privileges to the current user (HDI_USERNAME) AND to HDI_USER.

    Priority for the primary grantee:
      1. Explicit 'username' arg in tool call
      2. The agent's username (HDI_USERNAME, e.g. "AAK") — passed as `username` param
      3. HDI_USERNAME env var
      4. HANA_USER env var (fallback, likely HDI_USER)

    This ensures that user AAK can do data preview in DBX as AAK,
    and user SUSHANT can do data preview as SUSHANT — without anyone
    having to manually connect as HDI_USER.
    """
    container = _resolve_container(args, username)
    # Primary grantee: explicit arg > agent user (username) > env var
    hana_user = (
        args.get("username", "").strip()
        or username
        or os.environ.get("HDI_USERNAME", "")
        or os.environ.get("HANA_USER", "")
    )
    if not container:
        return json.dumps({"error": "container_name is required (or set HDI_CONTAINER env var)"})
    result = hana.grant_container_schema_privileges(container, hana_user or None)
    return json.dumps(result)


def _preview_artifact_data(hana: "HANAClient", args: dict, username: str = "") -> str:
    """
    Preview data from a deployed table or view.
    The container name is used as the runtime schema.
    """
    container = _resolve_container(args, username)
    object_name = args.get("object_name", "").strip().upper()
    row_limit = int(args.get("row_limit", 100))
    if not container:
        return json.dumps({"error": "container_name is required (or set HDI_CONTAINER env var)"})
    if not object_name:
        return json.dumps({"error": "object_name is required (e.g. 'BOOK', 'ORDERS_VIEW')"})
    rows = hana.preview_artifact_data(container, object_name, row_limit)
    return json.dumps(rows)


def _read_artifact_file(hana: "HANAClient", args: dict, username: str = "") -> str:
    container = _resolve_container(args, username)
    file_path = args.get("file_path", "").strip()
    if not container:
        return json.dumps({"error": "container_name is required (or set HDI_CONTAINER env var)"})
    if not file_path:
        return json.dumps({"error": "file_path is required (e.g. 'src/CV_SALES.hdbcalculationview')"})
    result = hana.read_artifact(container, file_path)
    return json.dumps(result)


def _list_schema_objects(hana: "HANAClient", args: dict, username: str = "") -> str:
    """List tables, views, procedures in a specific schema — for synonym target discovery."""
    schema_name = args.get("schema_name", "").strip().upper()
    if not schema_name:
        return json.dumps({"error": "schema_name is required"})
    sql = (
        f"SELECT TABLE_NAME AS OBJECT_NAME, 'TABLE' AS OBJECT_TYPE "
        f"FROM SYS.TABLES WHERE SCHEMA_NAME = '{schema_name}' "
        f"UNION ALL "
        f"SELECT VIEW_NAME, 'VIEW' "
        f"FROM SYS.VIEWS WHERE SCHEMA_NAME = '{schema_name}' "
        f"UNION ALL "
        f"SELECT PROCEDURE_NAME, 'PROCEDURE' "
        f"FROM SYS.PROCEDURES WHERE SCHEMA_NAME = '{schema_name}' "
        f"ORDER BY OBJECT_TYPE, OBJECT_NAME"
    )
    rows = hana.execute_sql(sql)
    if not rows:
        return json.dumps({"schema": schema_name, "objects": [], "message": "No objects found (schema may not exist or is empty)"})
    if len(rows) == 1 and "error" in rows[0]:
        return json.dumps(rows[0])
    return json.dumps({"schema": schema_name, "objects": rows, "count": len(rows)})


def _grant_synonym_access(hana: "HANAClient", args: dict, username: str = "") -> str:
    """
    Grant SELECT on source_schema to:
      - <target_container>#OO and #DI  (needed for MAKE / compile)
      - HANA_PRIV_USER and HDI_USERNAME     (needed for runtime synonym resolution by end users)

    Also enables cross-container access at the TARGET container's GROUP level.

    Two-step grant strategy:
      1. Direct GRANT SELECT ON SCHEMA (fast path — works when HDI_USER has GRANT OPTION)
      2. Fallback via SOURCE_SCHEMA#DI.GRANT_CONTAINER_SCHEMA_PRIVILEGES (works when
         HDI_USER has DI API access to the source container but not schema-level GRANT OPTION)

    Without granting HANA_PRIV_USER, synonyms compile and work for HDI_USER but fail for
    HANA_PRIV_USER with "insufficient privilege" because synonym resolution checks the
    CALLING USER's privileges on the underlying object, not the synonym owner's.
    """
    source_schema = args.get("source_schema", "").strip().upper()
    target_container = (args.get("target_container", "").strip().upper()
                        or _default_container().upper()
                        or (f"{username.strip().upper()}_CONTAINER" if username else ""))
    if not source_schema:
        return json.dumps({"error": "source_schema is required"})
    if not target_container:
        return json.dumps({"error": "target_container is required (or set HDI_CONTAINER env var)"})

    oo_user = f"{target_container}#OO"
    di_user = f"{target_container}#DI"

    # End users who need to query synonyms at runtime (not just compile them)
    uname = (username.strip().upper() if username
             else os.environ.get("HDI_USERNAME", "").strip().upper())
    extra_dbx = [u.strip().upper() for u in os.environ.get("HDI_DBX_USERS", "").split(",") if u.strip()]
    # Always include HANA_PRIV_USER; add uname if it's a real named user (not HDI_USER itself)
    end_users = list(dict.fromkeys(
        u for u in [os.environ.get("HANA_PRIV_USER", ""), uname] + extra_dbx
        if u and u not in ("HDI_USER", oo_user, di_user)
    ))

    # Full grant target list: technical users first, then end users
    all_targets = [oo_user, di_user] + end_users
    schema_grants = {}

    # ── Step 1: Direct schema-level GRANT (fast path) ─────────────────────────
    for target_user in all_targets:
        try:
            cur = hana.conn.cursor()
            cur.execute(
                f'GRANT SELECT, EXECUTE ON SCHEMA "{source_schema}" TO "{target_user}"'
            )
            cur.close()
            schema_grants[target_user] = "✅ granted"
        except Exception as e:
            schema_grants[target_user] = f"⚠️ {e}"
            try:
                cur.close()
            except Exception:
                pass

    # ── Step 1b: DI API fallback for failed users ─────────────────────────────
    # When HDI_USER lacks GRANT OPTION on the source schema but has DI API access
    # to it (e.g. source is another HDI container), use GRANT_CONTAINER_SCHEMA_PRIVILEGES.
    failed = [u for u, v in schema_grants.items() if "⚠️" in v]
    if failed:
        values_clause = " UNION ALL ".join(
            f"SELECT 'SELECT' AS PRIVILEGE_NAME, '' AS PRINCIPAL_SCHEMA_NAME, "
            f"'{u}' AS PRINCIPAL_NAME FROM DUMMY"
            for u in failed
        )
        fallback_sql = f"""DO BEGIN
  DECLARE lv_rc INT;
  DECLARE lv_req_id BIGINT;
  DECLARE lt_priv _SYS_DI.TT_SCHEMA_PRIVILEGES;
  DECLARE lt_params _SYS_DI.TT_PARAMETERS;
  DECLARE lt_msgs _SYS_DI.TT_MESSAGES;
  lt_priv = {values_clause};
  CALL "{source_schema}#DI"."GRANT_CONTAINER_SCHEMA_PRIVILEGES"(:lt_priv, :lt_params, lv_rc, lv_req_id, lt_msgs);
  SELECT lv_rc AS RC FROM DUMMY;
END;"""
        try:
            rows = hana.execute_sql(fallback_sql)
            if rows and isinstance(rows[0], dict) and rows[0].get("RC") == 0:
                for u in failed:
                    schema_grants[u] = "✅ granted (via DI API)"
            else:
                err = str(rows[0]) if rows else "no response"
                for u in failed:
                    schema_grants[u] = f"⚠️ DI fallback failed: {err}"
        except Exception as e:
            for u in failed:
                schema_grants[u] = f"⚠️ DI fallback error: {e}"

    # ── Step 2: Container GROUP level — enable cross-container access ──────────
    if username:
        group_name = f"{username.strip().upper()}_CONTAINER_GROUP"
    elif target_container.endswith("_CONTAINER"):
        group_name = target_container + "_GROUP"
    else:
        group_name = target_container + "_GROUP"

    cca_result = hana.configure_cross_container_access(group_name, enable=True)
    cca_msg = cca_result.get("message", "")

    all_schema_ok = all("✅" in v for v in schema_grants.values())
    return json.dumps({
        "return_code": 0 if all_schema_ok else 1,
        "source_schema": source_schema,
        "target_container": target_container,
        "target_group": group_name,
        "schema_grants": schema_grants,
        "cross_container_access": cca_msg,
        "message": (
            f"✅ Schema grants + cross-container access configured. "
            f"'{source_schema}' is now accessible from {target_container} and end users."
            if all_schema_ok else
            f"Schema grants partially failed — check 'schema_grants'. "
            f"Cross-container: {cca_msg}"
        ),
    })


def _list_hdi_containers(hana: "HANAClient", args: dict, username: str = "") -> str:
    """
    Discover available HDI containers and HANA schemas that can be used as synonym targets.
    Queries _SYS_DI.M_ALL_CONTAINERS for HDI containers and SYS.SCHEMAS for all schemas.
    """
    name_filter = args.get("filter", "").strip().upper()

    results: dict = {"hdi_containers": [], "schemas": []}

    # ── HDI containers ────────────────────────────────────────────────────────
    containers = hana.execute_sql(
        "SELECT CONTAINER_NAME, CONTAINER_GROUP_NAME "
        "FROM _SYS_DI.M_ALL_CONTAINERS "
        "ORDER BY CONTAINER_NAME"
    )
    if containers and "error" not in containers[0]:
        for c in containers:
            name = c.get("CONTAINER_NAME", "")
            if name_filter and name_filter not in name.upper():
                continue
            # Count objects in this container's runtime schema
            cnt_rows = hana.execute_sql(
                f"SELECT COUNT(*) AS CNT FROM ("
                f"SELECT TABLE_NAME AS O FROM SYS.TABLES WHERE SCHEMA_NAME = '{name}' "
                f"UNION ALL SELECT VIEW_NAME FROM SYS.VIEWS WHERE SCHEMA_NAME = '{name}' "
                f"UNION ALL SELECT PROCEDURE_NAME FROM SYS.PROCEDURES WHERE SCHEMA_NAME = '{name}')"
            )
            cnt = int(cnt_rows[0].get("CNT", 0)) if cnt_rows and "CNT" in cnt_rows[0] else 0
            results["hdi_containers"].append({
                "container": name,
                "group": c.get("CONTAINER_GROUP_NAME", ""),
                "object_count": cnt,
            })

    # ── All schemas (non-system) ──────────────────────────────────────────────
    schemas = hana.execute_sql(
        "SELECT SCHEMA_NAME, SCHEMA_OWNER "
        "FROM SYS.SCHEMAS "
        "WHERE HAS_PRIVILEGES = 'TRUE' "
        "  AND SCHEMA_NAME NOT LIKE '_SYS_%' "
        "  AND SCHEMA_NAME NOT IN ('SYS','SYSTEM','PUBLIC') "
        "ORDER BY SCHEMA_NAME"
    )
    if schemas and "error" not in schemas[0]:
        for s in schemas:
            name = s.get("SCHEMA_NAME", "")
            if name_filter and name_filter not in name.upper():
                continue
            results["schemas"].append({
                "schema": name,
                "owner": s.get("SCHEMA_OWNER", ""),
            })

    return json.dumps(results, indent=2)


def _grant_sp_role(hana: "HANAClient", args: dict, username: str = "") -> str:
    """
    For an already-deployed structured privilege, create and deploy the companion
    .hdbrole (with schema_analytic_privileges + auto-detected schema_object_privileges)
    and grant it to HDI_USER and HANA_PRIV_USER via GRANT_CONTAINER_SCHEMA_ROLE.

    Returns the real status dict from _deploy_and_grant_sp_role so failures are visible.
    """
    container = args.get("container_name", "").strip().upper() or _default_container()
    priv_name = args.get("privilege_name", "").strip().upper()
    if not container:
        return json.dumps({"error": "container_name is required (or set HDI_CONTAINER env var)"})
    if not priv_name:
        return json.dumps({"error": "privilege_name is required (e.g. 'EMPLOYEE_DEPT_FILTER')"})
    try:
        status = hana._deploy_and_grant_sp_role(container, priv_name, username or None)
        # Determine overall success: WRITE, MAKE, and all grants must have rc=0
        write_rc = status.get("write_rc", -1)
        make_rc = status.get("make_rc", -1)
        grants = status.get("grants", {})
        grant_failures = {u: r for u, r in grants.items() if r != 0}
        if write_rc != 0:
            return json.dumps({
                "return_code": write_rc,
                "message": f"WRITE failed (rc={write_rc}) — role '{priv_name}_ROLE' not deployed. "
                           "Check logs for details.",
                "status": status,
            })
        if make_rc != 0:
            return json.dumps({
                "return_code": make_rc,
                "message": f"MAKE failed (rc={make_rc}) — role '{priv_name}_ROLE' not activated. "
                           "Check logs for details.",
                "status": status,
            })
        if grant_failures:
            return json.dumps({
                "return_code": 1,
                "message": f"Role '{priv_name}_ROLE' deployed but grant failed for: {grant_failures}",
                "status": status,
            })
        return json.dumps({
            "return_code": 0,
            "message": (
                f"Role '{priv_name}_ROLE' deployed and granted to "
                f"{list(grants.keys())} in {container}. Data preview should now work."
            ),
            "status": status,
        })
    except Exception as e:
        return json.dumps({"return_code": 1, "message": str(e)})


def _execute_sql(hana: "HANAClient", args: dict, username: str = "") -> str:
    sql = args.get("sql", "").strip()
    if not sql:
        return json.dumps({"error": "sql is required"})
    try:
        rows = hana.execute_sql(sql)
        return json.dumps(rows)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _grant_remote_source_privilege(hana: "HANAClient", args: dict, username: str = "") -> str:
    """
    Grant CREATE VIRTUAL TABLE on a remote source.
    Grants to <container>#DI (so .hdbgrants can grant to #OO during MAKE) and HDI_USER.
    container_name is resolved from args or username.
    """
    remote_source = args.get("remote_source", "").strip()
    if not remote_source:
        return json.dumps({"return_code": 1, "message": "remote_source is required"})
    # Resolve container to derive #DI user
    container_name = (
        args.get("container_name", "").strip().upper()
        or _default_container().upper()
        or (f"{username.strip().upper()}_CONTAINER" if username else "")
    )
    # explicit grantee override (optional — normally leave blank so container_name drives it)
    grantee = args.get("grantee", "").strip()
    try:
        result = hana.grant_remote_source_privilege(
            remote_source=remote_source,
            container_name=container_name,
            grantee=grantee,
        )
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"return_code": 1, "message": str(e)})


# ──────────────────────────────────────────────────────────────────────────────
# Dispatcher
# ──────────────────────────────────────────────────────────────────────────────

_HANDLERS = {
    "list_schema_objects": _list_schema_objects,
    "grant_synonym_access": _grant_synonym_access,
    "list_hdi_containers": _list_hdi_containers,
    "grant_sp_role": _grant_sp_role,
    "read_artifact_doc": _read_artifact_doc,
    "create_container_group": _create_container_group,
    "create_hdi_container": _create_hdi_container,
    "grant_container_group_api": _grant_container_group_api,
    "grant_container_api_privileges": _grant_container_api_privileges,
    "create_artifact_file": _create_artifact_file,
    "deploy_artifact": _deploy_artifact,
    "list_artifacts": _list_artifacts,
    "drop_artifact": _drop_artifact,
    "drop_all_artifacts": _drop_all_artifacts,
    "drop_container": _drop_container,
    "configure_libraries": _configure_libraries,
    "grant_schema_privileges": _grant_schema_privileges,
    "preview_artifact_data": _preview_artifact_data,
    "read_artifact_file": _read_artifact_file,
    "execute_sql": _execute_sql,
    "grant_remote_source_privilege": _grant_remote_source_privilege,
}


def dispatch(hana: "HANAClient", tool_name: str, arguments: dict, username: str = "") -> str:
    """Route a tool call to its handler. Returns a JSON string."""
    handler = _HANDLERS.get(tool_name)
    if handler is None:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    try:
        return handler(hana, arguments, username=username)
    except Exception as e:
        return json.dumps({"error": f"Tool '{tool_name}' raised: {str(e)}"})