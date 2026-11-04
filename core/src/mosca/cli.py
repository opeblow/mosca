"""Command-line interface.

    mosca scan PATH [--out cbom.json]          inventory cryptography, write a CycloneDX CBOM
    mosca assess PATH [--json] [--answers F]   rank assets by quantum exposure
    mosca diff BEFORE AFTER                    compare two trees (e.g. main vs. a migration branch)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from . import __version__, cbom, diff, policy, report, risk
from .scanner import scan


def _http(method: str, url: str, body: dict | None = None) -> dict:
    headers = {"Content-Type": "application/json", "User-Agent": f"mosca/{__version__}"}
    token = os.environ.get("MOSCA_LEDGER_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        raise SystemExit(f"ledger returned {exc.code}: {detail}") from None
    except urllib.error.URLError as exc:
        raise SystemExit(f"cannot reach ledger at {url}: {exc.reason}") from None


def _assess(path: str, config: str | None, answers: str | None) -> risk.Assessment:
    result = scan(path)
    if answers and answers.startswith(("http://", "https://")):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
            json.dump(_http("GET", answers), fh)
        try:
            pol = policy.load(path, config, fh.name)
        finally:
            os.unlink(fh.name)
    else:
        pol = policy.load(path, config, answers)
    return risk.assess(result, pol)


def cmd_scan(args: argparse.Namespace) -> int:
    result = scan(args.path)
    doc = cbom.to_cbom(result, args.name)
    text = json.dumps(doc, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"{len(doc['components'])} cryptographic assets, {len(result.findings)} occurrences "
              f"in {result.files_scanned} files -> {args.out}")
    else:
        print(text)
    for err in result.errors:
        print(f"warning: {err}", file=sys.stderr)
    return 0


def cmd_assess(args: argparse.Namespace) -> int:
    assessment = _assess(args.path, args.config, args.answers)
    if args.push:
        if not args.repo:
            raise SystemExit("--push needs --repo")
        payload = {**report.to_json(assessment), "ref": args.ref}
        url = f"{args.push.rstrip('/')}/v1/repos/{args.repo}/assessments"
        res = _http("POST", url, payload)
        print(f"recorded assessment #{res.get('seq')} for {args.repo}", file=sys.stderr)
    if args.out:
        Path(args.out).write_text(json.dumps(report.to_json(assessment), indent=2) + "\n", encoding="utf-8")
    elif args.json:
        print(json.dumps(report.to_json(assessment), indent=2))
    else:
        print(report.chat_summary(assessment, limit=args.limit))
    if args.fail_above is not None and any(a.exposure > args.fail_above for a in assessment.assets):
        return 2
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    before = _assess(args.before, args.config, args.answers)
    after = _assess(args.after, args.config or str(Path(args.before) / "mosca.toml"), args.answers)
    print(diff.chat(diff.compare(before, after)))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mosca", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=f"mosca {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("scan", help="write a CycloneDX 1.6 CBOM")
    p.add_argument("path")
    p.add_argument("--out", "-o")
    p.add_argument("--name", help="component name in the CBOM metadata")
    p.set_defaults(func=cmd_scan)

    for name, func, helptext in (("assess", cmd_assess, "rank assets by quantum exposure"),):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("path")
        p.add_argument("--config", help="policy file (default: PATH/mosca.toml)")
        p.add_argument("--answers", help="owner answers: a JSON file or a ledger answers URL")
        p.add_argument("--json", action="store_true")
        p.add_argument("--out", "-o", help="write the JSON report to a file")
        p.add_argument("--push", metavar="LEDGER_URL",
                       help="record the assessment in a Mosca ledger (token: $MOSCA_LEDGER_TOKEN)")
        p.add_argument("--repo", help="repository name in the ledger")
        p.add_argument("--ref", help="branch or commit being assessed")
        p.add_argument("--limit", type=int, default=12)
        p.add_argument("--fail-above", type=float, metavar="P",
                       help="exit 2 if any asset's exposure exceeds P (for CI)")
        p.set_defaults(func=func)

    p = sub.add_parser("diff", help="compare two trees")
    p.add_argument("before")
    p.add_argument("after")
    p.add_argument("--config")
    p.add_argument("--answers")
    p.set_defaults(func=cmd_diff)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
