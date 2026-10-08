"""★★ **YuebanBridgeKit** —— 月伴的**通用桥骨架** ✓

> ★ 一句话：★ **桥是一个客户端** ✓ —— ★ 它为**任意一个世界**做五件事 ✓：
> ★ **上线报能力 · 上行只传结论 · 收 op 回执 · 离线队列 · 读口** ✓
> ★★ **换一个世界 = 只改一个适配文件** ✗ —— ★ 那是"通用"的判据 ✓
>
> ★ 契约：`Xihuyue/docs/契约-通用桥骨架（一个客户端·换世界只改编配层）（2026-10-08）.md` ✓
> ★ 上位：`Xihuyue/docs/设计-本地端与服务器（记忆服务端·表现层）.md` ✓
>             `Xihuyue/docs/协议-桥与平台（对外·v0）.md` ✓

★ **零依赖**（★ 只用标准库 ✓）⇒ ★ clone 下来就能跑 ✓
★ **许可**：★ 本项目自己的代码 ✓ —— 借形状的来源与许可见 `NOTICE.md` ✓
"""

from .bridge import Bridge
from .config import Manifest, ManifestError
from .gateway import Gateway, PlatformError, TransientError
from .protocol import API_VERSION
from .queue import EventQueue
from .world import BaseWorld, Event, Op, OpResult, World

__version__ = "0.1.0"

__all__ = [
    "Bridge", "Manifest", "ManifestError", "Gateway", "PlatformError",
    "TransientError", "EventQueue", "BaseWorld", "Event", "Op", "OpResult",
    "World", "API_VERSION", "__version__",
]
