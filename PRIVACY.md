# Privacy

Mosca is built to run inside your own environment. This page lists every kind of data each component handles, where it goes, and how to remove it.

## Summary

- **No telemetry.** Mosca does not collect usage analytics, crash reports or identifiers. There is nothing to opt out of.
- **No source code leaves your machine** unless you send it somewhere yourself.
- **You control the ledger.** It runs on your infrastructure, and the data in it belongs to you.

## Scanner (`mosca` CLI)

| Data | Where it goes |
|---|---|
| Your source code, configs, certificates | Read locally. Never stored, never transmitted. |
| Findings: file path, line number, a snippet of up to 200 characters of the matching line | Printed to your terminal or written to files you choose (`-o`, `--out`) |
| Assessment report (findings plus risk figures) | Sent only when you pass `--push`, and only to the ledger URL you give |

Snippets are taken from lines that contain cryptographic API calls or configuration. For PEM files, the snippet is the header line only (for example `-----BEGIN CERTIFICATE-----`); key material is never included.

## Ledger

The ledger stores what you send it, in a SQLite file on a volume you control:

| Stored | Why |
|---|---|
| Assessment reports, including file paths, snippets and owner usernames from `mosca.toml` | To show current exposure and its history |
| Owner answers: system name, number of years, the answering person's username, timestamp | To keep an auditable record of who decided each data lifetime |

The event log is append-only by design, so that answers stay auditable. To delete data, stop the service and delete the database file (the path in `MOSCA_LEDGER_DB`, `data/ledger.db` by default), or delete specific rows with any SQLite client. Usernames are the only personal data stored; use handles rather than full names if you prefer.

Reads are unauthenticated by default, so that a dashboard can be shared inside your network. **Do not expose the ledger to the public internet without an authenticating proxy** if your reports contain information you consider sensitive.

## Website

The website does not set cookies, use analytics, or load third-party scripts at runtime. Fonts are self-hosted at build time. The ledger page reads from the ledger server-side; your browser never contacts the ledger directly.

If you deploy the website on a hosting provider, that provider's own request logging applies.

## Chat integrations

When Mosca posts into a team chat, messages and attachments (for example a CBOM) are stored by that chat platform under its own terms. Mosca posts only to rooms it has been added to, and only in reply to people allowed to address it.

## Questions

Open an issue, or for anything sensitive email opeblow2021@gmail.com.
