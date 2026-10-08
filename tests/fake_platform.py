"""★★ **一个假平台**（★ 只跑在本机 ✓ —— ★ 它是**测试夹具** ✗，⛔ 不是产品 ✗）。

★ 为什么要有它（★ 契约 §九-2 ✓）：★ 判据是「**报能力 → 上行 → 对话 → 收 op → 回执**」
★ **端到端跑通** ✓ —— ★ 那就得有个"平台"能应答 ✓
★ 用它 ⇒ ★ **不用连真平台** ✓ · ★ **不会写他的库** ✗ · ★ 跑得快 ✓

★★ 它按 `协议-桥与平台（对外·v0）` 的**形状**应答 ✓ —— ★ 所以它也在**守着协议** ✓
★ 哪条协议变了、★ 这个假平台跟着改 ⇒ ★ 桥那边立刻会红 ✓
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse


class FakePlatform:
    """★ 记录桥打上来的每一样东西（★ 测试就拿它断言 ✓）"""

    def __init__(self, *, token: str = "fake-token", chat_reply: str = "嗯，我在。",
                 outbox: list[dict[str, Any]] | None = None) -> None:
        self.token = token
        self.chat_reply = chat_reply
        self.outbox = list(outbox or [])
        # ★ 每条记成 `(请求体, 判为新的条数, 判为重复的条数)` ✗ ——
        #   ⚠️ 光记请求体不够：★ "幂等有没有生效"要看**平台怎么判的** ✓
        #   （★ 我第一版就栽在这儿：★ 读了请求体的 `accepted` ⇒ 永远是 None ✓）
        self.received_events: list[tuple[dict[str, Any], int, int]] = []
        self.acks: list[dict[str, Any]] = []
        self.capabilities: list[dict[str, Any]] = []
        self.state_hits: list[dict[str, str]] = []
        self.login_hits = 0
        # ★ 幂等：★ 平台按 `local_id` 查重 ✓（★ 协议 §四 那条"确定性 id 查重" ✓）
        self._seen_ids: set[str] = set()
        self._srv: ThreadingHTTPServer | None = None
        self._t: threading.Thread | None = None
        self.port = 0

    # ── 起停 ───────────────────────────────────────────────────────
    def start(self) -> "FakePlatform":
        outer = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):        # ★ 别把测试日志刷满 ✓
                pass

            def _send(self, code: int, obj: Any) -> None:
                body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _body(self) -> dict[str, Any]:
                n = int(self.headers.get("Content-Length") or 0)
                if not n:
                    return {}
                try:
                    return json.loads(self.rfile.read(n).decode("utf-8"))
                except Exception:
                    return {}

            def _authed(self) -> bool:
                # ⚠️ 这个方法是**处理器自己**的（★ 不是 `FakePlatform` 的 ✗）——
                #   ★ 我第一版写成 `self._authed()` ⇒ 一路 AttributeError ✓
                h = str(self.headers.get("Authorization") or "")
                return h == "Bearer " + outer.token

            def do_GET(self):                                   # noqa: N802
                u = urlparse(self.path)
                if u.path == "/api/local/state":
                    if not self._authed():
                        return self._send(401, {"ok": False, "error": "请先登录"})
                    outer.state_hits.append(parse_qs(u.query))
                    return self._send(200, {
                        "ok": True,
                        "state": {"character_id": "demo-card", "character_name": "她",
                                  "awareness": "awake", "role_epoch": 1791449000.0},
                        # ★ 增量：★ 她新说的话（★ 测试要验"按 id 去重" ✓）
                        "replies": [{"id": "r-1", "content": "你回来啦", "emotion": "柔软",
                                     "role_ts": 1791449000.0, "proactive": True},
                                    {"id": "r-1", "content": "你回来啦", "emotion": "柔软",
                                     "role_ts": 1791449000.0, "proactive": True}],
                        "cursor": 1791449000.0})
                if u.path == "/api/bridge/outbox/pending":
                    if not self._authed():
                        return self._send(401, {"ok": False, "error": "请先登录"})
                    return self._send(200, {"ok": True, "items": outer.outbox})
                if u.path == "/v1/models":
                    if not self._authed():
                        return self._send(401, {"ok": False, "error": "请先登录"})
                    return self._send(200, {"object": "list", "data": [
                        {"id": "xihuyue:demo:demo-card", "object": "model"}]})
                return self._send(404, {"ok": False, "error": "没有这条路"})

            def do_POST(self):                                  # noqa: N802
                u = urlparse(self.path)
                b = self._body()
                if u.path in ("/api/login", "/api/auth/login"):
                    outer.login_hits += 1
                    if str(b.get("username")) and str(b.get("password")):
                        return self._send(200, {"ok": True, "token": outer.token})
                    return self._send(401, {"ok": False, "error": "账号不对"})
                if u.path == "/api/bridge/capabilities":
                    if not self._authed():
                        return self._send(401, {"ok": False, "error": "请先登录"})
                    outer.capabilities.append(b)
                    return self._send(200, {"ok": True})
                if u.path == "/api/demo/events":
                    if not self._authed():
                        return self._send(401, {"ok": False, "error": "请先登录"})
                    fresh, dup = 0, 0
                    for e in (b.get("events") or []):
                        lid = str(e.get("local_id") or "")
                        if lid in outer._seen_ids:
                            dup += 1
                        else:
                            outer._seen_ids.add(lid)
                            fresh += 1
                    outer.received_events.append((b, fresh, dup))
                    # ★★ 幂等：★ 收下了、★ 但重复的不算新的 ✓
                    return self._send(200, {"ok": True, "accepted": fresh, "duplicate": dup})
                if u.path == "/api/bridge/outbox/ack":
                    if not self._authed():
                        return self._send(401, {"ok": False, "error": "请先登录"})
                    outer.acks.append(b)
                    return self._send(200, {"ok": True})
                if u.path == "/v1/chat/completions":
                    if not self._authed():
                        return self._send(401, {"ok": False, "error": "请先登录"})
                    return self._send(200, {
                        "id": "chatcmpl-xhy-fake", "object": "chat.completion",
                        "created": 1791449000, "model": str(b.get("model") or ""),
                        "choices": [{"index": 0, "finish_reason": "stop",
                                     "message": {"role": "assistant",
                                                 "content": outer.chat_reply}}],
                        "usage": {"prompt_tokens": 0, "completion_tokens": 0,
                                  "total_tokens": 0},
                        "xihuyue": {"emotion": "柔软", "source": "demo",
                                    "card_id": "demo-card"}})
                return self._send(404, {"ok": False, "error": "没有这条路"})

        self._srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = int(self._srv.server_address[1])
        self._t = threading.Thread(target=self._srv.serve_forever, daemon=True)
        self._t.start()
        return self

    @property
    def base(self) -> str:
        return "http://127.0.0.1:%d" % self.port

    def stop(self) -> None:
        if self._srv is not None:
            self._srv.shutdown()
            self._srv.server_close()
        if self._t is not None:
            self._t.join(timeout=3)
