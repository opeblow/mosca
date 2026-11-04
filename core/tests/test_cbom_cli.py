import json

from mosca import cbom, cli
from mosca.scanner import scan


def test_cbom_shape(sample_repo):
    doc = cbom.to_cbom(scan(sample_repo))
    assert doc["bomFormat"] == "CycloneDX" and doc["specVersion"] == "1.6"
    comps = doc["components"]
    assert comps and all(c["type"] == "cryptographic-asset" for c in comps)
    rsa = next(c for c in comps if c["bom-ref"] == "crypto/algorithm/rsa-2048")
    props = rsa["cryptoProperties"]
    assert props["assetType"] == "algorithm"
    assert props["oid"] == "1.2.840.113549.1.1.1"
    assert props["algorithmProperties"]["nistQuantumSecurityLevel"] == 0
    assert rsa["evidence"]["occurrences"]
    assert doc["dependencies"][0]["dependsOn"]


def test_cbom_round_trip(sample_repo):
    original = scan(sample_repo)
    rebuilt = cbom.from_cbom(cbom.to_cbom(original))
    assert sorted((f.algorithm, f.path, f.line) for f in rebuilt.findings) == \
        sorted((f.algorithm, f.path, f.line) for f in original.findings)


def test_cli_scan_writes_file(sample_repo, tmp_path, capsys):
    out = tmp_path / "cbom.json"
    assert cli.main(["scan", str(sample_repo), "-o", str(out)]) == 0
    assert json.loads(out.read_text())["components"]
    assert "cryptographic assets" in capsys.readouterr().out


def test_cli_assess_json(sample_repo, capsys):
    assert cli.main(["assess", str(sample_repo), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["summary"]["to_migrate"] > 0
    assert {"system", "owner", "kind", "text"} <= set(data["pending_questions"][0])


def test_cli_fail_above_for_ci(sample_repo):
    assert cli.main(["assess", str(sample_repo), "--fail-above", "0.5"]) == 2


def test_scanner_skips_vendored_and_binary(write):
    root = write({
        "node_modules/x/index.js": 'createHash("md5")',
        "src/app.js": 'createHash("md5")',
    })
    (root / "src/blob.py").write_bytes(b"\x00\x01import hashlib; hashlib.md5()")
    result = scan(root)
    assert [f.path for f in result.findings] == ["src/app.js"]


def test_moscaignore(write):
    root = write({
        ".moscaignore": "# fixtures\nfixtures/\n**/generated.js\n",
        "fixtures/weak.py": "import hashlib\nhashlib.md5()\n",
        "src/a/generated.js": 'createHash("md5")',
        "src/app.js": 'createHash("sha1")',
    })
    assert [f.path for f in scan(root).findings] == ["src/app.js"]
