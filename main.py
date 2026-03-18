# main.py
"""
Telegram P2P-обменник в режиме polling (без webhook, без FastAPI)
"""

import asyncio
import logging
import os
import random
import uuid

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("ExchangerBot")

BOT_TOKEN = os.getenv("BOT_TOKEN") or "8725892114:AAGOQTmyHtQa9a2JIyhjwCSa1x1tqG1sdzQ"

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан!")

# ────────────────────────────────────────────────
# Утилиты

def get_rate() -> float:
    return 105.50 * (1 + random.uniform(0.05, 0.10))

def jitter(base: float) -> float:
    return round(base * random.uniform(0.92, 1.08), 2)

async def create_fake_payment(amount: float, order_id: str) -> str:
    tx = uuid.uuid4().hex[:10]
    url = f"https://test-pay.example.com/pay/{tx}?order={order_id}&sum={amount}"
    logger.info(f"Сгенерирована тестовая оплата → {url}")
    return url


# ────────────────────────────────────────────────
# Обработчики

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("USDT → RUB (карта/СБП)", callback_data="ex_usdt_rub")]
    ]
    await update.message.reply_text(
        "Добро пожаловать в симуляционный обменник\n"
        "Выберите направление:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "ex_usdt_rub":
        context.user_data["mode"] = "usdt_rub"
        await query.message.reply_text("Введите сумму в USDT (минимум 10):")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get("mode") != "usdt_rub":
        await update.message.reply_text("Напишите /start для начала")
        return

    try:
        amount = float(update.message.text.strip())
        if amount < 10:
            await update.message.reply_text("Сумма должна быть не меньше 10")
            return
    except:
        await update.message.reply_text("Введите число")
        return

    rate = get_rate()
    rub = jitter(amount * rate)

    order_id = str(uuid.uuid4())[:8].upper()
    payment_url = await create_fake_payment(amount, order_id)

    await update.message.reply_text(
        f"Ордер #{order_id}\n\n"
        f"Отправляете: {amount:.2f} USDT\n"
        f"Получаете ≈ {rub:.2f} RUB\n\n"
        f"Ссылка на оплату (тест):\n{payment_url}\n\n"
        "После оплаты напишите /confirm"
    )

    context.user_data.pop("mode", None)

async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "✅ Оплата подтверждена (симуляция)\n"
        "Зачислено на карту: 2200 1234 5678 9012\n"
        "Спасибо за использование!"
    )


# ────────────────────────────────────────────────
# Запуск polling

async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_query))
    app.add_handler(MessageHandler(filters.TEXT, text_handler))
    app.add_handler(CommandHandler("confirm", confirm))

    logger.info("Бот запущен в режиме polling")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    await asyncio.Event().wait()  # Держим бота живым


if __name__ == "__main__":
    asyncio.run(main())
