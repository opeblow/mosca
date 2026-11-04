"""mosca-agent register | run | say."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from .brain import Document, Mosca, Post
from .config import Identity, Settings
from .ledger import AnswerStore, LedgerStore, MemoryStore
from .switch import SwitchAgent, register
from .workspace import Workspace


def build_brain(s: Settings) -> Mosca:
    store: AnswerStore = (LedgerStore.connect(s.ledger_url, s.repo_name, s.ledger_token)
                          if s.ledger_url else MemoryStore())
    return Mosca(Workspace(s.repo, s.subdir, s.base_ref), store, s.repo_name)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="mosca-agent", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("register", help="register Mosca on a Switch server (needs SWITCH_REGISTRATION_KEY)")
    r.add_argument("--name", default="mosca")
    r.add_argument("--overwrite", action="store_true")
    sub.add_parser("run", help="connect to Switch and answer in rooms")
    say = sub.add_parser("say", help="run one command locally, without Switch")
    say.add_argument("text", nargs="+")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    s = Settings.from_env()

    if args.cmd == "register":
        key = os.environ.get("SWITCH_REGISTRATION_KEY")
        if not key:
            raise SystemExit("set SWITCH_REGISTRATION_KEY")
        ident = register(s.switch_url, key, args.name, args.overwrite)
        ident.save(s.state_file)
        print(f"registered {args.name} as {ident.agent_id}; identity saved to {s.state_file}")
        return 0

    brain = build_brain(s)
    if args.cmd == "say":
        for action in brain.handle(" ".join(args.text), "cli"):
            if isinstance(action, Post):
                print(action.body + "\n")
            elif isinstance(action, Document):
                print(f"[room document] {action.name}: {action.description}\n")
        return 0

    ident = Identity.load(s.state_file)
    if ident is None:
        raise SystemExit(f"no identity at {s.state_file}; run `mosca-agent register` first")
    try:
        asyncio.run(SwitchAgent(s.switch_url, ident, brain.handle).run())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
