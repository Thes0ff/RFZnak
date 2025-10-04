import aiosqlite
import asyncio
from math import radians, cos, sin, asin, sqrt
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramBadRequest

# ----------------------- КОНФИГУРАЦИЯ БОТА -----------------------
# ЗАМЕНИТЕ ЭТО НА ВАШ ТОКЕН
API_TOKEN = "8236936263:AAHlY1Yabi9wXB62p4a327sCmPgXghRLLJI" 

# ЗАМЕНИТЕ ЭТО НА ВАШ ТЕЛЕГРАМ ID для доступа к модерации
ADMIN_ID = 123456789 

session = AiohttpSession(timeout=60)

storage = MemoryStorage()
bot = Bot(token=API_TOKEN, session=session)
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

DB_PATH = "dating.db"


# ----------------------- СОСТОЯНИЯ -----------------------
class Registration(StatesGroup):
    [span_0](start_span)waiting_for_name = State()[span_0](end_span)
    [span_1](start_span)waiting_for_age = State()[span_1](end_span)
    [span_2](start_span)waiting_for_gender = State()[span_2](end_span)
    [span_3](start_span)waiting_for_looking_for = State()[span_3](end_span)
    [span_4](start_span)waiting_for_nsfw = State()[span_4](end_span)
    [span_5](start_span)waiting_for_description = State()[span_5](end_span)
    [span_6](start_span)waiting_for_photo = State()[span_6](end_span)
    [span_7](start_span)waiting_for_location = State()[span_7](end_span)

class EditProfile(StatesGroup):
    [span_8](start_span)waiting_for_new_name = State()[span_8](end_span)
    [span_9](start_span)waiting_for_new_age = State()[span_9](end_span)
    [span_10](start_span)waiting_for_new_description = State()[span_10](end_span)
    [span_11](start_span)waiting_for_new_photo = State()[span_11](end_span)
    [span_12](start_span)waiting_for_new_location = State()[span_12](end_span)

# НОВОЕ СОСТОЯНИЕ ДЛЯ ЖАЛОБ
class Reporting(StatesGroup):
    waiting_for_reason = State()


# ----------------------- БАЗА ДАННЫХ -----------------------
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            [span_13](start_span)telegram_id INTEGER UNIQUE,[span_13](end_span)
            name TEXT,
            age INTEGER,
            gender TEXT,
            looking_for TEXT,
            nsfw INTEGER DEFAULT 0,
            description TEXT,
            [span_14](start_span)latitude REAL,[span_14](end_span)
            [span_15](start_span)longitude REAL,[span_15](end_span)
            photo_id TEXT,
            [span_16](start_span)last_viewed INTEGER DEFAULT 0[span_16](end_span)
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            [span_17](start_span)id INTEGER PRIMARY KEY AUTOINCREMENT,[span_17](end_span)
            from_id INTEGER,
            to_id INTEGER,
            viewed INTEGER DEFAULT 0,
            UNIQUE(from_id, to_id)
        )
        """)
        # НОВАЯ ТАБЛИЦА ДЛЯ ЖАЛОБ
        await db.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reporter_id INTEGER,
            reported_id INTEGER,
            reason TEXT,
            status TEXT DEFAULT 'pending', -- pending, accepted, rejected
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (reporter_id) REFERENCES users(telegram_id),
            FOREIGN KEY (reported_id) REFERENCES users(telegram_id)
        )
        """)
        await db.commit()


async def save_user(telegram_id, **kwargs):
    async with aiosqlite.connect(DB_PATH) as db:
        [span_18](start_span)user = await get_user(telegram_id)[span_18](end_span)
        if user:
            for field, value in kwargs.items():
                if value is not None:
                    await db.execute(
                        [span_19](start_span)f"UPDATE users SET {field}=? WHERE telegram_id=?",[span_19](end_span)
                        (value, telegram_id),
                    )
        else:
            await db.execute("""
                INSERT INTO users (telegram_id, name, age, gender, looking_for, nsfw, description, latitude, longitude, photo_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            [span_20](start_span)""", ([span_20](end_span)
                telegram_id,
                kwargs.get("name"),
                kwargs.get("age"),
                kwargs.get("gender"),
                [span_21](start_span)kwargs.get("looking_for"),[span_21](end_span)
                kwargs.get("nsfw", 0),
                kwargs.get("description"),
                kwargs.get("latitude"),
                kwargs.get("longitude"),
                [span_22](start_span)kwargs.get("photo_id"),[span_22](end_span)
            ))
        await db.commit()


async def get_user(telegram_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        cols = [col[0] for col in cursor.description]
        [span_23](start_span)return dict(zip(cols, row))[span_23](end_span)


async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM users")
        rows = await cursor.fetchall()
        cols = [column[0] for column in cursor.description]
        return [dict(zip(cols, row)) for row in rows]


async def save_like(from_telegram_id, to_telegram_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO likes (from_id, to_id, viewed) VALUES (?, ?, 0)", (from_telegram_id, to_telegram_id))
        [span_24](start_span)await db.commit()[span_24](end_span)


async def get_unviewed_likes(telegram_id):
    """Получает непросмотренные лайки пользователя"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT from_id FROM likes 
            WHERE to_id=? AND viewed=0
        [span_25](start_span)""", (telegram_id,))[span_25](end_span)
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def mark_like_as_viewed(from_telegram_id, to_telegram_id):
    """Помечает лайк как просмотренный"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE likes SET viewed=1 
            WHERE from_id=? AND to_id=?
        [span_26](start_span)""", (from_telegram_id, to_telegram_id))[span_26](end_span)
        await db.commit()


async def count_unviewed_likes(telegram_id):
    """Считает количество непросмотренных лайков"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT COUNT(*) FROM likes 
            WHERE to_id=? AND viewed=0
        """, (telegram_id,))
        row = await cursor.fetchone()
        [span_27](start_span)return row[0] if row else 0[span_27](end_span)


async def delete_user(telegram_id):
    """Удаляет пользователя и все его лайки"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM users WHERE telegram_id=?", (telegram_id,))
        [span_28](start_span)await db.execute("DELETE FROM likes WHERE from_id=? OR to_id=?", (telegram_id, telegram_id))[span_28](end_span)
        await db.commit()


async def is_profile_complete(user):
    """Проверяет, заполнена ли анкета полностью"""
    if not user:
        return False
    return all([
        user.get("name"),
        user.get("age"),
        user.get("gender"),
        user.get("looking_for"),
        user.get("description"),
        user.get("photo_id"),
        user.get("latitude"),
        [span_29](start_span)user.get("longitude")[span_29](end_span)
    ])

# НОВЫЕ ФУНКЦИИ ДЛЯ ЖАЛОБ И МОДЕРАЦИИ
async def save_report(reporter_id, reported_id, reason):
    """Сохраняет жалобу в БД."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO reports (reporter_id, reported_id, reason) VALUES (?, ?, ?)",
            (reporter_id, reported_id, reason)
        )
        await db.commit()

async def get_pending_reports():
    """Получает все необработанные жалобы."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Получаем 10 последних необработанных
        cursor = await db.execute("SELECT * FROM reports WHERE status='pending' ORDER BY created_at DESC LIMIT 10") 
        rows = await cursor.fetchall()
        cols = [column[0] for column in cursor.description]
        return [dict(zip(cols, row)) for row in rows]

async def update_report_status(report_id, status):
    """Обновляет статус жалобы."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE reports SET status=? WHERE id=?",
            (status, report_id)
        )
        await db.commit()


# ----------------------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (ПОИСК) -----------------------
def haversine(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return 6371 * c


async def find_next_user(current_user, radius_km=50, max_age_diff=5):
    all_users = await get_all_users()
    
    # [span_30](start_span)Фильтруем пользователей по полу и заполненности анкеты[span_30](end_span)
    candidates = []
    for user in all_users:
        if user["telegram_id"] == current_user["telegram_id"]:
            continue
        if not user["latitude"] or not user["longitude"]:
            continue
        if user["id"] <= current_user["last_viewed"]:
            continue
        
        # [span_31](start_span)Проверяем соответствие пола[span_31](end_span)
        if user["gender"] != current_user["looking_for"]:
            continue
        
        # Проверяем расстояние
        dist = haversine(
            current_user["latitude"], current_user["longitude"],
            user["latitude"], user["longitude"]
        )
        [span_32](start_span)if dist > radius_km:[span_32](end_span)
            continue
        
        # Добавляем кандидата с разницей в возрасте
        age_diff = abs(user["age"] - current_user["age"])
        candidates.append((user, dist, age_diff))
    
    if not candidates:
        return None, None
    
    # Сортируем по разнице в возрасте, затем по расстоянию
    [span_33](start_span)candidates.sort(key=lambda x: (x[2], x[1]))[span_33](end_span)
    
    # Возвращаем первого подходящего
    return candidates[0][0], candidates[0][1]


async def update_last_viewed(telegram_id, viewed_id):
    async with aiosqlite.connect(DB_PATH) as db:
        [span_34](start_span)await db.execute("UPDATE users SET last_viewed=? WHERE telegram_id=?", (viewed_id, telegram_id))[span_34](end_span)
        await db.commit()


async def show_next_profile(chat_id, telegram_id):
    """Вспомогательная функция для показа следующей анкеты"""
    current_user = await get_user(telegram_id)
    if not current_user:
        await bot.send_message(chat_id, "Сначала создай анкету командой /start")
        return

    if not await is_profile_complete(current_user):
        await bot.send_message(chat_id, "Заполни анкету полностью, чтобы искать других 🙂")
        return

    user, dist = await find_next_user(current_user, radius_km=50)

    [span_35](start_span)if not user:[span_35](end_span)
        await bot.send_message(chat_id, "Пока анкет рядом нет 😔 Попробуй позже.")
        return

    gender_emoji = "👨" if user["gender"] == "male" else "👩"
    
    # Формируем описание с учетом 18+
    caption = f"{gender_emoji} {user['name']}, {user['age']} лет\n📍 {round(dist, 1)} км от тебя\n\n{user['description']}"
    
    # Показываем метку 18+ только если оба пользователя выставили nsfw=1
    if current_user["nsfw"] == 1 and user["nsfw"] == 1:
        [span_36](start_span)caption = f"🔥 18+ {caption}"[span_36](end_span)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️ Лайк", callback_data=f"like_{user['telegram_id']}"),
            InlineKeyboardButton(text="❌ Пропустить", callback_data=f"skip_{user['id']}")
        ],
        # ДОБАВЛЕНА КНОПКА ПОЖАЛОВАТЬСЯ
        [
            InlineKeyboardButton(text="⚠️ Пожаловаться", callback_data=f"report_{user['telegram_id']}")
        ]
    ])

    if user["photo_id"]:
        await bot.send_photo(chat_id, user["photo_id"], caption=caption, reply_markup=keyboard)
    else:
        await bot.send_message(chat_id, caption, reply_markup=keyboard)


# -[span_37](start_span)---------------------- МЕНЮ И КОМАНДЫ -----------------------[span_37](end_span)

async def set_main_menu_commands(bot: Bot):
    """Устанавливает список команд для меню Telegram"""
    commands = [
        BotCommand(command="start", description="Начать / Зарегистрироваться"),
        BotCommand(command="menu", description="Главное меню"),
        BotCommand(command="search", description="Искать анкеты"),
        BotCommand(command="likes", description="Посмотреть лайки"),
        BotCommand(command="my_profile", description="Моя анкета"),
        # Можно добавить BotCommand(command="mod", description="Модерация") для админа
    ]
    await bot.set_my_commands(commands)


@router.message(Command("menu"))
async def show_main_menu(message: types.Message):
    """Показывает главное меню с кнопками"""
    user = await get_user(message.from_user.id)
    [span_38](start_span)if not user or not await is_profile_complete(user):[span_38](end_span)
        await message.answer("Сначала заполни анкету командой /start")
        return

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Смотреть анкеты")],
            [KeyboardButton(text="👤 Моя анкета")],
        ],
        resize_keyboard=True,
        [span_39](start_span)one_time_keyboard=False[span_39](end_span)
    )
    [span_40](start_span)await message.answer("Добро пожаловать в главное меню! Выбери действие:", reply_markup=kb)[span_40](end_span)


@router.message(F.text == "🔍 Смотреть анкеты")
async def handle_search_button(message: types.Message):
    """Обработка кнопки 'Смотреть анкеты'"""
    await show_next_profile(message.chat.id, message.from_user.id)


@router.message(F.text == "👤 Моя анкета")
async def handle_my_profile_button(message: types.Message):
    """Обработка кнопки 'Моя анкета'"""
    await show_my_profile_action(message)


@router.message(Command("search"))
async def search(message: types.Message):
    """Команда /search"""
    await show_next_profile(message.chat.id, message.from_user.id)


@router.message(Command("my_profile"))
async def my_profile_command(message: types.Message):
    """Обработка команды /my_profile"""
    await show_my_profile_action(message)


# ----------------------- УПРАВЛЕНИЕ ПРОФИЛЕМ -----------------------

async def show_my_profile_action(message: types.Message, callback_data=None):
    [span_41](start_span)"""Вспомогательная функция для показа своей анкеты. Используется командами и кнопками."""[span_41](end_span)
    user = await get_user(message.from_user.id)
    
    if not user:
        await message.answer("Анкета не найдена")
        return
    
    gender_text = "Парень" if user["gender"] == "male" else "Девушка"
    looking_text = "парня" if user["looking_for"] == "male" else "девушку"
    nsfw_text = "🔥 Да" if user["nsfw"] == 1 else "💕 Нет"
    
    caption = (
        [span_42](start_span)f"👤 Твоя анкета:\n\n"[span_42](end_span)
        f"Имя: {user['name']}\n"
        f"Возраст: {user['age']} лет\n"
        f"Пол: {gender_text}\n"
        f"Ищу: {looking_text}\n"
        f"18+: {nsfw_text}\n\n"
        f"Описание: {user['description']}"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Изменить", callback_data="edit_profile"),
            [span_43](start_span)InlineKeyboardButton(text="🔄 Заполнить заново", callback_data="fill_anew"),[span_43](end_span)
            InlineKeyboardButton(text="🗑 Удалить", callback_data="delete_profile")
        ]
    ])
    
    # Удаляем предыдущее сообщение, если оно есть (например, в случае с кнопкой)
    try:
        if callback_data:
            await callback_data.message.delete()
        else:
            await message.delete()
    [span_44](start_span)except:[span_44](end_span)
        pass # Игнорируем ошибки удаления
    
    # Отправляем новую анкету
    if user["photo_id"]:
        await bot.send_photo(message.chat.id, user["photo_id"], caption=caption, reply_markup=kb)
    else:
        await bot.send_message(message.chat.id, text=caption, reply_markup=kb)


@router.callback_query(lambda c: c.data == "my_profile")
async def show_my_profile_callback(callback: types.CallbackQuery):
    """Обработка колбэка для просмотра анкеты"""
    await show_my_profile_action(callback.message, callback_data=callback)
    await callback.answer()


@router.callback_query(lambda c: c.data == "fill_anew")
async def handle_fill_anew(callback: types.CallbackQuery, state: FSMContext):
    [span_45](start_span)"""Сброс и начало регистрации с первого шага"""[span_45](end_span)
    await callback.answer("Начинаем регистрацию заново.")
    
    # Удаляем сообщение с анкетой
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
    
    # Начинаем процесс регистрации
    await callback.message.answer("Давай заполним анкету заново.\nНапиши своё имя:")
    await state.set_state(Registration.waiting_for_name)


# ----------------------- ОБРАБОТЧИКИ РЕГИСТРАЦИИ -----------------------
@router.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    """
    Стартовая функция. Показывает главное меню, если анкета заполнена, 
    [span_46](start_span)иначе начинает регистрацию.[span_46](end_span)
    """
    user = await get_user(message.from_user.id)
    
    if user and await is_profile_complete(user):
        await message.answer(
            "У тебя уже есть анкета! 😊\n"
            "Используй /menu или кнопку '👤 Моя анкета' внизу для навигации.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [span_47](start_span)[KeyboardButton(text="🔍 Смотреть анкеты")],[span_47](end_span)
                    [KeyboardButton(text="👤 Моя анкета")],
                ],
                resize_keyboard=True,
                one_time_keyboard=False
            [span_48](start_span))
        )
        return
    
    # Начинаем регистрацию
    await save_user(message.from_user.id)
    await message.answer("Привет! Давай создадим твою анкету.\nНапиши своё имя:", 
                         reply_markup=types.ReplyKeyboardRemove()) # Убираем лишние кнопки
    await state.set_state(Registration.waiting_for_name)


@router.message(Registration.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await save_user(message.from_user.id, name=message.text)
    await message.answer("Имя сохранено ✅\nТеперь укажи свой возраст (число):")
    await state.set_state(Registration.waiting_for_age)[span_48](end_span)


@router.message(Registration.waiting_for_age)
async def process_age(message: types.Message, state: FSMContext):
    try:
        age = int(message.text)
        if age < 18 or age > 100:
            await message.answer("Пожалуйста, укажи реальный возраст (от 18 до 100):")
            return
        
        await save_user(message.from_user.id, age=age)
        
        [span_49](start_span)kb = InlineKeyboardMarkup(inline_keyboard=[[span_49](end_span)
            [InlineKeyboardButton(text="👨 Парень", callback_data="gender_male")],
            [InlineKeyboardButton(text="👩 Девушка", callback_data="gender_female")]
        ])
        
        await message.answer("Возраст сохранён ✅\nУкажи свой пол:", reply_markup=kb)
        await state.set_state(Registration.waiting_for_gender)
    except ValueError:
        await message.answer("Пожалуйста, укажи возраст числом:")


@router.callback_query(Registration.waiting_for_gender)
async def process_gender(callback: types.CallbackQuery, state: FSMContext):
    gender = callback.data.split("_")[1]
    [span_50](start_span)await save_user(callback.from_user.id, gender=gender)[span_50](end_span)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Парня", callback_data="looking_male")],
        [InlineKeyboardButton(text="👩 Девушку", callback_data="looking_female")]
    ])
    
    await callback.message.edit_text("Пол сохранён ✅\nКого ты ищешь?", reply_markup=kb)
    await state.set_state(Registration.waiting_for_looking_for)
    await callback.answer()


@router.callback_query(Registration.waiting_for_looking_for)
async def process_looking_for(callback: types.CallbackQuery, state: FSMContext):
    looking_for = callback.data.split("_")[1]
    await save_user(callback.from_user.id, looking_for=looking_for)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [span_51](start_span)[InlineKeyboardButton(text="🔥 Да, ищу интим", callback_data="nsfw_yes")],[span_51](end_span)
        [InlineKeyboardButton(text="💕 Нет, серьёзные отношения", callback_data="nsfw_no")]
    ])
    
    warning_text = (
        "Предпочтения сохранены ✅\n\n"
        "🔞 Ищешь быстрые/интимные отношения?\n\n"
        "**Важно:** Твоя отметка '🔥 Интим' будет видна только тем, кто тоже ищет "
        [span_52](start_span)"такие отношения. Остальные пользователи её не увидят."[span_52](end_span)
    )
    
    await callback.message.edit_text(warning_text, reply_markup=kb)
    await state.set_state(Registration.waiting_for_nsfw)
    await callback.answer()


@router.callback_query(Registration.waiting_for_nsfw)
async def process_nsfw(callback: types.CallbackQuery, state: FSMContext):
    nsfw = 1 if callback.data.split("_")[1] == "yes" else 0
    await save_user(callback.from_user.id, nsfw=nsfw)
    
    await callback.message.edit_text("Настройки сохранены ✅")
    await callback.message.answer("Теперь напиши описание о себе:")
    await state.set_state(Registration.waiting_for_description)
    await callback.answer()


@router.message(Registration.waiting_for_description)
async def process_description(message: types.Message, state: FSMContext):
    await save_user(message.from_user.id, description=message.text)
    [span_53](start_span)await message.answer("Описание сохранено ✅\nТеперь отправь своё фото:")[span_53](end_span)
    await state.set_state(Registration.waiting_for_photo)


@router.message(Registration.waiting_for_photo)
async def process_photo(message: types.Message, state: FSMContext):
    if message.content_type != "photo":
        await message.answer("Пожалуйста, отправь фото:")
        return
    
    file_id = message.photo[-1].file_id
    await save_user(message.from_user.id, photo_id=file_id)
    
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Отправить локацию", request_location=True)]
        ],
        [span_54](start_span)resize_keyboard=True[span_54](end_span)
    )
    
    await message.answer("Фото сохранено ✅\nТеперь отправь геолокацию:", reply_markup=kb)
    await state.set_state(Registration.waiting_for_location)


@router.message(Registration.waiting_for_location)
async def process_location(message: types.Message, state: FSMContext):
    if message.content_type != "location":
        await message.answer("Пожалуйста, отправь геолокацию через кнопку:")
        return
    
    lat, lon = message.location.latitude, message.location.longitude
    await save_user(message.from_user.id, latitude=lat, longitude=lon)
    
    await message.answer(
        "Локация сохранена ✅\n\nРегистрация завершена! 🎉\n"
        [span_55](start_span)"Теперь можешь использовать /menu для навигации.",[span_55](end_span)
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🔍 Смотреть анкеты")],
                [KeyboardButton(text="👤 Моя анкета")],
            ],
            resize_keyboard=True,
            [span_56](start_span)one_time_keyboard=False[span_56](end_span)
        )
    )
    await state.clear()


# ----------------------- ПРОФИЛЬ ИЗМЕНЕНИЯ -----------------------
@router.callback_query(lambda c: c.data == "edit_profile")
async def edit_profile_menu(callback: types.CallbackQuery):
    """Меню изменения анкеты (ИСПРАВЛЕНО: edit_caption/edit_text)"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Имя", callback_data="edit_name")],
        [InlineKeyboardButton(text="🎂 Возраст", callback_data="edit_age")],
        [InlineKeyboardButton(text="👤 Пол", callback_data="edit_gender")],
        [InlineKeyboardButton(text="💑 Кого ищу", callback_data="edit_looking")],
        [InlineKeyboardButton(text="🔞 18+", callback_data="edit_nsfw")],
        [span_57](start_span)[InlineKeyboardButton(text="✍️ Описание", callback_data="edit_description")],[span_57](end_span)
        [InlineKeyboardButton(text="📷 Фото", callback_data="edit_photo")],
        [InlineKeyboardButton(text="📍 Локация", callback_data="edit_location")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_profile")]
    ])
    
    text = "Что хочешь изменить?"
    try:
        # Пытаемся изменить подпись (для сообщений с фото)
        await callback.message.edit_caption(caption=text, reply_markup=kb)
    except TelegramBadRequest:
        # [span_58](start_span)Если не удалось, значит это текстовое сообщение[span_58](end_span)
        await callback.message.edit_text(text, reply_markup=kb)
        
    await callback.answer()


@router.callback_query(lambda c: c.data == "back_to_profile")
async def back_to_profile(callback: types.CallbackQuery):
    """Вернуться к просмотру профиля"""
    await show_my_profile_action(callback.message, callback_data=callback)
    await callback.answer()


@router.callback_query(lambda c: c.data == "edit_name")
async def edit_name(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_caption(caption="Напиши новое имя:")
    except TelegramBadRequest:
        await callback.message.edit_text("Напиши новое имя:")
        
    [span_59](start_span)await state.set_state(EditProfile.waiting_for_new_name)[span_59](end_span)
    await callback.answer()


@router.message(EditProfile.waiting_for_new_name)
async def process_new_name(message: types.Message, state: FSMContext):
    await save_user(message.from_user.id, name=message.text)
    [span_60](start_span)await message.answer("Имя обновлено! ✅")[span_60](end_span)
    await state.clear()


@router.callback_query(lambda c: c.data == "edit_age")
async def edit_age(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_caption(caption="Напиши новый возраст:")
    except TelegramBadRequest:
        await callback.message.edit_text("Напиши новый возраст:")
        
    await state.set_state(EditProfile.waiting_for_new_age)
    await callback.answer()


@router.message(EditProfile.waiting_for_new_age)
async def process_new_age(message: types.Message, state: FSMContext):
    try:
        age = int(message.text)
        if age < 18 or age > 100:
            [span_61](start_span)await message.answer("Возраст должен быть от 18 до 100 лет")[span_61](end_span)
            return
        await save_user(message.from_user.id, age=age)
        await message.answer("Возраст обновлён! ✅")
        await state.clear()
    except ValueError:
        await message.answer("Укажи возраст числом")


@router.callback_query(lambda c: c.data == "edit_gender")
async def edit_gender(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Парень", callback_data="set_gender_male")],
        [span_62](start_span)[InlineKeyboardButton(text="👩 Девушка", callback_data="set_gender_female")][span_62](end_span)
    ])
    
    try:
        await callback.message.edit_caption(caption="Выбери пол:", reply_markup=kb)
    except TelegramBadRequest:
        await callback.message.edit_text("Выбери пол:", reply_markup=kb)
        
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("set_gender_"))
async def set_gender(callback: types.CallbackQuery):
    gender = callback.data.split("_")[2]
    await save_user(callback.from_user.id, gender=gender)
    
    try:
        [span_63](start_span)await callback.message.edit_caption(caption="Пол обновлён! ✅")[span_63](end_span)
    except TelegramBadRequest:
        await callback.message.edit_text("Пол обновлён! ✅")
        
    await callback.answer()


@router.callback_query(lambda c: c.data == "edit_looking")
async def edit_looking(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Парня", callback_data="set_looking_male")],
        [InlineKeyboardButton(text="👩 Девушку", callback_data="set_looking_female")]
    ])
    
    try:
        await callback.message.edit_caption(caption="Кого ищешь?", reply_markup=kb)
    except TelegramBadRequest:
        [span_64](start_span)await callback.message.edit_text("Кого ищешь?", reply_markup=kb)[span_64](end_span)
        
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("set_looking_"))
async def set_looking(callback: types.CallbackQuery):
    looking = callback.data.split("_")[2]
    await save_user(callback.from_user.id, looking_for=looking)
    
    try:
        [span_65](start_span)await callback.message.edit_caption(caption="Предпочтения обновлены! ✅")[span_65](end_span)
    except TelegramBadRequest:
        await callback.message.edit_text("Предпочтения обновлены! ✅")
        
    await callback.answer()


@router.callback_query(lambda c: c.data == "edit_nsfw")
async def edit_nsfw(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Да, ищу интим", callback_data="set_nsfw_1")],
        [InlineKeyboardButton(text="💕 Нет, серьёзные отношения", callback_data="set_nsfw_0")]
    ])
    
    try:
        await callback.message.edit_caption(caption="🔞 Ищешь быстрые/интимные отношения?", reply_markup=kb)
    except TelegramBadRequest:
        [span_66](start_span)await callback.message.edit_text("🔞 Ищешь быстрые/интимные отношения?", reply_markup=kb)[span_66](end_span)
        
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("set_nsfw_"))
async def set_nsfw(callback: types.CallbackQuery):
    nsfw = int(callback.data.split("_")[2])
    await save_user(callback.from_user.id, nsfw=nsfw)
    
    try:
        [span_67](start_span)await callback.message.edit_caption(caption="Настройки 18+ обновлены! ✅")[span_67](end_span)
    except TelegramBadRequest:
        await callback.message.edit_text("Настройки 18+ обновлены! ✅")
        
    await callback.answer()


@router.callback_query(lambda c: c.data == "edit_description")
async def edit_description(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_caption(caption="Напиши новое описание:")
    except TelegramBadRequest:
        await callback.message.edit_text("Напиши новое описание:")
        
    await state.set_state(EditProfile.waiting_for_new_description)
    await callback.answer()


@router.message(EditProfile.waiting_for_new_description)
async def process_new_description(message: types.Message, state: FSMContext):
    await save_user(message.from_user.id, description=message.text)
    [span_68](start_span)await message.answer("Описание обновлено! ✅")[span_68](end_span)
    await state.clear()


@router.callback_query(lambda c: c.data == "edit_photo")
async def edit_photo(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_caption(caption="Отправь новое фото:")
    except TelegramBadRequest:
        await callback.message.edit_text("Отправь новое фото:")
        
    await state.set_state(EditProfile.waiting_for_new_photo)
    await callback.answer()


@router.message(EditProfile.waiting_for_new_photo)
async def process_new_photo(message: types.Message, state: FSMContext):
    if message.content_type != "photo":
        await message.answer("Отправь фото, пожалуйста")
        [span_69](start_span)return[span_69](end_span)
    
    file_id = message.photo[-1].file_id
    await save_user(message.from_user.id, photo_id=file_id)
    [span_70](start_span)await message.answer("Фото обновлено! ✅")[span_70](end_span)
    await state.clear()


@router.callback_query(lambda c: c.data == "edit_location")
async def edit_location(callback: types.CallbackQuery, state: FSMContext):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Отправить локацию", request_location=True)]
        ],
        resize_keyboard=True
    )
    # Удаляем сообщение с анкетой, чтобы отправить новую кнопку
    try:
        await callback.message.delete()
    except:
        [span_71](start_span)pass[span_71](end_span)
        
    await bot.send_message(callback.message.chat.id, "Нажми на кнопку ниже, чтобы отправить новую геолокацию:", reply_markup=kb)
    await state.set_state(EditProfile.waiting_for_new_location)
    await callback.answer()


@router.message(EditProfile.waiting_for_new_location)
async def process_new_location(message: types.Message, state: FSMContext):
    if message.content_type != "location":
        await message.answer("Отправь геолокацию через кнопку")
        return
    
    lat, lon = message.location.latitude, message.location.longitude
    await save_user(message.from_user.id, latitude=lat, longitude=lon)
    [span_72](start_span)await message.answer("Локация обновлена! ✅", reply_markup=ReplyKeyboardMarkup([span_72](end_span)
        keyboard=[
            [KeyboardButton(text="🔍 Смотреть анкеты")],
            [KeyboardButton(text="👤 Моя анкета")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    ))
    await state.clear()


@router.callback_query(lambda c: c.data == "delete_profile")
async def confirm_delete(callback: types.CallbackQuery):
    """Подтверждение удаления (ИСПРАВЛЕНО: edit_caption/edit_text)"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            [span_73](start_span)InlineKeyboardButton(text="✅ Да, удалить", callback_data="confirm_delete_yes"),[span_73](end_span)
            InlineKeyboardButton(text="❌ Отмена", callback_data="confirm_delete_no")
        ]
    ])
    text = (
        "⚠️ Ты уверен, что хочешь удалить анкету?\n\n"
        "Все твои лайки и совпадения будут удалены!"
    )
    
    try:
        # [span_74](start_span)Пытаемся изменить подпись (для сообщений с фото)[span_74](end_span)
        await callback.message.edit_caption(caption=text, reply_markup=kb)
    except TelegramBadRequest:
        # Если не удалось, значит это текстовое сообщение
        await callback.message.edit_text(text, reply_markup=kb)
        
    await callback.answer()


@router.callback_query(lambda c: c.data == "confirm_delete_yes")
async def delete_profile_confirmed(callback: types.CallbackQuery):
    """Удаление подтверждено (ИСПРАВЛЕНО: edit_caption/edit_text)"""
    await delete_user(callback.from_user.id)
    text = (
        "Твоя анкета удалена 😢\n\n"
        [span_75](start_span)"Если захочешь вернуться, используй /start"[span_75](end_span)
    )
    
    try:
        # Пытаемся изменить подпись (для сообщений с фото)
        await callback.message.edit_caption(caption=text)
    except TelegramBadRequest:
        # Если не удалось, значит это текстовое сообщение
        await callback.message.edit_text(text)
        
    await callback.answer()


@router.callback_query(lambda c: c.data == "confirm_delete_no")
async def cancel_delete(callback: types.CallbackQuery):
    """Отмена удаления (ИСПРАВЛЕНО: edit_caption/edit_text)"""
    [span_76](start_span)text = "Удаление отменено ✅"[span_76](end_span)
    
    try:
        # Пытаемся изменить подпись (для сообщений с фото)
        await callback.message.edit_caption(caption=text)
    except TelegramBadRequest:
        # Если не удалось, значит это текстовое сообщение
        await callback.message.edit_text(text)
        
    await callback.answer()

# ----------------------- ОБРАБОТЧИКИ ЖАЛОБ -----------------------

@router.callback_query(lambda c: c.data.startswith("report_") and not c.data.startswith("report_processed_"))
async def handle_report_callback(callback: types.CallbackQuery, state: FSMContext):
    reported_id = int(callback.data.split("_")[1])
    
    # Сохраняем ID пользователя, на которого жалуемся
    await state.update_data(reported_id=reported_id)
    
    # Удаляем сообщение с анкетой
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
    
    # Предлагаем причины для удобства
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Реклама / Спам", callback_data="reason_spam")],
        [InlineKeyboardButton(text="Порнография / 18+", callback_data="reason_nsfw")],
        [InlineKeyboardButton(text="Оскорбления", callback_data="reason_insult")],
        [InlineKeyboardButton(text="Другое (напишу вручную)", callback_data="reason_other")]
    ])
    
    await bot.send_message(
        callback.message.chat.id, 
        "Укажи, пожалуйста, причину жалобы:", 
        reply_markup=kb
    )
    await state.set_state(Reporting.waiting_for_reason)
    await callback.answer()


@router.callback_query(Reporting.waiting_for_reason, F.data.startswith("reason_"))
async def process_reason_callback(callback: types.CallbackQuery, state: FSMContext):
    reason_type = callback.data.split("_")[1]
    
    if reason_type == "other":
        await callback.message.edit_text("Опиши подробно причину жалобы:")
        # Остаемся в этом же состоянии, ждем текстового сообщения
    else:
        # Причина выбрана из готовых, сохраняем и завершаем
        data = await state.get_data()
        reported_id = data.get("reported_id")
        
        # Получаем текст причины
        reason_map = {
            "spam": "Реклама / Спам",
            "nsfw": "Порнография / 18+",
            "insult": "Оскорбления"
        }
        reason_text = reason_map.get(reason_type, "Неизвестная причина")
            
        await save_report(callback.from_user.id, reported_id, reason_text)
        await state.clear()
        
        await callback.message.edit_text("Спасибо! Жалоба отправлена на модерацию. ✅")
        await callback.answer()
        
        # Показываем следующую анкету после жалобы
        await show_next_profile(callback.message.chat.id, callback.from_user.id)


@router.message(Reporting.waiting_for_reason)
async def process_reason_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    reported_id = data.get("reported_id")
    
    reason_text = message.text
    
    await save_report(message.from_user.id, reported_id, reason_text)
    await state.clear()
    
    await message.answer("Спасибо! Жалоба отправлена на модерацию. ✅")
    
    # Показываем следующую анкету после жалобы
    await show_next_profile(message.chat.id, message.from_user.id)

# ----------------------- СИСТЕМА МОДЕРАЦИИ (ADMIN_ID) -----------------------

@router.message(Command("mod"))
async def start_moderation(message: types.Message):
    """Команда для модерации жалоб (только для ADMIN_ID)"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("У вас нет прав администратора.")
        return

    reports = await get_pending_reports()
    
    if not reports:
        await message.answer("Нет новых жалоб на модерацию.")
        return
        
    # Обрабатываем первую жалобу
    report = reports[0]
    reported_user = await get_user(report["reported_id"])
    reporter_user = await get_user(report["reporter_id"])
    
    if not reported_user:
        # Если анкета удалена, автоматически помечаем жалобу как принятую
        await update_report_status(report["id"], "accepted") 
        await message.answer(f"Анкета ID: {report['reported_id']} была удалена. Жалоба закрыта.")
        # Ищем следующую
        await start_moderation(message) 
        return

    # Формируем сообщение модератору
    caption = (
        f"🚨 **Жалоба #{report['id']}**\n"
        f"Нарушитель: {reported_user.get('name')} (ID: {reported_user.get('telegram_id')})\n"
        f"Пол: {reported_user.get('gender')}, 18+: {'Да' if reported_user.get('nsfw') == 1 else 'Нет'}\n"
        f"Жалоба от: {reporter_user.get('name')} (ID: {reporter_user.get('telegram_id')})\n"
        f"Причина: {report['reason']}\n\n"
        f"--- ОПИСАНИЕ: {reported_user.get('description')} ---"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ УДАЛИТЬ АНКЕТУ", callback_data=f"mod_delete_{report['reported_id']}_{report['id']}"),
        ],
        [
            InlineKeyboardButton(text="❌ ОТКЛОНИТЬ ЖАЛОБУ", callback_data=f"mod_reject_{report['id']}"),
        ]
    ])
    
    # Показываем анкету нарушителя
    if reported_user["photo_id"]:
        await bot.send_photo(message.chat.id, reported_user["photo_id"], caption=caption, reply_markup=kb)
    else:
        await message.answer(caption, reply_markup=kb)


@router.callback_query(lambda c: c.data.startswith("mod_delete_"))
async def mod_delete_user(callback: types.CallbackQuery):
    # Извлекаем ID нарушителя и ID жалобы
    parts = callback.data.split("_")
    reported_id = int(parts[2])
    report_id = int(parts[3])
    
    # 1. Удаляем пользователя и все его данные
    await delete_user(reported_id)
    # 2. Обновляем статус текущей жалобы как "принятая"
    await update_report_status(report_id, "accepted") 
    
    try:
        await callback.message.edit_caption(caption=f"Пользователь ID: {reported_id} удален! ✅\nЖалоба #{report_id} закрыта.")
    except TelegramBadRequest:
        await callback.message.edit_text(f"Пользователь ID: {reported_id} удален! ✅\nЖалоба #{report_id} закрыта.")
        
    await callback.answer("Анкета удалена.")
    
    # 3. Показываем следующую жалобу
    await start_moderation(callback.message)
    

@router.callback_query(lambda c: c.data.startswith("mod_reject_"))
async def mod_reject_report(callback: types.CallbackQuery):
    # Извлекаем ID жалобы
    report_id = int(callback.data.split("_")[2])
    
    # 1. Отклоняем жалобу
    await update_report_status(report_id, "rejected")
    
    try:
        await callback.message.edit_caption(caption=f"Жалоба #{report_id} отклонена. ❌")
    except TelegramBadRequest:
        await callback.message.edit_text(f"Жалоба #{report_id} отклонена. ❌")
        
    await callback.answer("Жалоба отклонена.")
    
    # 2. Показываем следующую жалобу
    await start_moderation(callback.message)


# ----------------------- ЛАЙКИ И СОВПАДЕНИЯ -----------------------
@router.message(Command("likes"))
async def show_likes(message: types.Message):
    unviewed_likes = await get_unviewed_likes(message.from_user.id)
    
    [span_77](start_span)if not unviewed_likes:[span_77](end_span)
        await message.answer("У тебя пока нет новых лайков 😔")
        return
    
    from_telegram_id = unviewed_likes[0]
    from_user = await get_user(from_telegram_id)
    
    if not from_user:
        [span_78](start_span)await message.answer("Произошла ошибка. Попробуй позже.")[span_78](end_span)
        # Помечаем лайк как просмотренный, чтобы не зацикливаться на нём
        await mark_like_as_viewed(from_telegram_id, message.from_user.id)
        return
    
    current_user = await get_user(message.from_user.id)
    dist = haversine(
        current_user["latitude"], current_user["longitude"],
        from_user["latitude"], from_user["longitude"]
    )
    
    gender_emoji = "👨" if from_user["gender"] == "male" else "👩"
    [span_79](start_span)caption = f"❤️ Тебя лайкнул(а):\n\n{gender_emoji} {from_user['name']}, {from_user['age']} лет\n📍 {round(dist, 1)} км от тебя\n\n{from_user['description']}"[span_79](end_span)

    if current_user["nsfw"] == 1 and from_user["nsfw"] == 1:
        caption = f"🔥 18+ {caption}"

    remaining = len(unviewed_likes) - 1
    if remaining > 0:
        caption += f"\n\n💌 Ещё лайков: {remaining}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️ Ответить взаимностью", callback_data=f"like_back_{from_telegram_id}"),
        ],
        [
            [span_80](start_span)InlineKeyboardButton(text="❌ Пропустить", callback_data=f"skip_like_{from_telegram_id}")[span_80](end_span)
        ]
    ])
    
    if from_user["photo_id"]:
        await bot.send_photo(message.chat.id, from_user["photo_id"], caption=caption, reply_markup=keyboard)
    else:
        await message.answer(caption, reply_markup=keyboard)


@router.callback_query(lambda c: c.data.startswith("like_back_"))
async def handle_like_back(callback: types.CallbackQuery):
    from_telegram_id = int(callback.data.split("_")[2])
    to_telegram_id = callback.from_user.id
    
    [span_81](start_span)from_user = await get_user(from_telegram_id)[span_81](end_span)
    
    # >>> НОВАЯ ПРОВЕРКА: Если профиль, который лайкнул, удален
    if not from_user:
        # 1. Помечаем лайк как просмотренный
        await mark_like_as_viewed(from_telegram_id, to_telegram_id)
        
        # 2. Удаляем старую анкету с лайком
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            [span_82](start_span)pass[span_82](end_span)
            
        # 3. Отправляем уведомление
        await bot.send_message(
            to_telegram_id,
            "❌ Пользователь, который вас лайкнул, **уже удалил свою анкету**.",
            reply_markup=types.ReplyKeyboardRemove()
        )
        
        [span_83](start_span)await callback.answer("Пользователь удален.")[span_83](end_span)
        
        # 4. Показываем следующий лайк (если есть)
        await show_likes(callback.message)
        return
    # <<< КОНЕЦ НОВОЙ ПРОВЕРКИ
    
    # Если профиль существует (стандартный сценарий совпадения):
    await mark_like_as_viewed(from_telegram_id, to_telegram_id)
    await save_like(to_telegram_id, from_telegram_id)
    
    to_user = await get_user(to_telegram_id)
    
    try:
        [span_84](start_span)from_chat = await bot.get_chat(from_telegram_id)[span_84](end_span)
        from_username = f"@{from_chat.username}" if from_chat.username else "скрыт"
    except:
        from_username = "скрыт"
    
    try:
        to_chat = await bot.get_chat(to_telegram_id)
        to_username = f"@{to_chat.username}" if to_chat.username else "скрыт"
    except:
        to_username = "скрыт"
    
    await bot.send_message(
        [span_85](start_span)to_telegram_id,[span_85](end_span)
        f"🎉 У тебя совпадение с {from_user['name']}!\n"
        f"Telegram: {from_username}"
    )
    await bot.send_message(
        from_telegram_id,
        f"🎉 У тебя совпадение с {to_user['name']}!\n"
        f"Telegram: {to_username}"
    )
    
    [span_86](start_span)await callback.answer("Взаимность! 💕")[span_86](end_span)
    await callback.message.delete()
    
    # Показываем следующий лайк, если есть
    await show_likes(callback.message)


@router.callback_query(lambda c: c.data.startswith("skip_like_"))
async def handle_skip_like(callback: types.CallbackQuery):
    from_telegram_id = int(callback.data.split("_")[2])
    to_telegram_id = callback.from_user.id
    
    await mark_like_as_viewed(from_telegram_id, to_telegram_id)
    
    await callback.answer("Пропущено")
    await callback.message.delete()
    
    # Показываем следующий лайк, если есть
    await show_likes(callback.message)


@router.callback_query(lambda c: c.data.startswith("like_") and not c.data.startswith("like_back_"))
async def handle_like(callback: types.CallbackQuery):
    to_telegram_id = int(callback.data.split("_")[1])
    [span_87](start_span)from_telegram_id = callback.from_user.id[span_87](end_span)

    # Сохраняем лайк
    await save_like(from_telegram_id, to_telegram_id)
    
    # Получаем данные обоих пользователей
    from_user = await get_user(from_telegram_id)
    to_user = await get_user(to_telegram_id)

    # Если по какой-то причине одного из пользователей нет в БД, выходим
    if not from_user or not to_user:
        await callback.answer("Ошибка: пользователь не найден.", show_alert=True)
        return

    # Отправляем уведомление получателю в виде анкеты
    try:
        [span_88](start_span)dist = haversine([span_88](end_span)
            to_user["latitude"], to_user["longitude"],
            from_user["latitude"], from_user["longitude"]
        )
        
        gender_emoji = "👨" if from_user["gender"] == "male" else "👩"
        caption = f"❤️ Тебя лайкнул(а):\n\n{gender_emoji} {from_user['name']}, {from_user['age']} лет\n📍 {round(dist, 1)} км от тебя\n\n{from_user['description']}"
        
        # [span_89](start_span)Показываем метку 18+ только если оба выставили nsfw=1[span_89](end_span)
        if to_user["nsfw"] == 1 and from_user["nsfw"] == 1:
            caption = f"🔥 18+ {caption}"
        
        unviewed_count = await count_unviewed_likes(to_telegram_id)
        if unviewed_count > 1:
            caption += f"\n\n💌 Ещё лайков: {unviewed_count - 1}"

        [span_90](start_span)keyboard = InlineKeyboardMarkup(inline_keyboard=[[span_90](end_span)
            [
                InlineKeyboardButton(text="❤️ Ответить взаимностью", callback_data=f"like_back_{from_telegram_id}"),
            ],
            [
                InlineKeyboardButton(text="❌ Пропустить", callback_data=f"skip_like_{from_telegram_id}")
            ]
        ])
      
        [span_91](start_span)if from_user["photo_id"]:[span_91](end_span)
            await bot.send_photo(to_telegram_id, from_user["photo_id"], caption=caption, reply_markup=keyboard)
        else:
            await bot.send_message(to_telegram_id, caption, reply_markup=keyboard)

    except Exception as e:
        print(f"Не удалось отправить уведомление о лайке пользователю {to_telegram_id}: {e}")

    [span_92](start_span)await callback.answer("Лайк отправлен! ❤️")[span_92](end_span)
    
    # Обновляем last_viewed для того, кто лайкнул
    await update_last_viewed(from_telegram_id, to_user["id"])
    
    # Удаляем старое сообщение и показываем следующую анкету
    await callback.message.delete()
    await show_next_profile(callback.message.chat.id, from_telegram_id)


@router.callback_query(lambda c: c.data.startswith("skip_") and not c.data.startswith("skip_like_"))
async def handle_skip(callback: types.CallbackQuery):
    skipped_id = int(callback.data.split("_")[1])
    await update_last_viewed(callback.from_user.id, skipped_id)
    await callback.answer("Пропущено ❌")
    
    await callback.message.delete()
    await show_next_profile(callback.message.chat.id, callback.from_user.id)


# ----------------------- ЗАПУСК БОТА -----------------------
async def main():
    await init_db()
    
    # [span_93](start_span)>>> Регистрируем команды при запуске бота[span_93](end_span)
    await set_main_menu_commands(bot)
    print("Бот запущен 🚀")
    # Добавляем ADMIN_ID в контекст, чтобы он был доступен для модерации
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())