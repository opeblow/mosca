# Security policy

Mosca is a security tool, so a vulnerability in Mosca can mislead the teams who rely on it. We treat reports with priority.

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x (latest) | Yes |
| Older | No |

## Reporting a vulnerability

**Do not open a public issue.** Report privately through GitHub:

1. Go to the repository's **Security** tab.
2. Choose **Report a vulnerability**.
3. Describe the issue, the affected component (`core`, `ledger` or `web`), steps to reproduce, and the impact you expect.

If you cannot use GitHub, email opeblow2021@gmail.com with the subject line "Mosca security".

What happens next:

- We acknowledge your report within **3 working days**.
- We give you an initial assessment within **10 working days**.
- We agree a disclosure date with you. Our default is 90 days, or sooner once a fix is released.
- We credit you in the release notes unless you ask us not to.

## What counts

In scope:

- Code execution, path traversal or resource exhaustion triggered by scanning a crafted repository
- Authentication or authorisation bypass in the ledger API
- Injection or cross-site scripting in the website or ledger dashboard
- **False negatives that hide quantum-vulnerable cryptography** in a supported language or format, where the miss comes from a flaw in Mosca rather than an unsupported pattern
- Leaks of key material or secrets into reports, logs or the ledger

Out of scope:

- Patterns or languages that Mosca does not claim to support (please open a regular issue)
- Disagreement with the default threat prior, which is configurable by design
- Findings that require a compromised host or a malicious administrator
- Denial of service against a ledger that you run without authentication in front of it

## Design commitments

- The scanner never executes scanned code.
- The scanner makes no network requests unless you pass `--push` or a ledger `--answers` URL.
- Private keys found in a repository are reported by type, size and location only. Key material is never copied into a report.
- Ledger writes require a bearer token, compared in constant time.
