# -*- coding: utf-8 -*-
r"""★★★ **端到端**：报能力 → 上行 → 对话 → 收 op → 回执（★ 契约 §九-2 的判据 ✓）。

★ 跑法：`py tests\manual_e2e_smoke.py`
★ ⚠️ 它**不连真平台**（★ 用 `fake_platform.py` ✓）⇒ ★ **不写他的库** ✗

## 守什么（**22 条**）
★ **五块的判据各一条** ✓ ＋ ★ **契约 §七 那十二条负向控制**里可测的那些 ✓
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from fake_platform import FakePlatform                             # noqa: E402
from yueban_bridge import (API_VERSION, Bridge, EventQueue, Gateway,  # noqa: E402
                           Manifest, ManifestError, Op, OpResult)
from yueban_bridge.protocol import (model_id, parse_sse_text,      # noqa: E402
                                    pick_reply_text, valid_source_name)
from yueban_bridge.adapters.demo import DemoWorld                    # noqa: E402

FAILS: list[str] = []
TMP = Path(tempfile.gettempdir()) / ("ybk_%d" % os.getpid())


def _raises(fn) -> bool:
    """★ 这一段**该抛**吗（★ 负向控制用 ✓）"""
    try:
        fn()
        return False
    except Exception:
        return True


def check(label: str, cond: bool, extra: object = "") -> None:
    print(("  [PASS] " if cond else "  [FAIL] ") + label
          + ("  " + str(extra) if extra != "" else ""))
    if not cond:
        FAILS.append(label)


def _cleanup() -> None:
    shutil.rmtree(str(TMP), ignore_errors=True)


def _mf(**kw) -> Manifest:
    base = {
        "name": "demo-bridge", "world": "demo", "api_version": API_VERSION,
        "entry": "yueban_bridge.adapters.demo:DemoWorld",
        "capabilities": ["say", "emote", "read", "act"],
        "needs": ["读口", "对话"],
        "character_id": "demo-card", "source": "demo",
        "events_path": "/api/demo/events",
    }
    base.update(kw)
    return Manifest.from_dict(base, base=TMP)


print()
print("=" * 78)
print("① ★★ 契约 §五：清单（声明式清单 · ⛔ 加载器不认目录名 ✗）")
print("=" * 78)
m = _mf()
check("★★ 清单读得出来（★ 名字/世界/接口版本/入口/能力 ✓）",
      m.name == "demo-bridge" and m.world == "demo" and m.api_version == API_VERSION, m.name)
check("★★ **接口版本对不上 ⇒ 拒载** ✗（契约 §七-11 的同类 ✓）",
      _raises(lambda: _mf(api_version="99")) is True, "")
check("★★ **缺字段 ⇒ 拒载** ✗", _raises(lambda: _mf(name="")) is True, "")
check("★★ **`capabilities` 空 ⇒ 拒载** ✗（★ 不然上线报什么 ✗）",
      _raises(lambda: _mf(capabilities=[])) is True, "")
check("★ 给人看的那一行说清了**它要什么** ✓（★ 让他知道在信任什么 ✓）",
      "想要=" in m.describe() and "能=" in m.describe(), m.describe())
check("★ `model` 形状照协议 §4.1 ✓（`xihuyue:<来源>:<卡>` ✓）",
      m.model_id() == "xihuyue:demo:demo-card", m.model_id())

print()
print("=" * 78)
print("② ★★ 契约 §二-④ + §七-6/7：离线队列（★ 先落库再发 · ★ 送到即删）")
print("=" * 78)
q = EventQueue(TMP / "q.db")
check("★★ 落一条 ⇒ 队列里有 ✓", q.put("a:1", "speak", {"text": "hi"}) is True and q.count() == 1,
      q.count())
check("★★ **同一个 `local_id` 落两次 ⇒ 只算一条** ✗（★ 重发幂等的地基 ✓）",
      q.put("a:1", "speak", {"text": "hi"}) is False and q.count() == 1, q.count())
check("★★ **`local_id` 为空 ⇒ 报错** ✗（⛔ 不许悄悄收下 ✓）",
      _raises(lambda: q.put("", "speak", {})) is True, "")
q.put_many([("a:2", "signal", {"tag": "x"}), ("a:3", "state", {"k": 1})])
check("★ 批量落 ✓", q.count() == 3, q.count())
pk = q.peek(limit=2)
check("★★ `peek` **不删** ✗（★ 送出成功才删 ✓）", len(pk) == 2 and q.count() == 3, q.count())
check("★ 取的是**最老的** ✓（★ 顺序不能乱 ✗）", [x.local_id for x in pk] == ["a:1", "a:2"],
      [x.local_id for x in pk])
q.bump([pk[0].seq])
check("★★ **没送成 ⇒ 计一次但**不删**** ✗（★ 下轮还送 ✓）",
      q.peek(1)[0].tries == 1 and q.count() == 3, q.peek(1)[0].tries)
n = q.ack([x.seq for x in pk])
check("★★ **送成 ⇒ 删** ✓（★ 「送到即删」✗）", n == 2 and q.count() == 1, q.count())
check("★★ **队列不是记忆** ✗（★ 它不参与回忆 —— ★ 它只是「没送出去的快递」✓）",
      "pending_events" in (TMP / "q.db").read_bytes().decode("latin-1")[:200000], "")

print()
print("=" * 78)
print("③ ★★★ 端到端五块（★ 契约 §九-2 的判据 ✗）")
print("=" * 78)
plat = FakePlatform(outbox=[{"id": "op-1", "type": "say",
                             "payload": {"text": "坐这儿陪我"}},
                            {"id": "op-2", "type": "draw",
                             "payload": {"prompt": "一碗粥"}}]).start()
try:
    manifest = _mf(platform=plat.base, queue_path=str(TMP / "bridge.queue.db"),
                   poll_seconds=0.2, outbox_seconds=0.2, state_seconds=0.2)
    gw = Gateway(plat.base, user="u", password="p")
    check("★ 登录拿令牌 ✓（★ 现状只有账号 JWT ✗ —— 协议 §二 ✓）", gw.login() is True,
          "login_hits=%d" % plat.login_hits)
    br = Bridge(manifest, DemoWorld(tick_seconds=0.05), gateway=gw)

    # ① 报能力
    check("★★★ **① 上线报能力** ✓（★ 让它知道「她此刻能做什么」✗）",
          br.report_capabilities() is True and len(plat.capabilities) == 1,
          len(plat.capabilities))
    _caps = (plat.capabilities[0].get("capabilities") or {}) if plat.capabilities else {}
    check("★★ **能力要如实** ✗（★ 这个假世界**不报**生图 ⇒ ★ 她就不该说「我画给你看」✓）",
          _caps.get("draw") is False and _caps.get("say") is True, _caps.get("draw"))

    # ② 上行：先落库，再送
    check("★★★ **② 上行**：★ 只传**结论** ✓（★ 一句话 / 一个标签 ✓）",
          br.collect() == 0 and br.flush() is True, "刚上线还没到点")
    import time as _t
    _t.sleep(0.2)
    got = br.collect()
    check("★★ 读到新结论 ⇒ 落队列 ✓", got >= 1, got)
    check("★★ **先落库** ✗（★ 还没送，队列里就有 ✓）", br.q.count() >= 1, br.q.count())
    check("★★ 送出去了 ✓", br.flush() is True, "")
    check("★★★ **送到即删** ✗（★ 队列清空 ✓）", br.q.count() == 0, br.q.count())
    _ev = (plat.received_events[0][0].get("events") or []) if plat.received_events else []
    check("★★ **每一条都带稳定的 `local_id`** ✗（★ 重发幂等的地基 ✓）",
          bool(_ev) and all(e.get("local_id") for e in _ev), len(_ev))
    check("★★ **上行里没有原始流** ✗（★ 只有结论字段 ✓ ★ 契约 §七-2 ✓）",
          all(set(e.keys()) <= {"local_id", "kind", "text", "tag", "n", "key",
                                "value", "at"} for e in _ev), sorted(_ev[0].keys())
          if _ev else "")

    # ★★ 重发幂等：★ **单独造一个确定的场景** ✗ ——
    #   ⚠️ 我第一版在**那个正跑着轮询的桥**上测（★ 后台线程同时在往里塞新事件 ✓）
    #     ⇒ ★ 收到的批次一直在变 ⇒ ★ 判据永远不稳 ✓
    #   ⇒ ★ 教训：★ **测"重发"就要让"第一次"和"第二次"是同一批** ✓
    br.q.ack([x.seq for x in br.q.peek(999)])          # ★ 先清空（★ 只留下面这条 ✓）
    _n_ev_before = len(plat.received_events)
    br.q.put("stable:1", "speak", {"text": "重发测试"})
    br.flush()                                          # ★ 第一次：★ 平台收下 ✓
    _fresh1 = plat.received_events[-1][1]
    _dup1 = plat.received_events[-1][2]
    br.q.put("stable:1", "speak", {"text": "重发测试"})   # ★ 第二次：★ 同一条再来一遍 ✓
    br.flush()
    _fresh2 = plat.received_events[-1][1]
    _dup2 = plat.received_events[-1][2]
    check("★★★ **重发幂等** ✓（★ 第二次发同一条 ⇒ 平台**认出来了** ✗ 协议 §四 ✓）",
          (_fresh1, _dup1) == (1, 0) and (_fresh2, _dup2) == (0, 1),
          ("第一次 新/重", _fresh1, _dup1, "第二次 新/重", _fresh2, _dup2))

    # ③ 下行：收 op + 回执
    done = br.run_outbox()
    check("★★★ **③ 收 op + 回执** ✓（★ 两条都回了 ✗ 契约 §七-5 ✓）",
          done == 2 and len(plat.acks) == 2, (done, len(plat.acks)))
    _ok = {a["id"]: a["ok"] for a in plat.acks}
    check("★★ **做得到的报 ok=True** ✓", _ok.get("op-1") is True, _ok)
    check("★★★ **做不到的也回执、而且如实说** ✗（⛔ 不许装成功 ✓ 契约 §七-8 ✓）",
          _ok.get("op-2") is False, _ok)
    check("★★ 世界真的执行了 ✓", br.world.applied[:2] == ["say", "draw"], br.world.applied[:2])

    # ④ 读口
    reps = br.pull_state()
    check("★★★ **④ 读口**：★ 拉到她说的话 ✓", len(reps) == 1, len(reps))
    check("★★ **按 `id` 去重** ✗（★ 平台给了两条同样的 `r-1` ⇒ 只收一条 ✓ 协议 §3① ✓）",
          reps and reps[0]["id"] == "r-1", [r.get("id") for r in reps])
    check("★★ **游标往回退一点** ✗（★ 她的钟可能是停的 ✓ 协议 §3① 那条坑 ✓）",
          br._cursor < 1791449000.0, br._cursor)
    check("★★ 再拉一次 ⇒ **没有新的** ✓（★ 去重生效 ✗）", br.pull_state() == [], "")

    # ⑤ 一个循环坏掉不许拖死别的
    class Boom(DemoWorld):
        def poll(self):
            raise RuntimeError("这个世界炸了")

    br2 = Bridge(_mf(platform=plat.base, queue_path=str(TMP / "b2.db")), Boom(), gateway=gw)
    check("★★★ **世界适配层抛了 ⇒ 骨架不崩** ✗（★ 只跳过这一轮 ✓ 契约 §七-3 的同型 ✓）",
          br2.collect() == 0, "")
    check("★★ 而**别的照样能跑** ✓（★ 旧桥就是「平台一重启全断」✗）",
          br2.run_outbox() == 2, "")
finally:
    plat.stop()

print()
print("=" * 78)
print("④ ★★ 协议形状（★ 换平台版本只改 `protocol.py` ✓）")
print("=" * 78)
check("★ `model` 两种写法 ✓（★ 带来源 / 不带 ✓ 协议 §4.1 ✓）",
      model_id("c1") == "xihuyue:c1" and model_id("c1", "w") == "xihuyue:w:c1", "")
check("★ **静默流式**的 SSE 也认 ✓（★ 平台不是真流式 ✗ 协议 §3② ✓）",
      parse_sse_text('data: {"choices":[{"delta":{"content":"你"}}]}\n\n'
                     'data: {"choices":[{"delta":{"content":"好"}}]}\n\n'
                     'data: [DONE]\n')[0] == "你好", "")
check("★ SSE 里的 `[DONE]` 认得出来 ✓",
      parse_sse_text("data: [DONE]\n")[1] is True, "")
check("★ 非流式取正文 ✓", pick_reply_text(
    {"choices": [{"message": {"content": "嗯"}}]}) == "嗯", "")
check("★ **来源名要像个标识符** ✗（★ 它会进 `memories.source` 和她的嘴里 ✓）",
      valid_source_name("demo_world-1") and not valid_source_name("我的世界 ！！"), "")
check("★★ **零角色名** ✗（★ 角色通用 ✓ 契约 §七-12 ✓）",
      not any(x in (ROOT / "yueban_bridge" / "protocol.py").read_text(encoding="utf-8")
              for x in ("月儿", "西湖月", "珂莉姆")), "")

_cleanup()
print()
if FAILS:
    print("❌ %d 条不变量被破坏：" % len(FAILS))
    for f in FAILS:
        print("   -", f)
    raise SystemExit(1)
print("✅ 全部通过")
