# main.py

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
import os
from pathlib import Path

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
# ХРАНИЛИЩЕ ДАННЫХ
# ============================================================
# Храним ID закрепленных сообщений и время их создания для каждой группы
# Формат: {chat_id: {'message_id': int, 'created_at': datetime}}
# Telegram позволяет редактировать сообщения только в течение 48 часов
pinned_messages = {}

# ID бота (будет установлен при запуске)
bot_id = None

# Константы: максимальное время для редактирования/удаления сообщения (48 часов)
# Telegram позволяет редактировать и удалять свои сообщения только в течение 48 часов
EDIT_MESSAGE_MAX_AGE = timedelta(hours=48)
DELETE_MESSAGE_MAX_AGE = timedelta(hours=48)  # Только для своих сообщений

# ============================================================
# ОБРАБОТЧИКИ КОМАНД
# ============================================================
# Обработчик /start
@dp.message(Command('start'))
async def start(message: types.Message):
    await message.answer("Привет! Это challenge бот.\n\n"
                         "Бот готов к работе в группе!")

# Обработчик /help
@dp.message(Command('help'))
async def help(message: types.Message):
    await message.answer(
        "📖 Доступные команды:\n"
        "/start - начать\n"
        "/help - показать эту справку\n"
        "/test_group - протестировать отправку сообщения в группе (работает только в группах)\n"
        "/pin - закрепить сообщение (ответь на сообщение этой командой)\n"
        "/pin_new - создать и закрепить новое сообщение\n"
        "/edit_pinned - изменить текст закрепленного сообщения (введи новый текст после команды)\n"
        "/show_pinned_id - показать ID текущего закрепленного сообщения\n"
        "/delete_my - удалить сообщение бота (ответь на сообщение бота этой командой)\n"
        "/delete_any - удалить любое сообщение (требуются права администратора, ответь на сообщение)\n"
        "/test_inline_buttons - протестировать inline кнопки с callback_data\n"
        "/test_url_buttons - протестировать inline кнопки с URL\n"
        "/test_reply_keyboard - протестировать Reply клавиатуру (кнопки рядом с полем ввода)\n"
        "/remove_keyboard - убрать Reply клавиатуру"
    )

# ============================================================
# ТЕСТИРОВАНИЕ: ЗАКРЕПЛЕНИЕ СООБЩЕНИЙ В ГРУППЕ
# ============================================================
@dp.message(Command('pin'))
async def pin_message(message: types.Message):
    """Закрепляет сообщение, на которое ответили"""
    if message.chat.type not in ['group', 'supergroup']:
        await message.answer("❌ Эта команда работает только в группах!")
        return
    
    # Проверяем, есть ли ответ на сообщение
    if not message.reply_to_message:
        await message.answer(
            "❌ Чтобы закрепить сообщение, ответь на него командой /pin\n"
            "Например: ответь на любое сообщение и напиши /pin"
        )
        return
    
    try:
        pinned_msg_id = message.reply_to_message.message_id
        # Проверяем, является ли сообщение сообщением нашего бота (можно редактировать)
        is_this_bot_message = (message.reply_to_message.from_user and 
                              message.reply_to_message.from_user.id == bot_id)
        
        # Закрепляем сообщение
        await bot.pin_chat_message(
            chat_id=message.chat.id,
            message_id=pinned_msg_id,
            disable_notification=False  # True = закрепить без уведомления
        )
        
        # Сохраняем ID и время создания только если это сообщение нашего бота (можно редактировать)
        if is_this_bot_message:
            # Получаем время создания сообщения
            msg_date = message.reply_to_message.date
            pinned_messages[message.chat.id] = {
                'message_id': pinned_msg_id,
                'created_at': msg_date
            }
            response_text = (
                f"✅ Сообщение закреплено!\n"
                f"📌 ID закрепленного сообщения: {pinned_msg_id}\n"
                f"🕐 Создано: {msg_date.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"💡 Можно изменить командой /edit_pinned <новый текст> (в течение 48 часов)"
            )
        else:
            # Не сохраняем ID, так как нельзя редактировать чужое сообщение
            response_text = (
                f"✅ Сообщение закреплено!\n"
                f"📌 ID закрепленного сообщения: {pinned_msg_id}\n"
                f"⚠️ Это сообщение нельзя редактировать (оно не от бота)\n"
                f"💡 Для редактируемого сообщения используй /pin_new"
            )
        
        await message.answer(response_text)
        logger.info(
            f"✅ Сообщение {pinned_msg_id} закреплено в группе "
            f"{message.chat.title} (ID: {message.chat.id})"
        )
    except Exception as e:
        error_msg = str(e)
        if "not enough rights" in error_msg.lower() or "chat admin" in error_msg.lower():
            await message.answer(
                "❌ У бота нет прав администратора для закрепления сообщений!\n"
                "💡 Сделай бота администратором группы с правом 'Закреплять сообщения'"
            )
        else:
            await message.answer(f"❌ Ошибка при закреплении: {error_msg}")
        logger.error(f"❌ Ошибка закрепления сообщения: {e}")

@dp.message(Command('pin_new'))
async def pin_new_message(message: types.Message):
    """Создает новое сообщение и сразу закрепляет его"""
    if message.chat.type not in ['group', 'supergroup']:
        await message.answer("❌ Эта команда работает только в группах!")
        return
    
    try:
        # Создаем новое сообщение
        sent_message = await message.answer(
            f"📌 Это закрепленное сообщение!\n"
            f"🕐 Создано: {message.date.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"👤 Создал: {message.from_user.full_name}\n"
            f"💬 ID сообщения: будет показано после закрепления"
        )
        
        # Закрепляем его
        await bot.pin_chat_message(
            chat_id=message.chat.id,
            message_id=sent_message.message_id,
            disable_notification=False
        )
        
        # Сохраняем ID и время создания закрепленного сообщения
        msg_date = sent_message.date
        pinned_messages[message.chat.id] = {
            'message_id': sent_message.message_id,
            'created_at': msg_date
        }
        
        # Обновляем сообщение с ID и информацией о времени редактирования
        await sent_message.edit_text(
            f"📌 Это закрепленное сообщение!\n"
            f"🕐 Создано: {msg_date.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"👤 Создал: {message.from_user.full_name}\n"
            f"💬 ID сообщения: {sent_message.message_id}\n"
            f"⏰ Можно редактировать в течение 48 часов\n"
            f"💡 Изменить: /edit_pinned <новый текст>"
        )
        
        logger.info(
            f"✅ Новое сообщение {sent_message.message_id} создано и закреплено в группе "
            f"{message.chat.title} (ID: {message.chat.id})"
        )
    except Exception as e:
        error_msg = str(e)
        if "not enough rights" in error_msg.lower() or "chat admin" in error_msg.lower():
            await message.answer(
                "❌ У бота нет прав администратора для закрепления сообщений!\n"
                "💡 Сделай бота администратором группы с правом 'Закреплять сообщения'"
            )
        else:
            await message.answer(f"❌ Ошибка при создании и закреплении: {error_msg}")
        logger.error(f"❌ Ошибка создания и закрепления сообщения: {e}")

# ============================================================
# ТЕСТИРОВАНИЕ: ИЗМЕНЕНИЕ ЗАКРЕПЛЕННОГО СООБЩЕНИЯ
# ============================================================
@dp.message(Command('edit_pinned'))
async def edit_pinned_message(message: types.Message):
    """Изменяет текст закрепленного сообщения"""
    if message.chat.type not in ['group', 'supergroup']:
        await message.answer("❌ Эта команда работает только в группах!")
        return
    
    # Проверяем, есть ли закрепленное сообщение для этой группы
    pinned_data = pinned_messages.get(message.chat.id)
    if not pinned_data:
        await message.answer(
            "❌ Нет сохраненного закрепленного сообщения!\n"
            "💡 Сначала закрепи сообщение командой /pin_new (создаст новое) или /pin (закрепит существующее)\n"
            "⚠️ Важно: редактировать можно только сообщения, созданные ботом через /pin_new!"
        )
        return
    
    pinned_msg_id = pinned_data['message_id']
    created_at = pinned_data['created_at']
    
    # Проверяем возраст сообщения (Telegram позволяет редактировать только в течение 48 часов)
    now = datetime.now(timezone.utc)
    if isinstance(created_at, datetime):
        # Если created_at уже datetime с timezone
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
    else:
        # Если это другой формат, конвертируем
        created_at = created_at.replace(tzinfo=timezone.utc) if hasattr(created_at, 'replace') else datetime.fromtimestamp(created_at.timestamp(), tz=timezone.utc)
    
    message_age = now - created_at
    
    if message_age > EDIT_MESSAGE_MAX_AGE:
        hours_left = (message_age - EDIT_MESSAGE_MAX_AGE).total_seconds() / 3600
        await message.answer(
            f"❌ Сообщение слишком старое для редактирования!\n\n"
            f"📅 Создано: {created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
            f"⏰ Прошло: {int(message_age.total_seconds() / 3600)} часов\n"
            f"⏳ Лимит: 48 часов\n\n"
            f"💡 Telegram позволяет редактировать сообщения только в течение 48 часов после отправки.\n"
            f"✅ Решение: создай новое закрепленное сообщение через /pin_new"
        )
        # Удаляем из хранилища, так как сообщение больше нельзя редактировать
        pinned_messages.pop(message.chat.id, None)
        return
    
    # Показываем, сколько времени осталось до истечения срока редактирования
    time_left = EDIT_MESSAGE_MAX_AGE - message_age
    hours_left = int(time_left.total_seconds() / 3600)
    minutes_left = int((time_left.total_seconds() % 3600) / 60)
    
    # Получаем новый текст из команды
    # Формат: /edit_pinned новый текст сообщения
    command_text = message.text or ""
    parts = command_text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "❌ Укажи новый текст после команды!\n"
            "💡 Пример: /edit_pinned Это новый текст закрепленного сообщения"
        )
        return
    
    new_text = parts[1]
    
    try:
        # Пытаемся получить информацию о сообщении, чтобы проверить, можно ли его редактировать
        try:
            pinned_msg = await bot.get_chat(message.chat.id)
        except:
            pass
        
        # Редактируем закрепленное сообщение
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=pinned_msg_id,
            text=new_text
        )
        await message.answer(
            f"✅ Закрепленное сообщение обновлено!\n"
            f"📌 ID сообщения: {pinned_msg_id}\n"
            f"📝 Новый текст: {new_text[:50]}{'...' if len(new_text) > 50 else ''}\n"
            f"⏰ Осталось времени для редактирования: {hours_left}ч {minutes_left}м"
        )
        logger.info(
            f"✅ Закрепленное сообщение {pinned_msg_id} обновлено в группе "
            f"{message.chat.title} (ID: {message.chat.id})"
        )
    except Exception as e:
        error_msg = str(e).lower()
        if "message to edit not found" in error_msg or "message not found" in error_msg:
            await message.answer(
                "❌ Закрепленное сообщение не найдено!\n"
                "💡 Возможно, оно было удалено. Закрепи новое сообщение командой /pin_new"
            )
            # Удаляем из хранилища, если сообщение не найдено
            pinned_messages.pop(message.chat.id, None)
        elif "can't be edited" in error_msg or "can't edit" in error_msg:
            await message.answer(
                "❌ Это сообщение нельзя редактировать!\n\n"
                "💡 Причины:\n"
                "   • Сообщение было создано не ботом (закреплено через /pin)\n"
                "   • Сообщение слишком старое\n"
                "   • Сообщение содержит медиа, которое нельзя редактировать\n\n"
                "✅ Решение: используй /pin_new для создания нового закрепленного сообщения, которое можно редактировать"
            )
            # Очищаем хранилище, так как это сообщение нельзя редактировать
            pinned_messages.pop(message.chat.id, None)
        else:
            await message.answer(
                f"❌ Ошибка при редактировании: {str(e)}\n"
                f"💡 Попробуй создать новое закрепленное сообщение через /pin_new"
            )
        logger.error(f"❌ Ошибка редактирования закрепленного сообщения: {e}")

@dp.message(Command('show_pinned_id'))
async def show_pinned_id(message: types.Message):
    """Показывает ID и информацию о текущем закрепленном сообщении"""
    if message.chat.type not in ['group', 'supergroup']:
        await message.answer("❌ Эта команда работает только в группах!")
        return
    
    pinned_data = pinned_messages.get(message.chat.id)
    if pinned_data:
        pinned_msg_id = pinned_data['message_id']
        created_at = pinned_data['created_at']
        
        # Обрабатываем время
        if isinstance(created_at, datetime):
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
        else:
            created_at = created_at.replace(tzinfo=timezone.utc) if hasattr(created_at, 'replace') else datetime.fromtimestamp(created_at.timestamp(), tz=timezone.utc)
        
        now = datetime.now(timezone.utc)
        message_age = now - created_at
        time_left = EDIT_MESSAGE_MAX_AGE - message_age
        
        if time_left.total_seconds() > 0:
            hours_left = int(time_left.total_seconds() / 3600)
            minutes_left = int((time_left.total_seconds() % 3600) / 60)
            time_info = f"⏰ Осталось: {hours_left}ч {minutes_left}м"
        else:
            time_info = "❌ Срок редактирования истек (48 часов)"
        
        await message.answer(
            f"📌 Информация о закрепленном сообщении:\n"
            f"   ID: {pinned_msg_id}\n"
            f"   📅 Создано: {created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
            f"   {time_info}\n"
            f"   💡 Изменить: /edit_pinned <новый текст>"
        )
    else:
        await message.answer(
            "❌ Нет сохраненного закрепленного сообщения!\n"
            "💡 Сначала закрепи сообщение командой /pin или /pin_new"
        )

# ============================================================
# ТЕСТИРОВАНИЕ: УДАЛЕНИЕ СООБЩЕНИЙ
# ============================================================
@dp.message(Command('delete_my'))
async def delete_my_message(message: types.Message):
    """Удаляет сообщение бота (только свои сообщения, в течение 48 часов)"""
    if message.chat.type not in ['group', 'supergroup']:
        await message.answer("❌ Эта команда работает только в группах!")
        return
    
    # Проверяем, есть ли ответ на сообщение
    if not message.reply_to_message:
        await message.answer(
            "❌ Чтобы удалить сообщение, ответь на него командой /delete_my\n"
            "💡 Важно: можно удалить только сообщения, отправленные ботом, и только в течение 48 часов!"
        )
        return
    
    target_message = message.reply_to_message
    
    # Проверяем, является ли сообщение сообщением нашего бота
    if not target_message.from_user or target_message.from_user.id != bot_id:
        await message.answer(
            "❌ Это не сообщение бота!\n"
            "💡 Бот может удалять только свои собственные сообщения (в течение 48 часов)\n"
            "💡 Для удаления сообщений других пользователей используй /delete_any (требуются права администратора)"
        )
        return
    
    # Проверяем возраст сообщения (48 часов)
    msg_date = target_message.date
    if isinstance(msg_date, datetime):
        if msg_date.tzinfo is None:
            msg_date = msg_date.replace(tzinfo=timezone.utc)
    else:
        msg_date = msg_date.replace(tzinfo=timezone.utc) if hasattr(msg_date, 'replace') else datetime.fromtimestamp(msg_date.timestamp(), tz=timezone.utc)
    
    now = datetime.now(timezone.utc)
    message_age = now - msg_date
    
    if message_age > DELETE_MESSAGE_MAX_AGE:
        hours_passed = int(message_age.total_seconds() / 3600)
        await message.answer(
            f"❌ Сообщение слишком старое для удаления!\n\n"
            f"📅 Создано: {msg_date.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
            f"⏰ Прошло: {hours_passed} часов\n"
            f"⏳ Лимит: 48 часов\n\n"
            f"💡 Telegram позволяет удалять свои сообщения только в течение 48 часов после отправки."
        )
        return
    
    try:
        # Удаляем сообщение
        await bot.delete_message(
            chat_id=message.chat.id,
            message_id=target_message.message_id
        )
        await message.answer(
            f"✅ Сообщение удалено!\n"
            f"📌 ID удаленного сообщения: {target_message.message_id}\n"
            f"⏰ Возраст сообщения: {int(message_age.total_seconds() / 3600)}ч {int((message_age.total_seconds() % 3600) / 60)}м"
        )
        logger.info(
            f"✅ Сообщение {target_message.message_id} удалено в группе "
            f"{message.chat.title} (ID: {message.chat.id})"
        )
    except Exception as e:
        error_msg = str(e).lower()
        if "message to delete not found" in error_msg or "message not found" in error_msg:
            await message.answer(
                "❌ Сообщение не найдено!\n"
                "💡 Возможно, оно уже было удалено."
            )
        elif "can't be deleted" in error_msg or "can't delete" in error_msg:
            await message.answer(
                "❌ Это сообщение нельзя удалить!\n\n"
                "💡 Причины:\n"
                "   • Сообщение слишком старое (больше 48 часов)\n"
                "   • Сообщение было удалено ранее\n"
                "   • У бота нет прав на удаление"
            )
        else:
            await message.answer(f"❌ Ошибка при удалении: {str(e)}")
        logger.error(f"❌ Ошибка удаления сообщения: {e}")

@dp.message(Command('delete_any'))
async def delete_any_message(message: types.Message):
    """Удаляет любое сообщение в группе (требуются права администратора, без ограничения по времени)"""
    if message.chat.type not in ['group', 'supergroup']:
        await message.answer("❌ Эта команда работает только в группах!")
        return
    
    # Проверяем, есть ли ответ на сообщение
    if not message.reply_to_message:
        await message.answer(
            "❌ Чтобы удалить сообщение, ответь на него командой /delete_any\n"
            "💡 Требуются права администратора группы"
        )
        return
    
    target_message = message.reply_to_message
    target_msg_id = target_message.message_id
    
    try:
        # Удаляем сообщение (для администраторов нет ограничения по времени)
        await bot.delete_message(
            chat_id=message.chat.id,
            message_id=target_msg_id
        )
        await message.answer(
            f"✅ Сообщение удалено!\n"
            f"📌 ID удаленного сообщения: {target_msg_id}\n"
            f"👤 От: {target_message.from_user.full_name if target_message.from_user else 'Неизвестно'}"
        )
        logger.info(
            f"✅ Сообщение {target_msg_id} удалено администратором в группе "
            f"{message.chat.title} (ID: {message.chat.id})"
        )
    except Exception as e:
        error_msg = str(e).lower()
        if "not enough rights" in error_msg or "chat admin" in error_msg:
            await message.answer(
                "❌ У бота нет прав администратора для удаления сообщений!\n"
                "💡 Сделай бота администратором группы с правом 'Удалять сообщения'"
            )
        elif "message to delete not found" in error_msg or "message not found" in error_msg:
            await message.answer(
                "❌ Сообщение не найдено!\n"
                "💡 Возможно, оно уже было удалено."
            )
        else:
            await message.answer(f"❌ Ошибка при удалении: {str(e)}")
        logger.error(f"❌ Ошибка удаления сообщения администратором: {e}")

# ============================================================
# ТЕСТИРОВАНИЕ: ОТПРАВКА СООБЩЕНИЙ В ГРУППЕ
# ============================================================
@dp.message(Command('test_group'))
async def test_group_message(message: types.Message):
    """Тестовая команда для отправки сообщения в группе"""
    if message.chat.type in ['group', 'supergroup']:
        await message.answer(
            f"✅ Тест отправки сообщения в группе!\n"
            f"📊 Информация о группе:\n"
            f"   Название: {message.chat.title}\n"
            f"   ID группы: {message.chat.id}\n"
            f"   Тип: {message.chat.type}\n"
            f"   Отправитель: {message.from_user.full_name} (@{message.from_user.username or 'нет username'})"
        )
        logger.info(f"✅ Тестовое сообщение отправлено в группу {message.chat.title} (ID: {message.chat.id})")
    else:
        await message.answer("❌ Эта команда работает только в группах!")

# ============================================================
# ТЕСТИРОВАНИЕ: INLINE КНОПКИ С CALLBACK_DATA
# ============================================================
@dp.message(Command('test_inline_buttons'))
async def test_inline_buttons(message: types.Message):
    """Тестовая команда для проверки inline кнопок с callback_data"""
    # Создаем inline клавиатуру с кнопками
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Кнопка 1", callback_data="btn_1"),
                InlineKeyboardButton(text="✅ Кнопка 2", callback_data="btn_2")
            ],
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data="btn_refresh")
            ],
            [
                InlineKeyboardButton(text="❌ Закрыть", callback_data="btn_close")
            ]
        ]
    )
    
    await message.answer(
        "🧪 Тест inline кнопок с callback_data\n\n"
        "Нажми на любую кнопку ниже:",
        reply_markup=keyboard
    )
    logger.info(f"✅ Тест inline кнопок отправлен пользователю {message.from_user.id}")

# Обработчик нажатия на кнопку "Кнопка 1"
@dp.callback_query(F.data == "btn_1")
async def handle_button_1(callback: types.CallbackQuery):
    """Обработчик нажатия на первую кнопку"""
    await callback.answer("Ты нажал на кнопку 1! ✅", show_alert=False)
    await callback.message.edit_text(
        "🧪 Тест inline кнопок с callback_data\n\n"
        "✅ Ты нажал на кнопку 1!\n"
        "👤 Пользователь: " + callback.from_user.full_name + "\n"
        "🆔 ID: " + str(callback.from_user.id),
        reply_markup=callback.message.reply_markup  # Сохраняем клавиатуру
    )
    logger.info(f"✅ Пользователь {callback.from_user.id} нажал на кнопку 1")

# Обработчик нажатия на кнопку "Кнопка 2"
@dp.callback_query(F.data == "btn_2")
async def handle_button_2(callback: types.CallbackQuery):
    """Обработчик нажатия на вторую кнопку"""
    await callback.answer("Ты нажал на кнопку 2! ✅", show_alert=False)
    await callback.message.edit_text(
        "🧪 Тест inline кнопок с callback_data\n\n"
        "✅ Ты нажал на кнопку 2!\n"
        "👤 Пользователь: " + callback.from_user.full_name + "\n"
        "🆔 ID: " + str(callback.from_user.id),
        reply_markup=callback.message.reply_markup
    )
    logger.info(f"✅ Пользователь {callback.from_user.id} нажал на кнопку 2")

# Обработчик нажатия на кнопку "Обновить"
@dp.callback_query(F.data == "btn_refresh")
async def handle_button_refresh(callback: types.CallbackQuery):
    """Обработчик нажатия на кнопку обновления"""
    await callback.answer("Сообщение обновлено! 🔄", show_alert=False)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Кнопка 1", callback_data="btn_1"),
                InlineKeyboardButton(text="✅ Кнопка 2", callback_data="btn_2")
            ],
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data="btn_refresh")
            ],
            [
                InlineKeyboardButton(text="❌ Закрыть", callback_data="btn_close")
            ]
        ]
    )
    await callback.message.edit_text(
        "🧪 Тест inline кнопок с callback_data\n\n"
        "🔄 Сообщение обновлено!\n"
        "🕐 Время: " + datetime.now().strftime('%H:%M:%S') + "\n"
        "👤 Пользователь: " + callback.from_user.full_name,
        reply_markup=keyboard
    )
    logger.info(f"✅ Пользователь {callback.from_user.id} обновил сообщение")

# Обработчик нажатия на кнопку "Закрыть"
@dp.callback_query(F.data == "btn_close")
async def handle_button_close(callback: types.CallbackQuery):
    """Обработчик нажатия на кнопку закрытия"""
    await callback.answer("Сообщение закрыто! ❌", show_alert=False)
    await callback.message.edit_text(
        "❌ Сообщение закрыто пользователем " + callback.from_user.full_name
    )
    logger.info(f"✅ Пользователь {callback.from_user.id} закрыл сообщение")

# ============================================================
# ТЕСТИРОВАНИЕ: INLINE КНОПКИ С URL
# ============================================================
@dp.message(Command('test_url_buttons'))
async def test_url_buttons(message: types.Message):
    """Тестовая команда для проверки inline кнопок с URL"""
    # Создаем inline клавиатуру с кнопками, содержащими URL
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 Открыть Google", 
                    url="https://www.google.com"
                ),
                InlineKeyboardButton(
                    text="🔗 Открыть GitHub", 
                    url="https://github.com"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📚 Документация aiogram", 
                    url="https://docs.aiogram.dev/"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💬 Telegram Web", 
                    url="https://web.telegram.org"
                ),
                InlineKeyboardButton(
                    text="🔙 Вернуться к callback кнопкам", 
                    callback_data="btn_back_to_callback"
                )
            ]
        ]
    )
    
    await message.answer(
        "🧪 Тест inline кнопок с URL\n\n"
        "Нажми на кнопки ниже, чтобы открыть ссылки:\n"
        "• URL кнопки открывают ссылки в браузере\n"
        "• Можно комбинировать URL и callback кнопки\n"
        "• URL кнопки не требуют обработчиков callback",
        reply_markup=keyboard
    )
    logger.info(f"✅ Тест URL кнопок отправлен пользователю {message.from_user.id}")

# Обработчик для кнопки "Вернуться к callback кнопкам"
@dp.callback_query(F.data == "btn_back_to_callback")
async def handle_back_to_callback(callback: types.CallbackQuery):
    """Обработчик возврата к callback кнопкам"""
    await callback.answer("Возвращаемся к callback кнопкам! 🔄", show_alert=False)
    
    # Создаем клавиатуру с callback кнопками
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Кнопка 1", callback_data="btn_1"),
                InlineKeyboardButton(text="✅ Кнопка 2", callback_data="btn_2")
            ],
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data="btn_refresh")
            ],
            [
                InlineKeyboardButton(text="🔗 К URL кнопкам", callback_data="btn_to_url")
            ],
            [
                InlineKeyboardButton(text="❌ Закрыть", callback_data="btn_close")
            ]
        ]
    )
    
    await callback.message.edit_text(
        "🧪 Тест inline кнопок с callback_data\n\n"
        "Вернулись к callback кнопкам!\n"
        "Нажми на любую кнопку:",
        reply_markup=keyboard
    )
    logger.info(f"✅ Пользователь {callback.from_user.id} вернулся к callback кнопкам")

# Обработчик для перехода к URL кнопкам
@dp.callback_query(F.data == "btn_to_url")
async def handle_to_url(callback: types.CallbackQuery):
    """Обработчик перехода к URL кнопкам"""
    await callback.answer("Переходим к URL кнопкам! 🔗", show_alert=False)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 Открыть Google", 
                    url="https://www.google.com"
                ),
                InlineKeyboardButton(
                    text="🔗 Открыть GitHub", 
                    url="https://github.com"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📚 Документация aiogram", 
                    url="https://docs.aiogram.dev/"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Вернуться к callback кнопкам", 
                    callback_data="btn_back_to_callback"
                )
            ]
        ]
    )
    
    await callback.message.edit_text(
        "🧪 Тест inline кнопок с URL\n\n"
        "Нажми на кнопки ниже, чтобы открыть ссылки:",
        reply_markup=keyboard
    )
    logger.info(f"✅ Пользователь {callback.from_user.id} перешел к URL кнопкам")

# ============================================================
# ТЕСТИРОВАНИЕ: REPLY KEYBOARD (КНОПКИ РЯДОМ С ПОЛЕМ ВВОДА)
# ============================================================
@dp.message(Command('test_reply_keyboard'))
async def test_reply_keyboard(message: types.Message):
    """Тестовая команда для проверки Reply клавиатуры (кнопки рядом с полем ввода)"""
    # Создаем Reply клавиатуру
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="✅ Кнопка 1"),
                KeyboardButton(text="✅ Кнопка 2")
            ],
            [
                KeyboardButton(text="🔄 Обновить"),
                KeyboardButton(text="📊 Информация")
            ],
            [
                KeyboardButton(text="❌ Убрать клавиатуру")
            ]
        ],
        resize_keyboard=True,  # Автоматически подстраивает размер кнопок
        one_time_keyboard=False,  # Клавиатура остается после нажатия
        input_field_placeholder="Выбери кнопку или введи текст..."  # Подсказка в поле ввода
    )
    
    await message.answer(
        "🧪 Тест Reply клавиатуры (кнопки рядом с полем ввода)\n\n"
        "Теперь рядом с полем ввода появились кнопки!\n"
        "• Нажми на любую кнопку\n"
        "• Или введи текст\n"
        "• Маленькая кнопка рядом с полем ввода позволяет переключаться между клавиатурами",
        reply_markup=keyboard
    )
    logger.info(f"✅ Reply клавиатура отправлена пользователю {message.from_user.id}")

@dp.message(Command('remove_keyboard'))
async def remove_keyboard(message: types.Message):
    """Убирает Reply клавиатуру"""
    await message.answer(
        "✅ Клавиатура убрана!\n"
        "💡 Чтобы вернуть её, используй /test_reply_keyboard",
        reply_markup=ReplyKeyboardRemove()
    )
    logger.info(f"✅ Reply клавиатура убрана для пользователя {message.from_user.id}")

# Обработчики нажатий на кнопки Reply клавиатуры
@dp.message(F.text == "✅ Кнопка 1")
async def handle_reply_button_1(message: types.Message):
    """Обработчик нажатия на кнопку 1 в Reply клавиатуре"""
    await message.answer(
        f"✅ Ты нажал на кнопку 1!\n"
        f"👤 Пользователь: {message.from_user.full_name}\n"
        f"🆔 ID: {message.from_user.id}"
    )
    logger.info(f"✅ Пользователь {message.from_user.id} нажал на Reply кнопку 1")

@dp.message(F.text == "✅ Кнопка 2")
async def handle_reply_button_2(message: types.Message):
    """Обработчик нажатия на кнопку 2 в Reply клавиатуре"""
    await message.answer(
        f"✅ Ты нажал на кнопку 2!\n"
        f"👤 Пользователь: {message.from_user.full_name}\n"
        f"🆔 ID: {message.from_user.id}"
    )
    logger.info(f"✅ Пользователь {message.from_user.id} нажал на Reply кнопку 2")

@dp.message(F.text == "🔄 Обновить")
async def handle_reply_refresh(message: types.Message):
    """Обработчик нажатия на кнопку обновления в Reply клавиатуре"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="✅ Кнопка 1"),
                KeyboardButton(text="✅ Кнопка 2")
            ],
            [
                KeyboardButton(text="🔄 Обновить"),
                KeyboardButton(text="📊 Информация")
            ],
            [
                KeyboardButton(text="❌ Убрать клавиатуру")
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Выбери кнопку или введи текст..."
    )
    
    await message.answer(
        f"🔄 Клавиатура обновлена!\n"
        f"🕐 Время: {datetime.now().strftime('%H:%M:%S')}\n"
        f"👤 Пользователь: {message.from_user.full_name}",
        reply_markup=keyboard
    )
    logger.info(f"✅ Пользователь {message.from_user.id} обновил Reply клавиатуру")

@dp.message(F.text == "📊 Информация")
async def handle_reply_info(message: types.Message):
    """Обработчик нажатия на кнопку информации в Reply клавиатуре"""
    await message.answer(
        f"📊 Информация о Reply клавиатуре:\n\n"
        f"• Это Reply клавиатура (ReplyKeyboardMarkup)\n"
        f"• Кнопки появляются рядом с полем ввода\n"
        f"• Можно переключаться между обычной и Reply клавиатурой\n"
        f"• Работает в группах и личных сообщениях\n\n"
        f"👤 Пользователь: {message.from_user.full_name}\n"
        f"🆔 ID: {message.from_user.id}\n"
        f"💬 Чат: {message.chat.title if message.chat.type in ['group', 'supergroup'] else 'Личный чат'}"
    )
    logger.info(f"✅ Пользователь {message.from_user.id} запросил информацию о Reply клавиатуре")

@dp.message(F.text == "❌ Убрать клавиатуру")
async def handle_reply_remove(message: types.Message):
    """Обработчик нажатия на кнопку удаления клавиатуры"""
    await message.answer(
        "✅ Клавиатура убрана!\n"
        "💡 Чтобы вернуть её, используй /test_reply_keyboard",
        reply_markup=ReplyKeyboardRemove()
    )
    logger.info(f"✅ Пользователь {message.from_user.id} убрал Reply клавиатуру")

# ============================================================
# ОБРАБОТЧИК СООБЩЕНИЙ В ГРУППЕ
# ============================================================
@dp.message()
async def handle_message(message: types.Message):
    """Обработчик всех сообщений в группе"""
    # Пропускаем команды (они обрабатываются отдельными обработчиками)
    if message.text and message.text.startswith('/'):
        return
    
    # Обрабатываем сообщения в группе
    if message.chat.type in ['group', 'supergroup']:
        logger.info(
            f"📨 Сообщение в группе '{message.chat.title}':\n"
            f"   От: {message.from_user.full_name} (ID: {message.from_user.id})\n"
            f"   Текст: {message.text or 'Нет текста (медиа/стикер)'}\n"
            f"   ID сообщения: {message.message_id}"
        )
        
        # Пример: отвечаем на сообщения, содержащие "бот"
        if message.text and 'бот' in message.text.lower():
            await message.reply("🤖 Я здесь! Чем могу помочь?")
    else:
        logger.info(f"💬 Личное сообщение от {message.from_user.full_name}: {message.text}")

# ============================================================
# ГЛАВНАЯ ФУНКЦИЯ - ЗАПУСК БОТА
# ============================================================
async def main():
    """Главная функция - запускает бота"""
    global bot_id
    # Получаем информацию о боте один раз при запуске
    bot_info = await bot.get_me()
    bot_id = bot_info.id
    logger.info(f'🚀 Challenge бот запущен! Бот: @{bot_info.username} (ID: {bot_id})')
    try:
        # бот периодически запрашивает обновления у Telegram
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        logger.info('🛑 Бот остановлен')

if __name__ == '__main__':
    asyncio.run(main())

