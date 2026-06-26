# TG Tracker FastAPI

Учебное приложение для учета расходов через FastAPI, PostgreSQL и Telegram Bot.

## Стек

* Python 3.12+
* FastAPI
* PostgreSQL
* SQLAlchemy Async
* Alembic
* Pydantic Settings
* aiogram
* Docker Compose
* uv
* Ruff

---

## Структура проекта

```text
app/
├── main.py                # Точка входа FastAPI
├── core/
│   └── config.py          # Настройки приложения
├── db/
│   ├── base.py            # Declarative Base
│   └── session.py         # Engine, Session, get_db
├── expenses/
│   ├── models.py          # SQLAlchemy ORM модели
│   ├── schemas.py         # Pydantic схемы
│   ├── repository.py      # Работа с БД
│   ├── service.py         # Бизнес-логика
│   └── router.py          # API ручки
└── bot/                   # Telegram Bot

migrations/                # Alembic миграции
```

---

## Переменные окружения

Создать файл `.env`:

Use separate env files for Docker development and production:

```bash
cp .env.dev.example .env.dev
cp .env.prod.example .env.prod
```

Inside Docker containers always use `DB_HOST=db`, `DB_PORT=5432`, and
`API_BASE_URL=http://api:8000`. `DB_HOST_PORT` is only for exposing PostgreSQL
to the host in dev.

---

## Запуск PostgreSQL

Development:

```bash
docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml up -d --build
docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml exec api uv run alembic upgrade head
```

Проверить контейнеры:

Production:

```bash
docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml exec api uv run alembic upgrade head
```

Check rendered config:

```bash
docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml config
docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml config
```

---

## Установка зависимостей

```bash
uv sync
```

---

## Создание миграций

Создать новую миграцию:

```bash
alembic revision --autogenerate -m "Initial migration"
```

Применить миграции:

```bash
alembic upgrade head
```

Показать текущую версию:

```bash
alembic current
```

---

## Запуск приложения из app/

```bash
python main.py
```

Документация Swagger:

```text
http://127.0.0.1:8000/docs
```

---

## API

Создать расход:

```http
POST /bot/expenses
Authorization: Bearer <BOT_API_TOKEN>
```

Получить расходы текущего Telegram-пользователя по `telegram_id`:

```http
GET /bot/expenses?telegram_id=<telegram_id>&limit=10&offset=0
Authorization: Bearer <BOT_API_TOKEN>
```

`POST /bot/expenses` и `GET /bot/expenses` защищены `BOT_API_TOKEN`.

`BOT_TOKEN` is used only by aiogram. `BOT_API_TOKEN` is the internal bot-to-API
secret. `telegram_id` is the external Telegram user identifier; `user_id` is the
internal UUID stored in this app.

Получить расходы пользователя:

```http
GET /expenses/user/{user_id}
```

Изменить расход:

```http
PUT /expenses/{expense_id}
```

Удалить расход:

```http
DELETE /expenses/{expense_id}
```

---

## Проверка качества кода

Проверка Ruff:

```bash
ruff check .
```

Автоисправление:

```bash
ruff check . --fix
```

---

## Полезные команды

Создать виртуальное окружение:

```bash
uv venv
```

Активировать venv:

```bash
.venv\Scripts\activate
```

Добавить зависимость:

```bash
uv add package_name
```

Добавить dev-зависимость:

```bash
uv add --dev package_name
```

Обновить lock-файл:

```bash
uv sync
```

---

