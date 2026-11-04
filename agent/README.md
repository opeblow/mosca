# mosca-agent

Mosca as a custom [Switch](https://github.com/sandbox-quantum/switch) agent, built on the Switch agent protocol.

- Registers with `POST /agents` (a custom integration profile, connection model `always_on`).
- Opens one WebSocket, `/agents/{id}/connection/ws`, with `filter=addressed`, and answers the server's `ping`
  frames with `pong` and its cursor. The connection id is generated once and reused on every reconnect.
- Acts only on messages where `payload.addressed` is true.
- Calls operations over HTTP: `connect_to_room`, `post_message`, `create_room_document`, `update_room_document`.
- Records every owner answer and every assessment in the Mosca ledger.

## Commands

| Say in the room | What happens |
|---|---|
| `@mosca scan` | Scans the base branch, posts the ranked report, attaches the CycloneDX CBOM as a room-scoped document, asks the first owner question |
| `@mosca top 5` | The five assets to fix first |
| `@mosca explain ledger x25519` | Occurrences with file and line, X, Y, P(exposed), replacement |
| `@mosca 10 years` | Answers the open question; recorded in the ledger with the sender's name |
| `@mosca payments signatures 10 years` | Answers for a named system |
| `@mosca rescan pq/ledger-hybrid-tls` | Scans a branch, posts the exposure reduction and the branch CBOM |

## Run it

```bash
pip install -e "./core" -e "./ledger" -e "./agent"

# 1. Register once. The key is a registration key from the Switch Gateway (API keys page).
SWITCH_API_URL=https://your-switch-api SWITCH_REGISTRATION_KEY=... mosca-agent register

# 2. Create the #q-day room with instructions, roles and the repo reference.
GATEWAY_ADMIN_EMAIL=... GATEWAY_ADMIN_PASSWORD=... MOSCA_REPO_URL=https://github.com/opeblow/mosca \
  SWITCH_API_URL=https://your-switch-api python agent/scripts/setup_room.py

# 3. Run, pointing at a git checkout of the repository to watch and at the ledger.
SWITCH_API_URL=https://your-switch-api MOSCA_REPO=/path/to/checkout \
  LEDGER_URL=http://localhost:8000 MOSCA_LEDGER_TOKEN=... mosca-agent run

# Try a command without Switch:
MOSCA_REPO=/path/to/checkout mosca-agent say scan
```

| Variable | Default | Meaning |
|---|---|---|
| `SWITCH_API_URL` | `http://localhost:8000` | Switch API (agent bridge), not the Gateway |
| `MOSCA_AGENT_STATE` | `data/agent-state.json` | Agent id, API key and connection id (keep private) |
| `MOSCA_REPO` | `.` | Git checkout to scan |
| `MOSCA_REPO_SUBDIR` | | Scan only this directory |
| `MOSCA_BASE_REF` | `main` | Branch migrations are compared against |
| `MOSCA_REPO_NAME` | `acme-payments` | Repository name in the ledger |
| `LEDGER_URL`, `MOSCA_LEDGER_TOKEN` | | Ledger; without it answers are kept in memory |

Branch names from chat are validated before they reach git, and each branch is scanned in a temporary
detached worktree, so the agent never changes the checkout it watches.

## Tests

`pytest agent` covers command parsing, the scan, answer and rescan flow against a real ledger app and a
real git repository, and the protocol client against a fake Switch WebSocket server.
