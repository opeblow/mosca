from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SAMPLE = REPO / "examples" / "acme-payments"


@pytest.fixture
def sample_repo() -> Path:
    return SAMPLE


@pytest.fixture
def write(tmp_path: Path):
    """Write files into a temporary tree: write({"a/b.py": "..."}) -> root path."""

    def _write(files: dict[str, str]) -> Path:
        for rel, content in files.items():
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        return tmp_path

    return _write
