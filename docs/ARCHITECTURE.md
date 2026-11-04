# Architecture

## Components

### core: `mosca`

A pure-Python package with no runtime dependencies, so it installs anywhere a CI job or a coding agent runs.

```
scanner/            walk the tree, pick detectors per file, deduplicate findings
  python_ast.py     resolves imports and aliases with the stdlib AST
  lexical.py        JS/TS, Go, Java/Kotlin; strips comments while keeping line numbers
  configs.py        TLS groups and ciphers, SSH, JWT, openssl commands
  pem.py            certificates and keys (exact parsing with `cryptography` if present)
  deps.py           dependency manifests, lower confidence by design
taxonomy.py         the algorithm catalog: status, usage, OIDs, NIST levels, replacements
model.py            Finding, ScanResult
cbom.py             CycloneDX 1.6 writer and reader
policy.py           mosca.toml, owner answers, the threat prior
risk.py             Mosca model and prioritisation
report.py, diff.py  output for people and machines
cli.py              scan, assess, diff
```

Design rules:

- **One bad file never stops a scan.** Detector errors are collected and reported, not raised.
- **Determinism.** Findings are sorted, Monte Carlo runs are seeded, and the same inputs always produce the same report. This makes diffs and CI gates trustworthy.
- **Evidence over inference.** Every asset carries its occurrences (file, line, snippet, detector, confidence). Nothing is ranked without a location someone can open.

### ledger: `mosca_ledger`

FastAPI on SQLite (WAL mode). The only table is an append-only event log:

```sql
events(seq, repo, type IN ('assessment','answer'), payload JSON, actor, created_at)
```

Current state is a projection over events: the latest assessment, answers folded with last-write-wins, and the history series. Nothing is ever updated in place, so the audit trail is complete by construction. Writes require a bearer token compared in constant time; reads are open so a dashboard can be shared on an internal network.

SQLite is the right default for a single team's ledger (one writer, small events). The store sits behind one class, so moving to Postgres is a contained change.

### web

Next.js (App Router). The landing page is static. The ledger page renders on the server, reads `LEDGER_URL` with a short timeout and revalidation, and falls back to the bundled sample assessment so the page never breaks. The interactive diagram reimplements the closed-form part of the model in TypeScript so it responds instantly; the engine remains the source of truth.

## Data flow

1. `mosca assess` scans the repository and loads `mosca.toml`.
2. Owner answers are read from a file or from the ledger (`--answers <url>`).
3. The assessment is printed, written as JSON, or pushed to the ledger (`--push`).
4. The dashboard reads the latest assessment and the history from the ledger.
5. After a migration branch, `mosca diff` (or a new pushed assessment) shows the reduction.

## Security

- The scanner never executes scanned code and never sends anything over the network unless `--push` or a ledger `--answers` URL is given.
- Private keys found in a repository are reported by type only; key material is never copied into reports.
- The web app sets `nosniff`, `DENY` framing and a strict referrer policy.
