"""★ 平台那份**对外接口**的形状（唯一真源 —— 换平台版本只改这里 ✓）。

★ 为什么单独一个文件：★ 契约《通用桥骨架》§六 说 ★ 平台侧还缺三件
（每桥一把 key · 自检端点 · 来源登记 ✓）★ ⇒ ★ **那些路会变** ✗
★ 把"平台长什么样"收在一个地方 ⇒ ★ 变的时候只改这一份 ✓

⚠️ 边界：★ 这里**只放形状与路径**，⛔ 不放业务 ✗
"""

from __future__ import annotations

import json
import re
from typing import Any

# ★★ 我按哪一版接口写的（★ 清单里要报这个 ✓ · 平台对不上就拒 ✓）
API_VERSION = "1"

# ⚠️ 现状：★ 协议自称 **v0**（`docs/协议-桥与平台（对外·v0）.md` ✓）
#   ★ 所以这里记的是"我照哪一版写的"，⛔ 不是"平台已经稳定了" ✗
PROTOCOL_NOTE = "平台侧协议自我标记为 v0；本骨架按 v1 形状写，以路径为准。"


def join(base: str, path: str) -> str:
    """★ 拼 URL（★ 免得双斜杠 / 缺斜杠 ✗）"""
    return "%s/%s" % (str(base or "").rstrip("/"), str(path or "").lstrip("/"))


# ── ① 读口：她此刻是什么 + 她新说的话 ────────────────────────────────
# ★ 拉模式（⛔ 平台不推送 ✗ —— 契约 §七-4 ✓）
STATE_PATH = "/api/local/state"
STATE_QUERY = ("since", "limit", "character_id")

# ── ② 对话：OpenAI 兼容（协议 §3② ✓）────────────────────────────────
CHAT_PATH = "/v1/chat/completions"
MODELS_PATH = "/v1/models"


def model_id(card_id: str, source: str = "") -> str:
    """★ 协议 §4.1：`xihuyue:<来源>:<卡 id>` ✓

    ⚠️ 来源名**要按协议 §4.2 的三种口径**（`label`/`spoken`/`marker` ✓），
      ⛔ 别随手编 ✗ —— 没登记的来源界面上会显示成「其他」✓
    """
    _src = str(source or "").strip()
    _cid = str(card_id or "").strip()
    return "xihuyue:%s:%s" % (_src, _cid) if _src else "xihuyue:%s" % _cid


# ── ③ 上行：那个世界发生了什么（★ 只传结论 ✓）──────────────────────
# ⚠️ 现状：协议 §3③ 说这条**形态因游戏而异**、★ 统一形态**未建** ✗
#   ⇒ ★ 本骨架**只约定形状**，★ 具体路径由各世界自己的上报口定 ✓
#   ★ 这一步是**刻意的**：★ 等平台那三件做完，再收成一条 ✓
EVENT_PATH_HINT = "/api/hardware/event"       # ★ 通用形态（他回来了 / 他离开了）

# ── ④ 下行：她想做什么（★ 队列 + 回执 ✓）──────────────────────────
# ★ 参考现成范式 `rimworld_outbox`（★ 真库 493 行 ✓ —— 契约 §二-③ ✓）
# ⚠️ 现状：协议 §3④ 说**未建** ✗ ⇒ ★ 路径可配（见 config.rs 的 outbox_* ✓）
OUTBOX_PENDING_PATH = "/api/bridge/outbox/pending"
OUTBOX_ACK_PATH = "/api/bridge/outbox/ack"

# ── ⑤ 上线报能力（★ 骨架自己的那一块 ✓）───────────────────────────
# ⚠️ 现状：**平台还没有这个端点** ✗（★ 协议里没有 · ★ 那是我们要去做的 ✓）
#   ⇒ ★ 骨架先**打它、允许 404**（★ 记一条日志就好 ✓ —— ⛔ 不许因此崩 ✗）
CAPABILITIES_PATH = "/api/bridge/capabilities"


def parse_sse_text(raw: str) -> tuple[str, bool]:
    """★ 从 SSE 里抠出正文（★ 协议 §3②：★ 平台是"**静默流式**"✗ —— 一次算完才发 ✓）

    ★ 返回 `(正文, 见到过 [DONE])` ✓
    ⚠️ 只认 `data:` 行 —— ★ 别把 `event:` / 注释当正文 ✗
    """
    parts: list[str] = []
    done = False
    for line in str(raw or "").splitlines():
        s = line.strip()
        if not s.startswith("data:"):
            continue
        payload = s[len("data:"):].strip()
        if payload == "[DONE]":
            done = True
            continue
        try:
            obj = json.loads(payload)
        except Exception:
            continue
        for ch in (obj.get("choices") or []):
            txt = ((ch.get("delta") or {}).get("content")
                   or (ch.get("message") or {}).get("content"))
            if txt:
                parts.append(str(txt))
    return "".join(parts), done


def pick_reply_text(payload: dict[str, Any]) -> str:
    """★ 从非流式返回里取正文（★ 兼容 OpenAI 形状 + 平台扩展 `xihuyue` ✓）"""
    for ch in (payload.get("choices") or []):
        msg = ch.get("message") or ch.get("delta") or {}
        if msg.get("content"):
            return str(msg["content"])
    return ""


def extension_block(payload: dict[str, Any]) -> dict[str, Any]:
    """★ 平台扩展字段（★ 协议 §3②：`emotion` / `source` / `card_id` ✓）

    ⇒ ★ 桥拿它**驱动表情 / 语气** ✓（★ 那是"表现层"的事 ✓ —— 契约 §零 ✓）
    """
    ext = payload.get("xihuyue")
    return ext if isinstance(ext, dict) else {}


_SEG = re.compile(r"^[A-Za-z0-9_\-\.]{1,48}$")


def valid_source_name(name: str) -> bool:
    """★ 来源名要能当标识符（★ 因为它会进 `memories.source` ✓）

    ⚠️ 这条**故意严** ✗ —— 契约《通用桥骨架》§七-12：★ 零角色名 ✓
      ★ 而且来源名会进界面与她的嘴里 ⇒ ★ 太脏的名字会污染她的话 ✓
    """
    return bool(_SEG.match(str(name or "")))
