
import aiosqlite
from pathlib import Path
from datetime import datetime, timezone


DB_PATH = Path(__file__).resolve().parents[2] / "nexus_conversations.sqlite"


def current_time():
    return datetime.now(timezone.utc).isoformat()


async def init_conversation_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                thread_id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT 'New conversation',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        await db.commit()


async def create_conversation(thread_id: str, title: str = "New conversation"):
    now = current_time()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO conversations (thread_id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        """, (thread_id, title, now, now))
        await db.commit()

    return {
        "thread_id": thread_id,
        "title": title,
        "created_at": now,
        "updated_at": now
    }


async def list_conversations():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT thread_id, title, created_at, updated_at
            FROM conversations
            ORDER BY updated_at DESC
        """)

        rows = await cursor.fetchall()

    return [dict(row) for row in rows]


async def get_conversation(thread_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT thread_id, title, created_at, updated_at
            FROM conversations
            WHERE thread_id = ?
        """, (thread_id,))

        row = await cursor.fetchone()

    return dict(row) if row else None


async def rename_conversation(thread_id: str, title: str):
    now = current_time()

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            UPDATE conversations
            SET title = ?, updated_at = ?
            WHERE thread_id = ?
        """, (title, now, thread_id))

        await db.commit()

    return cursor.rowcount > 0


async def update_conversation_time(thread_id: str):
    now = current_time()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE conversations
            SET updated_at = ?
            WHERE thread_id = ?
        """, (now, thread_id))

        await db.commit()


async def delete_conversation(thread_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            DELETE FROM conversations
            WHERE thread_id = ?
        """, (thread_id,))

        await db.commit()

    return cursor.rowcount > 0
