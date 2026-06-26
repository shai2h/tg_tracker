# Домашняя работа №4

## Пункт 0 — Закрыть всё из PR #4

Перед тем как начинать следующие пункты — закрой все открытые комментарии. Конкретно:

**`to_read()` в роутере — убрать.**
Сейчас в `router.py` есть функция `to_read(expense)`, которая вручную маппит ORM-объект в схему. Это дублирует логику и ломается если добавить новое поле. Правильный вариант — использовать `@computed_field` в `ExpenseRead` для полей, которые требуют вычисления (у нас это `amount_rubles` — конвертация из копеек). Тогда роутер просто делает `return expense`, и Pydantic сам строит ответ через `from_attributes=True`.

```python
# в ExpenseRead:
from pydantic import computed_field

class ExpenseRead(BaseModel):
    id: UUID
    user_id: UUID
    category: str | None
    title: str
    amount_kopeiki: int  # читаем из ORM как есть
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def amount_rubles(self) -> Decimal:
        return Decimal(self.amount_kopeiki) / 100
```

**`flush` в `repository.create` — убрать.**
`flush` делает SQL без коммита, но зачем он тут? Вся транзакция коммитится в `get_db`. `refresh` без `flush` тоже работает — SQLAlchemy сам делает flush перед refresh. Если хочешь получить сгенерированные базой поля (например `created_at` с `server_default`) — используй `refresh`. Убери `flush`, оставь только `refresh`.
---

## Пункт 1 — Telegram Webhook

### Почему webhook, а не polling

Polling (`dp.start_polling`) — это бесконечный цикл, который каждые N секунд стучится к Telegram и спрашивает "есть новые сообщения?". Работает локально без публичного URL, но не подходит для продакшена: нельзя запустить несколько инстансов, занимает соединение, Telegram устаревает.

Webhook — это наоборот: ты регистрируешь у Telegram адрес, и он сам присылает тебе HTTP POST на каждое сообщение. Требует публичный HTTPS URL, зато масштабируется и работает как нормальный REST endpoint.

**Polling оставляй для локальной разработки** (`bot/handlers.py`). Webhook регистрируй только в продакшене.

### Что такое telegram_id vs user_id

Это самое важное — разберись один раз:

```
Telegram                     Наша БД
─────────────────────────────────────────────────────
message.from_user.id = 123   users.telegram_id = 123
                        →    users.id = UUID("abc-...")  ← это user_id
                             expenses.user_id = UUID("abc-...")
```

- `telegram_id` — это числовой ID пользователя в Telegram (например, `123456789`). Приходит в каждом сообщении как `message.from_user.id`. Это внешний идентификатор.
- `user_id` — это UUID, который мы генерируем внутри нашей системы. Хранится в таблице `users`. Это внутренний идентификатор.

Поэтому `POST /expenses` принимает `telegram_id: int`, сервис вызывает `get_or_create_user(telegram_id)`, получает внутренний `user.id`, и уже с ним создаёт расход. Вот почему `GET /expenses/user/{user_id}` принимает UUID, а не telegram_id.

### Что нужно сделать

**1. Добавить `TELEGRAM_WEBHOOK_SECRET` в конфиг.**

```python
class Settings(BaseSettings):
    ...
    TELEGRAM_WEBHOOK_SECRET: str  # генерируешь сам, любая строка
```

Этот секрет ты прописываешь при регистрации вебхука в Telegram. Telegram будет присылать его в каждом запросе в заголовке `X-Telegram-Bot-Api-Secret-Token`. Ты проверяешь — совпадает ли. Если нет — `403`. Это единственная защита публичного эндпоинта от левых запросов.

**2. Создать `app/bot/webhook.py` с роутером.**

Структура endpoint:

```python
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from app.core.config import get_settings

router = APIRouter(prefix="/webhook", tags=["webhook"])

@router.post("/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(None),
    service: ExpenseService = Depends(get_expense_service),
):
    settings = get_settings()

    # 1. Проверить секрет
    if x_telegram_bot_api_secret_token != settings.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")

    # 2. Распарсить Update от Telegram
    update = await request.json()

    # 3. Достать сообщение (update может прийти не с message, например inline query)
    message = update.get("message")
    if not message or not message.get("text"):
        return {"ok": True}  # игнорируем не-текстовые апдейты

    telegram_id = message["from"]["id"]
    username = message["from"].get("username")
    text = message["text"]

    # 4. Скормить апдейт диспетчеру — он сам раскидает по хендлерам
    from aiogram.types import Update as TgUpdate
    tg_update = TgUpdate(**update)
    await dp.feed_update(bot, tg_update)

    return {"ok": True}
```

**Важно:** Telegram всегда шлёт всё на один endpoint — и `/start`, и `/list`, и текстовое сообщение `кофе 150`, и фото, и всё остальное. Разруливать между командами — твоя задача.

Самый чистый способ — `dp.feed_update(bot, update)`. Ты передаёшь апдейт в тот же aiogram-диспетчер, который используется в polling. Он сам применяет фильтры (`Command("start")`, `F.text`, и т.д.) и вызывает нужный хендлер. Один `dp` — оба режима.

Это значит, что `bot/handlers.py` — это не "файл для polling". Это файл с логикой бота. И polling, и webhook просто разные способы доставить в него апдейты.

**3. Зарегистрировать роутер в `main.py`.**

**4. Зарегистрировать вебхук у Telegram.**

После деплоя — один раз вручную или через startup-событие FastAPI:

```bash
curl -X POST "https://api.telegram.org/bot{TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-domain.com/webhook/telegram",
    "secret_token": "your_secret_here"
  }'
```

**5. Ответить пользователю из webhook.**

Из webhook нельзя использовать `await message.answer()` как в aiogram polling. Есть два способа:
- Синхронный ответ: вернуть из endpoint JSON с `method`, `chat_id`, `text` — Telegram сам отправит сообщение.
- Асинхронный: вызвать Bot API через httpx после обработки.

Синхронный проще:

```python
return {
    "method": "sendMessage",
    "chat_id": telegram_id,
    "text": f"Сохранил: {title} — {amount} ₽",
}
```

**Что оставить как есть:** `bot/handlers.py` с polling не трогать. Локально запускаешь его для разработки, на проде — webhook.

### Как переключаться между режимами — lifespan в FastAPI

FastAPI умеет выполнять код при старте и остановке приложения через `lifespan`. Именно здесь нужно управлять и polling, и webhook — приложение само определяет режим по конфигу, ничего не нужно запускать руками.

Добавь в конфиг необязательную переменную:

```python
class Settings(BaseSettings):
    ...
    WEBHOOK_URL: str | None = None  # не задан локально, задан в продакшене
```

Теперь в `main.py`:

```python
import asyncio
from contextlib import asynccontextmanager
from aiogram import Bot
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    bot = Bot(token=settings.BOT_TOKEN)

    if settings.WEBHOOK_URL:
        # продакшен: регистрируем webhook, polling не нужен
        await bot.set_webhook(
            url=f"{settings.WEBHOOK_URL}/webhook/telegram",
            secret_token=settings.TELEGRAM_WEBHOOK_SECRET,
        )
        await bot.session.close()

        yield  # приложение работает

        bot = Bot(token=settings.BOT_TOKEN)
        await bot.delete_webhook()
        await bot.session.close()

    else:
        # локально: запускаем polling как фоновую задачу
        from bot.handlers import dp
        polling_task = asyncio.create_task(dp.start_polling(bot))

        yield  # приложение работает

        polling_task.cancel()
        await asyncio.gather(polling_task, return_exceptions=True)
        await bot.session.close()

app = FastAPI(lifespan=lifespan)
```

Три вещи, которые здесь важно понять:

**`asyncio.create_task`** — запускает корутину в фоне на том же event loop. Приложение не блокируется и продолжает принимать HTTP-запросы. Polling работает параллельно.

**`yield`** — это точка, в которой приложение живёт. Код до `yield` — startup, код после — shutdown. Форма `if/else` с двумя `yield` выглядит необычно, но это валидный Python: contextmanager просто требует хотя бы один `yield`.

**`polling_task.cancel()` + `gather(..., return_exceptions=True)`** — правильная остановка фоновой задачи. `cancel()` бросает `CancelledError` внутрь задачи, `gather` дожидается что задача завершилась. Без этого uvicorn при остановке будет ругаться на незавершённые задачи.

В `.env` для локальной разработки:
```
# WEBHOOK_URL не задан — lifespan запустит polling автоматически
```

В `.env` на сервере (или в переменных окружения на Railway/Render):
```
WEBHOOK_URL=https://your-app.railway.app
```

---

## Пункт 2 — Деплой

Приложение должно быть доступно по публичному HTTPS URL, чтобы Telegram мог слать на него запросы.

Рекомендую **Railway** или **Render** — оба бесплатны для небольших проектов, поддерживают Docker, дают HTTPS автоматически. Как деплоить — твоё решение, главное чтобы работало.

Критерий приёмки: я нахожу бота в Telegram и он отвечает на сообщение вида `кофе 150`.

---

## Пункт 3 — Тесты

### Главный вопрос перед каждым тестом

Прежде чем писать `assert` — ответь себе: _"что именно я проверяю и почему это может сломаться?"_ Тест без понятного ответа на этот вопрос — шум, а не документация.

Примеры хороших ответов:
- "Проверяю, что один telegram_id никогда не создаёт двух пользователей, потому что у нас `UNIQUE` на этом поле"
- "Проверяю, что `{}` в PATCH возвращает 422, потому что мы только что добавили `model_validator`"
- "Проверяю, что расходы одного пользователя не видны другому — это требование изоляции данных"

Тест без этого ответа — скорее всего просто повторяет код, а не проверяет инвариант.

### Что нужно покрыть

Ориентир — 30 тестов. Вот категории с примерами первых нескольких — дальше продолжаешь сам:

**Создание расходов (5–6 тестов)**

```python
async def test_create_expense_returns_201(client):
    # что: базовый happy path
    # почему: убеждаемся что роутер правильно возвращает 201, не 200
    response = await client.post("/expenses", json={
        "telegram_id": 1, "title": "coffee", "amount_rubles": "150.50"
    })
    assert response.status_code == 201

async def test_create_expense_amount_stored_correctly(client):
    # что: amount_rubles в ответе совпадает с тем что отправили
    # почему: конвертация rubles -> kopeiki -> rubles могла потерять копейки
    response = await client.post("/expenses", json={
        "telegram_id": 1, "title": "coffee", "amount_rubles": "150.50"
    })
    assert Decimal(response.json()["amount_rubles"]) == Decimal("150.50")
```

Дальше сам: нулевая сумма, отрицательная сумма, пустой title, title длиннее 255 символов, отсутствующие обязательные поля.

**Чтение расходов (3–4 теста)**

Создаём расход, читаем список, проверяем что данные совпадают. Плюс: пустой список для нового пользователя, pagination (limit/offset).

**telegram_id → user_id (2 теста)**

```python
async def test_same_telegram_id_same_user_id(client):
    # что: два расхода с одним telegram_id → один user_id
    # почему: это инвариант get_or_create_user, при нарушении данные изолированы неправильно
    r1 = await client.post("/expenses", json={"telegram_id": 42, "title": "a", "amount_rubles": "1.00"})
    r2 = await client.post("/expenses", json={"telegram_id": 42, "title": "b", "amount_rubles": "1.00"})
    assert r1.json()["user_id"] == r2.json()["user_id"]

async def test_different_telegram_id_different_user_id(client):
    # что: разные telegram_id → разные user_id
    r1 = await client.post("/expenses", json={"telegram_id": 1, "title": "a", "amount_rubles": "1.00"})
    r2 = await client.post("/expenses", json={"telegram_id": 2, "title": "b", "amount_rubles": "1.00"})
    assert r1.json()["user_id"] != r2.json()["user_id"]
```

**Изоляция пользователей (2 теста)**

Расходы пользователя 1 не видны пользователю 2. Удаление расхода пользователя 1 не влияет на пользователя 2.

**Обновление расходов (4–5 тестов)**

Happy path, несуществующий ID → 404, частичное обновление (только title), частичное обновление (только amount), пустое тело `{}` → 422.

**Удаление расходов (3 теста)**

Happy path → 204, повторное удаление → 404, после удаления в списке нет.

**Webhook (5–6 тестов)**

```python
async def test_webhook_without_secret_returns_403(client):
    response = await client.post("/webhook/telegram", json={"update_id": 1})
    assert response.status_code == 403

async def test_webhook_with_wrong_secret_returns_403(client):
    response = await client.post(
        "/webhook/telegram",
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
    )
    assert response.status_code == 403
```

Дальше сам: валидный запрос с правильным секретом создаёт расход, нетекстовый апдейт игнорируется, непонятный текст не создаёт расход и возвращает сообщение об ошибке.

Для тестов вебхука нужно будет переопределить `TELEGRAM_WEBHOOK_SECRET` — подумай как это сделать через `dependency_overrides` или `monkeypatch`.

### Coverage

После написания тестов запусти:

```bash
uv run pytest --cov=app --cov-report=term-missing
```

Цель — покрытие выше 80% для `app/`. Приложи скриншот или вывод в PR.

---

## Порядок выполнения

**0 → 1 → 2 → 3**

Пункт 0 нужен для того, чтобы у тебя была чистая база. Пункт 2 (деплой) сделай до тестов вебхука — иначе некуда регистрировать.
