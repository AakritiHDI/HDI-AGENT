"""
Session Manager — persists chat sessions as JSON files in logs/ui_sessions/
Each session file: logs/ui_sessions/<session_id>.json
Format:
{
  "session_id": "uuid",
  "title": "first user message (truncated)",
  "created_at": "ISO timestamp",
  "updated_at": "ISO timestamp",
  "username": "AAK",
  "messages": [
    {"role": "user"|"assistant", "content": "...", "timestamp": "..."}
  ]
}
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

_SESSION_DIR = Path(__file__).parent.parent / "logs" / "ui_sessions"


def _ensure_dir() -> None:
    _SESSION_DIR.mkdir(parents=True, exist_ok=True)


def _session_path(session_id: str) -> Path:
    return _SESSION_DIR / f"{session_id}.json"


def create_session(username: str) -> dict:
    _ensure_dir()
    session_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    session = {
        "session_id": session_id,
        "title": "New Chat",
        "created_at": now,
        "updated_at": now,
        "username": username.strip().upper(),
        "messages": [],
    }
    _session_path(session_id).write_text(json.dumps(session, indent=2), encoding="utf-8")
    return session


def get_session(session_id: str) -> dict | None:
    p = _session_path(session_id)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def list_sessions() -> list[dict]:
    """Return all sessions sorted by updated_at descending (newest first)."""
    _ensure_dir()
    sessions = []
    for p in _SESSION_DIR.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            # Return summary only (no messages) for the list view
            sessions.append({
                "session_id": data["session_id"],
                "title": data.get("title", "New Chat"),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
                "username": data.get("username", ""),
                "message_count": len(data.get("messages", [])),
            })
        except Exception:
            continue
    sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
    return sessions


def append_message(session_id: str, role: str, content: str) -> dict | None:
    session = get_session(session_id)
    if session is None:
        return None
    now = datetime.now().isoformat()
    session["messages"].append({
        "role": role,
        "content": content,
        "timestamp": now,
    })
    session["updated_at"] = now
    # Auto-title from the first user message
    if session["title"] == "New Chat" and role == "user":
        session["title"] = content[:60].strip()
    _session_path(session_id).write_text(json.dumps(session, indent=2), encoding="utf-8")
    return session


def delete_session(session_id: str) -> bool:
    p = _session_path(session_id)
    if p.exists():
        p.unlink()
        return True
    return False


def rename_session(session_id: str, new_title: str) -> dict | None:
    session = get_session(session_id)
    if session is None:
        return None
    session["title"] = new_title.strip()
    session["updated_at"] = datetime.now().isoformat()
    _session_path(session_id).write_text(json.dumps(session, indent=2), encoding="utf-8")
    return session