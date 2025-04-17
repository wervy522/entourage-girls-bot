from pyrogram import Client, filters
from pyrogram.types import Message
import json
import asyncio
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Загрузка конфигурации
try:
    with open("config.json", "r") as config_file:
        config = json.load(config_file)
        logger.info("Конфигурация успешно загружена")
        logger.debug(f"API_ID: {config['API_ID']}")
        logger.debug(f"BOT_TOKEN: {config['BOT_TOKEN'][:10]}...")
except Exception as e:
    logger.error(f"Ошибка при загрузке конфигурации: {e}")
    raise

# Инициализация бота
app = Client(
    "entourage_bot",
    api_id=config["API_ID"],
    api_hash=config["API_HASH"],
    bot_token=config["BOT_TOKEN"]
)

# Обработчик команды /start
@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    logger.info(f"Получена команда /start от пользователя {message.from_user.id}")
    try:
        await message.reply(
            "Привет! 👋\n\n"
            "Я бот Entourage Girls. Чтобы начать, просто напиши мне любое сообщение!"
        )
        logger.info("Отправлено приветственное сообщение")
    except Exception as e:
        logger.error(f"Ошибка при отправке приветственного сообщения: {e}")

# Обработчик текстовых сообщений
@app.on_message(filters.text & ~filters.command("start"))
async def handle_message(client: Client, message: Message):
    logger.info(f"Получено сообщение от пользователя {message.from_user.id}: {message.text}")
    try:
        await message.reply(
            "Спасибо за сообщение! 💖\n\n"
            "Чтобы присоединиться к нашему сообществу, заполни анкету:\n"
            f"{config['FORM_URL']}"
        )
        logger.info("Отправлен ответ на сообщение")
    except Exception as e:
        logger.error(f"Ошибка при отправке ответа: {e}")

# Запуск бота
async def main():
    logger.info("🤖 Бот запускается...")
    try:
        await app.start()
        logger.info("✅ Бот успешно запущен!")
        logger.info("Ожидание сообщений...")
        await asyncio.Event().wait()  # Бесконечное ожидание
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        raise
    finally:
        await app.stop()
        logger.info("Бот остановлен")

if __name__ == "__main__":
    asyncio.run(main()) 