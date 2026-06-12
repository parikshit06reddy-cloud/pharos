"""FastAPI surface for Pharos.

Endpoints:
  POST /brief            Server-Sent Events stream of the live pipeline stages.
  POST /brief/sync       One-shot Decision Brief (JSON).
  GET  /health
  GET  /model-card
  GET  /data-passport    (optional ?session_id= to include that session's redaction types)
  GET  /audit-log        tamper-evident, PHI-free chain
  DELETE /session/{id}   purge in-memory state + the session's audit rows (chain stays valid)
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .api import agent as agent_api
from .api import auth as auth_api
from .api import cases as cases_api
from .api import dashboard as dashboard_api
from .db import init_db
from .envload import load_env
from .governance import audit_log, data_passport, model_card
from .intake import ConsentError
from .pipeline import run_pipeline
from .reasoning_roles import REASONING_AGENTS, active_providers
from .seed import seed_users

load_env()  # load .env (real env vars win; no-op if absent)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_users()
    yield


app = FastAPI(
    title="Pharos",
    version="pharos-0.2.0",
    lifespan=lifespan,
    description="Hospital medication case-management with cited, triaged decision support. "
    "Synthetic data only. Not for clinical use.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev-only; the demo runs locally with synthetic data
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mounted under /api so client-side routes (/cases, /dashboard, ...) never collide with the API.
app.include_router(auth_api.router, prefix="/api")
app.include_router(cases_api.router, prefix="/api")
app.include_router(dashboard_api.router, prefix="/api")
app.include_router(agent_api.router, prefix="/api")

# In-memory only: maps a session/case id to the redaction TYPES seen at intake (never values).
_SESSION_REDACTIONS: dict[str, list[str]] = {}


def _remember(raw_case: dict, redactions: list[str]) -> None:
    for key in (raw_case.get("session_id"), raw_case.get("case_id")):
        if key:
            _SESSION_REDACTIONS[key] = redactions


def _sse(payload: dict) -> str:
    return f"event: {payload['event']}\ndata: {json.dumps(jsonable_encoder(payload['data']))}\n\n"


@app.get("/health")
def health() -> dict:
    providers = active_providers()
    return {
        "status": "ok",
        "service": "pharos",
        "version": app.version,
        "audit_chain_valid": audit_log.verify_chain(),
        "providers": providers,
        "foundry_iq_ready": providers["retrieval"] in ("foundry_iq", "foundry", "foundry_replay", "replay"),
        "reasoning_agents": REASONING_AGENTS,
        "offline_capable": True,
    }


@app.get("/model-card")
def get_model_card() -> dict:
    return model_card.model_card()


@app.get("/data-passport")
def get_data_passport(session_id: str | None = None) -> dict:
    return data_passport.passport(_SESSION_REDACTIONS.get(session_id or "", []))


@app.get("/audit-log")
def get_audit_log() -> dict:
    rows = audit_log.entries()
    return {"chain_valid": audit_log.verify_chain(), "entries": rows}


@app.delete("/session/{session_id}")
def delete_session(session_id: str) -> dict:
    _SESSION_REDACTIONS.pop(session_id, None)
    removed = audit_log.purge_case(session_id)
    return {
        "deleted": True,
        "session_id": session_id,
        "audit_rows_removed": removed,
        "chain_valid": audit_log.verify_chain(),
    }


@app.post("/brief")
async def brief_stream(request: Request):
    raw_case = await request.json()

    def gen():
        try:
            for ev in run_pipeline(raw_case):
                if ev["event"] == "intake":
                    _remember(raw_case, ev["data"].get("redactions", []))
                yield _sse(ev)
        except ConsentError as e:
            yield _sse({"event": "error", "data": {"error": "consent", "detail": str(e)}})

    return StreamingResponse(
        gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.post("/brief/sync")
async def brief_sync(request: Request):
    raw_case = await request.json()
    brief = None
    try:
        for ev in run_pipeline(raw_case):
            if ev["event"] == "intake":
                _remember(raw_case, ev["data"].get("redactions", []))
            elif ev["event"] == "brief":
                brief = ev["data"]
    except ConsentError as e:
        return JSONResponse(status_code=422, content={"error": "consent", "detail": str(e)})
    return JSONResponse(content=jsonable_encoder(brief))
