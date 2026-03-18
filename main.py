# main.py
"""
Профессиональный Telegram-бот + Mini App (P2P-обменник)
Polling + встроенный WebView, без внешних файлов
"""

import asyncio
import logging
import os
import random
import uuid
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
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
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("P2PBot")

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан!")

PORT = int(os.getenv("PORT", 8000))
BASE_URL = os.getenv("BASE_URL", f"http://0.0.0.0:{PORT}")
WEB_APP_URL = f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN', 'dhxhchxhxhx-production.up.railway.app')}/mini-app"

app = FastAPI(title="P2P Exchanger Mini App", version="1.0")


# Mini App (HTML + JS прямо в коде)
@app.get("/mini-app", response_class=HTMLResponse)
async def mini_app_page():
    return """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>P2P Обменник</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body { margin: 0; padding: 20px; font-family: system-ui, sans-serif; background: #f5f5f5; }
            .card { background: white; border-radius: 16px; padding: 24px; max-width: 500px; margin: auto; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }
            h1 { color: #0088cc; text-align: center; margin-bottom: 24px; }
            input { width: 100%; padding: 14px; margin: 12px 0; border: 1px solid #ddd; border-radius: 12px; font-size: 16px; box-sizing: border-box; }
            button { width: 100%; padding: 16px; background: #0088cc; color: white; border: none; border-radius: 12px; font-size: 17px; font-weight: 600; cursor: pointer; }
            button:hover { background: #006699; }
            #result { margin-top: 24px; padding: 16px; background: #e8f5ff; border-radius: 12px; line-height: 1.6; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>P2P Обмен USDT → RUB</h1>
            <input type="number" id="usdt" placeholder="Сумма в USDT" min="10" step="0.01">
            <button onclick="exchange()">Обменять</button>
            <div id="result"></div>
        </div>

        <script>
            Telegram.WebApp.ready();
            Telegram.WebApp.expand();

            function exchange() {
                const usdt = parseFloat(document.getElementById("usdt").value);
                if (!usdt || usdt < 10) {
                    document.getElementById("result").innerHTML = "<p style='color:#d32f2f'>Введите сумму от 10 USDT</p>";
                    return;
                }

                const rate = 105.50 * (1 + Math.random() * 0.1);
                const rub = Math.round(usdt * rate * (0.92 + Math.random() * 0.16) * 100) / 100;
                const order = Math.random().toString(36).slice(2, 10).toUpperCase();

                document.getElementById("result").innerHTML = `
                    <b>Ордер #${order}</b><br><br>
                    Вы отправляете: <b>${usdt.toFixed(2)} USDT</b><br>
                    Получаете: <b>${rub.toFixed(2)} RUB</b><br>
                    Курс: <b>${rate.toFixed(2)} RUB/USDT</b><br><br>
                    <small>Тестовый режим. Реальный обмен в разработке.</small>
                `;
            }
        </script>
    </body>
    </html>
    """


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("Открыть обменник", web_app=WebAppInfo(url=f"{BASE_URL}/mini-app"))]
    ]
    await update.message.reply_text(
        "Привет! Это профессиональный симулятор P2P-обмена USDT → RUB.\n\n"
        "Нажми кнопку ниже, чтобы открыть удобное приложение внутри Telegram:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


if __name__ == "__main__":
    import uvicorn

    # Запуск бота в polling + FastAPI для Mini App
    async def run_all():
        # Mini App сервер
        asyncio.create_task(
            uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT)).serve()
        )

        # Telegram polling
        application = Application.builder().token(BOT_TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        await application.initialize()
        await application.start()
        await application.updater.start_polling(drop_pending_updates=True)
        await asyncio.Event().wait()

    asyncio.run(run_all())
