"""★ 与平台说话的那一层（★ 只用标准库 ⇒ ★ **零依赖** ✓）。

★ 为什么零依赖（★ 刻意的 ✗）：★ 桥是"**给别人照着写**"的东西 ✓
⇒ ★ 别人 **clone 下来就能跑**，⛔ 不用先装 `pip install -r requirements.txt` ✗
（★ 收集账 §一「能不加依赖就不加」那条的同类 ✓）

⚠️ 边界（★ 契约 §零 ✓）：★★ 这一层**只管"跟平台说什么"** ✗ ——
★ **不许懂那个世界** ✓ · ★ **不许存记忆** ✗
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from . import protocol

log = logging.getLogger("yueban_bridge.gateway")

TIMEOUT = 20.0


class PlatformError(RuntimeError):
    """★ 平台那边回了个"不行"（★ 4xx ✓ —— ★ 别重试 ✗）"""

    def __init__(self, status: int, body: str) -> None:
        super().__init__("平台回了 %s：%s" % (status, str(body or "")[:200]))
        self.status = status
        self.body = body


class TransientError(RuntimeError):
    """★ 临时坏（★ 网络 · 5xx · 502 ✓）⇒ ★ **该重试** ✓（★ 队列会留着 ✓）"""


class Gateway:
    """★ 桥 → 平台的**唯一出口**（★ 一处定义 ✓）。"""

    def __init__(self, base: str, token: str = "", *, user: str = "",
                 password: str = "") -> None:
        self.base = str(base or "").rstrip("/")
        self.token = str(token or "")
        self.user = str(user or "")
        self.password = str(password or "")

    # ── 底层 ───────────────────────────────────────────────────────
    def _url(self, path: str) -> str:
        return protocol.join(self.base, path)

    def _req(self, method: str, path: str, *, body: dict[str, Any] | None = None,
             timeout: float = TIMEOUT) -> tuple[int, str]:
        data = None
        headers = {"Accept": "application/json", "User-Agent": "YuebanBridgeKit/0.1"}
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        req = urllib.request.Request(self._url(path), data=data, headers=headers,
                                     method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return int(r.status), r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            return int(e.code), e.read().decode("utf-8", errors="replace")
        except Exception as exc:                     # ★ 网络层的坏 ⇒ 临时
            raise TransientError("%s：%s" % (type(exc).__name__, exc))

    def _json(self, method: str, path: str, *, body: dict[str, Any] | None = None,
              allow: tuple[int, ...] = (200,), quiet_codes: tuple[int, ...] = ()) -> Any:
        code, text = self._req(method, path, body=body)
        if code in quiet_codes:                      # ★ 允许"平台还没有这个端点"✓
            return None
        if code in allow:
            try:
                return json.loads(text) if text.strip() else {}
            except Exception:
                return {}
        if 500 <= code or code in (408, 429):
            raise TransientError("平台回了 %s：%s" % (code, text[:160]))
        raise PlatformError(code, text)

    # ── 鉴权 ───────────────────────────────────────────────────────
    def login(self) -> bool:
        """★ 拿一枚令牌（★ 现状：★ 只有**账号 JWT** ✗ —— ★ 协议 §二 ✓）

        ⚠️⚠️ 协议原文警告：★「**现在别把账号 JWT 交给第三方**」✓ ——
        ★ 那是**全权**：★ 能改设置、★ 能读别的世界 ✓
        ⇒ ★ 现阶段只适合**你自己**写桥自用 ✓
        ★★ 平台侧"每桥一把 key"做完之前，★ **"通用"这两个字不成立** ✗
        """
        for path, body in (("/api/login", {"username": self.user, "password": self.password}),
                           ("/api/auth/login", {"username": self.user,
                                                "password": self.password})):
            try:
                obj = self._json("POST", path, body=body, quiet_codes=(404, 405))
            except PlatformError:
                continue
            except TransientError:
                continue
            if isinstance(obj, dict):
                tok = (obj.get("token") or obj.get("access_token")
                       or (obj.get("data") or {}).get("token"))
                if tok:
                    self.token = str(tok)
                    log.info("拿到令牌了（%s ✓）", path)
                    return True
        log.warning("没拿到令牌（★ 检查账号密码 / 平台地址 ✓）")
        return False

    # ── ① 读口：她此刻是什么 + 她新说的话 ────────────────────────
    def state(self, *, since: float = 0.0, limit: int = 20,
              character_id: str = "") -> dict[str, Any]:
        """★ 拉模式（⛔ 平台不推送 ✗ —— 契约 §七-4 ✓）

        ⚠️ 协议 §3① 的坑（★ 实测过 ✓）：★★ **她的钟可能是停的** ⇒
          `role_epoch` 不变 ⇒ ★ **严格递增的游标永远追不上新话** ✗
        ★ 本骨架的办法（★ 与协议给的临时办法一致 ✓）：
          ★ **下次带回来的 `since` 往回退一点** + ★ **按 `id` 去重** ✓
        """
        from urllib.parse import urlencode
        q = {"limit": int(limit)}
        if since:
            q["since"] = "%.6f" % float(since)
        if character_id:
            q["character_id"] = character_id
        return self._json("GET", protocol.STATE_PATH + "?" + urlencode(q)) or {}

    # ── ② 对话（★ OpenAI 兼容 ✓）─────────────────────────────────
    def say(self, text: str, *, model: str, timeout: float = 60.0) -> dict[str, Any]:
        """★ 他说一句 → ★ 她回一句 ✓（协议 §3② ✓）

        ⚠️ 协议 §3② 第 1 条：★★ **平台只认最后一条 `user`** ✗ ——
        ★ 历史**会被忽略** ✓（★ 故意的：★ 两边都记 = 两个她 ✗）
        ★ 所以这里**只发一条** ✓ —— ⛔ 别自作聪明攒历史 ✗
        """
        code, raw = self._req("POST", protocol.CHAT_PATH,
                              body={"model": model,
                                    "messages": [{"role": "user", "content": str(text)}],
                                    "stream": False}, timeout=timeout)
        if code >= 500 or code in (408, 429):
            raise TransientError("对话回了 %s：%s" % (code, raw[:160]))
        if code != 200:
            raise PlatformError(code, raw)
        try:
            return json.loads(raw)
        except Exception:
            raise PlatformError(code, raw)

    # ── ③ 上行（★ 只传结论 ✓）───────────────────────────────────
    def post_events(self, path: str, payload: dict[str, Any]) -> Any:
        return self._json("POST", path, body=payload)

    # ── ④ 下行：拉 op + 回执 ─────────────────────────────────────
    def outbox_pending(self, path: str, *, limit: int = 20) -> list[dict[str, Any]]:
        obj = self._json("GET", "%s?limit=%d" % (path, int(limit)),
                         quiet_codes=(404, 405, 501))
        if obj is None:
            return []
        items = obj.get("items") if isinstance(obj, dict) else obj
        return [x for x in (items or []) if isinstance(x, dict)]

    def outbox_ack(self, path: str, op_id: str, *, ok: bool, note: str = "") -> Any:
        return self._json("POST", path,
                          body={"id": str(op_id), "ok": bool(ok), "note": str(note or "")},
                          quiet_codes=(404, 405, 501))

    # ── ⑤ 上线报能力 ────────────────────────────────────────────
    def report_capabilities(self, path: str, payload: dict[str, Any]) -> bool:
        """★ 报"我此刻能做什么" ✓

        ⚠️ 现状：★★ **平台还没有这个端点** ✗（★ 协议里没有 · ★ 那是要去做的一件 ✓）
        ⇒ ★ 打上去、★ **404 就安静记一条** ✓ —— ⛔ 不许因此崩 ✗
        """
        obj = self._json("POST", path, body=payload, quiet_codes=(404, 405, 501))
        if obj is None:
            log.info("平台还没有「报能力」那个端点（★ 正常 —— 它还没做 ✓）")
            return False
        return True
