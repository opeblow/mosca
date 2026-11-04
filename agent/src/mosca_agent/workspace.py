"""Checks out branches of the watched repository so they can be scanned side by side."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

# Branch names come from chat, so they are validated before they reach git.
REF_RX = re.compile(r"^(?!-)(?!.*\.\.)[A-Za-z0-9._/-]{1,200}$")


class WorkspaceError(Exception):
    """Something a person in the room can fix, such as a branch name that does not exist."""


class Workspace:
    def __init__(self, repo: Path, subdir: str = "", base_ref: str = "main") -> None:
        self.repo = repo
        self.subdir = subdir
        self.base_ref = base_ref

    def _git(self, *args: str) -> str:
        proc = subprocess.run(["git", "-C", str(self.repo), *args],
                              capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            raise WorkspaceError(proc.stderr.strip() or f"git {args[0]} failed")
        return proc.stdout.strip()

    def resolve(self, ref: str) -> str:
        """The commit a branch name points to, fetching it from origin if needed."""
        if not REF_RX.match(ref):
            raise WorkspaceError(f"`{ref}` is not a valid branch name.")
        for candidate in (ref, f"origin/{ref}"):
            try:
                return self._git("rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}")
            except WorkspaceError:
                pass
        try:
            self._git("fetch", "--quiet", "origin", f"{ref}:refs/remotes/origin/{ref}")
            return self._git("rev-parse", "--verify", "--quiet", f"origin/{ref}^{{commit}}")
        except WorkspaceError:
            raise WorkspaceError(f"I can't find a branch called `{ref}`.") from None

    @contextmanager
    def checkout(self, ref: str) -> Iterator[tuple[Path, str]]:
        """A temporary, detached checkout of `ref`. Yields (path to scan, short commit)."""
        sha = self.resolve(ref)
        tmp = Path(tempfile.mkdtemp(prefix="mosca-"))
        target = tmp / "tree"
        try:
            self._git("worktree", "add", "--detach", "--quiet", str(target), sha)
            yield (target / self.subdir if self.subdir else target), sha[:7]
        finally:
            try:
                self._git("worktree", "remove", "--force", str(target))
            except WorkspaceError:
                pass
            shutil.rmtree(tmp, ignore_errors=True)
