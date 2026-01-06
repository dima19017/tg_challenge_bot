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
from database import (
    init_database,
    init_test_data,
    get_tracker_data_for_chat,
    get_all_habits_for_chat,
    get_all_users_for_chat,
    set_tracker_entry,
    get_user_habits_for_chat
)

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
def get_main_keyboard(selective: bool = True) -> ReplyKeyboardMarkup:
    """Главная клавиатура с основными кнопками"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="✅ Отметить привычку"),
                # KeyboardButton(text="📊 Мои привычки")
            ],
            [
                KeyboardButton(text="📈 Статистика"),
                # KeyboardButton(text="📋 Список привычек")
            ],
            # [
            #     KeyboardButton(text="ℹ️ Помощь")
            # ]
        ],
        resize_keyboard=True,  # Автоматически подстраивает размер кнопок
        selective=selective,  # По умолчанию показывать только запросившему пользователю
        input_field_placeholder="Выбери действие на клавиатуре..."
    )
    return keyboard

async def get_habits_keyboard(user_id: int, chat_id: int, selective: bool = True) -> ReplyKeyboardMarkup:
    """Генерирует клавиатуру с привычками пользователя"""
    keyboard_buttons = []
    
    # Получаем привычки пользователя из БД
    user_habits = await get_user_habits_for_chat(chat_id, user_id)
    
    if not user_habits:
        # Если у пользователя нет привычек, возвращаем пустую клавиатуру с кнопкой "Назад"
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🔙 Назад")]],
            resize_keyboard=True,
            selective=selective  # Показывать только запросившему пользователю
        )
    
    # Получаем метаданные привычек
    habits_meta = await get_all_habits_for_chat(chat_id)

    # Получаем статусы привычек за сегодня, чтобы подсветить состояние на кнопках
    from datetime import datetime
    today_str = datetime.now().date().strftime("%Y-%m-%d")
    tracker_today = await get_tracker_data_for_chat(chat_id, today_str, today_str)

    # Проверяем, выполнены ли все привычки пользователя на сегодня
    all_completed = False
    if user_habits:
        user_today_data = tracker_today.get(user_id, {})
        completed_flags = []
        for habit_id in user_habits:
            status = user_today_data.get(habit_id, {}).get(today_str)
            completed_flags.append(status is True)
        all_completed = bool(completed_flags) and all(completed_flags)
    
    # Добавляем верхнюю подсказку-заглушку
    hint_text = "🎉 Все привычки выполнены на сегодня!" if all_completed else "ℹ️ Отметь одну из привычек ниже"
    keyboard_buttons.append([KeyboardButton(text=hint_text)])

    # Создаем кнопки для каждой привычки
    for habit_id in sorted(user_habits):
        habit_info = habits_meta.get(habit_id, {})
        emoji = habit_info.get("emoji", "❓")
        name = habit_info.get("name", habit_id)

        # Определяем статус привычки на сегодня:
        # True  -> выполнена ✅
        # False/None/отсутствует -> ещё не выполнена 🔘
        status_map_for_user = tracker_today.get(user_id, {})
        status_for_habit = status_map_for_user.get(habit_id, {}).get(today_str)
        status_emoji = "✅" if status_for_habit is True else "🔘"

        # Формат кнопки: "🧎 Медитация ✅/🔘"
        button_text = f"{emoji} {name} {status_emoji}"
        keyboard_buttons.append([KeyboardButton(text=button_text)])
    
    # Добавляем кнопку "Назад"
    keyboard_buttons.append([KeyboardButton(text="🔙 Назад")])
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=keyboard_buttons,
        resize_keyboard=True,
        selective=selective,  # Показывать только запросившему пользователю
        input_field_placeholder="Выбери привычку для отметки..."
    )
    return keyboard

# ============================================================
# ОБРАБОТЧИКИ КОМАНД
# ============================================================
@dp.message(Command('start'))
async def start(message: types.Message):
    """
    Обработчик /start:
    - в группе: инициализирует данные, удаляет команду пользователя и показывает статистику как единственное постоянное сообщение
    - в личке: показывает краткое приветствие с клавиатурой
    """
    chat_id = message.chat.id

    if message.chat.type in ['group', 'supergroup']:
        # Инициализируем тестовые данные для группы (если ещё не инициализированы)
        await init_test_data(chat_id)

        # Удаляем сообщение пользователя с /start
        try:
            await bot.delete_message(
                chat_id=chat_id,
                message_id=message.message_id
            )
        except Exception as e:
            logger.warning(f"⚠️ Не удалось удалить сообщение пользователя: {e}")

        # Обновляем/создаём сообщение со статистикой (старое сообщение будет удалено внутри)
        await update_statistics_message(chat_id)
    else:
        # Для личных чатов оставим нормальное приветствие с клавиатурой
        await message.answer(
            "👋 Привет! Это бот для семейного челленджа!\n\n"
            "Добавь меня в семейную группу, чтобы вести общий трекер привычек.\n"
            "В группе используй кнопки для отметки привычек и просмотра статистики.",
            reply_markup=get_main_keyboard(selective=True),
            disable_notification=True
        )

@dp.message(Command('help'))
async def help(message: types.Message):
    await message.reply(
        "📖 Помощь:\n\n"
        "Используй кнопки на клавиатуре для навигации:\n"
        "• ✅ Отметить привычку - отметить выполнение\n"
        # "• 📊 Мои привычки - посмотреть свои привычки\n"
        "• 📈 Статистика - посмотреть статистику\n",
        # "• 📋 Список привычек - список всех привычек\n"
        # "• ℹ️ Помощь - показать эту справку",
        reply_markup=get_main_keyboard(selective=True),
        disable_notification=True
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
    await message.reply(user_info, parse_mode="HTML", reply_markup=get_main_keyboard(selective=True),disable_notification=True)

@dp.message(Command('chat_id'))
async def chat_id_command(message: types.Message):
    """Показывает ID чата (группы или личного чата)"""
    chat_type_emoji = {
        'private': '👤',
        'group': '👥',
        'supergroup': '👥',
        'channel': '📢'
    }
    chat_type_names = {
        'private': 'Личный чат',
        'group': 'Группа',
        'supergroup': 'Супергруппа',
        'channel': 'Канал'
    }
    
    emoji = chat_type_emoji.get(message.chat.type, '💬')
    type_name = chat_type_names.get(message.chat.type, 'Неизвестно')
    
    chat_info = (
        f"{emoji} Информация о чате:\n\n"
        f"🆔 Chat ID: <code>{message.chat.id}</code>\n"
        f"📝 Тип: {type_name}\n"
        f"📛 Название: {message.chat.title or message.chat.first_name or 'Не указано'}\n"
    )
    
    if message.chat.type in ['group', 'supergroup']:
        chat_info += (
            f"\n💡 Этот Chat ID нужен для:\n"
            f"• Заполнения данных через команду /init_data\n"
            f"• Использования скрипта init_chat_data.py для инициализации конкретного чата\n"
            f"• Настройки бота для этой группы"
        )
    
    await message.reply(chat_info, parse_mode="HTML", reply_markup=get_main_keyboard(selective=True), disable_notification=True)
    logger.info(f"✅ Chat ID показан: {message.chat.id} ({message.chat.type})")

@dp.message(Command('get_members'))
async def get_members(message: types.Message):
    """Собирает информацию о всех участниках группы (только для групп)"""
    if message.chat.type not in ['group', 'supergroup']:
        await message.reply(
            "❌ Эта команда работает только в группах!",
            reply_markup=get_main_keyboard(selective=True),
            disable_notification=True
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
        
        await message.reply(members_info, parse_mode="HTML", reply_markup=get_main_keyboard(selective=True), disable_notification=True)
        logger.info(f"✅ Список участников отправлен для группы {message.chat.id}")
    except Exception as e:
        await message.reply(
            f"❌ Ошибка получения участников: {str(e)}\n\n"
            f"💡 Убедись, что бот является администратором группы",
            reply_markup=get_main_keyboard(selective=True),
            disable_notification=True
        )
        logger.error(f"❌ Ошибка получения участников: {e}")

@dp.message(Command('init_data'))
async def init_data_command(message: types.Message):
    """Инициализирует тестовые данные для группы"""
    if message.chat.type not in ['group', 'supergroup']:
        await message.reply(
            "❌ Эта команда работает только в группах!",
            reply_markup=get_main_keyboard(selective=True),
            disable_notification=True
        )
        return
    
    try:
        chat_id = message.chat.id
        await message.reply(
            "⏳ Инициализирую данные для группы...",
            reply_markup=get_main_keyboard(selective=True),
            disable_notification=True
        )
        
        await init_test_data(chat_id)
        
        await message.reply(
            "✅ Данные успешно инициализированы!\n\n"
            "Добавлены следующие пользователи:\n"
            "👨‍💻 Дима - 3 привычки\n"
            "👩‍🎨 Лиза - 3 привычки\n"
            "🤱 Мама - 3 привычки\n"
            "🧑‍🚀 Саша - 3 привычки\n"
            "👨‍🚒 Папа - 1 привычка\n\n"
            "💡 Теперь можно использовать кнопку '📈 Статистика' для просмотра трекера.",
            reply_markup=get_main_keyboard(selective=True),
            disable_notification=True
        )
        logger.info(f"✅ Данные инициализированы для группы {chat_id}")
    except Exception as e:
        await message.reply(
            f"❌ Ошибка инициализации данных: {str(e)}",
            reply_markup=get_main_keyboard(selective=True),
            disable_notification=True
        )
        logger.error(f"❌ Ошибка инициализации данных: {e}")

# ============================================================
# ОБРАБОТЧИКИ КНОПОК КЛАВИАТУРЫ
# ============================================================
@dp.message(F.text == "✅ Отметить привычку")
async def mark_habit(message: types.Message):
    """Обработчик кнопки 'Отметить привычку'"""
    if message.chat.type not in ['group', 'supergroup']:
        await message.reply(
            "❌ Отметка привычек работает только в группах!\n"
            "Добавь бота в группу для использования.",
            reply_markup=get_main_keyboard(selective=True),
            disable_notification=True
        )
        return
    
    # Инициализируем данные, если еще не инициализированы
    await init_test_data(message.chat.id)
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверяем, есть ли пользователь в данных
    user_habits = await get_user_habits_for_chat(chat_id, user_id)
    if not user_habits:
        await message.reply(
            "❌ Твои привычки еще не настроены.\n"
            "Обратись к администратору группы.",
            reply_markup=get_main_keyboard(selective=True),
            disable_notification=True
        )
        return
    
    # Удаляем предыдущее сообщение "Выбери привычку", если оно есть
    if chat_id in habit_selection_message_id and user_id in habit_selection_message_id[chat_id]:
        try:
            await bot.delete_message(
                chat_id=chat_id,
                message_id=habit_selection_message_id[chat_id][user_id]
            )
        except Exception as e:
            logger.warning(f"⚠️ Не удалось удалить предыдущее сообщение выбора привычки: {e}")
    
    # Показываем клавиатуру с привычками пользователя
    # Используем selective=True и reply_to_message_id, чтобы клавиатура показывалась только запросившему пользователю
    habits_kb = await get_habits_keyboard(user_id, chat_id, selective=True)
    sent_message = await message.reply(
        "✅ Выбери привычку для отметки:",
        reply_markup=habits_kb,
        disable_notification=True
    )
    
    # Удаляем сообщение пользователя после отправки ответа (чтобы selective работал)
    try:
        await bot.delete_message(
            chat_id=chat_id,
            message_id=message.message_id
        )
    except Exception as e:
        logger.warning(f"⚠️ Не удалось удалить сообщение пользователя: {e}")
    
    # Сохраняем ID сообщения для последующего удаления
    if chat_id not in habit_selection_message_id:
        habit_selection_message_id[chat_id] = {}
    habit_selection_message_id[chat_id][user_id] = sent_message.message_id

@dp.message(F.text == "🔙 Назад")
async def back_to_main(message: types.Message):
    """Обработчик кнопки 'Назад' - возвращает главную клавиатуру"""
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    # Удаляем сообщение пользователя
    try:
        await bot.delete_message(
            chat_id=chat_id,
            message_id=message.message_id
        )
    except Exception as e:
        logger.warning(f"⚠️ Не удалось удалить сообщение пользователя: {e}")
    
    # Удаляем сообщение "Выбери привычку для отметки", если оно есть
    if chat_id in habit_selection_message_id and user_id in habit_selection_message_id[chat_id]:
        try:
            await bot.delete_message(
                chat_id=chat_id,
                message_id=habit_selection_message_id[chat_id][user_id]
            )
            del habit_selection_message_id[chat_id][user_id]
        except Exception as e:
            logger.warning(f"⚠️ Не удалось удалить сообщение выбора привычки: {e}")
    
    # Отправляем сообщение без уведомлений и удаляем его
    sent_message = await message.reply(
        "🔙 Возврат в главное меню",
        reply_markup=get_main_keyboard(selective=True),
        disable_notification=True
    )
    
    # Удаляем сообщение через небольшую задержку
    async def delete_after_delay():
        await asyncio.sleep(2)  # Задержка 2 секунды
        try:
            await bot.delete_message(
                chat_id=chat_id,
                message_id=sent_message.message_id
            )
        except Exception as e:
            logger.warning(f"⚠️ Не удалось удалить сообщение 'Возврат в главное меню': {e}")
    
    asyncio.create_task(delete_after_delay())


@dp.message(F.text.in_(["ℹ️ Отметь одну из привычек ниже", "🎉 Все привычки выполнены на сегодня!"]))
async def ignore_habits_hint(message: types.Message):
    """
    Заглушка в клавиатуре привычек: делаем кнопку визуальной,
    но при нажатии просто удаляем сообщение пользователя и ничего не отвечаем.
    """
    try:
        await bot.delete_message(
            chat_id=message.chat.id,
            message_id=message.message_id
        )
    except Exception as e:
        logger.warning(f"⚠️ Не удалось удалить сообщение с подсказкой: {e}")

@dp.message(lambda message: message.text and " " in message.text and 
             message.text not in ["✅ Отметить привычку", "📈 Статистика", "🔙 Назад",
                                  "ℹ️ Отметь одну из привычек ниже", "🎉 Все привычки выполнены на сегодня!"])
async def mark_habit_button(message: types.Message):
    """Обработчик нажатия на кнопку привычки (универсальный - работает с любыми эмодзи из БД)"""
    if message.chat.type not in ['group', 'supergroup']:
        # Игнорируем, если это не группа
        return
    
    # Проверяем формат кнопки: должна содержать пробел (эмодзи + название)
    button_text = message.text
    if " " not in button_text:
        # Это не кнопка привычки, игнорируем
        return
    
    # Инициализируем данные, если еще не инициализированы
    await init_test_data(message.chat.id)
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверяем, есть ли пользователь в данных
    user_habits = await get_user_habits_for_chat(chat_id, user_id)
    if not user_habits:
        await message.reply(
            "❌ Твои привычки еще не настроены.",
            reply_markup=get_main_keyboard(selective=True),
            disable_notification=True
        )
        return
    
    # Парсим текст кнопки: "🧎 Медитация" -> эмодзи и название
    # Разделяем по первому пробелу
    parts = button_text.split(" ", 2)
    if len(parts) != 3:
        # await message.reply(
        #     "❌ Ошибка определения привычки.",
        #     reply_markup=get_main_keyboard(selective=True),
        #     disable_notification=True
        # )
        return
    
    emoji = parts[0]
    habit_name = parts[1]
    
    # Находим habit_id по эмодзи и названию
    habits_meta = await get_all_habits_for_chat(chat_id)
    habit_id = None
    
    for hid, info in habits_meta.items():
        if info.get("emoji") == emoji and info.get("name") == habit_name:
            habit_id = hid
            break
    
    if not habit_id:
        # await message.reply(
        #     "❌ Привычка не найдена.",
        #     reply_markup=get_main_keyboard(selective=True),
        #     disable_notification=True
        # )
        return
    
    # Проверяем, есть ли эта привычка у пользователя
    if habit_id not in user_habits:
        # await message.reply(
        #     "❌ У тебя нет такой привычки.",
        #     reply_markup=get_main_keyboard(selective=True),
        #     disable_notification=True
        # )
        return
    
    # Отмечаем привычку для текущей даты
    from datetime import datetime
    today_str = datetime.now().date().strftime("%Y-%m-%d")
    
    # Сохраняем в БД (True - выполнено)
    await set_tracker_entry(chat_id, user_id, habit_id, today_str, True)
    
    # Удаляем сообщение "Выбери привычку для отметки", если оно есть
    if chat_id in habit_selection_message_id and user_id in habit_selection_message_id[chat_id]:
        try:
            await bot.delete_message(
                chat_id=chat_id,
                message_id=habit_selection_message_id[chat_id][user_id]
            )
            # Удаляем из словаря
            del habit_selection_message_id[chat_id][user_id]
        except Exception as e:
            logger.warning(f"⚠️ Не удалось удалить сообщение выбора привычки: {e}")
    
    # Обновляем статистику (это создаст новое сообщение со статистикой)
    await update_statistics_message(chat_id)
    
    # Получаем информацию о пользователе для отображения
    users_meta = await get_all_users_for_chat(chat_id)
    user_info = users_meta.get(user_id, {})
    user_name = user_info.get("name", message.from_user.full_name or "Пользователь")
    user_emoji = user_info.get("emoji", "👤")
    
    # Отправляем подтверждение как reply на сообщение пользователя (selective=True работает только с reply на сообщение пользователя)
    await message.reply(
        f"✅ {user_emoji} {user_name} отметил(а) привычку '{habit_name}' на сегодня!",
        reply_markup=get_main_keyboard(selective=True),
        disable_notification=True
    )
    
    # Удаляем сообщение пользователя ПОСЛЕ отправки подтверждения
    try:
        await bot.delete_message(
            chat_id=chat_id,
            message_id=message.message_id
        )
    except Exception as e:
        logger.warning(f"⚠️ Не удалось удалить сообщение пользователя: {e}")

# @dp.message(F.text == "📊 Мои привычки")
# async def my_habits(message: types.Message):
#     """Обработчик кнопки 'Мои привычки'"""
#     await message.answer(
#         "📊 Мои привычки\n\n"
#         "💡 Функционал в разработке...",
#         reply_markup=get_main_keyboard()
#     )

# ============================================================
# ФУНКЦИИ ДЛЯ РАБОТЫ СО СТАТИСТИКОЙ
# ============================================================
async def generate_statistics_text(chat_id: int) -> str:
    """Генерирует текст статистики в моноширинном формате"""
    from datetime import datetime, timedelta
    
    # Инициализируем данные, если еще не инициализированы
    await init_test_data(chat_id)

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

    # Получаем данные из БД
    today = datetime.now().date()
    date_start = (today - timedelta(days=6)).strftime("%Y-%m-%d")
    date_end = today.strftime("%Y-%m-%d")
    
    tracker_data = await get_tracker_data_for_chat(chat_id, date_start, date_end)
    users_metadata = await get_all_users_for_chat(chat_id)

    # Список пользователей в фиксированном порядке
    user_order = sorted(tracker_data.keys())

    # Эмодзи для счетчиков выполнения привычек
    counter_emojis = {
        0: "0️⃣",
        1: "1️⃣",
        2: "2️⃣",
        3: "3️⃣",
        4: "4️⃣",
        5: "5️⃣",
        6: "6️⃣",
        7: "7️⃣",
        8: "8️⃣",
        9: "9️⃣",
    }

    # Строка с кол-вом привычек пользователей (по одному на пользователя)
    habits_count_line_parts = ["  "]  # 2 пробела под датой
    for user_id in user_order:
        user_habits = tracker_data.get(user_id, {})
        total_habits = len(user_habits) if user_habits else 0

        if total_habits == 0:
            habits_count_line_parts.append("➖")
        else:
            habits_count_line_parts.append(counter_emojis.get(total_habits, str(total_habits)))
    header_lines.append("".join(habits_count_line_parts))

    # Строка с эмодзи пользователей (по одному на пользователя)
    users_emoji_line_parts = ["  "]  # 2 пробела в начале
    for user_id in user_order:
        user_emoji = users_metadata.get(user_id, {}).get("emoji", "❓")
        users_emoji_line_parts.append(user_emoji)
    header_lines.append("".join(users_emoji_line_parts))

    # Создаем список из 7 дат: от (сегодня - 6) до (сегодня)
    date_list = []
    for i in range(6):
        date = today - timedelta(days=5-i)  # От -6 до 0 (сегодня)
        date_list.append(date.strftime("%Y-%m-%d"))

    # Строки с датами и агрегированными статусами по пользователю (7 строк)
    date_rows = []
    for date_str in date_list:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day = date_obj.day
        day_str = str(day)
        
        # Формируем строку: число дня (однозначные числа выравниваем дополнительным пробелом)
        if len(day_str) == 1:
            row_parts = [day_str + " "]
        else:
            row_parts = [day_str]
        
        for user_id in user_order:
            user_habits = tracker_data.get(user_id, {})
            total_habits = len(user_habits) if user_habits else 0

            if total_habits == 0:
                # Если вдруг нет привычек — показываем пустой индикатор
                row_parts.append("➖")
                continue

            completed_count = 0
            for habit_id, dates_status in user_habits.items():
                status = dates_status.get(date_str)
                if status is True:
                    completed_count += 1

            if completed_count >= total_habits:
                row_parts.append("✅")
            else:
                row_parts.append(counter_emojis.get(completed_count, str(completed_count)))
        
        date_rows.append("".join(row_parts))
    
    full_text = "\n".join(header_lines + date_rows)
    return f"<pre>{full_text}</pre>"

# Храним ID закрепленного сообщения со статистикой для каждой группы
stats_message_id = {}

# Храним ID сообщения "Выбери привычку" для каждого пользователя в группе
# {chat_id: {user_id: message_id}}
habit_selection_message_id = {}

async def update_statistics_message(chat_id: int):
    """Обновляет или создает сообщение со статистикой"""
    stats_text = await generate_statistics_text(chat_id)
    
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
            parse_mode="HTML",
            reply_markup=get_main_keyboard(selective=False),
            disable_notification=True
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
        await message.reply(
            "❌ Статистика работает только в группах!\n"
            "Добавь бота в группу для использования.",
            reply_markup=get_main_keyboard(selective=True),
            disable_notification=True
        )
        return
    
    # Инициализируем данные, если еще не инициализированы
    await init_test_data(message.chat.id)
    
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

# @dp.message(F.text == "📋 Список привычек")
# async def list_habits(message: types.Message):
#     """Обработчик кнопки 'Список привычек'"""
#     await message.answer(
#         "📋 Список привычек\n\n"
#         "💡 Функционал в разработке...",
#         reply_markup=get_main_keyboard()
#     )

# @dp.message(F.text == "ℹ️ Помощь")
# async def help_button(message: types.Message):
#     """Обработчик кнопки 'Помощь'"""
#     await help(message)  # Используем ту же функцию, что и для команды /help

# ============================================================
# ГЛАВНАЯ ФУНКЦИЯ - ЗАПУСК БОТА
# ============================================================
async def main():
    """Главная функция - запускает бота"""
    logger.info('🚀 Challenge бот запущен!')
    
    # Инициализируем базу данных
    await init_database()
    logger.info('✅ База данных готова к работе')
    
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
