# main.py
"""
Симуляционный Telegram P2P-обменник USDT → RUB
Версия для Railway (Python 3.12), без базы данных, тестовые платежи
"""

import asyncio
import logging
import os
import random
import uuid

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

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# Конфиг из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан в переменных окружения Railway!")

PORT = int(os.getenv("PORT", 8000))
WEBHOOK_PATH = "/webhook"

# Автоматическое определение домена Railway
RAILWAY_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN")
WEBHOOK_URL = f"https://{RAILWAY_DOMAIN}{WEBHOOK_PATH}" if RAILWAY_DOMAIN else f"http://localhost:{PORT}{WEBHOOK_PATH}"

logger.info(f"Старт бота | Webhook: {WEBHOOK_URL}")

# FastAPI приложение
app = FastAPI(title="P2P Exchanger Test", version="1.0")

# Глобальный объект приложения Telegram
application: Application = None


# ──────────────────────────────────────────────────────────────────────────────
# Утилиты

def get_rate() -> float:
    """Симуляция курса с небольшой наценкой"""
    return 105.50 * (1 + random.uniform(0.05, 0.10))


def jitter_amount(base: float) -> float:
    """Лёгкая рандомизация суммы"""
    return round(base * random.uniform(0.92, 1.12), 2)


async def create_test_payment(amount_usdt: float, order_id: str) -> str:
    """Тестовая платёжная ссылка (без реального шлюза)"""
    fake_tx = uuid.uuid4().hex[:10]
    url = f"https://test-pay.example.com/{fake_tx}?order={order_id}&sum={amount_usdt}"
    logger.info(f"Создана тестовая оплата: {url}")
    return url


# ──────────────────────────────────────────────────────────────────────────────
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


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "ex_usdt_rub":
        context.user_data["mode"] = "usdt_rub"
        await query.message.reply_text("Введите сумму в USDT (минимум 10):")


async def handle_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get("mode") != "usdt_rub":
        await update.message.reply_text("Начните с /start")
        return

    try:
        amount = float(update.message.text.strip())
        if amount < 10:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введите число ≥ 10")
        return

    rate = get_rate()
    rub = jitter_amount(amount * rate)

    order_id = str(uuid.uuid4())[:8].upper()
    payment_url = await create_test_payment(amount, order_id)

    await update.message.reply_text(
        f"Ордер #{order_id}\n\n"
        f"Отправляете: {amount:.2f} USDT\n"
        f"Получаете ≈ {rub:.2f} RUB\n\n"
        f"Ссылка на оплату (тест):\n{payment_url}\n\n"
        "После оплаты напишите /confirm"
    )


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "✅ Оплата подтверждена (симуляция)\n"
        "Зачислено на карту: 2200 1234 5678 9012\n"
        "Спасибо за использование!"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Webhook

@app.post(WEBHOOK_PATH)
async def webhook(request: Request):
    update = Update.de_json(await request.json(), application.bot)
    await application.process_update(update)
    return {"ok": True}


# ──────────────────────────────────────────────────────────────────────────────
# Инициализация

async def init():
    global application
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback))
    application.add_handler(MessageHandler(filters.TEXT & \~filters.COMMAND, handle_amount))
    application.add_handler(CommandHandler("confirm", confirm))

    await application.initialize()
    await application.bot.set_webhook(url=WEBHOOK_URL)
    logger.info("Webhook установлен успешно")


# ──────────────────────────────────────────────────────────────────────────────
# Запуск

if __name__ == "__main__":
    import uvicorn

    # Инициализация бота
    asyncio.run(init())

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )
