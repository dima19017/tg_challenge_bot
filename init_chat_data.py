# init_chat_data.py
# Скрипт для инициализации данных для конкретного чата

import asyncio
import logging
from datetime import datetime, timedelta
from database import init_database, set_habit, set_user, set_tracker_entry

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def init_chat_data():
    """Инициализирует данные для чата -1003536850626"""
    # Инициализируем БД (создаем таблицы, если их нет)
    await init_database()
    logger.info("✅ База данных инициализирована")
    
    chat_id = -1003536850626
    
    # Пользователи
    user1_id = 1821405712  # dima
    user2_id = 496486645  # пупсень
    
    # Добавляем метаданные привычек
    await set_habit(chat_id, "warmup", "🧎", "Разминка")
    await set_habit(chat_id, "reading", "📚", "Чтение")
    await set_habit(chat_id, "running", "🏃", "Бег")
    await set_habit(chat_id, "herbs", "🌿", "Трава")
    await set_habit(chat_id, "water", "💧", "Вода")
    logger.info("✅ Метаданные привычек добавлены")
    
    # Добавляем метаданные пользователей
    await set_user(chat_id, user1_id, "👨", "dima")
    await set_user(chat_id, user2_id, "👶", "пупсень")
    logger.info("✅ Метаданные пользователей добавлены")
    
    # Создаем записи для всех дат (7 дней вперед) со статусом False
    today = datetime.now().date()
    dates = []
    for i in range(7):  # 7 дней вперед
        date = today + timedelta(days=i)
        dates.append(date.strftime("%Y-%m-%d"))
    
    # dima - 3 привычки: разминка, чтение, бег
    for date in dates:
        await set_tracker_entry(chat_id, user1_id, "warmup", date, False)
        await set_tracker_entry(chat_id, user1_id, "reading", date, False)
        await set_tracker_entry(chat_id, user1_id, "running", date, False)
    
    # пупсень - 2 привычки: трава, вода
    for date in dates:
        await set_tracker_entry(chat_id, user2_id, "herbs", date, False)
        await set_tracker_entry(chat_id, user2_id, "water", date, False)
    
    logger.info("✅ Записи трекера созданы для всех дат")
    
    print("\n" + "="*50)
    print("✅ Данные успешно инициализированы!")
    print("="*50)
    print(f"\n📊 Chat ID: {chat_id}")
    print("\n👤 Пользователи:")
    print(f"  👨 dima ({user1_id}) - 3 привычки:")
    print(f"     🧎 Разминка")
    print(f"     📚 Чтение")
    print(f"     🏃 Бег")
    print(f"\n  👶 пупсень ({user2_id}) - 2 привычки:")
    print(f"     🌿 Трава")
    print(f"     💧 Вода")
    print(f"\n📅 Созданы записи на 7 дней вперед (со статусом ⛔️)")


if __name__ == '__main__':
    asyncio.run(init_chat_data())

