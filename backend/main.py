"""FastAPI application — REST endpoints + WebSocket for Paper2Code."""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from models import (
    ProgressEvent,
    RunDetail,
    RunRequest,
    RunSummary,
    RunStatus,
    new_run,
)
from agent import run_pipeline
from paper_catalog import get_catalog, get_categories
from github_client import check_existing_repos


# ── In-memory store ──────────────────────────────────────────────────────────

runs: Dict[str, RunDetail] = {}
ws_connections: Dict[str, List[WebSocket]] = {}


# ── App ──────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(
    title="Paper2Code",
    description="ML Paper → Implementation Agent",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── REST endpoints ───────────────────────────────────────────────────────────

@app.post("/api/runs", response_model=RunSummary)
async def create_run(req: RunRequest):
    """Start a new pipeline run."""
    run = new_run(req)
    runs[run.id] = run

    # Fire-and-forget the pipeline in a background task
    asyncio.create_task(_execute_run(run))

    return RunSummary(
        id=run.id,
        paper_input=run.paper_input,
        repo_name=run.repo_name,
        status=run.status,
        created_at=run.created_at,
    )


@app.get("/api/runs", response_model=List[RunSummary])
async def list_runs():
    """List all runs, most recent first."""
    return [
        RunSummary(
            id=r.id,
            paper_input=r.paper_input,
            repo_name=r.repo_name,
            status=r.status,
            created_at=r.created_at,
            github_url=r.github_url,
        )
        for r in sorted(runs.values(), key=lambda r: r.created_at, reverse=True)
    ]


@app.get("/api/runs/{run_id}", response_model=RunDetail)
async def get_run(run_id: str):
    """Get full details of a specific run."""
    if run_id not in runs:
        raise HTTPException(status_code=404, detail="Run not found")
    return runs[run_id]


@app.get("/api/papers")
async def get_papers():
    """Return the curated paper catalog."""
    return {"papers": get_catalog(), "categories": get_categories()}


@app.get("/api/check-duplicate")
async def check_duplicate(paper_title: str):
    """Check if the user already has a GitHub repo implementing this paper."""
    matches = check_existing_repos(paper_title)
    return {"matches": matches, "has_duplicate": len(matches) > 0}


# ── WebSocket ────────────────────────────────────────────────────────────────

@app.websocket("/ws/runs/{run_id}")
async def ws_run(websocket: WebSocket, run_id: str):
    """Stream real-time progress for a pipeline run."""
    await websocket.accept()

    if run_id not in ws_connections:
        ws_connections[run_id] = []
    ws_connections[run_id].append(websocket)

    # Send existing logs as catch-up
    if run_id in runs:
        run = runs[run_id]
        for log in run.logs:
            try:
                await websocket.send_json(
                    ProgressEvent(
                        run_id=run_id,
                        status=run.status,
                        message=log,
                    ).model_dump()
                )
            except Exception:
                break

    try:
        # Keep the connection alive until client disconnects
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_connections.get(run_id, []).remove(websocket) if websocket in ws_connections.get(run_id, []) else None


# ── Background pipeline execution ───────────────────────────────────────────

async def _execute_run(run: RunDetail):
    """Run the pipeline and broadcast progress via WebSocket."""

    def on_progress(evt: ProgressEvent):
        # Broadcast to all WebSocket clients for this run
        listeners = ws_connections.get(run.id, [])
        for ws in listeners[:]:  # copy to avoid mutation issues
            try:
                asyncio.create_task(ws.send_json(evt.model_dump()))
            except Exception:
                listeners.remove(ws)

    await run_pipeline(run, on_progress=on_progress)
