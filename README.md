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

```env
DB_NAME=tg_tracker
DB_USER=user
DB_PASS=pass
DB_HOST=localhost
DB_PORT=5432

BOT_TOKEN=your_bot_token
```

---

## Запуск PostgreSQL

```bash
docker compose up -d
```

Проверить контейнеры:

```bash
docker compose ps
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
POST /expenses
```

Получить расходы пользователя:

```http
GET /expenses/user/{user_id}
```

Изменить расход:

```http
PATCH /expenses/{expense_id}
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

