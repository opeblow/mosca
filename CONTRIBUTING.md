# Contributing to Mosca

Thank you for helping. Mosca is used to make security decisions, so the bar is correctness first, clarity second, and features third.

## Ground rules

- Be kind. This project follows the [Code of Conduct](CODE_OF_CONDUCT.md).
- Report security issues privately. See [SECURITY.md](SECURITY.md). Never open a public issue for a vulnerability.
- Open an issue before starting large changes, so we can agree on the approach before you spend time on it.

## Set up

Requirements: Python 3.11 or later, Node.js 20 or later, Git.

```bash
git clone https://github.com/opeblow/mosca.git
cd mosca

python -m venv .venv
. .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -e "./core[dev]" -e "./ledger[dev]"

cd web && npm install
```

Run the checks:

```bash
pytest core
pytest ledger
cd web && npm run typecheck && npm run build
```

All of them run in CI on every pull request.

## Where things live

| Change | Files | Tests |
|---|---|---|
| Recognise a new algorithm | `core/src/mosca/taxonomy.py` | `core/tests/test_detectors.py` |
| Detect a new API, library or config format | `core/src/mosca/scanner/` | `core/tests/test_detectors.py` |
| Change the exposure model | `core/src/mosca/risk.py`, `docs/MODEL.md` | `core/tests/test_risk.py` |
| Ledger API | `ledger/src/mosca_ledger/` | `ledger/tests/` |
| Website | `web/src/` | `npm run typecheck`, `npm run build` |

## Adding a detector rule

Every new rule needs three tests:

1. **It finds the real thing**, with the right algorithm, line number and parameters (key size, curve).
2. **It ignores look-alikes**: the same text in a comment, a string that is not a call, or another language.
3. **It degrades safely**: a malformed file produces no findings and no exception.

Set `confidence` honestly: a resolved call site is about 0.95, a pattern match about 0.9, a configuration token about 0.75, and a dependency 0.5.

## Changing the model

The model in `risk.py` must stay deterministic and explainable. If you change a formula or a default:

- update [docs/MODEL.md](docs/MODEL.md) in the same pull request
- keep the property tests passing (exposure grows with X, falls as the threat prior moves later, and is identical for identical inputs)
- explain in the pull request description why the new behaviour is more accurate, with a source where one exists

## Pull requests

- Keep each pull request to one change, with a title that says what it does.
- Include tests. Bug fixes start with a test that fails without the fix.
- Run the full checks locally before asking for review.
- Do not commit secrets, real private keys, or scan output from private codebases. The sample repository in `examples/` is the place for test material.

## Commit messages

Use the imperative mood and say why when it is not obvious:

```
Detect X25519MLKEM768 in Caddy configs

Caddy names the hybrid group differently from OpenSSL, so edge
deployments behind Caddy were reported as classical-only.
```

## License

By contributing, you agree that your contributions are licensed under the [Apache License 2.0](LICENSE).
