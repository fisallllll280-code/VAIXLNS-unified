"""Small local-first FastAPI surface for VAIXLNS durable execution state."""
from __future__ import annotations

import hmac
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from infra.durable_store import DurableEventStore
from infra.vlns_server_client import ServerConfig, VLNSServerClient
from workspace.fabric import WorkspaceFabric
from workspace.vx_inspector import inspect as inspect_vx


DB_PATH = Path(os.getenv("VAIXLNS_DB_PATH", "var/vaixlns/events.db"))


class EventRequest(BaseModel):
    event_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    aggregate_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    capability: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class SnapshotRequest(BaseModel):
    snapshot_id: str = Field(min_length=1)
    state: dict[str, Any] = Field(default_factory=dict)
    lineage: list[str] = Field(default_factory=list)


class WorkspaceSessionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class WorkspaceMessageRequest(BaseModel):
    role: str = "user"
    content: str = Field(min_length=1, max_length=20000)
    agent_id: str | None = None


class WorkspaceIndexRequest(BaseModel):
    extra_roots: list[str] = Field(default_factory=list, max_length=10)


class WorkspaceAgentRunRequest(BaseModel):
    agent_id: str = Field(min_length=1, max_length=80)
    task: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None


def _authorized(authorization: str | None) -> bool:
    token = os.getenv("VAIXLNS_API_TOKEN")
    if token is None:
        return True
    if not authorization or not authorization.startswith("Bearer "):
        return False
    provided = authorization.removeprefix("Bearer ").strip()
    return hmac.compare_digest(provided, token)


def create_app(db_path: str | Path = DB_PATH, workspace_root: str | Path | None = None) -> FastAPI:
    app = FastAPI(title="VAIXLNS Runtime API", version="1.2.0")
    store = DurableEventStore(db_path)
    root = Path(workspace_root or os.getenv("VAIXLNS_REPO_ROOT", str(Path(__file__).resolve().parents[1]))).resolve()
    default_workspace_db = Path(db_path).with_name(Path(db_path).stem + ".workspace.db")
    workspace_db = Path(os.getenv("VAIXLNS_WORKSPACE_DB_PATH", str(default_workspace_db)))
    workspace = WorkspaceFabric(workspace_db, root)
    app.state.workspace_fabric = workspace

    def require_auth(authorization: str | None) -> None:
        if not _authorized(authorization):
            raise HTTPException(status_code=401, detail="AUTHORIZATION_REQUIRED")

    @app.on_event("shutdown")
    def _shutdown() -> None:
        store.close()

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "service": "VAIXLNS-runtime",
            "version": "1.2.0",
            "durable_store": store.verify_integrity(),
        }

    @app.get("/status")
    def status(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        if os.getenv("VAIXLNS_API_TOKEN") is not None:
            require_auth(authorization)
        events = store.events()
        latest = store.latest_snapshot()
        remote = ServerConfig.from_env("vlns-control")
        return {
            "service": "VAIXLNS-runtime",
            "event_count": len(events),
            "last_event_hash": store.last_hash,
            "snapshot_id": latest.snapshot_id if latest else None,
            "remote_vlns_configured": bool(remote.enabled and remote.base_url),
        }

    @app.get("/events")
    def events(
        aggregate_id: str | None = None,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        if os.getenv("VAIXLNS_API_TOKEN") is not None:
            require_auth(authorization)
        return {
            "events": [event.to_dict() for event in store.events(aggregate_id)],
            "integrity": store.verify_integrity(),
        }

    @app.post("/events", status_code=201)
    def append_event(
        event: EventRequest,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        result = store.append(**event.model_dump())
        return result.to_dict()

    @app.post("/snapshots", status_code=201)
    def save_snapshot(
        snapshot: SnapshotRequest,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        result = store.save_snapshot(
            snapshot_id=snapshot.snapshot_id,
            state=snapshot.state,
            lineage=snapshot.lineage,
        )
        return result.to_dict()

    @app.post("/federation/probe")
    def federation_probe(
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        config = ServerConfig.from_env("vlns-control")
        return VLNSServerClient(config).health()

    # Workspace dashboard and API. Reads remain local-first; all mutation routes
    # share the same configured API-token guard as the existing runtime.
    @app.get("/dashboard", response_class=HTMLResponse)
    def workspace_dashboard() -> HTMLResponse:
        dashboard_path = Path(__file__).resolve().parents[1] / "workspace" / "dashboard.html"
        try:
            return HTMLResponse(dashboard_path.read_text(encoding="utf-8"))
        except OSError:
            raise HTTPException(status_code=404, detail="WORKSPACE_DASHBOARD_NOT_INSTALLED") from None

    @app.get("/workspace/overview")
    def workspace_overview(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        if os.getenv("VAIXLNS_API_TOKEN") is not None:
            require_auth(authorization)
        return workspace.overview()

    @app.get("/workspace/sources")
    def workspace_sources(
        q: str | None = None,
        limit: int = 50,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        if os.getenv("VAIXLNS_API_TOKEN") is not None:
            require_auth(authorization)
        return {"sources": workspace.list_sources(query=q, limit=limit)}

    @app.get("/workspace/search")
    def workspace_search(
        q: str,
        limit: int = 10,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        if os.getenv("VAIXLNS_API_TOKEN") is not None:
            require_auth(authorization)
        return {"query": q, "results": workspace.search(q, limit=limit)}

    @app.post("/workspace/index/rebuild")
    def workspace_rebuild_index(
        request: WorkspaceIndexRequest,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        try:
            return workspace.rebuild_index(extra_roots=request.extra_roots)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None

    @app.get("/workspace/sessions")
    def workspace_sessions(
        limit: int = 50,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        if os.getenv("VAIXLNS_API_TOKEN") is not None:
            require_auth(authorization)
        return {"sessions": workspace.list_sessions(limit=limit)}

    @app.post("/workspace/sessions", status_code=201)
    def workspace_create_session(
        request: WorkspaceSessionRequest,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        try:
            session = workspace.create_session(request.title)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        return {"session": session}

    @app.get("/workspace/sessions/{session_id}")
    def workspace_session_detail(
        session_id: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        if os.getenv("VAIXLNS_API_TOKEN") is not None:
            require_auth(authorization)
        result = workspace.session_detail(session_id)
        if result is None:
            raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")
        return result

    @app.post("/workspace/sessions/{session_id}/messages", status_code=201)
    def workspace_add_message(
        session_id: str,
        request: WorkspaceMessageRequest,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        try:
            return workspace.add_message(session_id, request.role, request.content, request.agent_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND") from None
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None

    @app.get("/workspace/agents")
    def workspace_agents(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        if os.getenv("VAIXLNS_API_TOKEN") is not None:
            require_auth(authorization)
        return {"agents": workspace.list_agents()}

    @app.post("/workspace/agents/run")
    def workspace_run_agent(
        request: WorkspaceAgentRunRequest,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        try:
            return workspace.run_agent(request.agent_id, request.task, request.session_id)
        except KeyError as exc:
            code = str(exc).strip("'")
            status_code = 404 if code in {"AGENT_NOT_FOUND", "SESSION_NOT_FOUND"} else 422
            raise HTTPException(status_code=status_code, detail=code) from None
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None

    @app.get("/workspace/vx-inspector")
    def vx_inspector(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        if os.getenv("VAIXLNS_API_TOKEN") is not None:
            require_auth(authorization)
        return inspect_vx(root)

    @app.get("/inspector", response_class=HTMLResponse)
    def inspector_dashboard() -> HTMLResponse:
        path = Path(__file__).resolve().parents[1] / "workspace" / "inspector.html"
        try:
            return HTMLResponse(path.read_text(encoding="utf-8"))
        except OSError:
            raise HTTPException(status_code=404, detail="VX_INSPECTOR_NOT_INSTALLED") from None

    return app


app = create_app()
