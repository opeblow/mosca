"""Switch agent protocol client: registration, operations, and the WebSocket connection.

Events come down one WebSocket (`/agents/{id}/connection/ws`); the server sends `ping`
frames and the client answers `pong` with its cursor, which counts as the heartbeat.
Everything the agent does is an HTTP operation (`POST /agents/{id}/ops/{name}`).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

import httpx
import websockets

from . import __version__
from .brain import Action, Document, Post
from .config import Identity

log = logging.getLogger("mosca.agent")

PROFILE = {
    "connection_model": "always_on",
    "message_exchange": True,
    "pre_invocation_mediation": [],
    "post_invocation_mediation": [],
    "event_reporting": [],
}

DESCRIPTION = ("Finds every cryptographic algorithm in the repository, ranks it by quantum exposure "
               "with Mosca's inequality, asks owners how long their data must stay secret, and rescans "
               "migration branches. Say @mosca help.")


def register(base_url: str, registration_key: str, name: str = "mosca",
             overwrite: bool = False, client: httpx.Client | None = None,
             description: str = DESCRIPTION, display_name: str | None = None) -> Identity:
    """POST /agents with a registration key. The API key is returned once."""
    c = client or httpx.Client(timeout=30)
    r = c.post(f"{base_url}/agents", headers={"Authorization": f"Bearer {registration_key}"}, json={
        "name": name, "display_name": display_name or ("Mosca" if name == "mosca" else name),
        "description": description,
        "connector_type": "custom", "integration_profile": PROFILE, "overwrite": overwrite,
    })
    if r.status_code >= 400:
        raise RuntimeError(f"registration failed: {r.status_code} {r.text[:300]}")
    data = r.json()
    return Identity(agent_id=data["id"], api_key=data["api_key"])


class SwitchAgent:
    def __init__(self, base_url: str, identity: Identity,
                 handler: Callable[[str, str], list[Action]],
                 http: httpx.AsyncClient | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.me = identity
        self.handler = handler
        self.http = http or httpx.AsyncClient(timeout=60)
        self.cursor: int | None = None
        self.room: str | None = None          # the room operations are currently bound to
        self.documents: dict[tuple[str, str], str] = {}  # (room, name) -> document id
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.stopped = False

    # ---- HTTP operations ----
    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.me.api_key}", "X-Switch-Connection-Id": self.me.connection_id}

    async def op(self, operation: str, **args: Any) -> Any:
        r = await self.http.post(f"{self.base_url}/agents/{self.me.agent_id}/ops/{operation}",
                                 headers=self._headers, json=args)
        if r.status_code >= 400:
            raise RuntimeError(f"{operation} failed: {r.status_code} {r.text[:300]}")
        return r.json().get("result")

    async def enter(self, room_id: str) -> None:
        if self.room == room_id:
            return
        ctx = await self.op("connect_to_room", room_id=room_id, include_general_instructions=False)
        self.room = room_id
        for doc in (ctx or {}).get("documents", []) or []:
            if isinstance(doc, dict) and doc.get("name") and doc.get("id"):
                self.documents.setdefault((room_id, doc["name"]), doc["id"])

    async def perform(self, room_id: str, thread_id: str | None, actions: list[Action]) -> None:
        await self.enter(room_id)
        for action in actions:
            if isinstance(action, Post):
                args: dict[str, Any] = {"body": action.body}
                if thread_id:
                    args["thread_id"] = thread_id
                await self.op("post_message", **args)
            elif isinstance(action, Document):
                fields = {"name": action.name, "description": action.description,
                          "instructions": action.instructions, "content": action.content}
                doc_id = self.documents.get((room_id, action.name))
                if doc_id:
                    try:
                        await self.op("update_room_document", document_id=doc_id, **fields)
                        continue
                    except RuntimeError as exc:
                        log.warning("update failed, creating instead: %s", exc)
                res = await self.op("create_room_document", **fields)
                if isinstance(res, dict) and (res.get("id") or res.get("document_id")):
                    self.documents[(room_id, action.name)] = res.get("id") or res["document_id"]

    # ---- events ----
    def ws_url(self) -> str:
        scheme = "wss" if self.base_url.startswith("https") else "ws"
        host = self.base_url.split("://", 1)[1]
        q = {"connection_id": self.me.connection_id, "scope": "all", "filter": "addressed",
             "client": "mosca-agent", "client_version": __version__}
        if self.cursor is not None:
            q["start_from"] = str(self.cursor)
        return f"{scheme}://{host}/agents/{self.me.agent_id}/connection/ws?{urlencode(q)}"

    async def on_frame(self, ws: Any, frame: dict[str, Any]) -> None:
        event, data = frame.get("event"), frame.get("data") or {}
        if event == "ping":
            await ws.send(json.dumps({"type": "pong", "cursor": self.cursor or 0}))
            return
        seq = data.get("sequence") if isinstance(data, dict) else None
        if isinstance(seq, int):
            self.cursor = max(self.cursor or 0, seq)
        if event == "connection_state":
            log.info("connected: rooms=%s", data.get("rooms"))
            if isinstance(data.get("cursor"), int):
                self.cursor = data["cursor"]
        elif event == "refused":
            raise ConnectionRefusedError(str(data))
        elif event == "evicted":
            log.warning("evicted: %s", data)
            if data.get("code") == "taken_over":
                self.stopped = True
            raise ConnectionResetError(str(data))
        elif event == "message":
            payload = data.get("payload") or {}
            if payload.get("addressed") is True:  # reply only when addressed
                await self.queue.put(data)

    async def worker(self) -> None:
        while True:
            event = await self.queue.get()
            payload = event.get("payload") or {}
            room_id = event["room_id"]
            sender = payload.get("sender_name") or payload.get("sender") or "someone"
            try:
                actions = await asyncio.to_thread(self.handler, payload.get("body") or "", sender)
                await self.perform(room_id, payload.get("thread_id"), actions)
            except Exception as exc:  # one bad message never stops the agent
                log.exception("handling failed")
                try:
                    await self.perform(room_id, payload.get("thread_id"),
                                       [Post(f"Something went wrong: `{str(exc)[:200]}`")])
                except Exception:
                    log.exception("could not report the failure")
            finally:
                self.queue.task_done()

    async def listen_once(self) -> None:
        headers = {"Authorization": f"Bearer {self.me.api_key}"}
        async with websockets.connect(self.ws_url(), additional_headers=headers,
                                      ping_interval=20, max_size=8 * 1024 * 1024) as ws:
            async for raw in ws:
                await self.on_frame(ws, json.loads(raw))

    async def run(self) -> None:
        worker = asyncio.create_task(self.worker())
        delay = 1.0
        try:
            while not self.stopped:
                try:
                    await self.listen_once()
                    delay = 1.0
                except (OSError, websockets.WebSocketException, ConnectionError) as exc:
                    if self.stopped:
                        break
                    log.warning("connection lost (%s); reconnecting in %.0fs", exc, delay)
                    self.room = None
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 30.0)
        finally:
            worker.cancel()
