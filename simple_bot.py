import json
import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackContext, CallbackQueryHandler
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import aiohttp
import hmac
import hashlib
import base64
import time
import os

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загрузка конфигурации
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

BOT_TOKEN = config['BOT_TOKEN']
FORM_URL = config['FORM_URL']
TRIBUTE_LINK = config['TRIBUTE_LINK']
GOOGLE_SHEET_NAME = config['GOOGLE_SHEET_NAME']
LAVA_API_KEY = config['LAVA_API_KEY']
LAVA_SHOP_ID = config['LAVA_SHOP_ID']
LAVA_SECRET_KEY = config['LAVA_SECRET_KEY']

# Настройка Google Sheets
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('entourage-girls-club-4f9c9c9c9c9c.json', scope)
client = gspread.authorize(creds)
sheet = client.open(GOOGLE_SHEET_NAME).sheet1

# Словарь для хранения напоминаний
user_reminders = {}

def check_form_submission(username):
    """Проверка заполнения анкеты"""
    try:
        records = sheet.get_all_records()
        for record in records:
            tg = record.get("Напиши свой telegram для связи", "").strip().replace("@", "")
            if tg.lower() == username.lower():
                return True
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке анкеты: {e}")
        return False

def check_form_approved(username):
    """Проверка одобрения анкеты"""
    try:
        records = sheet.get_all_records()
        for record in records:
            tg = record.get("Напиши свой telegram для связи", "").strip().replace("@", "")
            status = record.get("Статус", "").lower()
            if tg.lower() == username.lower():
                # Проверяем статус
                if "оплат" in status:  # Если уже оплатила
                    return False
                return True  # Автоматически одобряем если анкета заполнена
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке одобрения: {e}")
        return False

async def send_reminder(context: ContextTypes.DEFAULT_TYPE, chat_id: int, level: int):
    """Отправка напоминания"""
    if level == 1:
        text = f"""Милая, хотим напомнить: вступление в Entourage Girls начинается с короткой анкеты. Это займёт 3 минуты, и позволит нам лучше узнать тебя и понять, подойдёт ли тебе клуб.

Вот форма: {FORM_URL}

С любовью, команда Entourage Girls 💖"""
    else:
        text = f"""Привет! Мы хотим уточнить — ты всё ещё рассматриваешь возможность вступления в наш клуб? Мы пока не получили твою анкету.

Entourage Girls — это не просто чат и встречи. Это атмосфера, стиль жизни и женщины, которые поддерживают, вдохновляют и становятся частью твоей реальности.

Если хочешь попробовать — анкета всё ещё открыта: {FORM_URL}

А если тебе больше откликается другой путь — это тоже ок. Главное, чтобы он был твоим 💫"""
    
    await context.bot.send_message(chat_id=chat_id, text=text)

async def create_payment(user_id: int, username: str) -> str:
    """Создание платежа в Lava Top"""
    url = "https://api.lava.top/payment/create"
    
    payload = {
        "shop_id": LAVA_SHOP_ID,
        "amount": "1000.00",  # Сумма в рублях
        "currency": "RUB",
        "order_id": f"order_{user_id}_{int(time.time())}",
        "hook_url": "https://345c-116-105-161-246.ngrok-free.app/webhook",  # URL для получения уведомлений
        "success_url": "https://t.me/EntourageGirlsClub_bot",  # URL после успешной оплаты
        "fail_url": "https://t.me/EntourageGirlsClub_bot",  # URL после неудачной оплаты
        "expire": 3600,  # Время жизни платежа в секундах
        "custom_fields": {
            "user_id": str(user_id),
            "username": username
        }
    }
    
    headers = {
        "Authorization": f"Bearer {LAVA_API_KEY}",
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return data.get('payment_url')
            else:
                logger.error(f"Ошибка создания платежа: {await response.text()}")
                return None

async def check_payment_status(order_id: str) -> bool:
    """Проверка статуса платежа"""
    url = f"https://api.lava.top/payment/status/{order_id}"
    
    headers = {
        "Authorization": f"Bearer {LAVA_API_KEY}",
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return data.get('status') == 'success'
            return False

async def send_invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка приглашения после одобрения анкеты"""
    user_id = update.effective_user.id
    username = update.effective_user.username or str(user_id)
    
    # Создаем платеж
    payment_url = await create_payment(user_id, username)
    if not payment_url:
        await update.message.reply_text(
            "Извините, произошла ошибка при создании платежа. Пожалуйста, попробуйте позже."
        )
        return
    
    # Отправляем приглашение с ссылкой на оплату
    await update.message.reply_text(
        f"Поздравляем! Ваша анкета одобрена! 🎉\n\n"
        f"Для вступления в клуб необходимо внести оплату. "
        f"После оплаты вы получите доступ к чату и всем мероприятиям.\n\n"
        f"Ссылка для оплаты: {payment_url}\n\n"
        f"Если у вас возникли вопросы, напишите нам."
    )
    
    # Устанавливаем напоминание через 12 часов
    context.job_queue.run_once(
        send_reminder,
        timedelta(hours=12),
        data={'user_id': user_id, 'username': username, 'payment_url': payment_url}
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await handle_message(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user = update.effective_user
    chat_id = update.effective_chat.id
    username = user.username

    if not username:
        await update.message.reply_text(
            "🙈 Пожалуйста, добавь username в настройках Telegram, чтобы мы могли связаться с тобой."
        )
        return

    logger.info(f"Получено сообщение от {username}")

    if check_form_approved(username):
        await send_invite(update, context)
        return

    if check_form_submission(username):
        await update.message.reply_text(
            "Спасибо, мы получили твою анкету! В течение 24 часов ты получишь ответ: пригласим тебя или, если не совпали — бережно сообщим об этом.\n\n"
            "Пока ты ждёшь, можешь заглянуть к нам в Instagram @entourage.girls — там много вдохновения и моментов из жизни клуба."
        )
        return

    # Создаем клавиатуру с кнопкой FAQ
    keyboard = [
        [InlineKeyboardButton("❓ Часто задаваемые вопросы", callback_data="faq")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем приветственное сообщение
    welcome_text = f"""Привет, милая! ✨

Спасибо за интерес к Entourage Girls — закрытому клубу девушек, которые хотят большего от жизни.

Наше сообщество уже объединило 1500 участниц: от блогеров до студенток топ-вузов, от основательниц брендов до девушек, которые просто чувствовали, что готовы к новому.

Здесь ты найдёшь не просто подруг — здесь ты найдёшь своё окружение, в котором раскрываешься, влюбляешься в жизнь и никогда больше не чувствуешь себя одной.

Внутри клуба — званые ужины, девичьи завтраки, конные прогулки, дни красоты с брендами и даже участие в неделях моды. Но главное — это связь между участницами и чувство, что ты в своём месте.

Клуб работает в формате годового членства, с ограниченным количеством мест. Мы принимаем в комьюнити только по анкетам — чтобы сохранить атмосферу и уровень.

Если хочешь получить личное приглашение — заполни короткую форму, она займёт 3 минуты:
{FORM_URL}

После этого мы рассмотрим заявку и ответим в течение суток.

С нетерпением ждём твою историю,
Entourage Girls 💖"""

    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

    # Планируем напоминания (тестовый режим - минуты вместо часов)
    context.job_queue.run_once(
        lambda ctx: send_reminder(ctx, chat_id, 1),
        timedelta(minutes=1)  # Было hours=12
    )
    context.job_queue.run_once(
        lambda ctx: send_reminder(ctx, chat_id, 2),
        timedelta(minutes=2)  # Было hours=24
    )

async def handle_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатия на кнопку FAQ"""
    query = update.callback_query
    await query.answer()

    # Создаем клавиатуру с вопросами
    keyboard = [
        [InlineKeyboardButton("💰 Сколько стоит вступление?", callback_data="faq_1")],
        [InlineKeyboardButton("💎 Можно узнать стоимость без анкеты?", callback_data="faq_2")],
        [InlineKeyboardButton("🎁 Что входит в членство?", callback_data="faq_3")],
        [InlineKeyboardButton("💬 Расскажи про чат", callback_data="faq_4")],
        [InlineKeyboardButton("🎉 Какие мероприятия?", callback_data="faq_5")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.reply_text(
        "Выберите интересующий вас вопрос:",
        reply_markup=reply_markup
    )

async def handle_faq_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора вопроса FAQ"""
    query = update.callback_query
    await query.answer()

    faq_answers = {
        "faq_1": f"""1. Сколько стоит вступление в клуб?

У нас действует годовое членство, стоимость которого остаётся символической — чтобы сохранить доступность и при этом ценность комьюнити.

Мы приглашаем в клуб девушек, с которыми у нас есть внутреннее совпадение — ведь самое главное здесь это атмосфера и окружение.

Если чувствуешь отклик — заполни короткую анкету, и мы свяжемся с тобой в течение 24 часов:
{FORM_URL}""",

        "faq_2": f"""2. А можно сразу узнать стоимость, не заполняя анкету?

Entourage Girls — это закрытое пространство, где важна не только цена, а ощущение «я среди своих».

Именно поэтому мы сначала знакомимся через анкету, чтобы понять, подойдёт ли тебе наш формат.

Если будет совпадение — ты получишь личное приглашение со всей информацией. Анкета тут:
{FORM_URL}""",

        "faq_3": f"""3. Что входит в членство?

После вступления ты получаешь:
• доступ к активному Telegram-чату 24/7
• участие в ежемесячных закрытых ивентах
• 1 бесплатный ивент в течение года
• подарки и предложения от брендов
• и главное — вдохновляющее женское окружение

Анкета займёт 3 минуты — и станет первым шагом к нашему пространству:
{FORM_URL}""",

        "faq_4": f"""4. А что за чат? Что там происходит?

Это живой клубный Telegram-чат, где девушки:
• общаются 24/7 на любые темы — от личного до карьерного
• знакомятся и находят подруг
• получают расписание мероприятий и приглашения на клубные события

Всё начинается с анкеты — если откликается, мы будем рады познакомиться:
{FORM_URL}""",

        "faq_5": f"""5. Какие мероприятия проходят в клубе?

У нас проходят:
• званые ужины и душевные завтраки
• арт-девичники, конные прогулки
• фотодни и дни красоты с брендами
• бал, ретриты и сезонные события

Всё это — в атмосфере поддержки и уюта.

Если хочешь быть частью — заполни анкету, и мы свяжемся с тобой лично:
{FORM_URL}"""
    }

    answer = faq_answers.get(query.data, "Извините, произошла ошибка. Попробуйте еще раз.")
    await query.message.reply_text(answer)

def main():
    """Запуск бота"""
    logger.info("Запуск бота...")
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_faq, pattern="^faq$"))
    application.add_handler(CallbackQueryHandler(handle_faq_answer, pattern="^faq_"))

    # Запускаем бота
    logger.info("Бот запущен и готов к работе")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main() 