"""★★ 五块的编排（★ 契约 §二 ✓）—— 骨架的**本体** ✓。

```
① 上线报能力 ──→ 平台（★ 让她知道她此刻能做什么 ✓）
② poll() ──→ 落队列（★ 先落库 ✗）──→ 送平台（★ 送成 ⇒ 删 ✓）
③ 拉 op ──→ world.apply() ──→ 回执（★ 每条都必须回 ✓）
④ 读口 ──→ 拉她新说的话（★ 游标 + 按 id 去重 ✓）
```

★ ⚠️ 一条**硬边界**（★ 契约 §零 ✓）：★★ 这里**不存记忆** ✗ ——
★ 队列只放"**还没送到的**" ✓ · ★ 送到即删 ✓ · ★ 不参与回忆 ✗
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from .config import Manifest
from .gateway import Gateway, PlatformError, TransientError
from .queue import EventQueue
from .world import Op, OpResult, World

log = logging.getLogger("yueban_bridge")

# ★★ 同一批最多带几条 ✗ —— ★ 平台那边有它自己的上限，这里只是"别一次塞爆" ✓
MAX_BATCH = 50


class Bridge:
    """★ 一个桥 = ★ 一份清单 + ★ 一个世界 + ★ 一条队列 + ★ 一个出口 ✓"""

    def __init__(self, manifest: Manifest, world: World, *,
                 gateway: Gateway | None = None,
                 queue: EventQueue | None = None) -> None:
        self.m = manifest
        self.world = world
        self.gw = gateway or Gateway(manifest.platform)
        self.q = queue or EventQueue(manifest.queue_path)
        self._stop = threading.Event()
        # ★ 她新说的话要**按 id 去重**（★ 协议 §3① 那条坑的解法 ✓）
        self._seen_reply_ids: set[str] = set()
        self._cursor = 0.0

    # ══ ① 上线报能力 ═══════════════════════════════════════════════
    def report_capabilities(self) -> bool:
        """★ "我此刻能做什么" ⇒ ★ 写进她的提示词，★ 她才不会"说自己做不到的事" ✓

        ★ 为什么这一步**排第一** ✗：《设计-本地端与服务器》§6 警告过 ——
        ★★ **本机不在时，生图/重模型直接消失，并且让她自己知道** ✓
        ★ 否则会出现「**她说她能画，但画不出来**」那种最伤沉浸的错 ✓
        """
        try:
            caps = self.world.capabilities() or {}
        except Exception as exc:
            log.warning("能力报不出来（★ 这一轮跳过 ✓）：%s", exc)
            return False
        payload = {
            "bridge": self.m.name,
            "world": self.m.world,
            "api_version": self.m.api_version,
            "source": self.m.source,
            "character_id": self.m.character_id,
            "capabilities": caps,
            "at": time.time(),
        }
        try:
            return self.gw.report_capabilities(self.m.capabilities_path, payload)
        except (TransientError, PlatformError) as exc:
            log.info("报能力没成（★ 不影响别的 ✓）：%s", exc)
            return False

    # ══ ② 上行：先落库，再送 ═══════════════════════════════════════
    def collect(self) -> int:
        """★ 拉世界的**新结论** ⇒ 落队列 ✓（★ 先落库 ✗ —— 契约 §七-6 ✓）"""
        try:
            events = self.world.poll() or []
        except Exception as exc:
            log.warning("poll 抛了（★ 这一轮跳过 ✓ · ★ 世界适配层的问题 ✗）：%s", exc)
            return 0
        n = 0
        for ev in events:
            try:
                if self.q.put(ev.local_id, ev.kind, {
                        "data": ev.data, "at": ev.at or time.time(),
                        "world": self.m.world}):
                    n += 1
            except Exception as exc:
                log.warning("有一条落不了队列（★ local_id=%s ✓）：%s",
                            getattr(ev, "local_id", "?"), exc)
        if n:
            log.info("落队列 %d 条（★ 队列里现在共 %d 条 ✓）", n, self.q.count())
        return n

    def flush(self) -> bool:
        """★ 把队列里的送出去（★ 送成 ⇒ 删 ✓ · ★ 没成 ⇒ 留着 + 计一次 ✓）"""
        items = self.q.peek(MAX_BATCH)
        if not items:
            return True
        event_path = self.m.events_path
        by_kind: dict[str, list[Any]] = {}
        for it in items:
            by_kind.setdefault(it.kind, []).append(it)
        all_ok = True
        for kind, group in by_kind.items():
            payload = {
                "world": self.m.world,
                "source": self.m.source,
                "bridge": self.m.name,
                # ★★ 每条都带**稳定的 `local_id`** ✗ ⇒ ★ 平台按它查重 ⇒ 重发幂等 ✓
                "events": [{"local_id": g.local_id, "kind": g.kind,
                            **(g.payload.get("data") or {}),
                            "at": g.payload.get("at")} for g in group],
            }
            try:
                self.gw.post_events(event_path, payload)
            except TransientError as exc:
                log.info("送不出去（★ 留着下次再送 ✓）：%s", exc)
                self.q.bump([g.seq for g in group])
                all_ok = False
                continue
            except PlatformError as exc:
                # ★ 4xx ⇒ ★ 平台**明确说不行** ✗ —— ★ 重试没用 ⇒ ★ 但**也不许悄悄丢** ✓
                log.warning("平台拒了这一批（★ %s ✓）⇒ 计一次、留着 ✗", exc)
                self.q.bump([g.seq for g in group])
                all_ok = False
                continue
            self.q.ack([g.seq for g in group])
        return all_ok

    # ══ ③ 下行：拉 op + 回执 ═══════════════════════════════════════
    def run_outbox(self) -> int:
        """★ 拉她想做的事 ⇒ 让世界执行 ⇒ ★ **每条都回执** ✗（契约 §七-5 ✓）"""
        try:
            pend = self.gw.outbox_pending(self.m.outbox_pending_path)
        except (TransientError, PlatformError) as exc:
            log.debug("outbox 拉不到（★ 可能平台还没这个端点 ✓）：%s", exc)
            return 0
        n = 0
        for raw in pend:
            op = Op(id=str(raw.get("id") or ""), type=str(raw.get("type") or ""),
                    payload=raw.get("payload") if isinstance(raw.get("payload"), dict)
                    else {})
            if not op.id:
                continue
            try:
                res = self.world.apply(op)
            except Exception as exc:
                # ★★ 做不了**也要回执** ✗ —— ★ 否则平台永远以为它没做完 ✓
                res = _fail(op.id, "%s: %s" % (type(exc).__name__, exc))
            try:
                self.gw.outbox_ack(self.m.outbox_ack_path, res.id, ok=res.ok,
                                   note=res.note)
                n += 1
            except (TransientError, PlatformError) as exc:
                # ★ 回执没送成 ⇒ ★ 下轮还会拉到同一条 ⇒ ★ 世界要能**重复执行不出事** ✓
                log.info("回执没送成（★ 下轮会再拉到同一条 ✓）：%s", exc)
        return n

    # ══ ④ 读口 ═════════════════════════════════════════════════════
    def pull_state(self) -> list[dict[str, Any]]:
        """★ 拉她新说的话 ⇒ ★ **按 id 去重** ✓（协议 §3① 那条坑的解法 ✓）"""
        try:
            obj = self.gw.state(since=self._cursor, character_id=self.m.character_id)
        except (TransientError, PlatformError) as exc:
            log.debug("读口拉不到：%s", exc)
            return []
        fresh: list[dict[str, Any]] = []
        for r in (obj.get("replies") or []):
            rid = str(r.get("id") or "")
            if rid and rid in self._seen_reply_ids:
                continue
            if rid:
                self._seen_reply_ids.add(rid)
            fresh.append(r)
        cur = obj.get("cursor")
        try:
            if cur:
                # ★★ 往回退一点点 ✗ —— ★ 她的钟可能是停的 ⇒ 严格递增会漏 ✓
                self._cursor = max(0.0, float(cur) - 0.001)
        except (TypeError, ValueError):
            pass
        return fresh

    # ══ 对话 ═══════════════════════════════════════════════════════
    def say(self, text: str) -> dict[str, Any]:
        """★ 他说一句 ⇒ ★ 她回一句 ✓（★ 表情/语气从扩展字段拿 ✓）"""
        return self.gw.say(text, model=self.m.model_id())

    # ══ 生命周期 ═══════════════════════════════════════════════════
    def start(self) -> None:
        """★ 起三个后台循环（★ 上行 / 下行 / 读口 ✓）—— ★ 一个线程一个 ✓"""
        self.report_capabilities()
        for name, fn, gap in (
                ("up", lambda: (self.collect(), self.flush()), self.m.poll_seconds),
                ("down", self.run_outbox, self.m.outbox_seconds),
                ("read", self.pull_state, self.m.state_seconds)):
            t = threading.Thread(target=self._loop, args=(name, fn, gap), daemon=True)
            t.start()
            log.info("起了 %s 循环（每 %.1f 秒 ✓）", name, gap)

    def _loop(self, name: str, fn, gap: float) -> None:
        while not self._stop.wait(max(0.5, float(gap))):
            try:
                fn()
            except Exception as exc:
                # ★ 一个循环坏掉**不许拖死别的** ✗（★ 上一版桥就是因为"平台一重启全断" ✓）
                log.warning("%s 循环这一步坏了（★ 下一跳继续 ✓）：%s", name, exc)

    def stop(self) -> None:
        self._stop.set()


def _fail(op_id: str, note: str) -> OpResult:
    """★ 做不了也要回执 ✓（★ 契约 §七-5 ✗）"""
    return OpResult(id=op_id, ok=False, note=note)
