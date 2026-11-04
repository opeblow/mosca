"""Create the #q-day room on a Switch server: instructions, roles, Mosca, and the repo reference.

    SWITCH_API_URL=... GATEWAY_ADMIN_EMAIL=... GATEWAY_ADMIN_PASSWORD=... \
    MOSCA_REPO_URL=https://github.com/opeblow/mosca python agent/scripts/setup_room.py

Idempotent enough for a demo: an existing room called q-day is reused.
"""

from __future__ import annotations

import json
import os
import sys

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from mosca_agent.config import Identity, Settings  # noqa: E402

ROOM = "q-day"

INSTRUCTIONS = """This room migrates our cryptography to post-quantum algorithms before quantum computers can break it.

How we work here:
1. @mosca scans the repository and posts the ranked exposure report. Its CBOM is attached to this room as a document.
2. Mosca asks each system owner one question: how many years their data must stay secret, or their signatures must stay trusted. Only the owner can answer. Answers are recorded in the Mosca ledger with the name of the person who gave them.
3. The security lead picks the asset to fix and hands it to @migrator.
4. @migrator opens a branch with a hybrid post-quantum change (for example X25519MLKEM768 key exchange) and posts the branch name.
5. @reviewer reviews the branch. The security lead approves or rejects it in this room. Nothing merges without a person approving it here.
6. @mosca rescan <branch> measures how much exposure the branch removes.

Rules: never paste private keys or secrets in this room. Prefer hybrid algorithms (classical plus post-quantum) during the transition. Cite file and line for every claim."""

ROLES = [
    {"name": "migrator", "exclusive": True, "instructions": (
        "You are the migrator. Exactly one agent holds this role at a time. Take the asset the security lead "
        "assigns, read its occurrences with `@mosca explain <asset>`, and make the smallest change that moves it "
        "to a hybrid or post-quantum algorithm: X25519MLKEM768 for TLS key exchange, ML-KEM (FIPS 203) for key "
        "encapsulation, ML-DSA (FIPS 204) for signatures. Work on a branch named pq/<system>-<change>, keep "
        "classical fallback where clients need it, and post the branch name and a short summary here. "
        "Do not merge.")},
    {"name": "reviewer", "exclusive": False, "instructions": (
        "You are a reviewer. Any number of agents can review. Review the migrator's branch for correctness, "
        "interoperability (will old clients still connect?), and whether the algorithm names and parameters match "
        "the NIST standards. Ask @mosca to rescan the branch. Post approve or request-changes with file and line "
        "references. A person makes the final call.")},
]


def main() -> int:
    s = Settings.from_env()
    ident = Identity.load(s.state_file)
    if ident is None:
        raise SystemExit("register Mosca first: mosca-agent register")
    gw = httpx.Client(base_url=f"{s.switch_url}/gateway", timeout=60)
    r = gw.post("/auth/login", json={"email": os.environ["GATEWAY_ADMIN_EMAIL"],
                                     "password": os.environ["GATEWAY_ADMIN_PASSWORD"]})
    r.raise_for_status()
    # Sent explicitly: the cookie is marked Secure and the API may be reached over plain http.
    gw.headers["Cookie"] = f"switch_auth={r.cookies['switch_auth']}"

    rooms = gw.get("/rooms").json()
    rooms = rooms.get("rooms", rooms) if isinstance(rooms, dict) else rooms
    room = next((x for x in rooms if x.get("name") == ROOM), None)
    if room is None:
        r = gw.post("/rooms", json={
            "name": ROOM, "description": "Post-quantum migration: find, rank, fix, verify.",
            "instructions": INSTRUCTIONS, "agent_ids": [ident.agent_id], "roles": ROLES,
            "user_names": [os.environ.get("MATTERMOST_USER", "user")],
        })
        if r.status_code >= 400:
            raise SystemExit(f"room create failed: {r.status_code} {r.text[:500]}")
        room = r.json()
        print(f"created room {ROOM}: {room['id']}")
    else:
        print(f"reusing room {ROOM}: {room['id']}")
    room_id = room.get("id") or room.get("room_id")

    repo_url = os.environ.get("MOSCA_REPO_URL")
    if repo_url:
        ops = httpx.Client(base_url=f"{s.switch_url}/agents/{ident.agent_id}/ops", timeout=60, headers={
            "Authorization": f"Bearer {ident.api_key}"})
        types = ops.post("/list_reference_types", json={}).json().get("result")
        print("reference types:", json.dumps(types)[:300])
        ref = ops.post("/create_reference", json={
            "type": "github", "name": "Repository under migration",
            "description": "The code Mosca scans and the migrator changes.",
            "instructions": "Branches named pq/* are migration branches. Ask @mosca rescan <branch> to measure one.",
            "value": {"urls": [repo_url]}, "read_visibility": "public", "write_visibility": "private"})
        print("create_reference:", ref.status_code, ref.text[:300])
        if ref.is_success:
            rid = ref.json()["result"].get("id")
            att = ops.post("/attach_reference_to_room", json={"room_id": room_id, "reference_id": rid})
            print("attach:", att.status_code, att.text[:200])
    print(json.dumps({"room_id": room_id}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
