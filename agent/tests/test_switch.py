"""The protocol client against a fake Switch: a WebSocket for events, a mock transport for operations."""

import asyncio
import json

import httpx
import websockets

from mosca_agent.brain import Document, Post
from mosca_agent.config import Identity
from mosca_agent.switch import PROFILE, SwitchAgent, register


def test_register_posts_profile():
    seen = {}

    def handle(req: httpx.Request) -> httpx.Response:
        seen["auth"] = req.headers["authorization"]
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"id": "a1", "api_key": "k1"})

    ident = register("http://s", "regkey", client=httpx.Client(transport=httpx.MockTransport(handle)))
    assert (ident.agent_id, ident.api_key) == ("a1", "k1")
    assert seen["auth"] == "Bearer regkey"
    assert seen["body"]["name"] == "mosca" and seen["body"]["integration_profile"] == PROFILE


def test_runtime_answers_only_addressed_messages():
    calls: list[tuple[str, dict]] = []
    pongs: list[dict] = []
    handled: list[str] = []

    def ops(req: httpx.Request) -> httpx.Response:
        name = req.url.path.rsplit("/", 1)[-1]
        assert req.headers["x-switch-connection-id"] == "c1"
        calls.append((name, json.loads(req.content)))
        if name == "create_room_document":
            return httpx.Response(200, json={"result": {"id": "d1"}})
        return httpx.Response(200, json={"result": {}})

    def handler(text: str, sender: str):
        handled.append(f"{sender}:{text}")
        return [Document("CBOM", "d", "i", "{}"), Post("hello " + sender)]

    def msg(seq: int, body: str, addressed: bool) -> str:
        return json.dumps({"event": "message", "id": seq, "data": {
            "type": "message", "room_id": "r1", "sequence": seq,
            "payload": {"addressed": addressed, "body": body, "sender_name": "ana", "thread_id": None}}})

    async def server(ws):
        assert ws.request.headers["Authorization"] == "Bearer k1"
        assert "connection_id=c1" in ws.request.path and "filter=addressed" in ws.request.path
        await ws.send(json.dumps({"event": "connection_state", "data": {"rooms": ["r1"], "cursor": 0}}))
        await ws.send(msg(1, "chatter", False))
        await ws.send(msg(2, "@mosca scan", True))
        await ws.send(json.dumps({"event": "ping", "data": {}}))
        pongs.append(json.loads(await ws.recv()))
        for _ in range(100):
            if any(c[0] == "post_message" for c in calls):
                break
            await asyncio.sleep(0.02)
        await ws.send(json.dumps({"event": "evicted", "data": {"code": "taken_over"}}))

    async def main():
        async with websockets.serve(server, "127.0.0.1", 0) as srv:
            port = srv.sockets[0].getsockname()[1]
            agent = SwitchAgent(f"http://127.0.0.1:{port}", Identity("a1", "k1", "c1"), handler,
                                http=httpx.AsyncClient(transport=httpx.MockTransport(ops)))
            await asyncio.wait_for(agent.run(), 10)
            return agent

    agent = asyncio.run(main())
    assert handled == ["ana:@mosca scan"]
    assert pongs == [{"type": "pong", "cursor": 2}]
    names = [c[0] for c in calls]
    assert names == ["connect_to_room", "create_room_document", "post_message"]
    assert calls[0][1]["room_id"] == "r1"
    assert calls[2][1] == {"body": "hello ana"}
    assert agent.documents[("r1", "CBOM")] == "d1"
