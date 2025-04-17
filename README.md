# Entourage Girls Bot 💖

Telegram-бот, созданный для ведения девушек через воронку Entourage.

## 📂 Структура

- `main.py` — логика Telegram-бота
- `config.json` — настройки токенов, ссылок и имён таблицы
- `requirements.txt` — зависимости
- `railway.toml` — автозапуск на Railway
- `credentials.json` — загружается вручную

## 🚀 Быстрый старт

1. Установи зависимости:

```
pip install -r requirements.txt
```

2. Добавь свои данные в `config.json`
3. Убедись, что рядом лежит `credentials.json`
4. Запусти:

```
python main.py
```

## 🌐 Деплой на Railway

- Залей проект на GitHub
- Railway автоматически запустит через `railway.toml`
- Не забудь загрузить `credentials.json` в "Files"