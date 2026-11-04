"""Settings, read from the environment, and the agent's saved identity."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    switch_url: str                 # the Switch agent bridge, e.g. http://localhost:8000
    state_file: Path                # where the agent id, API key and connection id are kept
    repo: Path                      # a git checkout of the repository Mosca watches
    subdir: str = ""                # scan only this directory of the checkout
    base_ref: str = "main"          # the branch migrations are compared against
    repo_name: str = "acme-payments"  # the repository's name in the ledger
    ledger_url: str | None = None
    ledger_token: str | None = None

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        env = dict(os.environ if env is None else env)
        return cls(
            switch_url=env.get("SWITCH_API_URL", "http://localhost:8000").rstrip("/"),
            state_file=Path(env.get("MOSCA_AGENT_STATE", "data/agent-state.json")),
            repo=Path(env.get("MOSCA_REPO", ".")),
            subdir=env.get("MOSCA_REPO_SUBDIR", "").strip("/"),
            base_ref=env.get("MOSCA_BASE_REF", "main"),
            repo_name=env.get("MOSCA_REPO_NAME", "acme-payments"),
            ledger_url=(env.get("LEDGER_URL") or None),
            ledger_token=(env.get("MOSCA_LEDGER_TOKEN") or None),
        )


@dataclass
class Identity:
    """What registration returns, plus the connection id the agent reuses across reconnects."""

    agent_id: str
    api_key: str
    connection_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @classmethod
    def load(cls, path: Path) -> Identity | None:
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(**data)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.__dict__, indent=2) + "\n", encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass  # best effort on filesystems without POSIX modes
