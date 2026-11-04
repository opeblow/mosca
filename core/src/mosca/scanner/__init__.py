"""Walks a source tree and runs every detector that applies to each file."""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path

from ..model import Finding, ScanResult
from ..policy import glob_regex
from . import configs, deps, lexical, pem, python_ast

MAX_FILE_BYTES = 2 * 1024 * 1024

SKIP_DIRS = frozenset({
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "env", "__pycache__",
    "dist", "build", "target", "vendor", ".next", ".turbo", ".cache", ".tox",
    ".mypy_cache", ".pytest_cache", "coverage", ".idea", ".vscode",
})

Detector = Callable[[str, str], Iterable[Finding]]


def detectors_for(path: Path) -> list[Detector]:
    name = path.name.lower()
    suffix = path.suffix.lower()
    found: list[Detector] = []
    if suffix == ".py":
        found.append(python_ast.detect)
    if suffix in lexical.LANGUAGES:
        found.append(lexical.detect)
    if configs.applies(name, suffix):
        found.append(configs.detect)
    if pem.applies(name, suffix):
        found.append(pem.detect)
    if deps.applies(name):
        found.append(deps.detect)
    return found


def iter_files(root: Path) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames
                             if d not in SKIP_DIRS and (not d.startswith(".") or d == ".github"))
        for filename in sorted(filenames):
            yield Path(dirpath) / filename


def _read_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw[:4096]:
        return None
    return raw.decode("utf-8", errors="replace")


IGNORE_FILE = ".moscaignore"


def load_ignore(root: Path) -> list[re.Pattern[str]]:
    """Read `.moscaignore`: one glob per line, `#` comments, `**` supported.

    A pattern ending in `/` ignores a directory and everything under it.
    """
    path = root / IGNORE_FILE
    if not path.is_file():
        return []
    patterns: list[re.Pattern[str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith("/"):
            line += "**"
        patterns.append(glob_regex(line.lstrip("/")))
    return patterns


def scan(root: str | os.PathLike[str]) -> ScanResult:
    root_path = Path(root).resolve()
    result = ScanResult(root=str(root_path))
    seen: set[tuple[str, str, int, str]] = set()
    ignored = load_ignore(root_path)

    for path in iter_files(root_path):
        detectors = detectors_for(path)
        if not detectors:
            continue
        if ignored and any(p.fullmatch(path.relative_to(root_path).as_posix()) for p in ignored):
            continue
        text = _read_text(path)
        if text is None:
            result.files_skipped += 1
            continue
        result.files_scanned += 1
        rel = path.relative_to(root_path).as_posix()
        for detect in detectors:
            try:
                for finding in detect(rel, text):
                    key = (finding.algorithm, finding.path, finding.line, finding.detector)
                    if key not in seen:
                        seen.add(key)
                        result.findings.append(finding)
            except Exception as exc:  # one bad file must never stop a scan
                result.errors.append(f"{rel}: {detect.__module__}: {exc}")

    result.findings.sort(key=lambda f: (f.path, f.line, f.algorithm))
    return result
