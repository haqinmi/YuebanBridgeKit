"""★★ **一个假世界**：★ 不接任何真游戏 ✓ —— 只为证明"这条环能跑" ✗。

★ 契约 §九-2：★ **骨架五块 + 一个假世界** ⇒ ★ 判据是
「**报能力 → 上行 → 对话 → 收 op → 回执**」★ **端到端跑通** ✓

★ 它**故意做得很小**（★ 100 行不到 ✓）—— ★ 它是**示范**，⛔ 不是产品 ✗
★ 但它**把三件容易做错的做对了** ✓：
  1. ★★ `local_id` **稳定**（★ 用 `tick` 编号 ✗ —— ⛔ 不用"当前时间" ✗）
  2. ★★ `poll()` **只返回新的**（★ 靠 `self._i` 游标 ✓ —— ⛔ 不返回"从头全部" ✗）
  3. ★★ **`poll()` 只给结论**（★ 一句描述 / 一个标签 ✓ —— ⛔ 不给原始日志 ✗）
"""

from __future__ import annotations

import time
from typing import Any

from ..world import BaseWorld, Event, Op, OpResult

# ★ 这个假世界会做的事（★ 就三样 ✓）
SCRIPT = (
    ("speak", {"text": "我回来了"}),
    ("signal", {"tag": "chopped_wood", "n": 3}),
    ("speak", {"text": "我想喝粥"}),
    ("state", {"key": "here", "value": False}),
    ("speak", {"text": "歇会儿吧"}),
    ("signal", {"tag": "rested", "n": 1}),
)


class DemoWorld(BaseWorld):
    """★ 一个假世界：★ "他"每隔几秒说一句，★ 世界记一笔 ✓

    ★ 接真世界时**照它的形状写** ⇒ ★ 你会知道"哪些是骨架的事、哪些是我的事" ✓
    """

    name = "demo"

    def __init__(self, *, tick_seconds: float = 2.0) -> None:
        self.tick_seconds = float(tick_seconds)
        self.started = time.time()
        self._i = 0                       # ★★ 游标：★ 已经报过几条 ✗
        self._tick = 0                    # ★ 生成的次数（★ 拿它编 local_id ✓）
        self.applied: list[str] = []      # ★ 记录执行过的 op（★ 自检用 ✓）
        self.last_error = ""

    # ── ① 我此刻能做什么 ──────────────────────────────────────────
    def capabilities(self) -> dict[str, Any]:
        return {
            # ★ 如实报 ✗ —— ★ 报了她能做的就必须能做 ✓
            "say": True,
            "emote": ["soft", "shy", "sleepy"],
            "read": ["chat", "inventory"],
            "act": ["wave", "sit", "chop"],
            # ★ 这个假世界**不报**生图 ⇒ ★ 她就不该说"我画给你看" ✓
            "draw": False,
        }

    # ── ② 那个世界发生了什么（★ 只传结论 ✗）──────────────────────
    def poll(self) -> list[Event]:
        """★ 只返回**新的**结论 ✓ —— ★ 这就是"重发幂等"的地基 ✗

        ⚠️ 三条**故意做对**的：
        · ★ 没有新的 ⇒ ★ 返回**空表** ✓（⛔ 不返回"从头全部" ✗）
        · ★ `local_id` = `demo:<生成次数>` ✓ ⇒ ★ **重发时还是那个 id** ✓
        · ★ `data` 里**只有结论** ✓（★ 一句话 / 一个标签 ✓ —— ⛔ 没有原始日志 ✗）
        """
        now = time.time()
        due = int((now - self.started) / self.tick_seconds)
        out: list[Event] = []
        while self._tick < min(due, len(SCRIPT) * 3):
            kind, data = SCRIPT[self._tick % len(SCRIPT)]
            self._tick += 1
            out.append(Event(kind=kind, local_id="demo:%d" % self._tick,
                             data=dict(data), at=now))
        self._i += len(out)
        return out

    # ── ③ 执行一条 op（★ 做不了也要回执 ✓）────────────────────────
    def apply(self, op: Op) -> OpResult:
        self.applied.append(op.type)
        if op.type in ("say", "wave", "sit", "chop"):
            return OpResult(id=op.id, ok=True, note="假世界说：做完了")
        if op.type == "draw":
            # ★★ 做不到的**要如实说** ✗ —— ★ 那正是"让她自己知道"那条 ✓
            return OpResult(id=op.id, ok=False, note="这个假世界没有生图能力")
        return OpResult(id=op.id, ok=False, note="不认识这个 op：%s" % op.type)

    # ── 给测试/自检用的一个便利 ───────────────────────────────────
    def push(self, kind: str, data: dict[str, Any]) -> Event:
        """★ 手动塞一条（★ 测试用 ✓ —— ★ 真世界不需要它 ✓）"""
        self._tick += 1
        return Event(kind=kind, local_id="demo:%d" % self._tick, data=dict(data),
                     at=time.time())
