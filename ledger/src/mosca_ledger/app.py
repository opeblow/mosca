"""HTTP API for the ledger.

Reads are open by default so a dashboard can be shared inside a company network.
Writes require `Authorization: Bearer $MOSCA_LEDGER_TOKEN`.
"""

from __future__ import annotations

import hmac
import os
import re
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Path, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from . import __version__
from .store import Store

REPO_RX = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"
RepoName = Annotated[str, Path(pattern=REPO_RX)]


class Summary(BaseModel):
    assets: int = Field(ge=0)
    to_migrate: int = Field(ge=0)
    exposed: int = Field(ge=0)
    classically_broken: int = Field(ge=0)
    quantum_safe: int = Field(ge=0)


class AssessmentIn(BaseModel):
    """Output of `mosca assess --json`, plus where it came from."""

    model_config = ConfigDict(extra="allow")

    ref: str | None = Field(default=None, max_length=200, description="branch or commit")
    now_year: float
    crqc_median_year: float
    crqc_p05_year: float
    target_exposure: float = Field(ge=0, le=1)
    readiness: float = Field(ge=0, le=1)
    summary: Summary
    pending_questions: list[dict[str, Any]] = Field(default_factory=list, max_length=500)
    assets: list[dict[str, Any]] = Field(max_length=5000)


class AnswerIn(BaseModel):
    system: str = Field(min_length=1, max_length=100)
    kind: Literal["shelf_life_years", "signature_lifetime_years"]
    years: float = Field(ge=0, le=100)
    answered_by: str = Field(min_length=1, max_length=100)


def create_app(store: Store | None = None, token: str | None = None) -> FastAPI:
    store = store or Store(os.environ.get("MOSCA_LEDGER_DB", "data/ledger.db"))
    token = token if token is not None else os.environ.get("MOSCA_LEDGER_TOKEN", "")

    app = FastAPI(title="Mosca Ledger", version=__version__)
    origins = [o for o in os.environ.get("MOSCA_LEDGER_CORS", "*").split(",") if o]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
                       allow_headers=["Authorization", "Content-Type"])

    def require_writer(authorization: str = Header(default="")) -> None:
        if not token:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "writes disabled: MOSCA_LEDGER_TOKEN is not set")
        scheme, _, supplied = authorization.partition(" ")
        if scheme.lower() != "bearer" or not hmac.compare_digest(supplied.encode(), token.encode()):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/v1/repos")
    def list_repos() -> list[dict[str, Any]]:
        out = []
        for repo in store.repos():
            latest = store.latest_assessment(repo)
            out.append({
                "repo": repo,
                "updated_at": latest.created_at if latest else None,
                "readiness": latest.payload.get("readiness") if latest else None,
                "summary": latest.payload.get("summary") if latest else None,
            })
        return out

    @app.get("/v1/repos/{repo}")
    def get_repo(repo: RepoName) -> dict[str, Any]:
        latest = store.latest_assessment(repo)
        if latest is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no assessments for this repository")
        return {
            "repo": repo,
            "updated_at": latest.created_at,
            "assessment": latest.payload,
            "answers": store.answers(repo),
            "history": store.history(repo),
        }

    @app.get("/v1/repos/{repo}/answers")
    def get_answers(repo: RepoName) -> dict[str, dict[str, Any]]:
        return store.answers(repo)

    @app.post("/v1/repos/{repo}/assessments", status_code=status.HTTP_201_CREATED,
              dependencies=[Depends(require_writer)])
    def post_assessment(repo: RepoName, body: AssessmentIn) -> dict[str, Any]:
        event = store.append(repo, "assessment", body.model_dump(mode="json"))
        return {"seq": event.seq, "created_at": event.created_at}

    @app.post("/v1/repos/{repo}/answers", status_code=status.HTTP_201_CREATED,
              dependencies=[Depends(require_writer)])
    def post_answer(repo: RepoName, body: AnswerIn) -> dict[str, Any]:
        if not re.fullmatch(r"[A-Za-z0-9._()/-]+", body.system):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid system name")
        event = store.append(repo, "answer", body.model_dump(), actor=body.answered_by)
        return {"seq": event.seq, "created_at": event.created_at}

    return app


app = create_app() if os.environ.get("MOSCA_LEDGER_AUTOSTART", "1") == "1" else None
