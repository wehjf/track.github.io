import aiosqlite
import datetime
from typing import Optional

DB_PATH = "executions.db"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT UNIQUE,
    user_id TEXT NOT NULL,
    username TEXT,
    ts INTEGER NOT NULL,
    execution_count INTEGER
);
"""

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_TABLE_SQL)
        await db.commit()

async def add_execution(message_id: Optional[str], user_id: str, username: str, ts: Optional[int] = None, execution_count: Optional[int] = None) -> bool:
    if ts is None:
        ts = int(datetime.datetime.utcnow().timestamp())
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO executions (message_id, user_id, username, ts, execution_count) VALUES (?, ?, ?, ?, ?)",
                (message_id, user_id, username, ts, execution_count),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

async def count_since(seconds_ago: int) -> int:
    cutoff = int((datetime.datetime.utcnow() - datetime.timedelta(seconds=seconds_ago)).timestamp())
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM executions WHERE ts >= ?", (cutoff,))
        row = await cur.fetchone()
        return row[0] if row else 0

async def unique_users_since(seconds_ago: int) -> int:
    cutoff = int((datetime.datetime.utcnow() - datetime.timedelta(seconds=seconds_ago)).timestamp())
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(DISTINCT user_id) FROM executions WHERE ts >= ?", (cutoff,))
        row = await cur.fetchone()
        return row[0] if row else 0

async def lifetime_count_for_user(user_id: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM executions WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return row[0] if row else 0

async def recent_executions(limit: int = 10):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT ts, user_id, username, execution_count, message_id FROM executions ORDER BY ts DESC LIMIT ?", (limit,))
        rows = await cur.fetchall()
        return rows
