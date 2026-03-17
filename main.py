# main.py
# Симуляционный Telegram-обменник USDT → RUB/CARD через high-risk шлюзы
# Версия для Railway / VPS деплоя (март 2026)

import asyncio
import uuid
import random
import hmac
import hashlib
from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException
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
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, String, Float, DateTime
import aiohttp
import os
import redis.asyncio as redis

# ──────────────────────────────────────────────────────────────────────────────
# Конфигурация из переменных окружения (Railway / .env / VPS)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CRYPTOMUS_API_KEY = os.getenv("CRYPTOMUS_API_KEY")
CRYPTOMUS_MERCHANT_ID = os.getenv("CRYPTOMUS_MERCHANT_ID")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://your-service.up.railway.app/webhook

# База данных — Railway PostgreSQL (DATABASE_URL) или локальный DB_URL
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("DB_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL или DB_URL не установлен в переменных окружения")

# Redis — опционально, для rate-limit / кэша курсов
REDIS_URL = os.getenv("REDIS_URL")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    order_id = Column(String(36), unique=True, index=True)
    user_id = Column(String(64))
    amount_usdt = Column(Float)
    amount_rub = Column(Float)
    currency = Column(String(8), default="RUB")
    status = Column(String(32), default="pending")  # pending → paid → delivered → refunded
    payment_url = Column(String(512))
    gateway = Column(String(32))  # cryptomus / enot
    tx_id = Column(String(128))
    refund_amount = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime)

app = FastAPI(title="Exchanger Simulator v12-test")

# Redis клиент (если REDIS_URL задан)
redis_client = None
if REDIS_URL:
    redis_client = redis.from_url(REDIS_URL)

# ──────────────────────────────────────────────────────────────────────────────
# Утилиты

async def get_rate() -> float:
    """Симуляция курса с накруткой 4–9%"""
    base_rate = 105.20  # примерный курс USDT → RUB
    spread = random.uniform(0.04, 0.09)
    return base_rate * (1 + spread)

def jitter_amount(base: float) -> float:
    """Рандомизация суммы ±8–12% для обхода velocity checks"""
    jitter = random.uniform(-0.08, 0.12)
    return round(base * (1 + jitter), 2)

async def create_cryptomus_payment(amount: float, order_id: str) -> Dict:
    """Создание платежа через Cryptomus"""
    async with aiohttp.ClientSession() as session:
        payload = {
            "amount": str(amount),
            "currency": "USDT",
            "order_id": order_id,
            "url_callback": f"{WEBHOOK_URL}",
            "url_success": f"https://t.me/{(await bot.get_me()).username}?start=success",
            "url_fail": f"https://t.me/{(await bot.get_me()).username}?start=fail",
        }
        headers = {"Authorization": f"Bearer {CRYPTOMUS_API_KEY}"}
        async with session.post(
            "https://api.cryptomus.com/v1/payment",
            json=payload,
            headers=headers
        ) as resp:
            if resp.status != 200:
                raise HTTPException(500, "Cryptomus API error")
            data = await resp.json()
            if data.get("result"):
                return {
                    "url": data["result"]["url"],
                    "tx_id": data["result"].get("uuid", "")
                }
            raise ValueError(data.get("message", "Cryptomus error"))

# ──────────────────────────────────────────────────────────────────────────────
# Telegram-бот хендлеры

bot = None  # будет инициализирован позже

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("USDT → RUB / Карта", callback_data="dir_usdt_rub")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Добро пожаловать в симуляционный P2P-обменник v12-test\n"
        "Выберите направление:",
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "dir_usdt_rub":
        context.user_data["direction"] = "USDT→RUB"
        await query.message.reply_text(
            "Введите сумму в USDT (мин. 10 USDT):"
        )

async def handle_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "direction" not in context.user_data:
        await update.message.reply_text("Сначала выберите направление через /start")
        return

    try:
        amount_usdt = float(update.message.text.strip())
        if amount_usdt < 10:
            raise ValueError
    except:
        await update.message.reply_text("Введите корректную сумму ≥ 10 USDT")
        return

    rate = await get_rate()
    amount_rub = jitter_amount(amount_usdt * rate)

    order_id = str(uuid.uuid4())
    user_id = str(update.effective_user.id)

    async with async_session() as session:
        order = Order(
            order_id=order_id,
            user_id=user_id,
            amount_usdt=amount_usdt,
            amount_rub=amount_rub,
            status="pending"
        )
        session.add(order)
        await session.commit()

    # Создаём оплату
    try:
        payment = await create_cryptomus_payment(amount_usdt, order_id)
        gateway = "cryptomus"
        payment_url = payment["url"]
        tx_id = payment["tx_id"]
    except Exception as e:
        await update.message.reply_text(f"Ошибка создания платежа: {str(e)}")
        return

    async with async_session() as session:
        order.payment_url = payment_url
        order.gateway = gateway
        order.tx_id = tx_id
        await session.commit()

    await update.message.reply_text(
        f"Ордер #{order_id[:8]}\n"
        f"{amount_usdt:.2f} USDT → {amount_rub:.2f} RUB\n"
        f"Оплатите по ссылке:\n{payment_url}\n\n"
        "После оплаты средства будут зачислены автоматически.\n"
        "Не закрывайте чат."
    )

# ──────────────────────────────────────────────────────────────────────────────
# Webhook для платежных систем

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    update = Update.de_json(await request.json(), bot)
    await application.process_update(update)
    return {"ok": True}

@app.post("/cryptomus")
async def cryptomus_callback(request: Request):
    try:
        data = await request.json()
        order_id = data.get("order_id")
        status = data.get("status")

        if status in ("paid", "confirmed"):
            async with async_session() as session:
                order = await session.query(Order).filter_by(order_id=order_id).first()
                if order and order.status == "pending":
                    order.status = "paid"
                    order.paid_at = datetime.utcnow()
                    await session.commit()

                    await bot.send_message(
                        order.user_id,
                        f"Оплата подтверждена!\n"
                        f"Сумма: {order.amount_rub:.2f} RUB зачислена.\n"
                        f"Реквизиты (тестовые): 2200 7000 9999 8888\n"
                        "Спасибо за обмен!"
                    )
        return JSONResponse({"status": "ok"})
    except Exception as e:
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)

# ──────────────────────────────────────────────────────────────────────────────
# Инициализация и запуск

application = None

async def init_app():
    global bot, application
    bot = Bot(token=BOT_TOKEN)
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & \~filters.COMMAND, handle_amount))

    # Установка webhook при запуске (только если не установлен)
    current_webhook = await bot.get_webhook_info()
    if not current_webhook.url or current_webhook.url != f"{WEBHOOK_URL}":
        await bot.set_webhook(url=f"{WEBHOOK_URL}")

if __name__ == "__main__":
    import uvicorn
    asyncio.run(init_app())
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
