"""Small local-first FastAPI surface for VAIXLNS durable execution state."""
from __future__ import annotations

import hmac
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from infra.durable_store import DurableEventStore
from infra.vlns_server_client import ServerConfig, VLNSServerClient


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


def _authorized(authorization: str | None) -> bool:
    token = os.getenv("VAIXLNS_API_TOKEN")
    if token is None:
        return True
    if not authorization or not authorization.startswith("Bearer "):
        return False
    provided = authorization.removeprefix("Bearer ").strip()
    return hmac.compare_digest(provided, token)


def create_app(db_path: str | Path = DB_PATH) -> FastAPI:
    app = FastAPI(title="VAIXLNS Runtime API", version="1.1.0")
    store = DurableEventStore(db_path)

    @app.on_event("shutdown")
    def _shutdown() -> None:
        store.close()

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "service": "VAIXLNS-runtime",
            "version": "1.1.0",
            "durable_store": store.verify_integrity(),
        }

    @app.get("/status")
    def status(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        if os.getenv("VAIXLNS_API_TOKEN") is not None and not _authorized(authorization):
            raise HTTPException(status_code=401, detail="AUTHORIZATION_REQUIRED")
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
        if os.getenv("VAIXLNS_API_TOKEN") is not None and not _authorized(authorization):
            raise HTTPException(status_code=401, detail="AUTHORIZATION_REQUIRED")
        return {
            "events": [event.to_dict() for event in store.events(aggregate_id)],
            "integrity": store.verify_integrity(),
        }

    @app.post("/events", status_code=201)
    def append_event(
        event: EventRequest,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        if not _authorized(authorization):
            raise HTTPException(status_code=401, detail="AUTHORIZATION_REQUIRED")
        result = store.append(**event.model_dump())
        return result.to_dict()

    @app.post("/snapshots", status_code=201)
    def save_snapshot(
        snapshot: SnapshotRequest,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        if not _authorized(authorization):
            raise HTTPException(status_code=401, detail="AUTHORIZATION_REQUIRED")
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
        if not _authorized(authorization):
            raise HTTPException(status_code=401, detail="AUTHORIZATION_REQUIRED")
        config = ServerConfig.from_env("vlns-control")
        return VLNSServerClient(config).health()

    return app


app = create_app()
