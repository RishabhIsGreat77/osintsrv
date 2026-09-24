cat > core/cache.py <<'PYEOF'
"""
core/cache.py — sqlite-backed cache for osint-srv.

Two tables:
  cache   — url -> body/status, with TTL
  history — every scan target + module + result summary
"""

import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

import aiosqlite


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "cache.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS cache (
    url     TEXT PRIMARY KEY,
    status  INTEGER,
    body    TEXT,
    ts      INTEGER
);
CREATE INDEX IF NOT EXISTS idx_cache_ts ON cache(ts);

CREATE TABLE IF NOT EXISTS history (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    module  TEXT,
    target  TEXT,
    summary TEXT,
    ts      INTEGER
);
CREATE INDEX IF NOT EXISTS idx_history_target ON history(target);
"""


class Cache:
    """Async cache — use as context manager."""

    def __init__(self, path: Optional[Path] = None, ttl: int = 86400):
        self.path = path or DB_PATH
        self.ttl = ttl
        self._db: Optional[aiosqlite.Connection] = None

    async def __aenter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self.path))
        await self._db.executescript(SCHEMA)
        await self._db.commit()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._db:
            await self._db.close()
            self._db = None

    async def get(self, url: str) -> Optional[Dict[str, Any]]:
        """Return cached entry or None if missing/expired."""
        if self._db is None:
            return None
        async with self._db.execute(
            "SELECT status, body, ts FROM cache WHERE url = ?", (url,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        status, body, ts = row
        if time.time() - ts > self.ttl:
            return None
        return {"status": status, "body": body, "ts": ts}

    async def set(self, url: str, status: int, body: str) -> None:
        if self._db is None:
            return
        await self._db.execute(
            "INSERT OR REPLACE INTO cache (url, status, body, ts) VALUES (?, ?, ?, ?)",
            (url, status, body, int(time.time())),
        )
        await self._db.commit()

    async def log(
        self, module: str, target: str, summary: Dict[str, Any]
    ) -> None:
        if self._db is None:
            return
        await self._db.execute(
            "INSERT INTO history (module, target, summary, ts) VALUES (?, ?, ?, ?)",
            (module, target, json.dumps(summary, default=str), int(time.time())),
        )
        await self._db.commit()

    async def history(self, limit: int = 50) -> List[Dict[str, Any]]:
        if self._db is None:
            return []
        async with self._db.execute(
            "SELECT module, target, summary, ts FROM history "
            "ORDER BY ts DESC LIMIT ?",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
        return [
            {"module": r[0], "target": r[1],
             "summary": json.loads(r[2]) if r[2] else {}, "ts": r[3]}
            for r in rows
        ]

    async def clear(self) -> None:
        if self._db is None:
            return
        await self._db.execute("DELETE FROM cache")
        await self._db.commit()
PYEOF
