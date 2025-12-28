# data.py
# Работа с данными трекера привычек через БД

from datetime import datetime, timedelta
import logging
from database import (
    init_database,
    set_habit, get_habit, get_all_habits_for_chat,
    set_user, get_user, get_all_users_for_chat,
    set_tracker_entry, get_tracker_entry, get_tracker_entries_for_date_range,
    get_user_habits_for_chat, get_all_user_habits_for_chat
)

logger = logging.getLogger(__name__)


# ============================================================
# ИНИЦИАЛИЗАЦИЯ ТЕСТОВЫХ ДАННЫХ
# ============================================================
async def init_test_data(chat_id: int):
    """Инициализирует тестовые данные для трекера в БД"""
    # Проверяем, есть ли уже данные в БД
    existing_habits = await get_all_habits_for_chat(chat_id)
    if existing_habits:
        logger.info(f"✅ Данные уже существуют для группы {chat_id}")
        return  # Данные уже инициализированы
    
    # Вымышленные user_id (позже будут заменены на реальные из Telegram)
    user1_id = 496486645  # 👨‍💻
    user2_id = 1821405712  # 👩‍🎨
    user3_id = 672221516  # 🤱
    user4_id = 5812633895  # 🧑‍🚀
    user5_id = 1069094241  # 👨‍🚒
    
    # Добавляем метаданные привычек
    await set_habit(chat_id, "meditation", "🧎", "Разминка")
    await set_habit(chat_id, "reading", "📚", "Чтение")
    await set_habit(chat_id, "sport", "🏋️", "отжимания")
    await set_habit(chat_id, "medicine", "💊", "Лекарство")
    await set_habit(chat_id, "milk", "🥛", "вода")
    await set_habit(chat_id, "walk", "🚶‍♀️", "Прогулка")
    await set_habit(chat_id, "dance", "🕺", "Брейк")
    await set_habit(chat_id, "positive", "👍", "Позитив")
    
    # Добавляем метаданные пользователей
    await set_user(chat_id, user1_id, "👨‍💻", "Дима")
    await set_user(chat_id, user2_id, "👩‍🎨", "Лиза")
    await set_user(chat_id, user3_id, "🤱", "Мама")
    await set_user(chat_id, user4_id, "🧑‍🚀", "Саша")
    await set_user(chat_id, user5_id, "👨‍🚒", "Папа")
    
    # Инициализируем структуру привычек для пользователей
    # Создаем записи для всех дат в диапазоне (7 дней вперед) с status=False
    # Это позволит видеть структуру привычек в статистике
    # 👨‍💻 - 3 привычки: 🧎, 📚, 🏋️
    # 👩‍🎨 - 3 привычки: 💊, 🏋️, 🥛
    # 🤱 - 3 привычки: 🚶‍♀️, 📚, 🥛
    # 🧑‍🚀 - 3 привычки: 📚, 🏋️, 🕺
    # 👨‍🚒 - 1 привычка: 👍
    
    today = datetime.now().date()
    dates = []
    for i in range(7):  # 7 дней вперед
        date = today + timedelta(days=i)
        dates.append(date.strftime("%Y-%m-%d"))
    
    # 👨‍💻 - 3 привычки
    for date in dates:
        await set_tracker_entry(chat_id, user1_id, "meditation", date, False)
        await set_tracker_entry(chat_id, user1_id, "reading", date, False)
        await set_tracker_entry(chat_id, user1_id, "sport", date, False)
    
    # 👩‍🎨 - 3 привычки
    for date in dates:
        await set_tracker_entry(chat_id, user2_id, "medicine", date, False)
        await set_tracker_entry(chat_id, user2_id, "sport", date, False)
        await set_tracker_entry(chat_id, user2_id, "milk", date, False)
    
    # 🤱 - 3 привычки
    for date in dates:
        await set_tracker_entry(chat_id, user3_id, "walk", date, False)
        await set_tracker_entry(chat_id, user3_id, "reading", date, False)
        await set_tracker_entry(chat_id, user3_id, "milk", date, False)
    
    # 🧑‍🚀 - 3 привычки
    for date in dates:
        await set_tracker_entry(chat_id, user4_id, "reading", date, False)
        await set_tracker_entry(chat_id, user4_id, "sport", date, False)
        await set_tracker_entry(chat_id, user4_id, "dance", date, False)
    
    # 👨‍🚒 - 1 привычка
    for date in dates:
        await set_tracker_entry(chat_id, user5_id, "positive", date, False)
    
    logger.info(f"✅ Тестовые данные инициализированы для группы {chat_id}")


# ============================================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С ДАННЫМИ (обертки над БД)
# ============================================================
async def get_tracker_data_for_chat(chat_id: int, date_start: str, date_end: str):
    """
    Получает данные трекера для группы в формате старой структуры:
    {user_id: {habit_id: {date: status}}}
    """
    # Получаем все записи из БД
    entries = await get_tracker_entries_for_date_range(chat_id, date_start, date_end)
    
    # Получаем всех пользователей и их привычки из записей
    all_user_habits = await get_all_user_habits_for_chat(chat_id)
    
    # Формируем структуру данных
    result = {}
    for user_id, habit_list in all_user_habits.items():
        result[user_id] = {}
        for habit_id in habit_list:
            result[user_id][habit_id] = {}
            # Заполняем статусы из БД
            for user_id_db, habit_id_db, date, status in entries:
                if user_id_db == user_id and habit_id_db == habit_id:
                    # Конвертируем status: 1 -> True, 0 -> False
                    # Если записи нет, status будет None (🔘)
                    status_bool = None if status is None else (status == 1)
                    result[user_id][habit_id][date] = status_bool
    
    return result


async def get_habits_metadata_for_chat(chat_id: int):
    """
    Получает метаданные привычек для группы
    Возвращает: {habit_id: {"emoji": "...", "name": "..."}}
    """
    return await get_all_habits_for_chat(chat_id)


async def get_users_metadata_for_chat(chat_id: int):
    """
    Получает метаданные пользователей для группы
    Возвращает: {user_id: {"emoji": "...", "name": "..."}}
    """
    return await get_all_users_for_chat(chat_id)


async def mark_habit(chat_id: int, user_id: int, habit_id: str, date: str, status: bool):
    """
    Отмечает привычку (True = ✅, False = ⛔️)
    """
    await set_tracker_entry(chat_id, user_id, habit_id, date, status)


async def get_habit_status(chat_id: int, user_id: int, habit_id: str, date: str):
    """
    Получает статус привычки
    Возвращает: True (✅), False (⛔️), или None (🔘)
    """
    status_int = await get_tracker_entry(chat_id, user_id, habit_id, date)
    if status_int is None:
        return None
    return status_int == 1


async def get_user_habits(chat_id: int, user_id: int):
    """
    Получает список habit_id для пользователя
    """
    return await get_user_habits_for_chat(chat_id, user_id)
