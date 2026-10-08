"""★ 命令行：`py -m yueban_bridge <命令>` ✓

★ 三个命令（★ 够用了 ✗ —— ⛔ 先不铺大 ✗）：
· `capabilities` —— ★ 只报一次能力（★ 看平台收不收 ✓）
· `selfcheck`    —— ★ 按契约 §八 走一遍"我接对了没"（★ 只读 ✓）
· `say`          —— ★ 说一句、看她怎么回 ✓
· `run`          —— ★ 常驻跑（★ 上行 / 下行 / 读口 ✓）

⚠️ **零依赖**（★ 只用标准库 ✓）⇒ ★ clone 下来就能跑 ✓
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import sys
import time
from typing import Any

from .bridge import Bridge
from .config import Manifest, ManifestError
from .gateway import Gateway, PlatformError, TransientError


def _load_world(entry: str) -> Any:
    """★ `包.模块:类名` ⇒ ★ 那个世界 ✓（★ 契约 §五 的 `entry` ✓）"""
    if ":" not in str(entry or ""):
        raise SystemExit("`entry` 要写成 `包.模块:类名`（现在是 %r）" % entry)
    mod_name, cls_name = str(entry).split(":", 1)
    try:
        mod = importlib.import_module(mod_name.strip())
    except Exception as exc:
        raise SystemExit("载入 %s 失败：%s" % (mod_name, exc))
    try:
        cls = getattr(mod, cls_name.strip())
    except AttributeError:
        raise SystemExit("%s 里没有 %s" % (mod_name, cls_name))
    return cls()


def _gateway(m: Manifest, args: argparse.Namespace) -> Gateway:
    gw = Gateway(m.platform, token=str(getattr(args, "token", "") or ""),
                 user=str(getattr(args, "user", "") or ""),
                 password=str(getattr(args, "password", "") or ""))
    if not gw.token:
        gw.login()
    return gw


def _report(gw: Gateway, m: Manifest, world: Any) -> None:
    """★ 契约 §八 那条自检：★ **一次回答"你的桥接对了没"** ✗

    ★ 平台侧的 `/v1/bridge/selfcheck` **还没做** ✗（★ 那是要去做的 ✓）
    ⇒ ★ 这里先在**桥这一侧**把能查的查了 ✓ —— ★ 平台那件做了之后接上 ✓
    """
    rows: list[tuple[str, bool, str]] = []
    rows.append(("清单读得出", True, m.describe()))
    rows.append(("接口版本", True, "桥 v%s / 骨架 v%s" % (m.api_version, "1")))
    try:
        caps = world.capabilities() or {}
        rows.append(("世界报能力", bool(caps), ",".join(sorted(caps.keys()))[:60]))
    except Exception as exc:
        rows.append(("世界报能力", False, "%s: %s" % (type(exc).__name__, exc)))
    try:
        obj = gw.state(character_id=m.character_id)
        _st = (obj or {}).get("state") or {}
        rows.append(("读口", bool(_st), "她此刻：%s" % _st.get("awareness", "?")))
    except (TransientError, PlatformError) as exc:
        rows.append(("读口", False, str(exc)[:60]))
    ok = gw.report_capabilities(m.capabilities_path, {"bridge": m.name,
                                                      "world": m.world})
    rows.append(("报能力", ok, "平台已收" if ok else "平台还没这个端点（★ 正常 ✓）"))
    print()
    for name, good, note in rows:
        print("  %s %-12s %s" % ("[OK]  " if good else "[XX]  ", name, note))
    print()
    if not all(r[1] for r in rows[:3]):
        raise SystemExit(1)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="yueban_bridge",
                                 description="月伴通用桥骨架（换世界只改编配层 ✓）")
    ap.add_argument("--manifest", "-m", default="bridge.json",
                    help="清单路径（★ 默认 ./bridge.json ✓）")
    ap.add_argument("--token", default="", help="既有令牌（★ 不给就现场登录 ✓）")
    ap.add_argument("--user", default="", help="账号（★ 现状只有账号 JWT ✗）")
    ap.add_argument("--password", default="", help="口令")
    ap.add_argument("--verbose", "-v", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("capabilities", help="只报一次能力")
    sub.add_parser("selfcheck", help="按契约 §八 查一遍")
    _say = sub.add_parser("say", help="说一句、看她怎么回")
    _say.add_argument("text")
    sub.add_parser("run", help="常驻跑（上行 / 下行 / 读口）")

    args = ap.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%H:%M:%S")

    try:
        m = Manifest.load(args.manifest)
    except ManifestError as exc:
        print("清单不对 ⇒ 拒载：%s" % exc, file=sys.stderr)
        return 2
    world = _load_world(m.entry)
    gw = _gateway(m, args)
    br = Bridge(m, world, gateway=gw)

    if args.cmd == "capabilities":
        ok = br.report_capabilities()
        print("报能力：%s" % ("平台收下了 ✓" if ok else "平台还没这个端点（★ 正常 ✓）"))
        return 0
    if args.cmd == "selfcheck":
        _report(gw, m, world)
        return 0
    if args.cmd == "say":
        try:
            obj = br.say(args.text)
        except (TransientError, PlatformError) as exc:
            print("她那边没回上：%s" % exc, file=sys.stderr)
            return 1
        from .protocol import extension_block, pick_reply_text
        print("她：%s" % pick_reply_text(obj))
        ext = extension_block(obj)
        if ext:
            print("（情绪 %s · 来源 %s ✓）" % (ext.get("emotion", "?"),
                                              ext.get("source", "?")))
        return 0
    if args.cmd == "run":
        print("★ %s" % m.describe())
        print("★ 队列：%s（★ 只放「还没送到的」✗ —— ⛔ 不是记忆 ✗）" % m.queue_path)
        br.start()
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            br.stop()
            print("\n停了 ✓")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
