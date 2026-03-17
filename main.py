# main.py
"""
Профессиональный симуляционный Telegram-обменник USDT → RUB
Версия для Railway (Python 3.12), без БД, с тестовыми платежами
Исправлены все синтаксические ошибки, добавлено логирование
"""

import asyncio
import logging
import os
import random
import uuid
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

# ──────────────────────────────────────────────────────────────────────────────
# Настройки логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Конфигурация (из переменных окружения Railway)
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан в переменных окружения Railway")

PORT = int(os.getenv("PORT", 8000))
WEBHOOK_PATH = "/webhook"

# Автоматическое определение домена от Railway
RAILWAY_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN")
WEBHOOK_URL = f"https://{RAILWAY_DOMAIN}{WEBHOOK_PATH}" if RAILWAY_DOMAIN else f"http://localhost:{PORT}{WEBHOOK_PATH}"

logger.info(f"Запуск бота | Webhook URL: {WEBHOOK_URL}")

# ──────────────────────────────────────────────────────────────────────────────
# FastAPI приложение
app = FastAPI(
    title="P2P Exchanger Simulator",
    description="Симуляционный Telegram-обменник для тестирования",
    version="1.0.0"
)

# Глобальные объекты
bot_application: Application = None

# ──────────────────────────────────────────────────────────────────────────────
# Утилиты

def calculate_rate() -> float:
    """Симуляция текущего курса с небольшой накруткой"""
    base = 105.50
    spread = random.uniform(0.05, 0.10)
    return base * (1 + spread)


def apply_jitter(amount: float) -> float:
    """Лёгкая рандомизация суммы для реализма"""
    jitter = random.uniform(-0.08, 0.12)
    return round(amount * (1 + jitter), 2)


async def create_test_payment(amount_usdt: float, order_id: str) -> str:
    """Симуляция создания платёжной ссылки (без реального шлюза)"""
    fake_tx = uuid.uuid4().hex[:10]
    url = f"https://test-gateway.example.com/pay/{fake_tx}?order={order_id}&amt={amount_usdt}"
    logger.info(f"Создана тестовая ссылка оплаты: {url}")
    return url

# ──────────────────────────────────────────────────────────────────────────────
# Обработчики Telegram

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("USDT → RUB (карта/СБП)", callback_data="ex_usdt_rub")]
    ]
    await update.message.reply_text(
        "Добро пожаловать в симуляционный P2P-обменник v1.0\n"
        "Выберите направление обмена:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "ex_usdt_rub":
        context.user_data["mode"] = "usdt_rub"
        await query.message.reply_text(
            "Введите сумму в USDT (минимум 10 USDT):"
        )


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get("mode") != "usdt_rub":
        await update.message.reply_text("Начните с команды /start")
        return

    try:
        usdt_amount = float(update.message.text.strip())
        if usdt_amount < 10:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введите корректное число не меньше 10")
        return

    rate = calculate_rate()
    rub_amount = apply_jitter(usdt_amount * rate)

    order_id = str(uuid.uuid4())[:8].upper()
    payment_url = await create_test_payment(usdt_amount, order_id)

    await update.message.reply_text(
        f"Ордер #{order_id}\n\n"
        f"Вы отправляете: {usdt_amount:.2f} USDT\n"
        f"Получаете ≈ {rub_amount:.2f} RUB\n\n"
        f"Ссылка на оплату (тестовая):\n{payment_url}\n\n"
        "После оплаты напишите /confirm для симуляции зачисления"
    )


async def cmd_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "✅ Оплата подтверждена (симуляция)\n"
        "Зачислено на карту: 2200 1234 5678 9012\n"
        "Сумма успешно получена. Спасибо за использование!"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Webhook-эндпоинт для Telegram

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    update = Update.de_json(await request.json(), bot_application.bot)
    await bot_application.process_update(update)
    return JSONResponse({"ok": True})


# ──────────────────────────────────────────────────────────────────────────────
# Инициализация бота

async def init_bot():
    global bot_application
    bot_application = Application.builder().token(BOT_TOKEN).build()

    # Регистрация обработчиков
    bot_application.add_handler(CommandHandler("start", cmd_start))
    bot_application.add_handler(CallbackQueryHandler(callback_query))
    bot_application.add_handler(MessageHandler(filters.TEXT & \~filters.COMMAND, text_handler))
    bot_application.add_handler(CommandHandler("confirm", cmd_confirm))

    await bot_application.initialize()
    await bot_application.bot.set_webhook(url=WEBHOOK_URL)
    logger.info("Webhook успешно установлен")


# ──────────────────────────────────────────────────────────────────────────────
# Запуск

if __name__ == "__main__":
    import uvicorn

    # Инициализация бота перед запуском сервера
    asyncio.run(init_bot())

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        log_level="info",
        workers=1,
    )
