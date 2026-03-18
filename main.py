# main.py
"""
Профессиональный Telegram-бот + Mini App (P2P-обменник USDT → RUB)
Версия 2026. Один файл, polling + Mini App WebView
"""

import asyncio
import logging
import os
import random
import uuid
from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ────────────────────────────────────────────────
# Конфигурация и логирование

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("P2PBot")

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан в переменных окружения")

PORT = int(os.getenv("PORT", 8000))
BASE_URL = os.getenv("BASE_URL", f"http://0.0.0.0:{PORT}")
WEB_APP_URL = os.getenv("WEB_APP_URL", f"{BASE_URL}/mini-app")  # ссылка на Mini App

# ────────────────────────────────────────────────
# FastAPI приложение (для Mini App и статических файлов)

app = FastAPI(title="P2P Exchanger Mini App", version="1.0")

# Подключаем папку static (если будет)
app.mount("/static", StaticFiles(directory="static"), name="static")


# Главная страница Mini App (просто HTML + JS)
@app.get("/mini-app", response_class=HTMLResponse)
async def mini_app(request: Request):
    return """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>P2P Обменник</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 0; padding: 20px; background: #f0f2f5; }
            .container { max-width: 500px; margin: auto; background: white; padding: 20px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }
            h1 { text-align: center; color: #0088cc; }
            input, button { width: 100%; padding: 12px; margin: 10px 0; border-radius: 12px; border: 1px solid #ddd; font-size: 16px; }
            button { background: #0088cc; color: white; border: none; font-weight: bold; cursor: pointer; }
            button:hover { background: #006699; }
            #result { margin-top: 20px; padding: 15px; background: #e8f5ff; border-radius: 12px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Обмен USDT → RUB</h1>
            <input type="number" id="amount" placeholder="Сумма в USDT" min="10" step="0.01">
            <button onclick="calculate()">Рассчитать</button>
            <div id="result"></div>
        </div>

        <script>
            Telegram.WebApp.ready();
            Telegram.WebApp.expand();

            function calculate() {
                const amount = parseFloat(document.getElementById("amount").value);
                if (!amount || amount < 10) {
                    document.getElementById("result").innerHTML = "<p style='color:red'>Введите сумму не менее 10 USDT</p>";
                    return;
                }

                // Симуляция курса и jitter
                const rate = 105.50 * (1 + Math.random() * 0.1);
                const rub = Math.round(amount * rate * (0.92 + Math.random() * 0.16) * 100) / 100;

                document.getElementById("result").innerHTML = `
                    <strong>Ордер #${Math.random().toString(36).slice(2,10).toUpperCase()}</strong><br><br>
                    Отправляете: ${amount.toFixed(2)} USDT<br>
                    Получаете: ≈ ${rub.toFixed(2)} RUB<br><br>
                    <strong>Курс:</strong> ${rate.toFixed(2)} RUB/USDT<br>
                    <small>Тестовый режим. Реальный обмен скоро.</small>
                `;
            }
        </script>
    </body>
    </html>
    """


# ────────────────────────────────────────────────
# Telegram-бот логика

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [
            InlineKeyboardButton(
                "Открыть Mini App",
                web_app=WebAppInfo(url=WEB_APP_URL)
            )
        ],
        [InlineKeyboardButton("Инструкция", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Добро пожаловать в профессиональный P2P-обменник USDT → RUB\n\n"
        "Нажмите кнопку ниже, чтобы открыть удобное приложение внутри Telegram:",
        reply_markup=reply_markup
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "help":
        await query.message.reply_text(
            "Как пользоваться:\n"
            "1. Нажмите «Открыть Mini App»\n"
            "2. Введите сумму в USDT\n"
            "3. Получите расчёт и тестовую ссылку\n\n"
            "В реальной версии будет интеграция Cryptomus / Enot.io"
        )


# ────────────────────────────────────────────────
# Запуск бота в режиме polling

async def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Бот запущен в режиме polling + Mini App")
    await application.initialize()
    await application.start()
    await application.updater.start_polling(
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"]
    )
    await asyncio.Event().wait()  # бесконечный цикл


if __name__ == "__main__":
    asyncio.run(main())
