"""
HANA HDI client — wraps hdbcli for HDI container management and artifact deployment.
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from hdbcli import dbapi
from dotenv import load_dotenv

load_dotenv()

# ── HDI logger ────────────────────────────────────────────────────────────────
# Logger is configured in HANAClient.__init__ with a per-session file inside
# logs/sessions/.  Getting the logger here makes it available to all module-level
# code before __init__ runs (writes are silently discarded until __init__ adds
# a file handler).
# ─────────────────────────────────────────────────────────────────────────────
_log = logging.getLogger("hdi")
_log.setLevel(logging.DEBUG)

_LOG_ROOT = Path(__file__).parent.parent / "logs"


class HANAClient:
    def __init__(self) -> None:
        host = os.environ["HANA_HOST"]
        port = int(os.environ.get("HANA_PORT", 443))
        user = os.environ["HANA_USER"]
        password = os.environ["HANA_PASSWORD"]

        self.conn = dbapi.connect(
            address=host,
            port=port,
            user=user,
            password=password,
            encrypt=True,
            sslValidateCertificate=False,
        )
        self.user = user
        self._pending_paths: list = []
        self._di_access_granted: set = set()

        from datetime import datetime as _dt
        _session_ts = _dt.now().strftime("%Y-%m-%d_%H-%M-%S")
        _session_ts_readable = _dt.now().strftime("%Y-%m-%d %H:%M:%S")

        (_LOG_ROOT / "sessions").mkdir(parents=True, exist_ok=True)
        (_LOG_ROOT / "artifacts").mkdir(parents=True, exist_ok=True)

        if not _log.handlers:
            _fmt = logging.Formatter(
                "%(asctime)s.%(msecs)03d | %(levelname)-7s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            _fh = logging.FileHandler(
                _LOG_ROOT / "sessions" / f"session_{_session_ts}.log",
                encoding="utf-8",
            )
            _fh.setLevel(logging.INFO)
            _fh.setFormatter(_fmt)
            _log.addHandler(_fh)

        _log.info("=" * 70)
        _log.info("SESSION START | %s | HANA_USER=%s", _session_ts_readable, user)
        _log.info("=" * 70)

        _startup_container = os.environ.get("HDI_CONTAINER", "").strip().upper()
        if _startup_container:
            self._update_artifact_tree(_startup_container)

    # ── Raw SQL ──────────────────────────────────────────────────────────────

    def execute_sql(self, sql: str) -> list:
        """Execute arbitrary SQL and return rows as a list of dicts."""
        cur = self.conn.cursor()
        try:
            cur.execute(sql)
            if cur.description:
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
            return []
        except Exception as e:
            return [{"error": str(e)}]
        finally:
            cur.close()

    # ── Container group ───────────────────────────────────────────────────────

    def configure_cross_container_access(self, group_name: str, enable: bool = True) -> dict:
        value = "True" if enable else ""
        cur = self.conn.cursor()
        try:
            cur.execute("CREATE LOCAL TEMPORARY COLUMN TABLE #CCA_PARAMS LIKE _SYS_DI.TT_PARAMETERS")
            cur.execute(
                "INSERT INTO #CCA_PARAMS (KEY, VALUE) VALUES ('enable_cross_container_access', ?)",
                (value,)
            )
            cur.execute(
                f"CALL _SYS_DI.CONFIGURE_CONTAINER_GROUP_PARAMETERS("
                f"'{group_name}', #CCA_PARAMS, _SYS_DI.T_NO_PARAMETERS, ?, ?, ?)"
            )
            row = cur.fetchone()
            rc = int(row[1]) if row else 1
            req_id = int(row[0]) if row else 0
            messages = []
            while cur.nextset():
                for mrow in cur:
                    messages.append({"type": mrow[0], "code": mrow[1], "message": mrow[2]})
            if rc <= 1:  # 0=success, 1=success-with-warnings
                action = "enabled" if enable else "disabled"
                _log.info("CROSS_CONTAINER | %s | %s req=%s", group_name, action, req_id)
                return {"return_code": 0, "message": f"cross_container_access {action} on {group_name}", "request_id": req_id}
            errors = [m["message"] for m in messages if m.get("type") == "ERROR"]
            _log.info("CROSS_CONTAINER | %s | rc=%d %s", group_name, rc, errors)
            return {"return_code": rc, "message": "; ".join(errors[:3]) or f"rc={rc}", "request_id": req_id}
        except Exception as e:
            _log.error("CROSS_CONTAINER | %s | exception: %s", group_name, e)
            return {"return_code": 1, "message": str(e), "request_id": 0}
        finally:
            try:
                cur.execute("DROP TABLE #CCA_PARAMS")
            except Exception:
                pass
            cur.close()

    def create_container_group(self, group_name: str) -> dict:
        sql = f"CALL _SYS_DI.CREATE_CONTAINER_GROUP('{group_name}', _SYS_DI.T_NO_PARAMETERS, ?, ?, ?)"
        return self._call_di_proc(sql, context=f"create_container_group({group_name})")

    def create_hdi_container(self, group_name: str, container_name: str) -> dict:
        """
        Create an HDI container inside a container group.

        Uses a DO BEGIN anonymous block instead of a direct CALL with ? OUT parameters
        to avoid the hdbcli prepare-step privilege check that raises (258, insufficient
        privilege) even when the calling user has EXECUTE on the procedure.
        The DO BEGIN approach sends the statement as a single anonymous block — no
        client-side prepare — which matches the manual SQL console execution model.
        """
        sql = f"""DO BEGIN
  DECLARE lv_rc     INT;
  DECLARE lv_req_id BIGINT;
  DECLARE lt_msgs   _SYS_DI.TT_MESSAGES;
  DECLARE lt_params _SYS_DI.TT_PARAMETERS;
  CALL "_SYS_DI#{group_name}"."CREATE_CONTAINER"(
      '{container_name}', :lt_params, lv_rc, lv_req_id, lt_msgs);
  SELECT lv_rc AS RC, lv_req_id AS REQ_ID FROM DUMMY;
END;"""
        cur = self.conn.cursor()
        try:
            cur.execute(sql)
            row = cur.fetchone()
            rc = int(row[0]) if row else 1          # RC is first SELECT column
            req_id = int(row[1]) if row else 0
            if rc <= 1:
                _log.info("CREATE_CONTAINER | %s | rc=%d req=%d", container_name, rc, req_id)
                return {"return_code": 0, "message": f"Container '{container_name}' created in group '{group_name}'", "request_id": req_id}
            _log.error("CREATE_CONTAINER | %s | rc=%d", container_name, rc)
            return {"return_code": rc, "message": f"Error in create_container({container_name}): rc={rc}", "request_id": req_id}
        except Exception as e:
            _log.error("CREATE_CONTAINER | %s | exception: %s", container_name, e)
            return {"return_code": 1, "message": f"Error in create_container({container_name}): {e}", "request_id": 0}
        finally:
            cur.close()

    def grant_container_group_api(self, group_name: str, username: str = None) -> dict:
        """
        Grant HDI container group admin API privileges to the connection user (CURRENT_USER).

        Uses a DO BEGIN anonymous block with CURRENT_USER — EXACTLY matching the working
        manual SQL pattern.
        """
        sql = f"""DO BEGIN
  DECLARE lv_rc     INT;
  DECLARE lv_req_id BIGINT;
  DECLARE lt_msgs   _SYS_DI.TT_MESSAGES;
  DECLARE lt_params _SYS_DI.TT_PARAMETERS;
  DECLARE lt_privs  _SYS_DI.TT_API_PRIVILEGES;
  lt_privs = SELECT PRIVILEGE_NAME, OBJECT_NAME, '' AS PRINCIPAL_SCHEMA_NAME, CURRENT_USER AS PRINCIPAL_NAME
             FROM _SYS_DI.T_DEFAULT_CONTAINER_GROUP_ADMIN_PRIVILEGES;
  CALL _SYS_DI.GRANT_CONTAINER_GROUP_API_PRIVILEGES(
      '{group_name}', :lt_privs, :lt_params, lv_rc, lv_req_id, lt_msgs);
  SELECT lv_rc AS RC, lv_req_id AS REQ_ID FROM DUMMY;
END;"""
        cur = self.conn.cursor()
        try:
            cur.execute(sql)
            row = cur.fetchone()
            rc = int(row[0]) if row else 1       # RC is first SELECT column in DO BEGIN
            req_id = int(row[1]) if row else 0
            if rc == 0 or rc == 1:
                _log.info("GRANT_GROUP_API | %s | rc=%d req=%d user=%s", group_name, rc, req_id, "CURRENT_USER")
                return {"return_code": 0, "message": f"Container group API granted (CURRENT_USER) on {group_name}", "request_id": req_id}
            _log.error("GRANT_GROUP_API | %s | rc=%d (FAILED)", group_name, rc)
            return {"return_code": rc, "message": f"rc={rc}", "request_id": req_id}
        except Exception as e:
            _log.error("GRANT_GROUP_API | %s | exception: %s", group_name, e)
            return {"return_code": 1, "message": str(e), "request_id": 0}
        finally:
            cur.close()

    def grant_container_api_privileges(self, group_name: str, container_name: str, username: str = None) -> dict:
        """
        Grant HDI DI API privileges for a specific container to the connection user (CURRENT_USER).

        WHY CURRENT_USER ONLY:
        - HDI_USERNAME (e.g. 'HDIAGENT') is NOT a real HANA database user; it is only
          used to derive the container name.  Including it as a grantee causes
          GRANT_CONTAINER_API_PRIVILEGES to return rc=-1 (error), granting nothing at all.
        - CURRENT_USER = HDI_USER (the actual HANA connection user).
        """
        explicit_user = (username or "").strip().upper()
        connection_user = self.user.upper()
        use_current_user = (not explicit_user) or (explicit_user != connection_user)
        grantee_sql = "CURRENT_USER" if use_current_user else f"'{explicit_user}'"
        display_grantees = ["CURRENT_USER"] if use_current_user else [explicit_user]

        sql = f"""DO BEGIN
  DECLARE lv_rc     INT;
  DECLARE lv_req_id BIGINT;
  DECLARE lt_msgs   _SYS_DI.TT_MESSAGES;
  DECLARE lt_params _SYS_DI.TT_PARAMETERS;
  DECLARE lt_privs  _SYS_DI.TT_API_PRIVILEGES;
  lt_privs = SELECT PRIVILEGE_NAME, OBJECT_NAME, '' AS PRINCIPAL_SCHEMA_NAME, {grantee_sql} AS PRINCIPAL_NAME
             FROM _SYS_DI.T_DEFAULT_CONTAINER_ADMIN_PRIVILEGES;
  CALL "_SYS_DI#{group_name}"."GRANT_CONTAINER_API_PRIVILEGES"(
      '{container_name}', :lt_privs, :lt_params, lv_rc, lv_req_id, lt_msgs);
  SELECT lv_rc AS RC, lv_req_id AS REQ_ID FROM DUMMY;
END;"""
        cur = self.conn.cursor()
        try:
            cur.execute(sql)
            row = cur.fetchone()
            rc = int(row[0]) if row else 1
            req_id = int(row[1]) if row else 0
            ok = (rc == 0 or rc == 1)
            if ok:
                _log.info("GRANT_CONTAINER_API | %s | rc=%d req=%d grantees=%s", container_name, rc, req_id, display_grantees)
                return {"return_code": 0, "message": f"Container API privileges granted to {', '.join(display_grantees)} on {container_name}", "request_id": req_id}
            _log.error("GRANT_CONTAINER_API | %s | rc=%d (FAILED)", container_name, rc)
            return {"return_code": rc, "message": f"rc={rc}", "request_id": req_id}
        except Exception as e:
            _log.error("GRANT_CONTAINER_API | %s | exception: %s", container_name, e)
            return {"return_code": 1, "message": str(e), "request_id": 0}
        finally:
            cur.close()

    def grant_container_schema_privileges(self, container: str, username: str = None) -> dict:
        """
        Grant SELECT/INSERT/UPDATE/DELETE/EXECUTE/CREATE TEMPORARY TABLE on the container's
        runtime schema to ALL relevant users.
        CRITICAL: GRANT_CONTAINER_SCHEMA_PRIVILEGES uses REPLACE semantics — ALL users
        MUST be inserted into the SAME temp table in ONE call.
        """
        primary_user = (username or os.environ.get("HDI_USERNAME", "") or self.user).upper()
        extra_dbx = [u.strip().upper() for u in os.environ.get("HDI_DBX_USERS", "").split(",") if u.strip()]
        SYSTEM_USERS = {"HDI_USER", "HE2E_USER"}
        all_candidates = list(dict.fromkeys([primary_user] + list(SYSTEM_USERS) + extra_dbx))
        target_users = all_candidates
        # NOTE: "CREATE TEMPORARY TABLE" is NOT a valid privilege for GRANT_CONTAINER_SCHEMA_PRIVILEGES.
        # Including it causes the entire DI API call to fail (rc≠0), blocking SELECT grants for all users.
        privileges = ["SELECT", "INSERT", "UPDATE", "DELETE", "EXECUTE"]

        di_result = "skipped"

        def _run_di_grant(users_to_grant):
            cur = self.conn.cursor()
            try:
                cur.execute("CREATE LOCAL TEMPORARY COLUMN TABLE #SP LIKE _SYS_DI.TT_SCHEMA_PRIVILEGES")
                for target in users_to_grant:
                    for priv in privileges:
                        cur.execute(
                            "INSERT INTO #SP (PRIVILEGE_NAME, PRINCIPAL_SCHEMA_NAME, PRINCIPAL_NAME) VALUES (?, '', ?)",
                            (priv, target),
                        )
                cur.execute(
                    f'CALL "{container}#DI".GRANT_CONTAINER_SCHEMA_PRIVILEGES(#SP, _SYS_DI.T_NO_PARAMETERS, ?, ?, ?)'
                )
                row = cur.fetchone()
                rc = int(row[1]) if row else 1
                messages = []
                while cur.nextset():
                    for mrow in cur:
                        messages.append({"type": mrow[0], "code": mrow[1], "message": mrow[2]})
                if rc == 0:
                    return 0, f"DI API granted to: {', '.join(users_to_grant)}"
                errors = [m["message"] for m in messages if m.get("type") == "ERROR"]
                return rc, f"DI API rc={rc}: {'; '.join(errors[:2])}"
            except Exception as e:
                return 1, f"DI API exception: {e}"
            finally:
                try:
                    cur.execute("DROP TABLE #SP")
                except Exception:
                    pass
                cur.close()

        di_rc, di_result = _run_di_grant(target_users)
        if di_rc != 0:
            fallback_users = [u for u in target_users if u in ("HDI_USER", "HE2E_USER")]
            if fallback_users:
                di_rc2, di_result2 = _run_di_grant(fallback_users)
                di_result = f"{di_result} -> retry fallback: {di_result2}"
        _log.info("SCHEMA_GRANT | %s | DI API rc=%d | %s", container, di_rc, di_result)

        sql_results = []
        for target in target_users:
            try:
                cur2 = self.conn.cursor()
                cur2.execute(
                    f"GRANT SELECT, INSERT, UPDATE, DELETE, EXECUTE "
                    f'ON SCHEMA "{container}" TO {target}'
                )
                sql_results.append(f"OK {target}")
                cur2.close()
            except Exception as e:
                sql_results.append(f"WARN {target}: {e}")
                try:
                    cur2.close()
                except Exception:
                    pass

        sql_summary = " | ".join(sql_results)
        return {
            "return_code": 0,
            "message": (
                f"Schema privileges on {container}: "
                f"{di_result} | Direct SQL: [{sql_summary}]"
            ),
            "request_id": 0,
        }

    # ── Artifact operations ───────────────────────────────────────────────────

    def _write_file_to_workarea(self, container: str, path: str, content: str) -> dict:
        """
        Low-level: write one file to the HDI work area via DI.WRITE.
        Does NOT add to _pending_paths.

        Uses a DO BEGIN anonymous block with a typed _SYS_DI.TT_FILESFOLDERS_CONTENT
        table variable. Content is hex-encoded (HEXTOBIN) to avoid SQL injection.

        Auto-creates the src/ folder in the same WRITE call via UNION ALL.
        """
        _log.debug("WRITE | %s | %s | staging...", container, path)
        content_bytes = content.encode("utf-8")
        hex_content = content_bytes.hex().upper()
        path_esc = path.replace("'", "''")

        sql = (
            "DO BEGIN\n"
            "  DECLARE v_rc     INTEGER;\n"
            "  DECLARE v_req_id BIGINT;\n"
            "  DECLARE lt_msgs  _SYS_DI.TT_MESSAGES;\n"
            "  DECLARE lt_prm   _SYS_DI.TT_PARAMETERS;\n"
            "  DECLARE lt_paths _SYS_DI.TT_FILESFOLDERS_CONTENT;\n"
            f"  lt_paths = SELECT 'src/' AS PATH, NULL AS CONTENT FROM DUMMY\n"
            f"             UNION ALL\n"
            f"             SELECT '{path_esc}' AS PATH, HEXTOBIN('{hex_content}') AS CONTENT FROM DUMMY;\n"
            f'  CALL "{container}#DI".WRITE(:lt_paths, :lt_prm, v_rc, v_req_id, :lt_msgs);\n'
            "  SELECT v_rc AS RC, v_req_id AS REQ_ID FROM DUMMY;\n"
            "  SELECT SEVERITY AS TYPE, MESSAGE_CODE AS CODE, MESSAGE FROM :lt_msgs;\n"
            "END;"
        )
        cur = self.conn.cursor()
        try:
            cur.execute(sql)
            row = cur.fetchone()
            rc = int(row[0]) if row else 1
            req_id = int(row[1]) if row else 0
            messages = []
            while cur.nextset():
                for mrow in cur:
                    if len(mrow) >= 3:
                        messages.append({"type": mrow[0], "code": mrow[1], "message": mrow[2]})
            if rc == 0:
                _log.debug("WRITE | %s | %s | rc=0 req=%s", container, path, req_id)
                return {"return_code": 0, "message": f"Written (request_id={req_id})", "request_id": req_id}
            msg = "; ".join(m["message"] for m in messages[:3]) or f"WRITE failed (rc={rc})"
            _log.info("WRITE | %s | %s | rc=%d req=%s msg=%s", container, path, rc, req_id, msg)
            return {"return_code": rc, "message": msg, "request_id": req_id}
        except Exception as e:
            _log.error("WRITE | %s | %s | exception: %s", container, path, e)
            return {"return_code": 1, "message": f"Error writing: {e}", "request_id": 0}
        finally:
            cur.close()

    def write_artifact(self, container: str, path: str, content: str, username: str = None) -> dict:
        """Stage a design-time artifact via DI.WRITE (does NOT deploy).
        Adds path to _pending_paths for targeted MAKE in deploy().
        """
        self._ensure_di_api_access(container, username)
        result = self._write_file_to_workarea(container, path, content)

        if result["return_code"] != 0 and result.get("message", "").startswith("WRITE failed (rc="):
            hdiconfig_key = f"hdiconfig_{container.upper()}"
            if hdiconfig_key not in self._di_access_granted:
                _log.info(
                    "WRITE | %s | %s | rc=1 no HANA message — "
                    "updating .hdiconfig to register new plugins, then retrying",
                    container, path,
                )
                cfg_wr = self._write_file_to_workarea(container, ".hdiconfig", self._HDICONFIG)
                if cfg_wr["return_code"] == 0:
                    cfg_mk = self._run_make(container, [".hdiconfig"])
                    if cfg_mk["return_code"] == 0:
                        self._di_access_granted.add(hdiconfig_key)
                        _log.info("WRITE | %s | .hdiconfig updated -- retrying WRITE for %s", container, path)
                        result = self._write_file_to_workarea(container, path, content)
                    else:
                        errs = [m["message"] for m in cfg_mk.get("messages", []) if m.get("type") == "ERROR"]
                        _log.info("WRITE | %s | .hdiconfig MAKE failed: %s", container, errs)
                else:
                    _log.info("WRITE | %s | .hdiconfig WRITE failed: %s", container, cfg_wr.get("message"))

        if result["return_code"] == 0:
            if path not in self._pending_paths:
                self._pending_paths.append(path)
        return result

    # The .hdiconfig content that registers ALL supported HDI plugin types.
    _HDICONFIG = """{
    "minimum_feature_version": "1015",
    "file_suffixes": {
        "hdbapplicationtime":        { "plugin_name": "com.sap.hana.di.applicationtime" },
        "hdbcalculationview":        { "plugin_name": "com.sap.hana.di.calculationview" },
        "hdbcollection":             { "plugin_name": "com.sap.hana.di.collection" },
        "hdbcollectionindex":        { "plugin_name": "com.sap.hana.di.collection.index" },
        "hdbcollectionadjindex":     { "plugin_name": "com.sap.hana.di.collection.adjacency_index" },
        "hdbconstraint":             { "plugin_name": "com.sap.hana.di.constraint" },
        "txt":                       { "plugin_name": "com.sap.hana.di.copyonly" },
        "hdbdropcreatetable":        { "plugin_name": "com.sap.hana.di.dropcreatetable" },
        "hdbeshconfig":              { "plugin_name": "com.sap.hana.di.eshconfig" },
        "hdbflowgraph":              { "plugin_name": "com.sap.hana.di.flowgraph" },
        "hdbfunction":               { "plugin_name": "com.sap.hana.di.function" },
        "hdbgraphworkspace":         { "plugin_name": "com.sap.hana.di.graphworkspace" },
        "hdbindex":                  { "plugin_name": "com.sap.hana.di.index" },
        "hdblibrary":                { "plugin_name": "com.sap.hana.di.library" },
        "hdblogicalschema":          { "plugin_name": "com.sap.hana.di.logicalschema" },
        "hdbprocedure":              { "plugin_name": "com.sap.hana.di.procedure" },
        "hdbprojectionview":         { "plugin_name": "com.sap.hana.di.projectionview" },
        "hdbprojectionviewconfig":   { "plugin_name": "com.sap.hana.di.projectionview.config" },
        "hdbreptask":                { "plugin_name": "com.sap.hana.di.reptask" },
        "hdbresultcache":            { "plugin_name": "com.sap.hana.di.resultcache" },
        "hdbrole":                   { "plugin_name": "com.sap.hana.di.role" },
        "hdbroleconfig":             { "plugin_name": "com.sap.hana.di.role.config" },
        "hdbsearchruleset":          { "plugin_name": "com.sap.hana.di.searchruleset" },
        "hdbsequence":               { "plugin_name": "com.sap.hana.di.sequence" },
        "hdbanalyticprivilege":      { "plugin_name": "com.sap.hana.di.analyticprivilege" },
        "hdbview":                   { "plugin_name": "com.sap.hana.di.view" },
        "hdbstatistics":             { "plugin_name": "com.sap.hana.di.statistics" },
        "hdbstructuredprivilege":    { "plugin_name": "com.sap.hana.di.structuredprivilege" },
        "hdbstructuredfilter":       { "plugin_name": "com.sap.hana.di.structuredfilter" },
        "hdbsynonym":                { "plugin_name": "com.sap.hana.di.synonym" },
        "hdbsynonymconfig":          { "plugin_name": "com.sap.hana.di.synonym.config" },
        "hdbsystemversioning":       { "plugin_name": "com.sap.hana.di.systemversioning" },
        "hdbtable":                  { "plugin_name": "com.sap.hana.di.table" },
        "hdbmigrationtable":         { "plugin_name": "com.sap.hana.di.table.migration" },
        "hdbtabletype":              { "plugin_name": "com.sap.hana.di.tabletype" },
        "hdbtabledata":              { "plugin_name": "com.sap.hana.di.tabledata" },
        "csv":                       { "plugin_name": "com.sap.hana.di.tabledata.source" },
        "properties":                { "plugin_name": "com.sap.hana.di.tabledata.properties" },
        "hdbtrigger":                { "plugin_name": "com.sap.hana.di.trigger" },
        "hdbvirtualfunction":        { "plugin_name": "com.sap.hana.di.virtualfunction" },
        "hdbvirtualfunctionconfig":  { "plugin_name": "com.sap.hana.di.virtualfunction.config" },
        "hdbvirtualprocedure":       { "plugin_name": "com.sap.hana.di.virtualprocedure" },
        "hdbvirtualprocedureconfig": { "plugin_name": "com.sap.hana.di.virtualprocedure.config" },
        "hdbvirtualtable":           { "plugin_name": "com.sap.hana.di.virtualtable" },
        "hdbvirtualtableconfig":     { "plugin_name": "com.sap.hana.di.virtualtable.config" },
        "hdbschedulerjob":           { "plugin_name": "com.sap.hana.di.schedulerjob" },
        "hdbfabricvirtualtable":     { "plugin_name": "com.sap.hana.di.sharedreplica" },
        "hdbgrants":                 { "plugin_name": "com.sap.hana.di.grants" }
    }
}"""

    def _run_make(self, container: str, deploy_paths: list, undeploy_paths: list = None) -> dict:
        """
        Internal: run DI.MAKE with a specific deploy/undeploy list.
        MAKE signature: (DEPLOY, UNDEPLOY, PATH_PARAMETERS, PARAMETERS, RC, REQ_ID, MESSAGES)
        PATH_PARAMETERS is TT_FILESFOLDERS_PARAMETERS — empty but required as 3rd IN param.
        """
        undeploy_paths = undeploy_paths or []
        _log.debug("MAKE_START | %s | deploy=%s | undeploy=%s", container, deploy_paths, undeploy_paths)
        t0 = time.monotonic()
        cur = self.conn.cursor()
        try:
            cur.execute("CREATE LOCAL TEMPORARY COLUMN TABLE #MAKE_PARAMS LIKE _SYS_DI.TT_PARAMETERS")
            cur.execute(
                "INSERT INTO #MAKE_PARAMS (KEY, VALUE) VALUES ('com.sap.hana.di.view/optimized_replace', 'true')"
            )
            cur.execute("CREATE LOCAL TEMPORARY COLUMN TABLE #DEPLOY_LIST LIKE _SYS_DI.TT_FILESFOLDERS")
            for p in deploy_paths:
                cur.execute("INSERT INTO #DEPLOY_LIST (PATH) VALUES (?)", (p,))
            cur.execute("CREATE LOCAL TEMPORARY COLUMN TABLE #PATH_PARAMS LIKE _SYS_DI.TT_FILESFOLDERS_PARAMETERS")
            cur.execute(
                f'CALL "{container}#DI".MAKE('
                f'#DEPLOY_LIST, _SYS_DI.T_NO_FILESFOLDERS, '
                f'#PATH_PARAMS, #MAKE_PARAMS, ?, ?, ?)'
            )
            row = cur.fetchone()
            req_id = int(row[0]) if row else 0
            rc = int(row[1]) if row else 1
            messages = []
            while cur.nextset():
                for mrow in cur:
                    messages.append({"type": mrow[0], "code": mrow[1], "message": mrow[2]})

            elapsed = time.monotonic() - t0
            for m in messages:
                msg_type = (m.get("type") or "INFO").upper()
                msg_text = m.get("message", "")
                msg_path = m.get("path", "")
                if msg_type == "ERROR":
                    _log.debug("HANA_MSG | %s | ERROR | %s | %s", container, msg_path or "-", msg_text)
                elif msg_type == "WARNING":
                    _log.debug("HANA_MSG | %s | WARN  | %s | %s", container, msg_path or "-", msg_text)
                else:
                    _log.debug("HANA_MSG | %s | %-5s | %s | %s", container, msg_type, msg_path or "-", msg_text)

            success = rc <= 1
            status = "OK" if success else "FAIL"
            _log.debug("MAKE_END | %s | rc=%d %s | request_id=%s | elapsed=%.2fs", container, rc, status, req_id, elapsed)
            return {"return_code": 0 if success else rc, "request_id": req_id, "messages": messages}
        except Exception as e:
            elapsed = time.monotonic() - t0
            _log.debug("MAKE_END | %s | EXCEPTION after %.2fs: %s", container, elapsed, e)
            return {"return_code": 1, "request_id": 0, "messages": [{"type": "ERROR", "message": str(e)}]}
        finally:
            for tbl in ["#MAKE_PARAMS", "#DEPLOY_LIST", "#PATH_PARAMS"]:
                try:
                    cur.execute(f"DROP TABLE {tbl}")
                except Exception:
                    pass
            cur.close()

    def _deploy_and_grant_sp_role(self, container: str, priv_name: str, username: str = None) -> dict:
        """
        Deploy a companion .hdbrole that bundles a structured privilege via
        schema_analytic_privileges, then grant the role to HDI_USER + HE2E_USER.
        """
        import json as _json

        role_name = f"{priv_name}_ROLE"
        status = {"role": role_name, "write_rc": -1, "make_rc": -1, "grants": {}}

        self._ensure_di_api_access(container, username)

        dep_rows = self.execute_sql(
            f"SELECT DEPENDENT_OBJECT_NAME AS V "
            f"FROM SYS.OBJECT_DEPENDENCIES "
            f"WHERE BASE_SCHEMA_NAME = '{container.upper()}' "
            f"  AND BASE_OBJECT_NAME = '{priv_name.upper()}' "
            f"  AND DEPENDENT_OBJECT_TYPE = 'VIEW' "
            f"  AND DEPENDENT_SCHEMA_NAME = '{container.upper()}'"
        )
        view_names = [r["V"] for r in (dep_rows or []) if "V" in r]
        _log.info("SP_ROLE | %s | SP=%s | dependent_views=%s", container, priv_name, view_names)

        role_def = {
            "role": {
                "name": role_name,
                "schema_analytic_privileges": [{"privileges": [priv_name]}],
            }
        }
        if view_names:
            role_def["role"]["schema_object_privileges"] = [
                {"privileges": ["SELECT"], "objects": view_names}
            ]

        role_content = _json.dumps(role_def, indent=2)
        role_file_path = f"src/{role_name}.hdbrole"
        _log.info("SP_ROLE | %s | role_content=%s", container, role_content)

        wr = self._write_file_to_workarea(container, role_file_path, role_content)
        write_rc = wr.get("return_code", 1)
        status["write_rc"] = write_rc
        _log.info("SP_ROLE | %s | WRITE %s -> rc=%s req=%s msg=%s",
                  container, role_file_path, write_rc, wr.get("request_id"), wr.get("message"))
        if write_rc != 0:
            _log.info("SP_ROLE | %s | WRITE failed -- skipping MAKE + GRANT", container)
            return status

        mr = self._run_make(container, [role_file_path])
        make_rc = mr.get("return_code", 1)
        status["make_rc"] = make_rc
        _log.info("SP_ROLE | %s | MAKE %s -> rc=%s", container, role_file_path, make_rc)
        if make_rc != 0:
            errs = [m["message"] for m in mr.get("messages", []) if m.get("type") == "ERROR"]
            _log.info("SP_ROLE | %s | MAKE errors: %s", container, errs)
            return status

        for grant_user in ["HDI_USER", "HE2E_USER"]:
            cur = self.conn.cursor()
            try:
                cur.execute("CREATE LOCAL TEMPORARY COLUMN TABLE #CSR_MSGS LIKE _SYS_DI.TT_MESSAGES")
                cur.execute(
                    f'CALL "{container}#DI".GRANT_CONTAINER_SCHEMA_ROLE(?, ?, ?, ?, #CSR_MSGS)',
                    (role_name, grant_user)
                )
                row = cur.fetchone()
                rc     = int(row[1]) if row else 1
                req_id = int(row[0]) if row else 0
                status["grants"][grant_user] = rc
                if rc == 0:
                    _log.info("SP_ROLE | %s | GRANT %s -> %s req=%s", container, role_name, grant_user, req_id)
                else:
                    _log.info("SP_ROLE | %s | GRANT %s -> %s rc=%d", container, role_name, grant_user, rc)
            except Exception as e:
                status["grants"][grant_user] = str(e)
                _log.info("SP_ROLE | %s | GRANT %s -> %s exception: %s", container, role_name, grant_user, e)
            finally:
                try:
                    cur.execute("DROP TABLE #CSR_MSGS")
                except Exception:
                    pass
                cur.close()
        try:
            cur = self.conn.cursor()
            cur.execute("CREATE LOCAL TEMPORARY COLUMN TABLE #CLEANUP_FILES (PATH NVARCHAR(511))")
            cur.execute("INSERT INTO #CLEANUP_FILES VALUES (?)", (role_file_path,))
            cur.execute(f'CALL "{container}#DI".DELETE(#CLEANUP_FILES, _SYS_DI.T_NO_PARAMETERS, ?, ?, ?)')
            while cur.nextset():
                pass
            try:
                cur.execute("DROP TABLE #CLEANUP_FILES")
            except Exception:
                pass
            cur.close()
        except Exception:
            try:
                cur.close()
            except Exception:
                pass

        return status

    def _grant_structured_privilege(self, container: str, priv_name: str, username: str = None) -> None:
        """GRANT STRUCTURED PRIVILEGE to primary user, HDI_USER, HE2E_USER."""
        primary_user = (username or os.environ.get("HDI_USERNAME", "") or self.user).upper()
        extra_dbx = [u.strip().upper() for u in os.environ.get("HDI_DBX_USERS", "").split(",") if u.strip()]
        all_users = list(dict.fromkeys([primary_user, "HDI_USER", "HE2E_USER"] + extra_dbx))
        connection_user = self.user.upper()
        target_users = [u for u in all_users if u != connection_user]
        full_priv_name = f"{container.upper()}::{priv_name}"

        for target in target_users:
            try:
                cur = self.conn.cursor()
                cur.execute(f'GRANT STRUCTURED PRIVILEGE "{full_priv_name}" TO {target}')
                cur.close()
                _log.debug("SP_GRANT | %s | %s -> %s OK", container, full_priv_name, target)
            except Exception as e:
                _log.debug("SP_GRANT | %s | %s -> %s FAIL %s", container, full_priv_name, target, e)
                try:
                    cur.close()
                except Exception:
                    pass

    def _ensure_di_api_access(self, container: str, username: str = None) -> None:
        """
        Self-healing: ensure HDI_USER has DI API file-level privileges on the container.
        Cached per session to avoid repeating slow grant calls.
        """
        group_name = container.upper() + "_GROUP"

        cache_key = container.upper()
        if cache_key in self._di_access_granted:
            _log.debug("ENSURE_DI | %s | already granted this session -- skipping", cache_key)
            return

        group_granted = False
        try:
            r1 = self.grant_container_group_api(group_name, username)
            group_granted = r1.get("return_code", 1) == 0
        except Exception:
            pass

        container_granted = False
        try:
            r2 = self.grant_container_api_privileges(group_name, container, username)
            container_granted = r2.get("return_code", 1) == 0
        except Exception:
            pass

        if container_granted:
            self._di_access_granted.add(cache_key)
            _log.debug("ENSURE_DI | %s | grants succeeded -- cached", cache_key)
        else:
            _log.debug(
                "ENSURE_DI | %s | grants attempted but container grant failed (will retry) | group=%s container=%s",
                cache_key, group_granted, container_granted,
            )

    def _log_make_undeploy(self, container: str, file_path: str) -> dict:
        """Run a targeted undeploy MAKE and log it. Returns the raw make result."""
        _log.debug("MAKE_START | %s | deploy=[] | undeploy=[%s]", container, file_path)
        t0 = time.monotonic()
        cur2 = self.conn.cursor()
        try:
            cur2.execute("CREATE LOCAL TEMPORARY COLUMN TABLE #DROP_PARAMS LIKE _SYS_DI.TT_PARAMETERS")
            cur2.execute(
                "INSERT INTO #DROP_PARAMS (KEY, VALUE) VALUES ('com.sap.hana.di.view/optimized_replace', 'true')"
            )
            cur2.execute("CREATE LOCAL TEMPORARY COLUMN TABLE #UNDEPLOY_LIST LIKE _SYS_DI.TT_FILESFOLDERS")
            cur2.execute("INSERT INTO #UNDEPLOY_LIST (PATH) VALUES (?)", (file_path,))
            cur2.execute("CREATE LOCAL TEMPORARY COLUMN TABLE #UNDEPLOY_PP LIKE _SYS_DI.TT_FILESFOLDERS_PARAMETERS")
            cur2.execute(
                f'CALL "{container}#DI".MAKE('
                f'_SYS_DI.T_NO_FILESFOLDERS, #UNDEPLOY_LIST, '
                f'#UNDEPLOY_PP, #DROP_PARAMS, ?, ?, ?)'
            )
            row2 = cur2.fetchone()
            req_id = int(row2[0]) if row2 else 0
            rc2 = int(row2[1]) if row2 else 1
            messages2 = []
            while cur2.nextset():
                for mrow in cur2:
                    messages2.append({"type": mrow[0], "code": mrow[1], "message": mrow[2]})
            elapsed = time.monotonic() - t0
            for m in messages2:
                msg_type = (m.get("type") or "INFO").upper()
                _log.debug("HANA_MSG | %s | %s | %s", container, msg_type, m.get("message", ""))
            success2 = rc2 <= 1
            status = "OK" if success2 else "FAIL"
            _log.debug("MAKE_END | %s | rc=%d %s | elapsed=%.2fs", container, rc2, status, elapsed)
            return {"return_code": 0 if success2 else rc2, "request_id": req_id, "messages": messages2}
        except Exception as e:
            _log.debug("MAKE_END | %s | EXCEPTION: %s", container, e)
            return {"return_code": 1, "request_id": 0, "messages": []}
        finally:
            for tbl in ["#DROP_PARAMS", "#UNDEPLOY_LIST", "#UNDEPLOY_PP"]:
                try:
                    cur2.execute(f"DROP TABLE {tbl}")
                except Exception:
                    pass
            cur2.close()

    def deploy(self, container: str, username: str = None) -> dict:
        """
        Compile & activate staged artifacts via DI.MAKE.
        """
        _log.debug("=" * 70)
        _log.debug("DEPLOY_START | container=%s | user=%s", container, username or os.environ.get("HDI_USERNAME", "?"))

        self._ensure_di_api_access(container, username)

        try:
            self.grant_container_schema_privileges(container, username)
        except Exception:
            pass

        container_is_empty = self._runtime_schema_is_empty(container)
        obj_count_sql = (
            f"SELECT COUNT(*) AS CNT FROM ("
            f"SELECT TABLE_NAME FROM SYS.TABLES WHERE SCHEMA_NAME='{container.upper()}' "
            f"UNION ALL SELECT VIEW_NAME FROM SYS.VIEWS WHERE SCHEMA_NAME='{container.upper()}' "
            f"UNION ALL SELECT PROCEDURE_NAME FROM SYS.PROCEDURES WHERE SCHEMA_NAME='{container.upper()}')"
        )
        try:
            cnt_rows = self.execute_sql(obj_count_sql)
            obj_count = int(cnt_rows[0].get("CNT", 0)) if cnt_rows else 0
        except Exception:
            obj_count = -1
        _log.debug("EMPTY_CHECK | %s | is_empty=%s | deployed_objects=%s", container, container_is_empty, obj_count)

        pending = list(self._pending_paths)
        self._pending_paths.clear()

        if not pending:
            return {
                "return_code": 0,
                "message": "No files were staged -- deploy skipped (nothing to activate).",
                "request_id": 0,
                "details": [],
            }

        if container_is_empty:
            _log.debug("DEPLOY_MODE | %s | FRESH (empty container -- writing .hdiconfig + all pending)", container)
            self._write_file_to_workarea(container, ".hdiconfig", self._HDICONFIG)
            result = self._run_make(container, [".hdiconfig"] + pending)
        else:
            _CV_EXT   = ".hdbcalculationview"
            _LIB_EXT  = ".hdblibrary"
            cv_in_pending  = [p for p in pending if p.endswith(_CV_EXT)]
            lib_in_pending = [p for p in pending if p.endswith(_LIB_EXT)]
            other_pending  = [p for p in pending if not p.endswith(_CV_EXT) and not p.endswith(_LIB_EXT)]

            if cv_in_pending or lib_in_pending:
                root_wr = self._write_file_to_workarea(container, ".hdiconfig", self._HDICONFIG)
                src_wr  = self._write_file_to_workarea(container, "src/.hdiconfig", self._HDICONFIG)

                cfg_paths = []
                if root_wr.get("return_code", 1) == 0:
                    cfg_paths.append(".hdiconfig")
                if src_wr.get("return_code", 1) == 0:
                    cfg_paths.append("src/.hdiconfig")

                if not cfg_paths:
                    _log.info(
                        "DEPLOY_MODE | %s | HDICONFIG_WRITE_FAILED — both .hdiconfig WRITEs failed "
                        "(root_rc=%s src_rc=%s); CV/lib MAKE would silently no-op — aborting deploy",
                        container,
                        root_wr.get("return_code"), src_wr.get("return_code"),
                    )
                    return {
                        "return_code": 1,
                        "message": (
                            "Cannot deploy CV/library: failed to write .hdiconfig and src/.hdiconfig "
                            f"to work area (root: {root_wr.get('message','?')}, "
                            f"src: {src_wr.get('message','?')}). "
                            "Without .hdiconfig in the MAKE the calculationview/library plugin is not "
                            "activated and the artifact silently no-ops."
                        ),
                        "request_id": 0,
                        "details": [],
                    }

                if cv_in_pending:
                    deploy_list = cfg_paths + pending
                    _log.info(
                        "DEPLOY_MODE | %s | TARGETED+HDICONFIG(CV) | cfg=%s -- MAKE with %s",
                        container, cfg_paths, cv_in_pending,
                    )
                    result = self._run_make(container, deploy_list)

                if lib_in_pending:
                    lib_deploy_list = cfg_paths + lib_in_pending + other_pending
                    _log.info(
                        "DEPLOY_MODE | %s | TARGETED+HDICONFIG(LIB) | cfg=%s -- MAKE with %s",
                        container, cfg_paths, lib_in_pending,
                    )
                    result = self._run_make(container, lib_deploy_list)

                if not cv_in_pending and not lib_in_pending:
                    result = self._run_make(container, pending)
            else:
                _log.debug("DEPLOY_MODE | %s | TARGETED (existing container -- only new files)", container)
                result = self._run_make(container, pending)

        rc = result["return_code"]
        req_id = result["request_id"]
        messages = result["messages"]

        errors = [m for m in messages if m.get("type") == "ERROR"]
        info = [m for m in messages if m.get("type") != "ERROR"]

        if rc == 0:
            _log.debug("DEPLOY_END | %s | SUCCESS | request_id=%s", container, req_id)
            try:
                self.grant_container_schema_privileges(container, username)
            except Exception:
                pass
            try:
                self._update_artifact_tree(container)
            except Exception:
                pass

            cv_files_deployed = [p for p in pending if p.endswith(".hdbcalculationview")]
            if cv_files_deployed:
                from pathlib import Path as _CVP
                cv_errors = []
                for _cp in cv_files_deployed:
                    _cn = _CVP(_cp).stem.upper()
                    if req_id:
                        _mm = self.execute_sql(
                            f"SELECT SEVERITY, MESSAGE_CODE, MESSAGE, PATH "
                            f"FROM \"{container.upper()}#DI\".\"M_MESSAGES\" "
                            f"WHERE REQUEST_ID = {req_id} "
                            f"ORDER BY ROW_ID"
                        )
                        _log.info(
                            "CV_VERIFY | %s | %s | M_MESSAGES (req=%s): %s",
                            container, _cn, req_id, _mm,
                        )
                        mm_errs = [r for r in (_mm or []) if r.get("SEVERITY") == "ERROR"]
                        if mm_errs:
                            cv_errors.append(
                                f"{_cn}: M_MESSAGES errors: "
                                + "; ".join(r.get("MESSAGE", "") for r in mm_errs[:3])
                            )
                    _cv_chk = self.execute_sql(
                        f"SELECT VIEW_NAME, VIEW_TYPE FROM SYS.VIEWS "
                        f"WHERE SCHEMA_NAME = '{container.upper()}' AND VIEW_NAME = '{_cn}'"
                    )
                    _log.info("CV_VERIFY | %s | %s | SYS.VIEWS: %s", container, _cn, _cv_chk)
                    if not _cv_chk or (len(_cv_chk) == 1 and "error" in _cv_chk[0]):
                        cv_errors.append(
                            f"{_cn}: not found in SYS.VIEWS after deploy — "
                            "silent no-op (ensure .hdiconfig + src/.hdiconfig are in the MAKE call)"
                        )
                if cv_errors:
                    _log.info(
                        "CV_VERIFY | %s | FAIL — rc was 0 but CV(s) missing: %s",
                        container, cv_errors,
                    )
                    return {
                        "return_code": 1,
                        "message": "CV deploy returned rc=0 but object(s) not created: " + " | ".join(cv_errors),
                        "request_id": req_id,
                        "details": messages,
                    }

            sp_files = [p for p in pending if p.endswith(".hdbstructuredprivilege")]
            for sp_path in sp_files:
                from pathlib import Path as _Path
                priv_name = _Path(sp_path).stem
                try:
                    self._grant_structured_privilege(container, priv_name, username)
                except Exception:
                    pass
                try:
                    self._deploy_and_grant_sp_role(container, priv_name, username)
                except Exception:
                    pass

            lib_files_deployed = [p for p in pending if p.endswith(".hdblibrary")]
            if lib_files_deployed:
                from pathlib import Path as _LV
                lib_errors = []
                for _lp in lib_files_deployed:
                    _ln = _LV(_lp).stem.upper()
                    if req_id:
                        _mm = self.execute_sql(
                            f"SELECT SEVERITY, MESSAGE_CODE, MESSAGE, PATH "
                            f"FROM \"{container.upper()}#DI\".\"M_MESSAGES\" "
                            f"WHERE REQUEST_ID = {req_id} "
                            f"ORDER BY ROW_ID"
                        )
                        _log.info(
                            "LIB_VERIFY | %s | %s | M_MESSAGES (req=%s): %s",
                            container, _ln, req_id, _mm,
                        )
                        mm_errs = [r for r in (_mm or []) if r.get("SEVERITY") == "ERROR"]
                        if mm_errs:
                            lib_errors.append(
                                f"{_ln}: M_MESSAGES errors: "
                                + "; ".join(r.get("MESSAGE", "") for r in mm_errs[:3])
                            )
                    _lv = self.execute_sql(
                        f"SELECT LIBRARY_NAME, SCHEMA_NAME FROM SYS.LIBRARIES "
                        f"WHERE SCHEMA_NAME = '{container.upper()}' AND LIBRARY_NAME = '{_ln}'"
                    )
                    _log.info("LIB_VERIFY | %s | %s | SYS.LIBRARIES: %s", container, _ln, _lv)
                    if not _lv or (len(_lv) == 1 and "error" in _lv[0]):
                        lib_errors.append(
                            f"{_ln}: not found in SYS.LIBRARIES after deploy — "
                            "silent no-op (ensure .hdiconfig + src/.hdiconfig are in the MAKE call)"
                        )
                if lib_errors:
                    _log.info(
                        "LIB_VERIFY | %s | FAIL — rc was 0 but library(ies) missing: %s",
                        container, lib_errors,
                    )
                    return {
                        "return_code": 1,
                        "message": "Library deploy returned rc=0 but object(s) not created: " + " | ".join(lib_errors),
                        "request_id": req_id,
                        "details": messages,
                    }

            # ── VT object-level grants ────────────────────────────────────────
            # SDA-backed virtual tables require an explicit object-level
            # GRANT SELECT on the VT itself so that views referencing the VT
            # are visible and queryable in DBX.  Schema-level grants (from
            # grant_container_schema_privileges above) are NOT sufficient for
            # VT→SDA chains — HANA checks privileges on the VT object directly
            # when resolving the remote source access for end users.
            vt_files_deployed = [p for p in pending if p.endswith(".hdbvirtualtable")]
            if vt_files_deployed:
                from pathlib import Path as _VTP2
                _vt_conn_user = self.user.upper()
                _vt_uname = (username or os.environ.get("HDI_USERNAME", "") or "").strip().upper()
                _vt_extra = [u.strip().upper() for u in os.environ.get("HDI_DBX_USERS", "").split(",") if u.strip()]
                _vt_targets = list(dict.fromkeys(
                    u for u in [_vt_conn_user, _vt_uname, "HDI_USER", "HE2E_USER"] + _vt_extra if u
                ))
                for _vp in vt_files_deployed:
                    _vt_name = _VTP2(_vp).stem.upper()
                    for _tgt in _vt_targets:
                        try:
                            _vc = self.conn.cursor()
                            _vc.execute(
                                f'GRANT SELECT ON "{container.upper()}"."{_vt_name}" TO {_tgt}'
                            )
                            _vc.close()
                            _log.info("VT_GRANT | %s | %s → %s OK", container, _vt_name, _tgt)
                        except Exception as _vte:
                            _log.info("VT_GRANT | %s | %s → %s WARN: %s", container, _vt_name, _tgt, _vte)
                            try:
                                _vc.close()
                            except Exception:
                                pass

            return {
                "return_code": 0,
                "message": f"Deploy succeeded (request_id={req_id})",
                "request_id": req_id,
                "details": info,
            }

        vt_files = [p for p in pending if p.endswith(".hdbvirtualtable")]
        if vt_files:
            from pathlib import Path as _VTPath
            vt_names = [_VTPath(p).stem.upper() for p in vt_files]
            try:
                name_list = ", ".join(f"'{n}'" for n in vt_names)
                vt_rows = self.execute_sql(
                    f"SELECT TABLE_NAME FROM SYS.VIRTUAL_TABLES "
                    f"WHERE SCHEMA_NAME = '{container.upper()}' "
                    f"AND TABLE_NAME IN ({name_list})"
                )
                found = {r["TABLE_NAME"] for r in (vt_rows or []) if "TABLE_NAME" in r}
                if found == set(vt_names):
                    _log.debug(
                        "DEPLOY_END | %s | VT_VERIFIED | rc=%d was non-zero but all VTs exist in runtime: %s",
                        container, rc, list(found)
                    )
                    try:
                        self.grant_container_schema_privileges(container, username)
                    except Exception:
                        pass
                    try:
                        self._update_artifact_tree(container)
                    except Exception:
                        pass
                    # VT object-level grants (same as rc==0 path above)
                    from pathlib import Path as _VTP3
                    _vt_conn_user2 = self.user.upper()
                    _vt_uname2 = (username or os.environ.get("HDI_USERNAME", "") or "").strip().upper()
                    _vt_extra2 = [u.strip().upper() for u in os.environ.get("HDI_DBX_USERS", "").split(",") if u.strip()]
                    _vt_targets2 = list(dict.fromkeys(
                        u for u in [_vt_conn_user2, _vt_uname2, "HDI_USER", "HE2E_USER"] + _vt_extra2 if u
                    ))
                    for _vp2 in vt_files:
                        _vt_name2 = _VTP3(_vp2).stem.upper()
                        for _tgt2 in _vt_targets2:
                            try:
                                _vc2 = self.conn.cursor()
                                _vc2.execute(
                                    f'GRANT SELECT ON "{container.upper()}"."{_vt_name2}" TO {_tgt2}'
                                )
                                _vc2.close()
                                _log.info("VT_GRANT | %s | %s → %s OK", container, _vt_name2, _tgt2)
                            except Exception as _vte2:
                                _log.info("VT_GRANT | %s | %s → %s WARN: %s", container, _vt_name2, _tgt2, _vte2)
                                try:
                                    _vc2.close()
                                except Exception:
                                    pass
                    return {
                        "return_code": 0,
                        "message": f"Deploy succeeded — virtual table(s) verified in runtime: {', '.join(found)}",
                        "request_id": req_id,
                        "details": [],
                    }
            except Exception as _vte:
                _log.debug("DEPLOY_END | %s | VT verification failed: %s", container, _vte)

        if not errors:
            try:
                m_rows = self.execute_sql(
                    f"SELECT SEVERITY AS type, MESSAGE AS message, PATH AS path "
                    f"FROM \"{container}#DI\".\"M_MESSAGES\" "
                    f"WHERE REQUEST_ID = {req_id} AND SEVERITY = 'ERROR'"
                ) if req_id else []
                if not m_rows or (len(m_rows) == 1 and "error" in m_rows[0]):
                    m_rows = self.execute_sql(
                        f"SELECT SEVERITY AS type, MESSAGE AS message, PATH AS path "
                        f"FROM \"{container}#DI\".\"M_MESSAGES\" "
                        f"WHERE REQUEST_ID = (SELECT MAX(REQUEST_ID) FROM \"{container}#DI\".\"M_MESSAGES\") "
                        f"AND SEVERITY = 'ERROR'"
                    )
                if m_rows and not (len(m_rows) == 1 and "error" in m_rows[0]):
                    errors = m_rows
                    messages = m_rows
                    _log.debug("DEPLOY_END | %s | M_MESSAGES fallback: %d errors", container, len(errors))
            except Exception as _me:
                _log.debug("DEPLOY_END | %s | M_MESSAGES fallback failed: %s", container, _me)

        err_msgs = "; ".join(m.get("message", str(m)) for m in errors[:3]) or "MAKE failed"
        _log.debug("DEPLOY_END | %s | FAILED rc=%d | %s", container, rc, err_msgs)
        return {"return_code": rc, "message": err_msgs, "request_id": req_id, "details": messages}

    def drop_artifact(self, container: str, file_path: str) -> dict:
        """Delete one artifact via DI.DELETE then run a targeted MAKE to undeploy it."""
        _log.debug("DROP_ARTIFACT | %s | %s", container, file_path)
        cur = self.conn.cursor()
        try:
            cur.execute("CREATE LOCAL TEMPORARY COLUMN TABLE #DEL_FILES (PATH NVARCHAR(511))")
            cur.execute("INSERT INTO #DEL_FILES VALUES (?)", (file_path,))
            cur.execute(f'CALL "{container}#DI".DELETE(#DEL_FILES, _SYS_DI.T_NO_PARAMETERS, ?, ?, ?)')
            row = cur.fetchone()
            rc = int(row[1]) if row else 1
            messages = []
            while cur.nextset():
                for mrow in cur:
                    messages.append({"type": mrow[0], "code": mrow[1], "message": mrow[2]})
            if rc != 0:
                errors = [m["message"] for m in messages if m.get("type") == "ERROR"]
                _log.debug("DELETE | %s | %s | rc=%d %s", container, file_path, rc, "; ".join(errors[:2]))
                return {"return_code": rc, "message": "; ".join(errors[:3]) or "DELETE failed"}
            _log.debug("DELETE | %s | %s | rc=0", container, file_path)
        except Exception as e:
            _log.debug("DELETE | %s | %s | exception: %s", container, file_path, e)
            return {"return_code": 1, "message": f"Error deleting artifact: {e}"}
        finally:
            try:
                cur.execute("DROP TABLE #DEL_FILES")
            except Exception:
                pass
            cur.close()

        make_result = self._log_make_undeploy(container, file_path)
        rc2 = make_result["return_code"]
        req_id = make_result["request_id"]
        messages2 = make_result["messages"]
        if rc2 == 0:
            return {"return_code": 0, "message": f"Artifact '{file_path}' dropped successfully (request_id={req_id})"}
        errors2 = [m["message"] for m in messages2 if m.get("type") == "ERROR"]
        return {"return_code": rc2, "message": "; ".join(errors2[:3]) or "MAKE (undeploy) failed"}

    def list_artifacts(self, container: str) -> list:
        """List all files in the HDI container's work area via DI.LIST."""
        c = container.upper()
        sql = (
            'DO BEGIN\n'
            '  DECLARE v_rc     INT;\n'
            '  DECLARE v_req_id BIGINT;\n'
            '  DECLARE lt_params TABLE (KEY NVARCHAR(256), VALUE NVARCHAR(256));\n'
            '  DECLARE lt_filter TABLE (PATH NVARCHAR(511));\n'
            '  DECLARE lt_msgs   TABLE ('
            'REQUEST_ID BIGINT, ROW_ID BIGINT, LEVEL INT, TYPE NVARCHAR(32), '
            'LIBRARY_ID NVARCHAR(256), PLUGIN_ID NVARCHAR(256), PATH NVARCHAR(511), '
            'SEVERITY NVARCHAR(16), MESSAGE_CODE BIGINT, MESSAGE NVARCHAR(5000), '
            'LOCATION NVARCHAR(64), LOCATION_PATH NVARCHAR(256), TIMESTAMP_UTC TIMESTAMP);\n'
            '  DECLARE lt_result TABLE ('
            'PATH NVARCHAR(511), CREATE_USER_NAME NVARCHAR(256), CREATE_APPUSER_NAME NVARCHAR(256), '
            'CREATE_TIMESTAMP_UTC TIMESTAMP, MODIFICATION_USER_NAME NVARCHAR(256), '
            'MODIFICATION_APPUSER_NAME NVARCHAR(256), MODIFICATION_TIMESTAMP_UTC TIMESTAMP, '
            'SIZE BIGINT, SHA256 NVARCHAR(64));\n'
            f'  CALL "{c}#DI".LIST(\n'
            '    :lt_filter,\n'
            '    :lt_params,\n'
            '    v_rc, v_req_id, :lt_msgs, :lt_result\n'
            '  );\n'
            "  SELECT PATH FROM :lt_result WHERE PATH NOT LIKE '%/';\n"
            'END;'
        )
        cur = self.conn.cursor()
        try:
            cur.execute(sql)
            if cur.description:
                return [{"PATH": row[0]} for row in cur.fetchall()]
            return []
        except Exception as e:
            return [{"error": str(e)}]
        finally:
            cur.close()

    def drop_all_artifacts(self, container: str) -> dict:
        """Remove ALL artifacts from an HDI container."""
        c = container.upper()
        di = f'"{c}#DI"'

        files = self.list_artifacts(c)
        if files and "error" in files[0]:
            return {"return_code": 1, "message": f"Failed to list artifacts: {files[0]['error']}", "dropped": []}
        if not files:
            _log.debug("DROP_ALL | %s | no artifacts to drop", c)
            return {"return_code": 0, "message": "No artifacts to drop.", "dropped": []}

        paths = [f["PATH"] for f in files if "PATH" in f]
        _log.debug("DROP_ALL | %s | dropping %d artifact(s): %s", c, len(paths), paths)

        cur = self.conn.cursor()
        try:
            cur.execute("CREATE LOCAL TEMPORARY COLUMN TABLE #DA_DEPLOY LIKE _SYS_DI.TT_FILESFOLDERS")
            cur.execute("CREATE LOCAL TEMPORARY COLUMN TABLE #DA_UNDEPLOY LIKE _SYS_DI.TT_FILESFOLDERS")
            cur.execute("CREATE LOCAL TEMPORARY COLUMN TABLE #DA_PP LIKE _SYS_DI.TT_FILESFOLDERS_PARAMETERS")
            cur.execute("CREATE LOCAL TEMPORARY COLUMN TABLE #DA_PARAMS LIKE _SYS_DI.TT_PARAMETERS")
            for p in paths:
                cur.execute("INSERT INTO #DA_UNDEPLOY (PATH) VALUES (?)", (p,))
            cur.execute(f"CALL {di}.MAKE(#DA_DEPLOY, #DA_UNDEPLOY, #DA_PP, #DA_PARAMS, ?, ?, ?)")
            row = cur.fetchone()
            rc_make = int(row[0]) if row else 0
            while cur.nextset():
                pass

            cur.execute("CREATE LOCAL TEMPORARY COLUMN TABLE #DA_DEL LIKE _SYS_DI.TT_FILESFOLDERS")
            for p in paths:
                cur.execute("INSERT INTO #DA_DEL (PATH) VALUES (?)", (p,))
            cur.execute(f"CALL {di}.DELETE(#DA_DEL, _SYS_DI.T_NO_PARAMETERS, ?, ?, ?)")
            row2 = cur.fetchone()
            rc_del = int(row2[0]) if row2 else 0
            while cur.nextset():
                pass

            for t in ["#DA_DEPLOY", "#DA_UNDEPLOY", "#DA_PP", "#DA_PARAMS", "#DA_DEL"]:
                try:
                    cur.execute(f"DROP TABLE {t}")
                except Exception:
                    pass

            rc = max(rc_make, rc_del)
            return {
                "return_code": rc,
                "message": f"Dropped {len(paths)} artifact(s) from {c}. MAKE rc={rc_make}, DELETE rc={rc_del}.",
                "dropped": paths,
            }
        except Exception as e:
            return {"return_code": 1, "message": f"drop_all_artifacts error: {e}", "dropped": []}
        finally:
            cur.close()

    def configure_libraries(self, container_name: str) -> dict:
        """
        Configure the default HDI libraries for a container using the GROUP-level procedure.

        Uses "_SYS_DI#<GROUP>".CONFIGURE_LIBRARIES in a DO BEGIN block.
        Group name is derived from container name (convention: <CONTAINER>_GROUP).
        Idempotent: safe to call multiple times.
        """
        c = container_name.strip().upper()
        group_name = c + "_GROUP"   # HDIAGENT_CONTAINER -> HDIAGENT_CONTAINER_GROUP

        sql = f"""DO BEGIN
  DECLARE lv_rc     INT;
  DECLARE lv_req_id BIGINT;
  DECLARE lt_msgs   _SYS_DI.TT_MESSAGES;
  DECLARE lt_params _SYS_DI.TT_PARAMETERS;
  DECLARE lt_libs   _SYS_DI.TT_LIBRARY_CONFIGURATION;
  lt_libs = SELECT 'ADD' AS ACTION, LIBRARY_NAME FROM _SYS_DI.T_DEFAULT_LIBRARIES;
  CALL "_SYS_DI#{group_name}"."CONFIGURE_LIBRARIES"(
      '{c}', :lt_libs, :lt_params, lv_rc, lv_req_id, lt_msgs);
  SELECT lv_rc AS RC, lv_req_id AS REQ_ID FROM DUMMY;
END;"""
        cur = self.conn.cursor()
        try:
            cur.execute(sql)
            row = cur.fetchone()
            rc = int(row[0]) if row else 1
            req_id = int(row[1]) if row else 0
            ok = (rc == 0 or rc == 1)
            if ok:
                _log.info("CONFIGURE_LIBRARIES | %s | rc=%d OK (request_id=%s)", c, rc, req_id)
                return {"return_code": 0, "message": f"Libraries configured for {c} (request_id={req_id})", "request_id": req_id}
            _log.error("CONFIGURE_LIBRARIES | %s | rc=%d FAILED", c, rc)
            return {"return_code": rc, "message": f"Error in configure_libraries({c}): rc={rc}", "request_id": req_id}
        except Exception as e:
            _log.error("CONFIGURE_LIBRARIES | %s | exception: %s", c, e)
            return {"return_code": 1, "message": f"Error in configure_libraries({c}): {e}", "request_id": 0}
        finally:
            cur.close()

    def drop_container(self, group_name: str, container_name: str) -> dict:
        """Force-drop an HDI container (ignore_work=true, ignore_deployed=true)."""
        _log.debug("DROP_CONTAINER | group=%s | container=%s", group_name, container_name)
        cur = self.conn.cursor()
        try:
            cur.execute("CREATE LOCAL TEMPORARY COLUMN TABLE #DROP_PARAMS LIKE _SYS_DI.TT_PARAMETERS")
            cur.execute("INSERT INTO #DROP_PARAMS (KEY, VALUE) VALUES ('ignore_work', 'true')")
            cur.execute("INSERT INTO #DROP_PARAMS (KEY, VALUE) VALUES ('ignore_deployed', 'true')")
            cur.execute(
                f'CALL "_SYS_DI#{group_name}".DROP_CONTAINER(\'{container_name}\', #DROP_PARAMS, ?, ?, ?)'
            )
            row = cur.fetchone()
            rc = int(row[1]) if row else 1
            req_id = int(row[0]) if row else 0
            messages = []
            while cur.nextset():
                for mrow in cur:
                    messages.append({"type": mrow[0], "code": mrow[1], "message": mrow[2]})
            if rc == 0:
                return {"return_code": 0, "message": f"Container {container_name} dropped successfully", "request_id": req_id}
            errors = [m["message"] for m in messages if m.get("type") == "ERROR"]
            return {"return_code": rc, "message": "; ".join(errors[:3]) or f"rc={rc}", "request_id": req_id}
        except Exception as e:
            return {"return_code": 1, "message": str(e), "request_id": 0}
        finally:
            try:
                cur.execute("DROP TABLE #DROP_PARAMS")
            except Exception:
                pass
            cur.close()

    def read_artifact(self, container: str, file_path: str) -> dict:
        """Read a staged artifact's raw content from the HDI container work area via DI.READ."""
        c = container.upper()
        sql = (
            'DO BEGIN\n'
            '  DECLARE v_rc     INT;\n'
            '  DECLARE v_req_id BIGINT;\n'
            '  DECLARE lt_params  TABLE (KEY NVARCHAR(256), VALUE NVARCHAR(256));\n'
            '  DECLARE lt_filter  TABLE (PATH NVARCHAR(511));\n'
            '  DECLARE lt_msgs    TABLE ('
            'REQUEST_ID BIGINT, ROW_ID BIGINT, LEVEL INT, TYPE NVARCHAR(32), '
            'LIBRARY_ID NVARCHAR(256), PLUGIN_ID NVARCHAR(256), PATH NVARCHAR(511), '
            'SEVERITY NVARCHAR(16), MESSAGE_CODE BIGINT, MESSAGE NVARCHAR(5000), '
            'LOCATION NVARCHAR(64), LOCATION_PATH NVARCHAR(256), TIMESTAMP_UTC TIMESTAMP);\n'
            '  DECLARE lt_result  TABLE ('
            'PATH NVARCHAR(511), CONTENT_TYPE NVARCHAR(4000), CONTENT BLOB);\n'
            f"  INSERT INTO lt_filter VALUES ('{file_path}');\n"
            f'  CALL "{c}#DI".READ(\n'
            '    :lt_filter,\n'
            '    :lt_params,\n'
            '    v_rc, v_req_id, :lt_msgs, :lt_result\n'
            '  );\n'
            '  SELECT PATH, CONTENT FROM :lt_result;\n'
            'END;'
        )
        cur = self.conn.cursor()
        try:
            cur.execute(sql)
            if cur.description:
                rows = cur.fetchall()
                if rows:
                    path_val = rows[0][0]
                    content_blob = rows[0][1]
                    if isinstance(content_blob, (bytes, bytearray)):
                        content_str = content_blob.decode("utf-8")
                    else:
                        content_str = str(content_blob) if content_blob is not None else ""
                    return {"return_code": 0, "path": path_val, "content": content_str}
            return {"return_code": 1, "message": f"Artifact '{file_path}' not found in work area"}
        except Exception as e:
            return {"return_code": 1, "message": f"Error reading artifact: {e}"}
        finally:
            cur.close()

    def preview_artifact_data(self, container: str, object_name: str, row_limit: int = 100) -> list:
        """Preview data from a deployed table or view via SELECT TOP."""
        sql = f'SELECT TOP {row_limit} * FROM "{container}"."{object_name}"'
        return self.execute_sql(sql)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _grant_sysbi_cv_access(self, container: str, cv_names: list, username: str = None) -> None:
        """
        Grant everything a user needs to see and query Calculation Views in DBX / HANA Studio.
        """
        c = container.upper()
        primary_user = (username or os.environ.get("HDI_USERNAME", "") or self.user).upper()
        extra_dbx = [u.strip().upper() for u in os.environ.get("HDI_DBX_USERS", "").split(",") if u.strip()]
        target_users = list(dict.fromkeys([primary_user, "HDI_USER"] + extra_dbx))

        priv_user = os.environ.get("HANA_PRIV_USER", "")
        priv_password = os.environ.get("HANA_PRIV_PASSWORD", "")

        use_priv = False
        priv_conn = None
        if priv_user and priv_password:
            try:
                priv_conn = dbapi.connect(
                    address=os.environ["HANA_HOST"],
                    port=int(os.environ.get("HANA_PORT", 443)),
                    user=priv_user,
                    password=priv_password,
                    encrypt=True,
                    sslValidateCertificate=False,
                )
                use_priv = True
            except Exception as _e:
                _log.warning("SYS_BIC_GRANT | could not connect as %s: %s", priv_user, _e)

        conn_to_use = priv_conn if use_priv else self.conn
        granting_user = priv_user if use_priv else self.user

        try:
            for target in target_users:
                try:
                    _cur = conn_to_use.cursor()
                    _cur.execute(f'GRANT SELECT ON SCHEMA "_SYS_BIC" TO "{target}"')
                    _cur.close()
                    _log.info("SYS_BIC_GRANT | SCHEMA _SYS_BIC | %s -> %s | OK", granting_user, target)
                except Exception as _e:
                    _log.warning("SYS_BIC_GRANT | SCHEMA _SYS_BIC | %s -> %s | WARN: %s", granting_user, target, _e)

                for cv_name in cv_names:
                    obj_path = f"{c}/{cv_name}"
                    try:
                        _cur = conn_to_use.cursor()
                        _cur.execute(f'GRANT SELECT ON "_SYS_BIC"."{obj_path}" TO "{target}"')
                        _cur.close()
                        _log.info("SYS_BIC_GRANT | %s | %s -> %s | OK", obj_path, granting_user, target)
                    except Exception as _e:
                        _log.warning("SYS_BIC_GRANT | %s | %s -> %s | WARN: %s", obj_path, granting_user, target, _e)

                try:
                    _cur = conn_to_use.cursor()
                    _cur.execute(f'GRANT ANALYTIC PRIVILEGE "_SYS_BI_CP_ALL" TO "{target}"')
                    _cur.close()
                    _log.info("SYS_BIC_GRANT | _SYS_BI_CP_ALL | %s -> %s | OK", granting_user, target)
                except Exception as _e:
                    _log.warning("SYS_BIC_GRANT | _SYS_BI_CP_ALL | %s -> %s | WARN: %s", granting_user, target, _e)
        finally:
            if use_priv and priv_conn:
                try:
                    priv_conn.close()
                except Exception:
                    pass

    def _update_artifact_tree(self, container: str) -> None:
        """Write/refresh logs/artifact_tree.txt with all deployed objects."""
        from datetime import datetime as _dt
        c = container.upper()
        try:
            tables = self.execute_sql(f"SELECT TABLE_NAME AS N FROM SYS.TABLES WHERE SCHEMA_NAME='{c}' ORDER BY TABLE_NAME")
            views = self.execute_sql(f"SELECT VIEW_NAME AS N FROM SYS.VIEWS WHERE SCHEMA_NAME='{c}' ORDER BY VIEW_NAME")
            procs = self.execute_sql(f"SELECT PROCEDURE_NAME AS N FROM SYS.PROCEDURES WHERE SCHEMA_NAME='{c}' ORDER BY PROCEDURE_NAME")
            triggers = self.execute_sql(f"SELECT TRIGGER_NAME AS N FROM SYS.TRIGGERS WHERE SUBJECT_SCHEMA_NAME='{c}' ORDER BY TRIGGER_NAME")
            vtables = self.execute_sql(f"SELECT TABLE_NAME AS N FROM SYS.VIRTUAL_TABLES WHERE SCHEMA_NAME='{c}' ORDER BY TABLE_NAME")
            cvs = []
            _di_files = []
            try:
                _di_files = self.list_artifacts(c)
                if _di_files and not (len(_di_files) == 1 and "error" in _di_files[0]):
                    from pathlib import Path as _CVListPath
                    cvs = [
                        {"N": _CVListPath(f["PATH"]).stem}
                        for f in _di_files
                        if "PATH" in f and f["PATH"].endswith(".hdbcalculationview")
                    ]
            except Exception:
                cvs = []
            _cv_names_upper = {r["N"].upper() for r in cvs if "N" in r}
            funcs = self.execute_sql(f"SELECT FUNCTION_NAME AS N FROM SYS.FUNCTIONS WHERE SCHEMA_NAME='{c}' ORDER BY FUNCTION_NAME")
            seqs = self.execute_sql(f"SELECT SEQUENCE_NAME AS N FROM SYS.SEQUENCES WHERE SCHEMA_NAME='{c}' ORDER BY SEQUENCE_NAME")
            syns = self.execute_sql(f"SELECT SYNONYM_NAME AS N FROM SYS.SYNONYMS WHERE SCHEMA_NAME='{c}' ORDER BY SYNONYM_NAME")
            libs_raw = self.execute_sql(f"SELECT LIBRARY_NAME AS N FROM SYS.LIBRARIES WHERE SCHEMA_NAME='{c}' ORDER BY LIBRARY_NAME")
            if not libs_raw or (len(libs_raw) == 1 and "error" in libs_raw[0]):
                try:
                    if not isinstance(_di_files, list):
                        _di_files = self.list_artifacts(c)
                    if _di_files and not (len(_di_files) == 1 and "error" in _di_files[0]):
                        from pathlib import Path as _LibPath
                        libs_raw = [
                            {"N": _LibPath(f["PATH"]).stem}
                            for f in _di_files
                            if "PATH" in f and f["PATH"].endswith(".hdblibrary")
                        ]
                except Exception:
                    libs_raw = []

            # DI LIST fallback for views: if SYS.VIEWS returned empty or a privilege error
            # (e.g. SELECT not yet granted to HDI_USER on the new view), fall back to
            # counting .hdbview files from the DI work area — same pattern used for CVs/libs.
            if (not views or (len(views) == 1 and "error" in views[0])):
                try:
                    if not isinstance(_di_files, list):
                        _di_files = self.list_artifacts(c)
                    if _di_files and not (len(_di_files) == 1 and "error" in _di_files[0]):
                        from pathlib import Path as _VPath
                        views = [
                            {"N": _VPath(f["PATH"]).stem}
                            for f in _di_files
                            if "PATH" in f and f["PATH"].endswith(".hdbview")
                        ]
                except Exception:
                    pass

            EXT = {
                "TABLE": "hdbtable", "VIEW": "hdbview",
                "PROCEDURE": "hdbprocedure", "TRIGGER": "hdbtrigger",
                "VIRTUAL_TABLE": "hdbvirtualtable", "CALCULATION_VIEW": "hdbcalculationview",
                "FUNCTION": "hdbfunction", "SEQUENCE": "hdbsequence", "SYNONYM": "hdbsynonym",
                "LIBRARY": "hdblibrary",
            }
            items = []
            for r in (tables or []):
                if "N" in r:
                    items.append(("TABLE", r["N"]))
            for r in (vtables or []):
                if "N" in r and not any(name == r["N"] for _, name in items):
                    items.append(("VIRTUAL_TABLE", r["N"]))
            for r in (views or []):
                if "N" in r and r["N"].upper() not in _cv_names_upper:
                    items.append(("VIEW", r["N"]))
            for r in (cvs or []):
                if "N" in r:
                    items.append(("CALCULATION_VIEW", r["N"]))
            for r in (procs or []):
                if "N" in r:
                    items.append(("PROCEDURE", r["N"]))
            for r in (libs_raw or []):
                if "N" in r:
                    items.append(("LIBRARY", r["N"]))
            for r in (funcs or []):
                if "N" in r:
                    items.append(("FUNCTION", r["N"]))
            for r in (seqs or []):
                if "N" in r:
                    items.append(("SEQUENCE", r["N"]))
            for r in (syns or []):
                if "N" in r:
                    items.append(("SYNONYM", r["N"]))
            for r in (triggers or []):
                if "N" in r:
                    items.append(("TRIGGER", r["N"]))

            ts = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
            lines = [
                f"{c} -- deployed artifacts (as of {ts})",
                "└── src/",
            ]
            for i, (obj_type, name) in enumerate(items):
                prefix = "└──" if i == len(items) - 1 else "├──"
                ext = EXT.get(obj_type, obj_type.lower())
                lines.append(f"    {prefix} {name}.{ext}")

            tree_path = _LOG_ROOT / "artifact_tree.txt"
            tree_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            _log.info("ARTIFACT_TREE | %s | %d objects written to logs/artifact_tree.txt", c, len(items))
        except Exception as e:
            _log.warning("ARTIFACT_TREE | %s | failed to write artifact_tree.txt: %s", c, e)

    def _runtime_schema_is_empty(self, container: str) -> bool:
        """
        Return True only when the container's runtime schema has NO deployed objects.
        On error, returns False (assume NOT empty — safer).
        """
        c = container.upper()
        try:
            result = self.execute_sql(
                f"SELECT COUNT(*) AS CNT FROM ("
                f"  SELECT TABLE_NAME AS OBJ FROM SYS.TABLES WHERE SCHEMA_NAME = '{c}' "
                f"  UNION ALL "
                f"  SELECT VIEW_NAME  AS OBJ FROM SYS.VIEWS  WHERE SCHEMA_NAME = '{c}' "
                f"  UNION ALL "
                f"  SELECT PROCEDURE_NAME AS OBJ FROM SYS.PROCEDURES WHERE SCHEMA_NAME = '{c}' "
                f"  UNION ALL "
                f"  SELECT TABLE_NAME AS OBJ FROM SYS.VIRTUAL_TABLES WHERE SCHEMA_NAME = '{c}' "
                f"  UNION ALL "
                f"  SELECT FUNCTION_NAME AS OBJ FROM SYS.FUNCTIONS WHERE SCHEMA_NAME = '{c}' "
                f"  UNION ALL "
                f"  SELECT SEQUENCE_NAME AS OBJ FROM SYS.SEQUENCES WHERE SCHEMA_NAME = '{c}'"
                f")"
            )
            cnt = int(result[0].get("CNT", 1)) if result else 1
            return cnt == 0
        except Exception:
            return False

    def _call_di_proc(self, sql: str, context: str = "") -> dict:
        """Execute a DI procedure returning (return_code, request_id, messages)."""
        cur = self.conn.cursor()
        try:
            cur.execute(sql)
            row = cur.fetchone()
            rc = int(row[1]) if row else 1
            req_id = int(row[0]) if row else 0
            messages = []
            while cur.nextset():
                for mrow in cur:
                    messages.append({"type": mrow[0], "code": mrow[1], "message": mrow[2]})
            if rc <= 1:
                return {"return_code": 0, "message": f"OK (request_id={req_id})", "request_id": req_id}
            errors = [m["message"] for m in messages if m.get("type") == "ERROR"]
            return {"return_code": rc, "message": "; ".join(errors[:3]) or f"{context} failed (rc={rc})", "request_id": req_id}
        except Exception as e:
            return {"return_code": 1, "message": f"Error in {context}: {e}", "request_id": 0}
        finally:
            cur.close()

    def _parse_di_call_row(self, row) -> tuple:
        """Parse a result row from a direct hdbcli CALL statement.
        Returns (return_code, request_id).
        """
        if not row:
            return 1, 0
        return int(row[1]), int(row[0])

    def grant_remote_source_privilege(
        self,
        remote_source: str,
        container_name: str = "",
        grantee: str = "",
    ) -> dict:
        """
        Grant CREATE VIRTUAL TABLE privilege on a remote source.
        """
        priv_user = os.environ.get("HANA_PRIV_USER", "HE2E_USER")
        priv_password = os.environ.get("HANA_PRIV_PASSWORD", "")
        host = os.environ["HANA_HOST"]
        port = int(os.environ.get("HANA_PORT", 443))

        if not priv_password:
            return {
                "return_code": 1,
                "message": "HANA_PRIV_PASSWORD not set in .env — cannot auto-grant remote source privilege.",
            }

        if container_name:
            oo_user = f"{container_name.upper()}#OO"
            di_user = f"{container_name.upper()}#DI"
            grantees = [oo_user, di_user, "HDI_USER"]
        elif grantee:
            grantees = [grantee]
        else:
            grantees = ["HDI_USER"]

        try:
            priv_conn = dbapi.connect(
                address=host,
                port=port,
                user=priv_user,
                password=priv_password,
                encrypt=True,
                sslValidateCertificate=False,
            )
        except Exception as e:
            return {"return_code": 1, "message": f"Could not connect as {priv_user}: {e}"}

        results = []
        overall_rc = 0
        try:
            for g in grantees:
                try:
                    cur = priv_conn.cursor()
                    sql = (
                        f'GRANT CREATE VIRTUAL TABLE ON REMOTE SOURCE "{remote_source}" '
                        f'TO "{g}" WITH GRANT OPTION'
                    )
                    cur.execute(sql)
                    cur.close()
                    _log.info(
                        "REMOTE_SOURCE_GRANT | %s | %s -> %s | OK",
                        remote_source, priv_user, g,
                    )
                    results.append(f'"{g}": granted')
                except Exception as e:
                    _log.warning("REMOTE_SOURCE_GRANT | %s | %s -> %s | FAIL: %s", remote_source, priv_user, g, e)
                    results.append(f'"{g}": {e}')
                    if "#OO" in g:
                        overall_rc = 1

            msg = "; ".join(results)
            return {
                "return_code": overall_rc,
                "message": (
                    f'GRANT CREATE VIRTUAL TABLE on remote source "{remote_source}" '
                    f'(via {priv_user}): {msg}'
                ),
            }
        finally:
            try:
                priv_conn.close()
            except Exception:
                pass

    # ── Connection ────────────────────────────────────────────────────────────

    def disconnect(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass