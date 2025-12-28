# database.py
# Работа с базой данных SQLite для хранения данных трекера привычек

import aiosqlite
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)

# Путь к файлу БД
DB_PATH = Path(__file__).parent / "habits_tracker.db"


# ============================================================
# ИНИЦИАЛИЗАЦИЯ БД
# ============================================================
async def init_database():
    """Инициализирует базу данных: создает таблицы, если их нет"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Таблица tracker_entries - отметки привычек
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tracker_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                habit_id TEXT NOT NULL,
                date TEXT NOT NULL,
                status INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(chat_id, user_id, habit_id, date)
            )
        """)
        
        # Индекс для быстрого поиска по chat_id, user_id и date
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_user_date 
            ON tracker_entries(chat_id, user_id, date)
        """)
        
        # Таблица habits - метаданные привычек
        await db.execute("""
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                habit_id TEXT NOT NULL,
                emoji TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(chat_id, habit_id)
            )
        """)
        
        # Индекс для быстрого поиска по chat_id и habit_id
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_habit 
            ON habits(chat_id, habit_id)
        """)
        
        # Таблица users - метаданные пользователей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                emoji TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(chat_id, user_id)
            )
        """)
        
        # Индекс для быстрого поиска по chat_id и user_id
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_user 
            ON users(chat_id, user_id)
        """)
        
        await db.commit()
        logger.info("✅ База данных инициализирована")


# ============================================================
# РАБОТА С TRACKER_ENTRIES (отметки привычек)
# ============================================================
async def get_tracker_entry(
    chat_id: int, 
    user_id: int, 
    habit_id: str, 
    date: str
) -> Optional[int]:
    """
    Получает статус отметки привычки
    Возвращает: 1 (True/✅), 0 (False/⛔️), или None (🔘)
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT status FROM tracker_entries
            WHERE chat_id = ? AND user_id = ? AND habit_id = ? AND date = ?
        """, (chat_id, user_id, habit_id, date)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row["status"]
            return None


async def set_tracker_entry(
    chat_id: int,
    user_id: int,
    habit_id: str,
    date: str,
    status: Optional[bool]
) -> None:
    """
    Устанавливает или обновляет отметку привычки
    status: True (✅), False (⛔️), None (удаляет запись)
    """
    async with aiosqlite.connect(DB_PATH) as db:
        if status is None:
            # Удаляем запись, если status = None
            await db.execute("""
                DELETE FROM tracker_entries
                WHERE chat_id = ? AND user_id = ? AND habit_id = ? AND date = ?
            """, (chat_id, user_id, habit_id, date))
        else:
            # Вставляем или обновляем запись
            status_int = 1 if status else 0
            await db.execute("""
                INSERT INTO tracker_entries (chat_id, user_id, habit_id, date, status, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(chat_id, user_id, habit_id, date) 
                DO UPDATE SET status = ?, updated_at = CURRENT_TIMESTAMP
            """, (chat_id, user_id, habit_id, date, status_int, status_int))
        
        await db.commit()


async def get_tracker_entries_for_date_range(
    chat_id: int,
    date_start: str,
    date_end: str
) -> List[Tuple[int, str, str, Optional[int]]]:
    """
    Получает все отметки для группы в диапазоне дат
    Возвращает список кортежей: (user_id, habit_id, date, status)
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT user_id, habit_id, date, status
            FROM tracker_entries
            WHERE chat_id = ? AND date >= ? AND date <= ?
            ORDER BY user_id, habit_id, date
        """, (chat_id, date_start, date_end)) as cursor:
            rows = await cursor.fetchall()
            return [(row["user_id"], row["habit_id"], row["date"], row["status"]) for row in rows]


async def get_user_habits_for_chat(chat_id: int, user_id: int) -> List[str]:
    """
    Получает список habit_id для пользователя в группе
    """
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT DISTINCT habit_id
            FROM tracker_entries
            WHERE chat_id = ? AND user_id = ?
            ORDER BY habit_id
        """, (chat_id, user_id)) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]


# ============================================================
# РАБОТА С HABITS (метаданные привычек)
# ============================================================
async def get_habit(chat_id: int, habit_id: str) -> Optional[Dict[str, str]]:
    """
    Получает метаданные привычки
    Возвращает: {"emoji": "...", "name": "..."} или None
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT emoji, name FROM habits
            WHERE chat_id = ? AND habit_id = ?
        """, (chat_id, habit_id)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"emoji": row["emoji"], "name": row["name"]}
            return None


async def set_habit(
    chat_id: int,
    habit_id: str,
    emoji: str,
    name: str
) -> None:
    """
    Создает или обновляет метаданные привычки
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO habits (chat_id, habit_id, emoji, name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(chat_id, habit_id) 
            DO UPDATE SET emoji = ?, name = ?
        """, (chat_id, habit_id, emoji, name, emoji, name))
        await db.commit()


async def get_all_habits_for_chat(chat_id: int) -> Dict[str, Dict[str, str]]:
    """
    Получает все привычки для группы
    Возвращает: {habit_id: {"emoji": "...", "name": "..."}}
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT habit_id, emoji, name FROM habits
            WHERE chat_id = ?
            ORDER BY habit_id
        """, (chat_id,)) as cursor:
            rows = await cursor.fetchall()
            result = {}
            for row in rows:
                result[row["habit_id"]] = {
                    "emoji": row["emoji"],
                    "name": row["name"]
                }
            return result


# ============================================================
# РАБОТА С USERS (метаданные пользователей)
# ============================================================
async def get_user(chat_id: int, user_id: int) -> Optional[Dict[str, str]]:
    """
    Получает метаданные пользователя
    Возвращает: {"emoji": "...", "name": "..."} или None
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT emoji, name FROM users
            WHERE chat_id = ? AND user_id = ?
        """, (chat_id, user_id)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"emoji": row["emoji"], "name": row["name"]}
            return None


async def set_user(
    chat_id: int,
    user_id: int,
    emoji: str,
    name: str
) -> None:
    """
    Создает или обновляет метаданные пользователя
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (chat_id, user_id, emoji, name, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(chat_id, user_id) 
            DO UPDATE SET emoji = ?, name = ?, updated_at = CURRENT_TIMESTAMP
        """, (chat_id, user_id, emoji, name, emoji, name))
        await db.commit()


async def get_all_users_for_chat(chat_id: int) -> Dict[int, Dict[str, str]]:
    """
    Получает всех пользователей для группы
    Возвращает: {user_id: {"emoji": "...", "name": "..."}}
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT user_id, emoji, name FROM users
            WHERE chat_id = ?
            ORDER BY user_id
        """, (chat_id,)) as cursor:
            rows = await cursor.fetchall()
            result = {}
            for row in rows:
                result[row["user_id"]] = {
                    "emoji": row["emoji"],
                    "name": row["name"]
                }
            return result


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================
async def get_all_user_habits_for_chat(chat_id: int) -> Dict[int, List[str]]:
    """
    Получает все привычки для всех пользователей в группе
    Возвращает: {user_id: [habit_id, ...]}
    """
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT DISTINCT user_id, habit_id
            FROM tracker_entries
            WHERE chat_id = ?
            ORDER BY user_id, habit_id
        """, (chat_id,)) as cursor:
            rows = await cursor.fetchall()
            result = {}
            for row in rows:
                user_id = row[0]
                habit_id = row[1]
                if user_id not in result:
                    result[user_id] = []
                result[user_id].append(habit_id)
            return result

