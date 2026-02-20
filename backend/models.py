"""Pydantic models for Paper2Code API."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────────

class RunStatus(str, Enum):
    PENDING = "pending"
    PARSING_PAPER = "parsing_paper"
    GENERATING_ARCHITECTURE = "generating_architecture"
    GENERATING_CODE = "generating_code"
    EXECUTING_CODE = "executing_code"
    REFINING_CODE = "refining_code"
    GENERATING_README = "generating_readme"
    GENERATING_NOTEBOOK = "generating_notebook"
    PUSHING_TO_GITHUB = "pushing_to_github"
    COMPLETED = "completed"
    FAILED = "failed"


# ── Request / Response ───────────────────────────────────────────────────────

class RunRequest(BaseModel):
    """Body for POST /api/runs."""
    paper_input: str = Field(..., description="arXiv URL or free-text paper description")
    repo_name: str = Field(..., description="GitHub repository name to create")
    max_iterations: int = Field(default=5, ge=1, le=10, description="Max refinement iterations")
    framework: str = Field(default="pytorch", description="ML framework: pytorch or tensorflow")


class RunSummary(BaseModel):
    """Lightweight view returned in list endpoints."""
    id: str
    paper_input: str
    repo_name: str
    status: RunStatus
    created_at: str
    github_url: Optional[str] = None


class RunDetail(BaseModel):
    """Full view of a pipeline run."""
    id: str
    paper_input: str
    repo_name: str
    status: RunStatus
    created_at: str
    max_iterations: int
    framework: str
    current_iteration: int = 0

    # Generated artefacts
    paper_info: Optional[str] = None
    architecture_doc: Optional[str] = None
    generated_code: Optional[str] = None
    readme: Optional[str] = None
    notebook_json: Optional[str] = None
    github_url: Optional[str] = None
    colab_url: Optional[str] = None

    # Execution trace
    logs: List[str] = Field(default_factory=list)
    error: Optional[str] = None


# ── WebSocket event ──────────────────────────────────────────────────────────

class ProgressEvent(BaseModel):
    """Sent over WebSocket to stream progress."""
    run_id: str
    status: RunStatus
    message: str
    iteration: Optional[int] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── In-memory store helper ───────────────────────────────────────────────────

def new_run(req: RunRequest) -> RunDetail:
    """Create a fresh RunDetail from a request."""
    return RunDetail(
        id=uuid.uuid4().hex[:12],
        paper_input=req.paper_input,
        repo_name=req.repo_name,
        status=RunStatus.PENDING,
        created_at=datetime.now(timezone.utc).isoformat(),
        max_iterations=req.max_iterations,
        framework=req.framework,
    )
