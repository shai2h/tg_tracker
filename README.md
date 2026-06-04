# TG Tracker

Минимальное приложение для учета расходов через Telegram-бота.

## Стек

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- aiogram
- Docker Compose
- Ruff

## Возможности

- Добавить расход через Telegram: `/add coffee 300`
- Посмотреть свои расходы: `/list`
- Создать расход через FastAPI
- Получить расходы пользователя
- Удалить расход

## Переменные окружения


Создать `.env` в корне проекта:

```env
POSTGRES_DB=tracker
POSTGRES_USER=admin
POSTGRES_PASSWORD=your_password
DATABASE_URL=postgresql+psycopg://admin:your_password@127.0.0.1:5432/tracker
BOT_TOKEN=your_bot_token
```

## Поднять PostgreSQL
```bash
docker compose up -d
```


## Запуск FastAPI

```bash
uvicorn app.main:app --reload
```

## Swagger

http://127.0.0.1:8000/docs

## Запуск телеграмм бота

python bot.py

## Проверка линтером

ruff check .