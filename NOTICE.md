# 借了谁的形状 · 谁的许可 · 谁不能用

> ★ 按平台仓 `AGENTS.md` **§1.6 硬步骤**走完（★ 说清要什么 → ★ 去 GitHub 找（中英都搜）
> → ★ 查许可 → ★ 记账 ✓）· ★ 收集账在 `Xihuyue/docs/收集账.md` **2026-10-08 通用桥骨架** ✓
>
> ★★ **一句话**：★ 本仓**没有一行代码**是从别处搬来的 ✓ —— ★ 借的全是**形状** ✓

---

## ★★ 借了形状的（★ 许可干净 ✓）

| 来源 | 许可 | ★ 借了什么 | ★ 在哪 |
|---|---|---|---|
| ★★ [Home Assistant `manifest.json`](https://developers.home-assistant.io/docs/creating_integration_manifest/) | ★ **Apache-2.0** ✓ | ★★ **声明式清单**：★ 一个扩展 = **一个目录 + 一张清单**，★ 清单里写清"我是谁 · 我按哪版接口写 · 我要什么" ✓ | ★ `config.py` 那张 `bridge.json` ✓ |
| ★★ [pytest-dev/pluggy](https://github.com/pytest-dev/pluggy) | ★ **MIT** ✓ | ★★ **钩子**：★ **宿主定钩子、扩展只实现钩子** ✓ | ★ `world.py` 那三个钩子 ✓ |
| ★★ **transactional outbox**（★ 模式，不是某一份代码 ✓） | ★ 公共模式 | ★★ **先落库再发** ⇒ ★ 发失败不丢 ✓ | ★ `queue.py` ✓ |

★ ⚠️ **"借形状"的意思**（★ 说清楚 ✗）：★ 我们**照那个做法自己写** ✓ ——
★ ⛔ **不是复制代码** ✗ · ★ ⛔ **不是加依赖** ✗（★ 本仓**零依赖** ✓）

---

## ★★ ⛔ 明确**不用**的（★ 以及为什么 ✓）

| 来源 | 许可 | ★ 为什么不用 |
|---|---|---|
| ★ [aklivity/zilla](https://github.com/aklivity/zilla) | ★★ **Aklivity Community License** ✗ | ★★ **它不是 OSS** ✗ —— [它自己的说明](https://docs.aklivity.io/latest/reference/editions/licensing)写着：★ **"不得做成与它竞争的在线服务"** 那条限制 ✓ ⇒ ★ **许可不明级 ⇒ 不用** ✗（★ 只有"一个引擎多协议共享路由/鉴权"这个**想法**可以参考 ✓） |
| ★ [Smooth-E/instant-games-bridge-godot](https://github.com/Smooth-E/instant-games-bridge-godot) | ★ 未核 | ★ 它的方向是「**一套桥适配多个平台**」✗ —— ★ 我们要的是**反的**（★ 一个骨架适配多个世界 ✓） |
| ★ [VoyageForge/Bridge](https://github.com/VoyageForge/Bridge) · [garretreichenbach/StarBridge](https://github.com/garretreichenbach/StarBridge) | ★ 未核 | ★ 形态与我们无关 ✓（★ 名字撞了而已 ✗ —— ★ 留名备查 ✓） |
| ★ [valkyrie-fnd/valkyrie-event-adapter](https://github.com/valkyrie-fnd/valkyrie-event-adapter) | ★ 未核 | ★ 它是**博彩事件**专用的 ✓ |
| ★ `universal-bridge`（npm） | ★ 未核 | ★ 那是个**通用翻译**包，与我们的"世界适配"不同型 ✓ |

---

## ★ 我们**自己**的（★ 不是借的 ✓）

| 件 | 出处 |
|---|---|
| ★★ **五块分工**（报能力 / 上行 / op 回执 / 离线队列 / 读口） | ★ 平台契约《通用桥骨架》§二 ✓ |
| ★★ **"队列 ≠ 记忆"** 那条边界 | ★ 平台《设计-本地端与服务器》§3 + ★ **实测**（旧客户端 `LocalCache.cs` ✓） |
| ★★ **"只传结论"** | ★ 平台协议 §五 **红线 4** ✓ |
| ★★ **`local_id` 稳定 ⇒ 重发幂等** | ★ 平台协议 §四（"确定性 id 查重"✓）+ ★ 2026-10-08 的实测教训 ✓ |
| ★ **三循环互不拖死** | ★ **实测**：★ 旧桥"平台一重启全断" ✓ |
| ★ **`pending_events` 这个表名** | ★ **实测**：★ 旧客户端叫 `pending_memories` ⇒ 读的人会误解 ✓ |

---

## ⚠️ 一条诚实的话

★★ **本仓是"骨架"，不是"沙箱"** ✗ ——
★ 桥是**任意代码**，★ 它跑在**你自己的机器**上、★ 拿**你自己的令牌** ✓
★ 平台侧那份契约《桥不归平台》§三 写着：★ 「**信任门挡不住有心人** ✓ ——
★ 它挡的是**误装**与**不知情**」✓
⇒ ★ 所以：★★ **只跑你自己看得懂源码的桥** ✗
