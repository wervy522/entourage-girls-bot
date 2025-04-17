import json
import os
import asyncio
import gspread
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from oauth2client.service_account import ServiceAccountCredentials
from pyrogram import Client, filters, idle
from pyrogram.types import Message

print("[DEBUG] Начало инициализации бота...")

# Загрузка конфигурации
with open("config.json", "r") as config_file:
    config = json.load(config_file)
    print("[DEBUG] Конфигурация загружена успешно")

API_ID = config["API_ID"]
API_HASH = config["API_HASH"]
BOT_TOKEN = config["BOT_TOKEN"]
GOOGLE_SHEET_NAME = config["GOOGLE_SHEET_NAME"]
FORM_URL = config["FORM_URL"]
TRIBUTE_LINK = config["TRIBUTE_LINK"]

print(f"[DEBUG] API_ID: {API_ID}")
print(f"[DEBUG] BOT_TOKEN: {BOT_TOKEN[:10]}...")

# Telegram client
app = Client("entourage_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
scheduler = AsyncIOScheduler()

print("[DEBUG] Клиент Telegram инициализирован")

# Подключение к Google Sheets
try:
    scope = ["https://spreadsheets.google.com/feeds",'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    gs_client = gspread.authorize(creds)
    sheet = gs_client.open(GOOGLE_SHEET_NAME).sheet1
    print("[DEBUG] Подключение к Google Sheets успешно")
except Exception as e:
    print(f"[ERROR] Ошибка при подключении к Google Sheets: {str(e)}")

# Пользователи и запланированные напоминания
user_timers = {}

# --- Проверки анкеты и статуса ---
def check_form_submission(username):
    try:
        print(f"[DEBUG] Проверка отправки анкеты для @{username}")
        records = sheet.get_all_records()
        print(f"[DEBUG] Получено {len(records)} записей из таблицы")
        for record in records:
            tg = record.get("Как с тобой лучше связаться?", "").strip().replace("@", "")
            print(f"[DEBUG] Сравниваем {tg.lower()} с {username.lower()}")
            if tg.lower() == username.lower():
                print(f"[DEBUG] Найдено совпадение для @{username}")
                return True
        print(f"[DEBUG] Анкета не найдена для @{username}")
        return False
    except Exception as e:
        print(f"[ERROR] Ошибка при проверке отправки анкеты: {str(e)}")
        return False

def check_form_approved(username):
    try:
        print(f"[DEBUG] Проверка одобрения анкеты для @{username}")
        records = sheet.get_all_records()
        print(f"[DEBUG] Получено {len(records)} записей из таблицы")
        for record in records:
            tg = record.get("Как с тобой лучше связаться?", "").strip().replace("@", "")
            status = record.get("Статус", "").lower()
            print(f"[DEBUG] Проверка записи: tg={tg}, status={status}")
            if tg.lower() == username.lower() and "одобр" in status:
                print(f"[DEBUG] Найдено одобрение для @{username}")
                return True
        print(f"[DEBUG] Одобрение не найдено для @{username}")
        return False
    except Exception as e:
        print(f"[ERROR] Ошибка при проверке одобрения анкеты: {str(e)}")
        return False

# --- Напоминания и авто-сообщения ---
async def send_reminder(client, chat_id, level):
    if level == 1:
        text = f"""💌 Милая, ты ещё не заполнила анкету Entourage Girls.

Это займёт 3 минуты: {FORM_URL}
"""
    elif level == 2:
        text = f"""✨ Привет! Напоминаем, что анкета всё ещё открыта для тебя.

Если хочешь в клуб Entourage — заполни сейчас: {FORM_URL}
"""
    await client.send_message(chat_id, text)
    print(f"[Reminder {level}] -> {chat_id}")

async def send_invite(client, chat_id):
    text = f"""💖 Привет, дорогая!

Мы рады пригласить тебя в закрытое комьюнити Entourage Girls. Ты прошла отбор, и теперь можешь присоединиться!

🔗 Ссылка на оплату участия: {TRIBUTE_LINK}

💌 Приглашение действительно 24 часа.
"""
    await client.send_message(chat_id, text)
    print(f"[Invite Sent] -> {chat_id}")

    scheduler.add_job(lambda: asyncio.create_task(
        client.send_message(chat_id, f"🔔 Напоминаем: твоё приглашение в Entourage всё ещё активно. {TRIBUTE_LINK}")
    ), 'date', run_date=datetime.now() + timedelta(hours=24))

    scheduler.add_job(lambda: asyncio.create_task(
        client.send_message(chat_id, f"❗️Это финальное напоминание: приглашение скоро истекает. Успей присоединиться: {TRIBUTE_LINK}")
    ), 'date', run_date=datetime.now() + timedelta(hours=48))

# --- Обработка входящих сообщений ---
@app.on_message(filters.command("start") | filters.text)
async def handle_message(client, message: Message):
    try:
        username = message.from_user.username
        chat_id = message.chat.id
        print(f"[DEBUG] Получено сообщение от @{username}: {message.text}")
        print(f"[DEBUG] Chat ID: {chat_id}")

        if not username:
            print("[DEBUG] Пользователь без username")
            await message.reply("🙈 Пожалуйста, добавь username в настройках Telegram, чтобы мы могли связаться с тобой.")
            return

        print(f"[DEBUG] Проверка анкеты для @{username}")
        if check_form_approved(username):
            print(f"[DEBUG] Анкета одобрена для @{username}")
            await send_invite(client, chat_id)
            return

        if check_form_submission(username):
            print(f"[DEBUG] Анкета уже отправлена для @{username}")
            await message.reply("💌 Спасибо! Мы получили твою анкету. В течение 24 часов с тобой свяжется куратор Entourage Girls.")
            print(f"[Анкета уже есть] @{username}")
        else:
            print(f"[DEBUG] Новая анкета для @{username}")
            welcome_text = f"""Привет, милая! ✨

Ты в шаге от закрытого сообщества Entourage Girls — места силы, вдохновения и женской энергии. 💫

Чтобы попасть в клуб, начни с анкеты — это займёт 3 минуты:
{FORM_URL}

С любовью, команда Entourage 💖
"""
            await message.reply(welcome_text)
            print(f"[Отправлено приветствие] @{username}")

            scheduler.add_job(send_reminder, 'date', run_date=datetime.now() + timedelta(hours=12), args=[client, chat_id, 1])
            scheduler.add_job(send_reminder, 'date', run_date=datetime.now() + timedelta(hours=24), args=[client, chat_id, 2])
            print(f"[Напоминания запланированы] @{username}")
    except Exception as e:
        print(f"[ERROR] Ошибка при обработке сообщения: {str(e)}")
        try:
            await message.reply("Произошла ошибка при обработке сообщения. Пожалуйста, попробуйте позже.")
        except:
            print("[ERROR] Не удалось отправить сообщение об ошибке")

# --- Запуск бота ---
async def main():
    try:
        print("[DEBUG] Запуск планировщика...")
        scheduler.start()
        print("[DEBUG] Запуск клиента Telegram...")
        await app.start()
        print("🤖 EntourageBot запущен и ждёт сообщений...")
        await idle()
    except Exception as e:
        print(f"[ERROR] Ошибка при запуске бота: {str(e)}")
    finally:
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())