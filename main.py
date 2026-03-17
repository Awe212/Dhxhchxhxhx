# main.py
"""
Симуляционный Telegram P2P-обменник USDT → RUB
Версия без фильтров, без БД, тестовые платежи
Готов к Railway (Python 3.12)
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
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("ExchangerBot")

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан в переменных окружения!")

PORT = int(os.getenv("PORT", 8000))
WEBHOOK_PATH = "/webhook"

RAILWAY_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN")
WEBHOOK_URL = f"https://{RAILWAY_DOMAIN}{WEBHOOK_PATH}" if RAILWAY_DOMAIN else f"http://localhost:{PORT}{WEBHOOK_PATH}"

logger.info(f"Запуск бота | Webhook URL: {WEBHOOK_URL}")

# FastAPI приложение
app = FastAPI(title="P2P Exchanger Test", version="1.0")

# Глобальный объект
application: Application = None


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


async def any_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Обрабатываем любое текстовое сообщение
    # Если пользователь уже в режиме обмена — обрабатываем сумму
    if context.user_data.get("mode") == "usdt_rub":
        try:
            amount = float(update.message.text.strip())
            if amount < 10:
                await update.message.reply_text("Сумма должна быть не меньше 10 USDT")
                return
        except:
            await update.message.reply_text("Пожалуйста, введите число")
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

        # Сбрасываем режим после обработки
        context.user_data.pop("mode", None)
    else:
        # Если не в режиме — просто подсказка
        await update.message.reply_text("Напишите /start для начала обмена")


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "✅ Оплата подтверждена (симуляция)\n"
        "Зачислено на карту: 2200 1234 5678 9012\n"
        "Спасибо за использование!"
    )


# ────────────────────────────────────────────────
# Webhook

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    update = Update.de_json(await request.json(), application.bot)
    await application.process_update(update)
    return {"ok": True}


# ────────────────────────────────────────────────
# Инициализация

async def setup():
    global application
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_query))
    application.add_handler(MessageHandler(filters.TEXT, any_text_handler))  # любой текст
    application.add_handler(CommandHandler("confirm", confirm))

    await application.initialize()
    await application.bot.set_webhook(url=WEBHOOK_URL)
    logger.info("Webhook успешно установлен")


# ────────────────────────────────────────────────
# Запуск — ТОЛЬКО ЗДЕСЬ

if __name__ == "__main__":
    import uvicorn
    asyncio.run(setup())
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )
