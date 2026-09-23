"""
FastAPI backend for HDI Agent UI.

Endpoints:
  GET  /api/config                — returns HDI_USERNAME from .env + setup status
  POST /api/setup                 — creates container group, container, grants (idempotent)
  GET  /api/setup/status          — current setup status
  GET  /api/sessions              — list all chat sessions
  POST /api/sessions              — create new session
  GET  /api/sessions/{id}         — get session with full message history
  DELETE /api/sessions/{id}       — delete a session
  PATCH /api/sessions/{id}/rename — rename session title
  POST /api/sessions/{id}/chat    — send message, get agent response
  GET  /api/health                — health check
"""
from __future__ import annotations

import os
import sys
import json
import threading
import logging
from contextlib import asynccontextmanager

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent.agent import HDIAgent
from agent.hana_client import HANAClient
from agent.tools import dispatch
from api.session_manager import (
    create_session,
    get_session,
    list_sessions,
    append_message,
    delete_session,
    rename_session,
)

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
_log = logging.getLogger("hdi.api")

# ── Setup state (shared across threads) ───────────────────────────────────────
_setup_state: dict = {
    "status": "idle",   # idle | running | done | error
    "steps": [],        # list of {"step": str, "result": str, "ok": bool}
    "username": "",
    "container": "",
    "error": None,
}
_setup_lock = threading.Lock()


def _run_hdi_setup(username: str) -> None:
    """
    Idempotent HDI setup: creates container group + container + grants.
    Safe to run multiple times — 'already exists' errors are ignored.
    Called in a background thread on startup if HDI_USERNAME is set.
    """
    global _setup_state
    uname = username.strip().upper()
    group = f"{uname}_CONTAINER_GROUP"
    container = f"{uname}_CONTAINER"

    with _setup_lock:
        _setup_state["status"] = "running"
        _setup_state["username"] = uname
        _setup_state["container"] = container
        _setup_state["steps"] = []
        _setup_state["error"] = None

    _log.info("HDI setup starting for user=%s container=%s", uname, container)

    # All setup steps are idempotent:
    # - create steps: failure = already exists → ok
    # - grant steps: failure = already granted → ok
    # Only a Python exception (connection failure, etc.) is a real error.
    CREATE_STEPS = {"create_container_group", "create_hdi_container"}

    steps = [
        ("create_container_group",         {"group_name": group}),
        # grant_container_group_api MUST come before create_hdi_container:
        # CREATE_CONTAINER requires the calling user to already hold group API
        # privileges on _SYS_DI#<GROUP>.  Without this grant first, the call
        # fails with (258, "insufficient privilege") for any user who is not
        # already a _SYS_DI global admin.
        ("grant_container_group_api",      {"group_name": group}),
        ("create_hdi_container",           {"group_name": group, "container_name": container}),
        ("grant_container_api_privileges", {"group_name": group, "container_name": container}),
        ("grant_schema_privileges",        {"container_name": container}),
        # configure_libraries MUST be called after the container exists and has DI API privileges.
        # It registers HANA's built-in type providers (db://DOUBLE, db://INTEGER, etc.) with the
        # container.  Without it, deploying any .hdblibrary file fails with:
        #   "the file requires db://DOUBLE which is not provided by any file"
        # Idempotent — safe to call on an already-configured container.
        ("configure_libraries",            {"container_name": container}),
    ]

    hana = None
    try:
        hana = HANAClient()
        completed = []
        for tool_name, args in steps:
            try:
                raw = dispatch(hana, tool_name, args, username=uname)
                result = json.loads(raw) if isinstance(raw, str) else raw
                rc = result.get("rc", result.get("return_code", 0))
                msg = str(result.get("message", result.get("error", raw)))

                # Distinguish real failures from "already exists / already granted":
                #   rc=0  → clean success
                #   rc!=0 AND message contains no HANA exception code → likely "already exists"
                #   rc!=0 AND message contains "(258, …)" / "(362, …)" / "(339, …)" → REAL failure
                HANA_ERROR_CODES = ("(258,", "(362,", "(339,", "(332,", "(286,")
                is_real_error = rc != 0 and any(code in msg for code in HANA_ERROR_CODES)

                if is_real_error:
                    ok = False
                    display_msg = f"⚠️ FAILED: {msg[:300]}"
                    _log.error("Setup step %s FAILED: rc=%s msg=%s", tool_name, rc, msg)
                elif rc != 0:
                    # Non-zero rc but no known HANA error code → treat as idempotent "already exists"
                    ok = True
                    if tool_name in CREATE_STEPS:
                        display_msg = "Already exists ✓"
                    else:
                        display_msg = "Already granted ✓"
                    _log.info("Setup step %s: already exists/granted (rc=%s)", tool_name, rc)
                else:
                    ok = True
                    display_msg = msg[:200] if msg and msg != str(raw) else "Done ✓"
                    _log.info("Setup step %s: rc=0 OK", tool_name)

                completed.append({"step": tool_name, "result": display_msg, "ok": ok})
            except Exception as e:
                completed.append({"step": tool_name, "result": str(e)[:200], "ok": False})
                _log.warning("Setup step %s exception: %s", tool_name, e)

        with _setup_lock:
            _setup_state["steps"] = completed
            _setup_state["status"] = "done"
        _log.info("HDI setup complete for %s", container)

    except Exception as exc:
        with _setup_lock:
            _setup_state["status"] = "error"
            _setup_state["error"] = str(exc)
        _log.error("HDI setup failed: %s", exc)
    finally:
        if hana:
            try:
                hana.disconnect()
            except Exception:
                pass


# ── FastAPI lifespan: auto-run setup on startup ────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    env_username = os.environ.get("HDI_USERNAME", "").strip().upper()
    if env_username:
        _log.info("HDI_USERNAME=%s detected — starting container setup in background", env_username)
        t = threading.Thread(target=_run_hdi_setup, args=(env_username,), daemon=True)
        t.start()
    else:
        _log.info("HDI_USERNAME not set in .env — skipping auto-setup")
    yield
    # Cleanup (nothing needed)


# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(title="HDI Agent API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory agent store: session_id → HDIAgent instance ─────────────────────
_agents: dict[str, HDIAgent] = {}


def _get_or_create_agent(session_id: str, username: str) -> HDIAgent:
    """
    Get existing agent for session, or create a new one.
    Injects bootstrap context: container already exists → always use Workflow B.
    (Setup is handled by the /api/setup endpoint, not by the agent.)
    """
    if session_id not in _agents:
        agent = HDIAgent(username=username)
        uname = username.strip().upper()
        container = f"{uname}_CONTAINER"
        group = f"{uname}_CONTAINER_GROUP"

        agent.history.append({
            "role": "user",
            "content": (
                f"My HDI container '{container}' in group '{group}' already exists "
                f"and all privileges are granted. Use Workflow B for all artifact "
                f"deployments — do NOT create a new container group or container.\n\n"
                f"IMPORTANT — container lock for this session:\n"
                f"- The ONLY container for this session is **{container}**.\n"
                f"- When calling create_artifact_file, deploy_artifact, grant_schema_privileges, "
                f"list_artifacts, drop_artifact, or any other tool, ALWAYS pass "
                f"container_name='{container}'.\n"
                f"- When writing raw SQL via execute_sql (e.g. SELECT, GRANT, CALL), ALWAYS use "
                f"'{container}' as the schema/container name — never substitute any other container "
                f"name you see mentioned in the conversation (such as test containers).\n"
                f"- If a user mentions a different container name in passing, DO NOT switch to it. "
                f"Clarify that the session container is '{container}'."
            ),
        })
        agent.history.append({
            "role": "assistant",
            "content": (
                f"Understood. The container for this entire session is locked to **{container}**. "
                f"I will use `{container}` in every tool call and in every SQL statement I write — "
                f"regardless of any other container names that may appear in the conversation. "
                f"I will not switch containers mid-session."
            ),
        })

        _agents[session_id] = agent
        _log.info("Created HDIAgent for session %s (user=%s)", session_id, username)
    return _agents[session_id]


# ── Request/Response models ────────────────────────────────────────────────────

class NewSessionRequest(BaseModel):
    username: str


class ChatRequest(BaseModel):
    message: str


class RenameRequest(BaseModel):
    title: str


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/api/config")
def get_config():
    """
    Returns the HDI configuration from .env:
    - username (from HDI_USERNAME)
    - container name
    - setup status
    Used by the React UI to skip the username modal when HDI_USERNAME is pre-configured.
    """
    env_username = os.environ.get("HDI_USERNAME", "").strip().upper()
    container = f"{env_username}_CONTAINER" if env_username else ""
    with _setup_lock:
        status = _setup_state["status"]
    return {
        "username": env_username,
        "container": container,
        "setup_status": status,
    }


@app.post("/api/setup")
def trigger_setup():
    """
    Manually trigger HDI container setup.
    Idempotent — safe to call even if container already exists.
    """
    env_username = os.environ.get("HDI_USERNAME", "").strip().upper()
    if not env_username:
        raise HTTPException(status_code=400, detail="HDI_USERNAME not set in .env")

    with _setup_lock:
        current = _setup_state["status"]

    if current == "running":
        return {"status": "already_running", "username": env_username}

    t = threading.Thread(target=_run_hdi_setup, args=(env_username,), daemon=True)
    t.start()
    return {"status": "started", "username": env_username}


@app.get("/api/setup/status")
def get_setup_status():
    """Returns the current setup status and step results."""
    with _setup_lock:
        return dict(_setup_state)


@app.get("/api/sessions")
def get_sessions():
    return list_sessions()


@app.post("/api/sessions", status_code=201)
def create_new_session(req: NewSessionRequest):
    session = create_session(req.username)
    _log.info("New session: %s for user %s", session["session_id"], req.username)
    return session


@app.get("/api/sessions/{session_id}")
def get_session_detail(session_id: str):
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.delete("/api/sessions/{session_id}")
def delete_session_endpoint(session_id: str):
    ok = delete_session(session_id)
    _agents.pop(session_id, None)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted", "session_id": session_id}


@app.patch("/api/sessions/{session_id}/rename")
def rename_session_endpoint(session_id: str, req: RenameRequest):
    session = rename_session(session_id, req.title)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "renamed", "title": session["title"]}


@app.post("/api/sessions/{session_id}/chat")
def chat(session_id: str, req: ChatRequest):
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    username = session.get("username", "")
    agent = _get_or_create_agent(session_id, username)

    append_message(session_id, "user", req.message)

    try:
        response = agent.chat(req.message)
    except Exception as exc:
        _log.error("Agent error in session %s: %s", session_id, exc)
        error_msg = f"⚠️ Agent error: {exc}"
        append_message(session_id, "assistant", error_msg)
        return {"response": error_msg}

    append_message(session_id, "assistant", response)
    return {"response": response}


@app.get("/api/health")
def health():
    with _setup_lock:
        setup_status = _setup_state["status"]
    return {"status": "ok", "active_sessions": len(_agents), "setup": setup_status}