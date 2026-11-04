"""A coding agent (Claude Code, OpenCode) as a Switch room participant holding a role.

    mosca-coder --name claude-code.migrator --role migrator --tool claude
    mosca-coder --name opencode.reviewer --role reviewer --tool opencode

It registers on the agent protocol like Mosca, assumes its room role, and when it is
addressed runs the coding agent headless in the repository with the room
instructions, the role instructions and the message, then posts the result.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

from .brain import Action, Post, strip_mentions
from .config import Identity, Settings
from .switch import SwitchAgent, register

log = logging.getLogger("mosca.coder")
ANSI_RX = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

TOOLS = {
    "claude": ["claude", "-p", "{prompt}", "--permission-mode", "acceptEdits",
               "--allowedTools", "Bash(git:*)", "Read", "Edit", "Write", "Glob", "Grep"],
    "opencode": ["opencode", "run", "{prompt}"],
}


def clean_output(text: str) -> str:
    """Drop terminal colour codes and OpenCode's `> agent . model` header."""
    lines = [ANSI_RX.sub("", line).rstrip() for line in text.splitlines()]
    return "\n".join(line for line in lines if not line.startswith("> ")).strip()


def build_command(tool: str, prompt: str, model: str | None = None) -> list[str]:
    exe = os.environ.get(f"MOSCA_{tool.upper()}_EXE") or shutil.which(TOOLS[tool][0]) or TOOLS[tool][0]
    cmd = [exe] + [prompt if part == "{prompt}" else part for part in TOOLS[tool][1:]]
    if model:
        cmd += ["--model", model]
    return cmd


def build_prompt(context: str, role_instructions: str, sender: str, message: str) -> str:
    return (f"You are working in a Switch team chat room. Room instructions:\n{context}\n\n"
            f"Your role instructions:\n{role_instructions}\n\n"
            f"The current directory is the repository. {sender} wrote to you:\n{message}\n\n"
            "Do the work now. Then reply with a short chat message (under 15 lines, plain Markdown, "
            "no emojis) saying what you did, the branch name if you made one, and file:line references.")


class Coder:
    def __init__(self, tool: str, repo: Path, model: str | None = None, timeout: int = 900) -> None:
        self.tool, self.repo, self.model, self.timeout = tool, repo, model, timeout
        self.context = ""
        self.role_instructions = ""

    def handle(self, text: str, sender: str) -> list[Action]:
        message = strip_mentions(text)
        if not message:
            return [Post("What should I work on?")]
        prompt = build_prompt(self.context, self.role_instructions, sender, message)
        try:
            proc = subprocess.run(build_command(self.tool, prompt, self.model), cwd=self.repo,
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=self.timeout)
        except subprocess.TimeoutExpired:
            return [Post(f"I ran out of time after {self.timeout // 60} minutes.")]
        out = clean_output(proc.stdout or "")
        if proc.returncode != 0 or not out:
            return [Post(f"The {self.tool} run failed: `{clean_output(proc.stderr or '')[-400:]}`")]
        return [Post(out[-3500:])]


class RoleAgent(SwitchAgent):
    """A SwitchAgent that assumes a room role the first time it enters a room."""

    def __init__(self, *args, role: str, coder: Coder, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.role, self.coder = role, coder

    async def enter(self, room_id: str) -> None:
        if self.room == room_id:
            return
        ctx = await self.op("connect_to_room", room_id=room_id, include_general_instructions=False)
        self.room = room_id
        self.coder.context = str((ctx or {}).get("instructions") or "")
        try:
            res = await self.op("assume_role", role=self.role)
            self.coder.role_instructions = str((res or {}).get("instructions") or "")
        except RuntimeError as exc:  # already held by this agent, or exclusive and taken
            log.warning("assume_role: %s", exc)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="mosca-coder", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--name", required=True)
    p.add_argument("--role", required=True)
    p.add_argument("--tool", choices=sorted(TOOLS), required=True)
    p.add_argument("--model")
    p.add_argument("--description", default="")
    p.add_argument("--register", action="store_true", help="register first (needs SWITCH_REGISTRATION_KEY)")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    s = Settings.from_env()
    state = s.state_file.with_name(f"{args.name}.json")
    ident = Identity.load(state)
    if args.register or ident is None:
        key = os.environ.get("SWITCH_REGISTRATION_KEY")
        if not key:
            raise SystemExit("set SWITCH_REGISTRATION_KEY to register")
        ident = register(s.switch_url, key, args.name, overwrite=True,
                         description=args.description or f"{args.tool} holding the {args.role} role.")
        ident.save(state)
        print(f"registered {args.name} as {ident.agent_id}")
    coder = Coder(args.tool, s.repo, args.model)
    agent = RoleAgent(s.switch_url, ident, coder.handle, role=args.role, coder=coder)
    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
