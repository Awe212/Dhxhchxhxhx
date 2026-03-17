# main.py
# Симуляционный Telegram-обменник USDT → RUB (тестовая версия для Railway)
# Токен уже вставлен. После деплоя проверь /start в Telegram

import asyncio
import uuid
import random
import os
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import aiohttp

# ──────────────────────────────────────────────────────────────────────────────
# ТВОЙ ТОКЕН УЖЕ ЗДЕСЬ
BOT_TOKEN = "8725892114:AAGOQTmyHtQa9a2JIyhjwCSa1x1tqG1sdzQ"

# Получаем домен от Railway автоматически
RAILWAY_PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN")
PORT = int(os.getenv("PORT", 8000))
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://{RAILWAY_PUBLIC_DOMAIN}{WEBHOOK_PATH}" if RAILWAY_PUBLIC_DOMAIN else f"http://localhost:{PORT}{WEBHOOK_PATH}"

print(f"Запуск бота с webhook: {WEBHOOK_URL}")

# FastAPI приложение
app = FastAPI(title="Exchanger Test v12 - Railway")

# Глобальные переменные для бота
bot = None
application = None

# ──────────────────────────────────────────────────────────────────────────────
# Простые утилиты (без БД для начала, чтобы не было ошибок)

async def get_rate() -> float:
    return 105.50 * (1 + random.uniform(0.05, 0.10))

def jitter_amount(base: float) -> float:
    return round(base * random.uniform(0.92, 1.12), 2)

async def create_test_invoice(amount_usdt: float, order_id: str) -> str:
    # Симуляция ссылки на оплату (пока без реального Cryptomus)
    print(f"Создаём тестовый инвойс: {amount_usdt} USDT, ордер {order_id}")
    return f"https://test-payment.example.com/pay/{order_id}?amount={amount_usdt}"

# ──────────────────────────────────────────────────────────────────────────────
# Telegram команды

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("USDT → RUB (карта/СБП)", callback_data="exchange_usdt_rub")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Привет! Это тестовый симуляционный обменник.\n"
        "Выбери направление:",
        reply_markup=reply_markup
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "exchange_usdt_rub":
        context.user_data["mode"] = "usdt_to_rub"
        await query.message.reply_text("Введи сумму в USDT (минимум 10):")

async def amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("mode") != "usdt_to_rub":
        await update.message.reply_text("Начни с /start")
        return

    try:
        usdt = float(update.message.text.strip())
        if usdt < 10:
            raise ValueError
    except:
        await update.message.reply_text("Введи число не меньше 10")
        return

    rate = await get_rate()
    rub = jitter_amount(usdt * rate)

    order_id = str(uuid.uuid4())[:8].upper()

    payment_url = await create_test_invoice(usdt, order_id)

    await update.message.reply_text(
        f"Ордер: {order_id}\n"
        f"Отправляешь: {usdt:.2f} USDT\n"
        f"Получаешь ≈ {rub:.2f} RUB\n\n"
        f"Ссылка на оплату (тест):\n{payment_url}\n\n"
        "После оплаты напиши /paid — пришлю симуляцию зачисления"
    )

async def paid_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Оплата подтверждена (симуляция)!\n"
        "Реквизиты: 2200 1234 5678 9012 (тестовая карта)\n"
        "Сумма зачислена. Спасибо!"
    )

# ──────────────────────────────────────────────────────────────────────────────
# Webhook для Telegram

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    update = Update.de_json(await request.json(), bot)
    await application.process_update(update)
    return {"ok": True}

# ──────────────────────────────────────────────────────────────────────────────
# Запуск

async def setup_bot():
    global bot, application
    bot = await Bot(token=BOT_TOKEN).initialize()
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & \~filters.COMMAND, amount_handler))
    application.add_handler(CommandHandler("paid", paid_handler))

    await bot.set_webhook(url=WEBHOOK_URL)
    print("Webhook успешно установлен!")

if __name__ == "__main__":
    import uvicorn
    asyncio.run(setup_bot())
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, log_level="info")
