"""★ 桥的配置（★ 一个世界一份 `bridge.json` ✓ —— 契约 §五 ✓）。

★★ 来历：★ 借 **Home Assistant `manifest.json`**（Apache-2.0 ✓）那套 ——
★ **声明式清单**：★ 一个桥 = ★ 一个目录 + 一张清单 ✓
★★ ⛔ **加载器不认目录名** ✗ —— ★ 只认清单里写的 ✓

★★ 许可说明：★ 我们**只借"清单"这个形状** ✗ —— ★ HA 的代码一行都没抄 ✓
（★ 收集账 2026-10-08「通用桥骨架」✓）
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import protocol


class ManifestError(ValueError):
    """★ 清单不对 ⇒ ★ **拒载** ✗（⛔ 不"试试看" ✓ —— 契约 §七-11 的同类规矩 ✓）"""


REQUIRED = ("name", "world", "api_version", "entry", "capabilities")


@dataclass
class Manifest:
    """★ 那张清单（★ 对应 `bridge.json` ✓）。"""

    name: str
    world: str                                  # ★ 接的是哪个世界（★ 进 memories.source ✓）
    api_version: str                            # ★ 我照哪版接口写的
    entry: str                                  # ★ 从哪个模块进（"包.模块:类名" ✓）
    capabilities: list[str] = field(default_factory=list)
    needs: list[str] = field(default_factory=list)      # ★ 我要平台给什么（摆给人看 ✓）
    display_name: str = ""
    version: str = "0.1.0"
    # ── 平台侧地址（★ 可覆盖 ✓）─────────────────────────────────────
    platform: str = "http://127.0.0.1:5000"
    character_id: str = ""
    source: str = ""                            # ★ 来源名（★ 协议 §4.1 ✓）
    outbox_pending_path: str = protocol.OUTBOX_PENDING_PATH
    outbox_ack_path: str = protocol.OUTBOX_ACK_PATH
    capabilities_path: str = protocol.CAPABILITIES_PATH
    # ★★ 上报口：★★ **由本世界自己声明** ✗ ——
    #   ★ 协议 §3③ 原文：★「游戏特有的上行，现有实现是按游戏各自开的
    #     …… **【未建】统一形态**」✓ ⇒ ★ 统一之前，★ 这就是**清单里的一项** ✓
    events_path: str = "/api/bridge/events"
    poll_seconds: float = 5.0
    outbox_seconds: float = 5.0
    state_seconds: float = 10.0
    # ★ 队列（★ "还没送到的" ✓ —— ⛔ 不是记忆 ✗）
    queue_path: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Manifest":
        p = Path(path)
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ManifestError("清单读不了：%s（%s）" % (p, exc))
        if not isinstance(raw, dict):
            raise ManifestError("清单必须是一个 JSON 对象")
        return cls.from_dict(raw, base=p.parent)

    @classmethod
    def from_dict(cls, raw: dict[str, Any], *, base: Path | None = None) -> "Manifest":
        missing = [k for k in REQUIRED if not str(raw.get(k) or "").strip()]
        if missing:
            raise ManifestError("清单缺字段：%s" % ", ".join(missing))
        # ★★ 接口版本对不上 ⇒ ★ **拒载** ✗（⛔ 不"试试看" ✓）
        if str(raw["api_version"]) != protocol.API_VERSION:
            raise ManifestError(
                "接口版本对不上：这个桥写的是 %s，本骨架是 %s ⇒ 拒载"
                % (raw["api_version"], protocol.API_VERSION))
        caps = raw.get("capabilities")
        if not isinstance(caps, list) or not caps:
            raise ManifestError("`capabilities` 必须是非空数组（★ 不然上线报什么 ✗）")
        needs = raw.get("needs") or []
        if not isinstance(needs, list):
            raise ManifestError("`needs` 必须是数组")
        qp = str(raw.get("queue_path") or "").strip()
        if not qp:
            qp = str((base or Path(".")) / (str(raw["name"]) + ".queue.db"))
        return cls(
            name=str(raw["name"]).strip(),
            world=str(raw["world"]).strip(),
            api_version=str(raw["api_version"]).strip(),
            entry=str(raw["entry"]).strip(),
            capabilities=[str(x) for x in caps],
            needs=[str(x) for x in needs],
            display_name=str(raw.get("display_name") or raw["name"]),
            version=str(raw.get("version") or "0.1.0"),
            platform=str(raw.get("platform") or "http://127.0.0.1:5000").rstrip("/"),
            character_id=str(raw.get("character_id") or "").strip(),
            source=str(raw.get("source") or raw["world"]).strip(),
            outbox_pending_path=str(raw.get("outbox_pending_path")
                                    or protocol.OUTBOX_PENDING_PATH),
            outbox_ack_path=str(raw.get("outbox_ack_path") or protocol.OUTBOX_ACK_PATH),
            capabilities_path=str(raw.get("capabilities_path")
                                  or protocol.CAPABILITIES_PATH),
            events_path=str(raw.get("events_path") or "/api/bridge/events"),
            poll_seconds=float(raw.get("poll_seconds") or 5.0),
            outbox_seconds=float(raw.get("outbox_seconds") or 5.0),
            state_seconds=float(raw.get("state_seconds") or 10.0),
            queue_path=qp,
        )

    def describe(self) -> str:
        """★ 给人看的一行（★ 上线时打出来 ✓ —— ★ 让他知道自己在信任什么 ✓）"""
        return ("%s（%s）· 世界=%s · 接口v%s · 想要=%s · 能=%s"
                % (self.display_name, self.version, self.world, self.api_version,
                   ",".join(self.needs) or "无", ",".join(self.capabilities)))

    def model_id(self) -> str:
        """★ 协议 §4.1 的形状 ✓"""
        return protocol.model_id(self.character_id, self.source)
