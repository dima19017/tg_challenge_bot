# main.py

import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, BotCommand
from dotenv import load_dotenv
import os
from pathlib import Path
from data import init_test_data, tracker_data, habits_metadata, users_metadata

# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================
# Загрузка .env файла из родительской директории
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота
BOT_TOKEN = os.getenv('BOT_CHALLENGE_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_CHALLENGE_TOKEN не найден в .env файле")

bot = Bot(token=BOT_TOKEN)
# Инициализация FSM storage (хранилище состояний в памяти)
storage = MemoryStorage()
# Инициализация маршрутизатора сообщений и событий
dp = Dispatcher(storage=storage)

# ============================================================
# КЛАВИАТУРА (ВСЕГДА ДОСТУПНА)
# ============================================================
def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Главная клавиатура с основными кнопками"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="✅ Отметить привычку"),
                KeyboardButton(text="📊 Мои привычки")
            ],
            [
                KeyboardButton(text="📈 Статистика"),
                KeyboardButton(text="📋 Список привычек")
            ],
            [
                KeyboardButton(text="ℹ️ Помощь")
            ]
        ],
        resize_keyboard=True,  # Автоматически подстраивает размер кнопок
        input_field_placeholder="Выбери действие на клавиатуре..."
    )
    return keyboard

# ============================================================
# ОБРАБОТЧИКИ КОМАНД
# ============================================================
@dp.message(Command('start'))
async def start(message: types.Message):
    await message.answer(
        "👋 Привет! Это бот для семейного челленджа!\n\n"
        "💡 Используй кнопки ниже для навигации.\n"
        "Все действия можно выполнить одним нажатием!",
        reply_markup=get_main_keyboard()
    )
    
    # Инициализируем тестовые данные для группы
    if message.chat.type in ['group', 'supergroup']:
        init_test_data(message.chat.id)

@dp.message(Command('help'))
async def help(message: types.Message):
    await message.answer(
        "📖 Помощь:\n\n"
        "Используй кнопки на клавиатуре для навигации:\n"
        "• ✅ Отметить привычку - отметить выполнение\n"
        "• 📊 Мои привычки - посмотреть свои привычки\n"
        "• 📈 Статистика - посмотреть статистику\n"
        "• 📋 Список привычек - список всех привычек\n"
        "• ℹ️ Помощь - показать эту справку",
        reply_markup=get_main_keyboard()
    )

@dp.message(Command('my_id'))
async def my_id(message: types.Message):
    """Показывает ID пользователя для заполнения данных"""
    user_info = (
        f"👤 Информация о тебе:\n\n"
        f"🆔 User ID: <code>{message.from_user.id}</code>\n"
        f"👤 Имя: {message.from_user.full_name}\n"
        f"📱 Username: @{message.from_user.username or 'не указан'}\n\n"
        f"💡 Используй этот User ID для заполнения данных в data.py"
    )
    await message.answer(user_info, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(Command('get_members'))
async def get_members(message: types.Message):
    """Собирает информацию о всех участниках группы (только для групп)"""
    if message.chat.type not in ['group', 'supergroup']:
        await message.answer(
            "❌ Эта команда работает только в группах!",
            reply_markup=get_main_keyboard()
        )
        return
    
    try:
        # Получаем список администраторов группы
        admins = await bot.get_chat_administrators(chat_id=message.chat.id)
        
        members_info = "👥 Участники группы:\n\n"
        
        # Собираем информацию об администраторах
        for admin in admins:
            user = admin.user
            members_info += (
                f"👤 {user.full_name}\n"
                f"   🆔 ID: <code>{user.id}</code>\n"
                f"   📱 @{user.username or 'нет username'}\n\n"
            )
        
        # Если участников много, можно добавить информацию о других участниках
        # Но для этого нужно, чтобы они написали в группе
        
        members_info += (
            "💡 Чтобы получить ID других участников:\n"
            "• Попроси их написать /my_id в группе\n"
            "• Или используй их ID из сообщений в группе"
        )
        
        await message.answer(members_info, parse_mode="HTML", reply_markup=get_main_keyboard())
        logger.info(f"✅ Список участников отправлен для группы {message.chat.id}")
    except Exception as e:
        await message.answer(
            f"❌ Ошибка получения участников: {str(e)}\n\n"
            f"💡 Убедись, что бот является администратором группы",
            reply_markup=get_main_keyboard()
        )
        logger.error(f"❌ Ошибка получения участников: {e}")

# ============================================================
# ОБРАБОТЧИКИ КНОПОК КЛАВИАТУРЫ
# ============================================================
@dp.message(F.text == "✅ Отметить привычку")
async def mark_habit(message: types.Message):
    """Обработчик кнопки 'Отметить привычку'"""
    await message.answer(
        "✅ Отметить привычку\n\n"
        "💡 Функционал в разработке...",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "📊 Мои привычки")
async def my_habits(message: types.Message):
    """Обработчик кнопки 'Мои привычки'"""
    await message.answer(
        "📊 Мои привычки\n\n"
        "💡 Функционал в разработке...",
        reply_markup=get_main_keyboard()
    )

# ============================================================
# ФУНКЦИИ ДЛЯ РАБОТЫ СО СТАТИСТИКОЙ
# ============================================================
def generate_statistics_text(chat_id: int) -> str:
    """Генерирует текст статистики в моноширинном формате"""
    from datetime import datetime, timedelta
    
    # Инициализируем данные, если еще не инициализированы
    init_test_data(chat_id)

    months_ru = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
        5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
        9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
    }
    month_num = datetime.now().month
    month_name = months_ru.get(month_num, "Месяц")

    # Формируем заголовок
    header_lines = [
        "календарь",
        f"месяц: {month_name}"
    ]

    # Строка с эмодзи пользователей (повторенные по количеству привычек)
    users_emoji_line_parts = ["  "]  # 2 пробела в начале
    if chat_id in tracker_data and chat_id in users_metadata:
        for user_id, habits_data in sorted(tracker_data[chat_id].items()):
            user_emoji = users_metadata[chat_id].get(user_id, {}).get("emoji", "❓")
            num_habits = len(habits_data)
            # Повторяем эмодзи пользователя столько раз, сколько у него привычек
            users_emoji_line_parts.append(user_emoji * num_habits)
    header_lines.append("".join(users_emoji_line_parts))

    # Строка с эмодзи привычек (в том же порядке, что и пользователи)
    # Сохраняем порядок привычек для использования в строках с датами
    habits_order = []  # Список кортежей (user_id, habit_id) в порядке отображения
    habits_emoji_line_parts = ["  "]  # 2 пробела в начале
    if chat_id in tracker_data and chat_id in habits_metadata:
        for user_id, habits_data in sorted(tracker_data[chat_id].items()):
            # Для каждого пользователя выводим все его привычки по порядку
            for habit_id in sorted(habits_data.keys()):
                habits_order.append((user_id, habit_id))
                habit_emoji = habits_metadata[chat_id].get(habit_id, {}).get("emoji", "❓")
                habits_emoji_line_parts.append(habit_emoji)
    header_lines.append("".join(habits_emoji_line_parts))

    # Создаем список из 7 дат: от (сегодня - 6) до (сегодня)
    today = datetime.now().date()
    date_list = []
    for i in range(7):
        date = today - timedelta(days=6-i)  # От -6 до 0 (сегодня)
        date_list.append(date.strftime("%Y-%m-%d"))

    # Строки с датами и статусами (7 строк)
    date_rows = []
    for date_str in date_list:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day = date_obj.day
        
        # Формируем строку: число дня + статусы для всех привычек
        row_parts = [str(day)]
        
        # Добавляем статусы для всех привычек в том же порядке, что и в строке 4
        if chat_id in tracker_data:
            for user_id, habit_id in habits_order:
                dates_status = tracker_data[chat_id].get(user_id, {}).get(habit_id, {})
                status = dates_status.get(date_str)
                if status is True:
                    row_parts.append("✅")
                elif status is False:
                    row_parts.append("⛔️")
                else:
                    row_parts.append("🔘")
        
        date_rows.append("".join(row_parts))
    
    full_text = "\n".join(header_lines + date_rows)
    return f"<pre>{full_text}</pre>"

# Храним ID закрепленного сообщения со статистикой для каждой группы
stats_message_id = {}

async def update_statistics_message(chat_id: int):
    """Обновляет или создает сообщение со статистикой"""
    stats_text = generate_statistics_text(chat_id)
    
    try:
        if chat_id in stats_message_id:
            # Удаляем старое сообщение со статистикой
            try:
                await bot.delete_message(
                    chat_id=chat_id,
                    message_id=stats_message_id[chat_id]
                )
                logger.info(f"✅ Старое сообщение со статистикой удалено для группы {chat_id}")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось удалить старое сообщение: {e}")
        
        # Создаем новое сообщение со статистикой
        await create_statistics_message(chat_id, stats_text)
    except Exception as e:
        logger.error(f"❌ Ошибка обновления статистики: {e}")

async def create_statistics_message(chat_id: int, stats_text: str):
    """Создает новое сообщение со статистикой и закрепляет его"""
    try:
        # Отправляем сообщение
        sent_message = await bot.send_message(
            chat_id=chat_id,
            text=stats_text,
            parse_mode="HTML"
        )
        
        # Закрепляем сообщение
        # try:
        #     await bot.pin_chat_message(
        #         chat_id=chat_id,
        #         message_id=sent_message.message_id,
        #         disable_notification=True
        #     )
        # except Exception as e:
        #     logger.warning(f"⚠️ Не удалось закрепить сообщение (нужны права администратора): {e}")
        
        # Сохраняем ID сообщения
        stats_message_id[chat_id] = sent_message.message_id
        logger.info(f"✅ Статистика создана для группы {chat_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка создания статистики: {e}")

@dp.message(F.text == "📈 Статистика")
async def statistics(message: types.Message):
    """Обработчик кнопки 'Статистика'"""
    if message.chat.type not in ['group', 'supergroup']:
        await message.answer(
            "❌ Статистика работает только в группах!\n"
            "Добавь бота в группу для использования.",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Инициализируем данные, если еще не инициализированы
    init_test_data(message.chat.id)
    
    # Удаляем сообщение пользователя
    try:
        await bot.delete_message(
            chat_id=message.chat.id,
            message_id=message.message_id
        )
    except Exception as e:
        logger.warning(f"⚠️ Не удалось удалить сообщение пользователя: {e}")
    
    # Обновляем статистику (функция сама удалит старое сообщение, если оно есть)
    await update_statistics_message(message.chat.id)

@dp.message(F.text == "📋 Список привычек")
async def list_habits(message: types.Message):
    """Обработчик кнопки 'Список привычек'"""
    await message.answer(
        "📋 Список привычек\n\n"
        "💡 Функционал в разработке...",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "ℹ️ Помощь")
async def help_button(message: types.Message):
    """Обработчик кнопки 'Помощь'"""
    await help(message)  # Используем ту же функцию, что и для команды /help

# ============================================================
# ГЛАВНАЯ ФУНКЦИЯ - ЗАПУСК БОТА
# ============================================================
async def main():
    """Главная функция - запускает бота"""
    logger.info('🚀 Challenge бот запущен!')
    
    # ============================================================
    # НАСТРОЙКА BOT COMMANDS MENU (ЗАКОММЕНТИРОВАНО)
    # ============================================================
    # Раскомментируй, если хочешь включить меню команд рядом с вложениями (📎)
    # Это меню показывает список команд бота при нажатии на кнопку рядом с вложениями
    #
    # commands = [
    #     BotCommand(command="start", description="🚀 Начать работу с ботом"),
    #     BotCommand(command="help", description="📖 Показать справку"),
    # ]
    # await bot.set_my_commands(commands)
    # logger.info('✅ Bot Commands Menu настроено')
    #
    # Если меню уже настроено и хочешь его отключить, раскомментируй следующую строку:
    # await bot.set_my_commands([])  # Очищает список команд (отключает меню)
    
    try:
        # бот периодически запрашивает обновления у Telegram
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        logger.info('🛑 Бот остановлен')

if __name__ == '__main__':
    asyncio.run(main())
