import asyncio
import logging
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, F, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery
from aiogram.filters import Command

# --- Настройки ---
API_TOKEN = "8695632610:AAEqnBJbWlSaqGocbaeoqWL6ZqSZpuJ41Pw"
PRICE_IN_STARS = 1  # Цена в звездах за 1 эмодзи

# --- Инициализация ---
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- База Данных (SQLite) ---
def init_db():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    # Таблица пользователей и их эмодзи
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            premium_emojis TEXT DEFAULT ''
        )
    ''')
    # Таблица для логирования транзакций
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            date TEXT,
            telegram_payment_charge_id TEXT UNIQUE
        )
    ''')
    conn.commit()
    conn.close()

# --- Вспомогательные функции ---
def add_emoji_to_user(user_id: int, emoji_id: str):
    """Добавляет ID эмодзи пользователю в БД"""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT premium_emojis FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if result:
        current_emojis = result[0]
        new_emojis = f"{current_emojis},{emoji_id}" if current_emojis else emoji_id
        cursor.execute("UPDATE users SET premium_emojis = ? WHERE user_id = ?", (new_emojis, user_id))
    else:
        cursor.execute("INSERT INTO users (user_id, premium_emojis) VALUES (?, ?)", (user_id, emoji_id))
    conn.commit()
    conn.close()

def get_user_emojis(user_id: int) -> list:
    """Возвращает список ID эмодзи пользователя"""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT premium_emojis FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result and result[0]:
        return result[0].split(',')
    return []

# --- Хендлеры команд ---

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "🌟 *Добро пожаловать в Эмодзи-Магазин!* 🌟\n\n"
        "Здесь ты можешь купить эксклюзивные премиум эмодзи.\n"
        "💰 *Цена:* 1 эмодзи = 1 Звезда Telegram\n\n"
        "👇 Нажми на кнопку ниже, чтобы выбрать эмодзи!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✨ Купить новый эмодзи ✨", callback_data="buy_emoji")],
            [InlineKeyboardButton(text="📦 Мои эмодзи", callback_data="my_emojis")]
        ]),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "buy_emoji")
async def show_emoji_shop(callback: CallbackQuery):
    """Показывает каталог доступных эмодзи с кнопкой покупки"""
    await callback.answer()
    
    # Здесь ты можешь добавить реальные ID эмодзи, которые купил на Fragment
    # Пока просто заглушка для демонстрации
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Огненный Лис", callback_data="purchase_emoji:5368324170671202286")],
        [InlineKeyboardButton(text="🎨 Неоновая Клякса", callback_data="purchase_emoji:5735975430289161622")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    
    await callback.message.edit_text(
        "🛍 *Выбери премиум эмодзи для покупки:*\n\n"
        "Цена каждого эмодзи: 1 Telegram Звезда ⭐️\n\n"
        "_После нажатия кнопки, Telegram откроет окно оплаты._",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("purchase_emoji:"))
async def process_emoji_purchase(callback: CallbackQuery):
    """Создает счет на оплату (Invoice) через Telegram Stars"""
    emoji_id = callback.data.split(":")[1]
    
    # Сохраняем ID эмодзи во временные данные, чтобы потом знать, что выдавать
    # В реальном проекте используй FSM (машину состояний) или словарь в памяти
    # Для простоты - запоминаем в callback.data, но это плохая практика для продакшена.
    # Лучше использовать FSM, но для примера сойдет.
    
    await callback.answer()
    
    # Создаем счет (Invoice)
    # Название товара и описание
    title = "Премиум Эмодзи"
    description = "Получи эксклюзивный премиум эмодзи для использования в любом чате!"
    # Цена в звездах (XTR - внутренняя валюта Telegram)
    prices = [LabeledPrice(label="Цена (⭐ Stars)", amount=PRICE_IN_STARS)]
    # В параметр start_parameter можно передать что угодно уникальное
    start_parameter = f"buy_emoji_{emoji_id}_{callback.from_user.id}"
    
    # Клавиатура с кнопкой оплаты
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Оплатить 1 Звездой 💎", pay=True)],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="buy_emoji")]
    ])
    
    try:
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=title,
            description=description,
            payload=f"emoji_{emoji_id}",  # Важные данные, чтобы понять, ЧТО купили
            provider_token="",  # Для Stars оставляем пустым
            currency="XTR",     # XTR = Telegram Stars
            prices=prices,
            start_parameter=start_parameter,
            reply_markup=keyboard
        )
        await callback.message.delete()  # Удаляем предыдущее меню
    except Exception as e:
        logging.error(f"Ошибка отправки инвойса: {e}")
        await callback.message.answer("❌ Не удалось создать платеж. Попробуй позже.")

@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    """Обязательная проверка перед оплатой. Всегда подтверждаем."""
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: Message):
    """Выполняется при успешной оплате"""
    payment_info = message.successful_payment
    payload = payment_info.invoice_payload  # Строка вида "emoji_5368324170671202286"
    telegram_charge_id = payment_info.telegram_payment_charge_id
    user_id = message.from_user.id
    
    # Извлекаем ID эмодзи из payload
    if payload.startswith("emoji_"):
        emoji_id = payload.replace("emoji_", "")
    else:
        await message.answer("❌ Ошибка: не удалось определить товар.")
        return
    
    # 1. Сохраняем транзакцию в БД, чтобы не засчитать повторно
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO transactions (user_id, amount, date, telegram_payment_charge_id) VALUES (?, ?, ?, ?)",
            (user_id, PRICE_IN_STARS, datetime.now().isoformat(), telegram_charge_id)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # Такая транзакция уже была обработана
        await message.answer("⚠️ Этот платеж уже был обработан ранее.")
        conn.close()
        return
    conn.close()
    
    # 2. Добавляем эмодзи пользователю в БД
    add_emoji_to_user(user_id, emoji_id)
    
    # 3. Поздравляем пользователя и даем инструкцию
    await message.answer(
        f"✅ *Поздравляю! Оплата прошла успешно!*\n\n"
        f"🎁 Ты получил новый премиум эмодзи!\n\n"
        f"✨ *Как использовать:*\n"
        f"1. Скопируй команду ниже\n"
        f"2. Вставь её в любое поле ввода текста (чат, описание, статус)\n"
        f"3. Telegram сам превратит ссылку в эмодзи\n\n"
        f"`[{chr(128139)}](tg://emoji?id={emoji_id})`\n\n"
        f"Ты всегда можешь вернуться в меню и нажать 'Мои эмодзи', чтобы скопировать ссылку снова.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_menu")]
        ]),
        parse_mode="MarkdownV2"  # Важно для ссылок tg://
    )

@dp.callback_query(F.data == "my_emojis")
async def show_my_emojis(callback: CallbackQuery):
    """Показывает список купленных пользователем эмодзи"""
    user_id = callback.from_user.id
    emojis_list = get_user_emojis(user_id)
    
    if not emojis_list:
        await callback.answer("У тебя пока нет купленных эмодзи!", show_alert=True)
        return
    
    text = "📦 *Твои премиум эмодзи:*\n\n"
    keyboard_buttons = []
    
    for e_id in emojis_list:
        # Каждая ссылка вида: [🗿](tg://emoji?id=123456)
        text += f"• `[{chr(128139)}](tg://emoji?id={e_id})` \n"
        keyboard_buttons.append([InlineKeyboardButton(text=f"Скопировать код", callback_data=f"copy_emoji:{e_id}")])
    
    text += "\n_Нажми на кнопку, чтобы скопировать ссылку на эмодзи._"
    keyboard_buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")])
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
        parse_mode="MarkdownV2"
    )

@dp.callback_query(F.data.startswith("copy_emoji:"))
async def copy_emoji_command(callback: CallbackQuery):
    """Отправляет в чат ссылку, которую юзер может скопировать"""
    emoji_id = callback.data.split(":")[1]
    await callback.answer("Вот твой эмодзи! Нажми и удерживай, чтобы скопировать.", show_alert=False)
    
    await callback.message.answer(
        f"✨ *Твой эмодзи:*\n\n"
        f"`[{chr(128139)}](tg://emoji?id={emoji_id})`\n\n"
        f"Скопируй эту ссылку и используй в Telegram\\!",
        parse_mode="MarkdownV2"
    )

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    await cmd_start(callback.message)

# --- Запуск ---
async def main():
    init_db()
    logging.basicConfig(level=logging.INFO)
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
