import shutil
import subprocess
from pathlib import Path

import pytest

SAMPLE = Path(__file__).resolve().parents[2] / "examples" / "acme-payments"
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "core.autocrlf=false"]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """The sample repository as a git repo, plus a branch that moves the ledger to hybrid TLS."""
    root = tmp_path / "acme"
    shutil.copytree(SAMPLE, root)
    run = lambda *a: subprocess.run([*GIT, "-C", str(root), *a], check=True, capture_output=True)  # noqa: E731
    run("init", "-q", "-b", "main")
    run("add", "-A")
    run("commit", "-qm", "sample")
    run("checkout", "-qb", "pq/ledger-hybrid-tls")
    go = root / "services" / "ledger" / "server.go"
    go.write_text(go.read_text().replace("[]tls.CurveID{tls.X25519, tls.CurveP256}",
                                         "[]tls.CurveID{tls.X25519MLKEM768}"))
    run("commit", "-qam", "ledger: hybrid post-quantum key exchange")
    run("checkout", "-q", "main")
    return root
