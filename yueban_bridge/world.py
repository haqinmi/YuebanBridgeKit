"""★★ **世界适配层**：换一个世界，只改这一族（★ 契约 §四 ✓）。

★★ 这个文件就是"通用"的判据 ✗ ——
★ 接一个新世界 = ★ **写一份 `World` 的子类** ✓ · ★ 骨架其余部分**一个字都不动** ✓
★ 如果为了接一个世界要改到骨架别处 ⇒ ★ **那不叫通用** ✗（契约 §七-10 ✓）

## 钩子只有三个（★ 借 `pluggy` 那条：平台定钩子、实现只填钩子 ✓）
  1. `capabilities()` —— ★ 我此刻能做什么（★ 上线报给平台 ✓）
  2. `poll()`         —— ★ 读到什么新结论了（★ **只传结论** ✗）
  3. `apply(op)`      —— ★ 执行一条平台下发的 op，并回报结果 ✓

⚠️ 三条边界（都是硬的 ✓）：
· ★★ **`poll()` 只许返回"结论"** ✗ —— ⛔ 不许把原始流丢出来 ✓（契约 §七-2）
· ★★ **不许在这里碰平台** ✗ —— 平台由 `Bridge` 管；这里只跟**那个世界**打交道 ✓
· ★★ **不许存记忆** ✗ —— 世界适配层可以是无状态的；要不要缓存由骨架的队列管 ✓
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class Event:
    """★ 上行的**一条结论**（★ 不是原始日志 ✗）。

    ★ 三种形状（照平台已有的口径 ✓ —— 一句话 / 一个标签 / 一条事件 ✓）：
    | `kind` | 用在哪 | `data` 例 |
    |---|---|---|
    | `utterance` | ★ 那个世界里**说了一句话** | `{"text": "…", "who": "user"}` |
    | `state` | ★ **状态变了**（他离开了 / 他回来了）| `{"key": "here", "value": False}` |
    | `signal` | ★ **一个标签**（做完了什么 / 拿到了什么）| `{"tag": "chopped_wood", "n": 3}` |

    ★★ `local_id` 必须**稳定且唯一** ✗ —— ★ 平台按它查重 ✓
      ★ ⛔ 不许用"当前时间"当 id ✗（★ 重发时会变成新的一条 ⇒ 幂等就废了 ✓）
      ★ 做法：★ 世界里的那个顺序号 / 那行日志的偏移 / 一个内容指纹 ✓
    """

    kind: str
    local_id: str
    data: dict[str, Any] = field(default_factory=dict)
    at: float = 0.0                     # ★ 那条结论**在那个世界里**发生的时间


@dataclass
class Op:
    """★ 平台下发的**一条意图**（★ "她想做什么" ✓ —— 契约 §二-③ ✓）。"""

    id: str
    type: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class OpResult:
    """★ 一条 op 的**回执**（★ 契约 §七-5：★ 每条 op 必须回执 ✓）。"""

    id: str
    ok: bool
    note: str = ""


@runtime_checkable
class World(Protocol):
    """★★ 换世界就实现这一个（★ 契约 §四 ✓）。"""

    name: str               # ★ 世界的标识（★ 会进 `memories.source` ✓）

    def capabilities(self) -> dict[str, Any]:
        """★ 我此刻能做什么 ⇒ ★ 上线时报给平台，★ 写进她的提示词 ✓

        ★ 例：`{"say": True, "emote": ["soft", "shy"], "read": ["chat", "inventory"]}`
        ⚠️ **如实报** ✗ —— ★ 报了她能做的、就必须能做 ✓
          ★ 否则"她说她能画，但画不出来"（《设计-本地端与服务器》§6 警告过 ✓）
        """
        ...

    def poll(self) -> list[Event]:
        """★ 读**新的**结论（★ 没有就给空表 ✓ —— ⛔ 不许返回"从头全部" ✗）

        ★★ 这条最要紧 ✗：★ 契约 §七-6/7 —— ★ 发失败不丢（骨架的队列管 ✓）·
          ★★ 但**重发要幂等** ✓ ⇒ ★ 这里**只返回游标之后的**，★ 且 `local_id` 稳定 ✓
        """
        ...

    def apply(self, op: Op) -> OpResult:
        """★ 执行一条 op（★ 做不了**也要回执**，★ `ok=False` + 原因 ✓）"""
        ...


class BaseWorld:
    """★ 给世界适配层用的**最小默认**（★ 省得每份都写一遍 ✓）

    ⚠️ 它**故意什么都不做** ✗ —— ★ 这是"一个世界的最低要求"的示范 ✓
    """

    name = "unnamed"

    def capabilities(self) -> dict[str, Any]:
        return {"say": False, "emote": [], "read": []}

    def poll(self) -> list[Event]:
        return []

    def apply(self, op: Op) -> OpResult:
        return OpResult(id=op.id, ok=False, note="这个世界没有实现 apply()")
