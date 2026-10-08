"""★★ **离线队列**：先落库再发 ⇒ ★ 发失败**不丢** ✓（契约 §二-④ · §七-6 ✓）。

## ★★★ 一条要写死的边界（★ 契约 §三 ✓）
★★ **这个队列不是"第二份记忆"** ✗ —— ★ 它只是**没送出去的快递** ✓：
· ★ 只存**还没送到的** ✓
· ★ **送到即删** ✓
· ★ **不参与回忆** ✗（★ 她永远读不到这里的东西 ✓）
· ★ **不是真源** ✗（★ 真源永远只有平台 ✓）

★★ 所以它**不违反**那条唯一纪律（「本地端不做记忆」✓）——
★ 实测来历：★ 旧客户端 `YuebanPushClient/LocalCache.cs`（102 行 ✓）★ 那张表叫
`pending_memories` ✗ · ★★ **但读源码：它只是离线队列** ✓ ⇒ ★ 名字会让人误解 ⇒
★ 本骨架**一律叫 `pending_events`** ✗（★ 收集账 2026-10-08 ✓）

## ★ 为什么要"先落库再发"（★ 不是洁癖 ✓）
★ 直接发 ⇒ ★ **进程崩了 / 网断了 / 平台重启了** ⇒ ★ 那条结论**永远没了** ✗
★ 而"他回来了""她说了一句话"这类事，★ **丢了就是丢了** ✓（★ 世界不会再发生一次 ✓）
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

TABLE = "pending_events"


@dataclass
class Queued:
    seq: int
    local_id: str
    kind: str
    payload: dict[str, Any]
    tries: int = 0


class EventQueue:
    """★ 一个**单文件 SQLite 队列**（★ 先落库再发 ✓ · ★ 送到即删 ✓）。

    ⚠️ 单进程用（★ 桥是单进程的 ✓ —— ⛔ 别拿它当多进程共享队列 ✗）
    """

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._lock = threading.Lock()
        p = Path(self.path)
        if p.parent and str(p.parent) not in ("", "."):
            p.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    # ── 连接（★ 每线程一份 ✓）──────────────────────────────────────
    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=10.0, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=FULL")     # ★ 这一条是重点：★ 断电也不丢 ✗
        return c

    def _init(self) -> None:
        with self._lock:
            c = self._conn()
            try:
                c.execute(
                    "CREATE TABLE IF NOT EXISTS %s ("
                    " seq INTEGER PRIMARY KEY AUTOINCREMENT,"
                    " local_id TEXT NOT NULL,"
                    " kind TEXT NOT NULL,"
                    " payload TEXT NOT NULL,"
                    " tries INTEGER NOT NULL DEFAULT 0,"
                    " created_at REAL NOT NULL)" % TABLE)
                # ★★ 同一个 `local_id` 只许有一条 ✗ —— ★ 那是"重发幂等"的地基 ✓
                c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_pe_local "
                          "ON %s(local_id)" % TABLE)
                c.commit()
            finally:
                c.close()

    # ── 写入 ───────────────────────────────────────────────────────
    def put(self, local_id: str, kind: str, payload: dict[str, Any]) -> bool:
        """★ 落一条（★ 已在 ⇒ 返回 False ✓ —— ★ **重复入队不算错** ✓）

        ★★ `local_id` 必须稳定 ✗ —— ★ 世界适配层那边保证（见 `world.Event` ✓）
        """
        _id = str(local_id or "").strip()
        if not _id:
            raise ValueError("local_id 不能为空（★ 它是查重的地基 ✗）")
        with self._lock:
            c = self._conn()
            try:
                c.execute("INSERT OR IGNORE INTO %s(local_id, kind, payload, created_at) "
                          "VALUES (?,?,?,?)" % TABLE,
                          (_id, str(kind or ""), json.dumps(payload or {},
                                                            ensure_ascii=False),
                           time.time()))
                n = c.total_changes
                c.commit()
                return n > 0
            finally:
                c.close()

    def put_many(self, items: Iterable[tuple[str, str, dict[str, Any]]]) -> int:
        n = 0
        for local_id, kind, payload in items:
            if self.put(local_id, kind, payload):
                n += 1
        return n

    # ── 读取 ───────────────────────────────────────────────────────
    def peek(self, limit: int = 50) -> list[Queued]:
        """★ 取最老的 N 条（★ **不删** ✗ —— ★ 送出成功才删 ✓）"""
        with self._lock:
            c = self._conn()
            try:
                rows = list(c.execute(
                    "SELECT seq, local_id, kind, payload, tries FROM %s "
                    "ORDER BY seq LIMIT ?" % TABLE, (int(limit),)))
            finally:
                c.close()
        out: list[Queued] = []
        for r in rows:
            try:
                payload = json.loads(r["payload"])
            except Exception:
                payload = {}
            out.append(Queued(seq=int(r["seq"]), local_id=str(r["local_id"]),
                              kind=str(r["kind"]), payload=payload,
                              tries=int(r["tries"] or 0)))
        return out

    def ack(self, seqs: Iterable[int]) -> int:
        """★ 送出去了 ⇒ **删掉** ✓（★ 这就是"送到即删" ✗）"""
        ids = [int(x) for x in seqs]
        if not ids:
            return 0
        with self._lock:
            c = self._conn()
            try:
                q = "DELETE FROM %s WHERE seq IN (%s)" % (TABLE, ",".join("?" * len(ids)))
                c.execute(q, ids)
                n = c.total_changes
                c.commit()
                return n
            finally:
                c.close()

    def bump(self, seqs: Iterable[int]) -> None:
        """★ 没送成 ⇒ 记一次（★ 留着下次再送 ✓ —— ★ 但**不删** ✗）"""
        ids = [int(x) for x in seqs]
        if not ids:
            return
        with self._lock:
            c = self._conn()
            try:
                q = ("UPDATE %s SET tries = tries + 1 WHERE seq IN (%s)"
                     % (TABLE, ",".join("?" * len(ids))))
                c.execute(q, ids)
                c.commit()
            finally:
                c.close()

    def count(self) -> int:
        with self._lock:
            c = self._conn()
            try:
                return int(list(c.execute("SELECT COUNT(*) FROM %s" % TABLE))[0][0])
            finally:
                c.close()
