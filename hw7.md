# Домашка 7 — Чистая архитектура: слои, абстракции, транспорты

## Контекст

После hw6 приложение работает, но архитектура рыхлая: сервис знает про Future бота,
воркер глотает ошибки, репозиторий нигде не абстрагирован, логи — просто строки.

Цель этой домашки — сделать «витринный» проект: каждый слой знает только о своём
соседе, модули переиспользуемы, ошибки видны.

---

## Часть 1. Починить баги из hw6

### 1.1 Гонка commit/enqueue

**Проблема.** В `middleware.py` сессия коммитится *после* возврата хендлера.
`service.create()` вызывает `queue.enqueue()` *до* коммита. Воркер просыпается
на `await session.commit()` и делает `UPDATE` на несуществующую строку — 0 строк,
молча, категория теряется навсегда.

Убедись что понял: в сценарии без таймаута (классификация успела за 3 сек)
баг воспроизводится в 100% случаев.

**Что сделать.** `enqueue` должен вызываться *после* коммита. Вынеси его из
`service.create()` в middleware — после `await session.commit()`:

```python
# middleware.py
result = await handler(event, data)
await session.commit()

if enqueue := data.get("pending_enqueue"):
    await enqueue()
```

В `service.create()` вместо `await self.queue.enqueue(...)` сохрани колбэк:

```python
data["pending_enqueue"] = lambda: self.queue.enqueue(expense_id, title, on_done)
```

### 1.2 Мёртвые ретраи

**Проблема.** `classify()` ловит все исключения внутри и всегда возвращает кортеж.
`_classify_with_retries` никогда не попадает в `except` — три попытки не происходит,
`_UNKNOWN_CATEGORY` недостижим.

Кроме того, количество ретраев не должно быть заботой классификатора или воркера —
это знание о конкретном провайдере. GigaChat может хотеть 3 ретрая, другой провайдер
— 1 или 10.

**Что сделать.**

Перенеси логику ретраев в `GigaChatProvider`. Добавь `max_retries: int` в конструктор
(и в `Settings`). Ретраить только на 5xx — на 4xx ретрай бессмысленен, это наша ошибка:

```python
class GigaChatProvider:
    def __init__(self, ..., max_retries: int = 3):
        self._max_retries = max_retries

    async def complete(self, prompt: str, response_format: dict | None = None) -> str:
        for attempt in range(self._max_retries):
            try:
                return await self._do_request(prompt, response_format)
            except httpx.HTTPStatusError as e:
                if e.response.status_code < 500:
                    raise  # 4xx — не ретраим
                if attempt == self._max_retries - 1:
                    raise
```

Убери `_classify_with_retries` из воркера совсем — он больше не нужен.
`_process_task` вызывает `classify()` один раз, оборачивает в `try/except`
и при любом исключении использует `"неизвестно"`:

```python
async def _process_task(self, task: _ClassificationTask) -> None:
    try:
        category, confidence = await self._classifier.classify(task.title)
    except Exception:
        logger.exception("classification_failed", title=task.title)
        category, confidence = "неизвестно", 0.0
    ...
```

`classify()` больше не глотает исключения — бросает если провайдер не ответил
или ответ не распарсился. Единственная логика что остаётся в `classify()` —
проверка что категория входит в `ALLOWED_CATEGORIES`.

### 1.3 Server-side JSON schema

**Проблема.** Сейчас JSON-структура описана только в тексте промпта. GigaChat
может вернуть markdown-обёртку, пояснения, что угодно. Клиентский `json.loads`
молча падает в `("другое", 0.0)`.

GigaChat поддерживает `response_format` — серверная гарантия что ответ будет JSON.
Почитай документацию, там есть пример с `{"type": "json_object"}`.

**Что сделать.**

Текущий `LLMProvider` протокол принимает только `prompt: str` — расширь его:

```python
class LLMProvider(Protocol):
    async def complete(
        self,
        prompt: str,
        response_format: dict | None = None,
    ) -> str: ...
```

В `GigaChatProvider.complete()` передавай `response_format` в тело запроса если
он передан. В `classifier.py` передавай `{"type": "json_object"}` при вызове.

---

## Часть 2. Уведомления через очередь без Future

**Сейчас** `ExpenseService.create()` принимает `category_future: asyncio.Future` —
это деталь aiogram-хендлера протекла в доменный сервис. REST API передаёт `None`
и не знает зачем этот параметр.

**Что сделать.** Убери `category_future` из сигнатуры сервиса. Храни в задаче
`chat_id` и `enqueued_at`. Воркер сам шлёт сообщение:

```python
@dataclass
class _ClassificationTask:
    expense_id: UUID
    title: str
    chat_id: int
    enqueued_at: float  # time.monotonic()
```

После классификации воркер проверяет таймаут и шлёт сообщение напрямую через `bot`:

```python
async def _process_task(self, task: _ClassificationTask) -> None:
    category = await self._classify_with_retries(task.title)
    await self._repository.update_category(task.expense_id, category)

    elapsed = time.monotonic() - task.enqueued_at
    if elapsed < 3.0:
        await self._bot.send_message(task.chat_id, f"Категория: {category} ✓")
```

`ClassificationQueue` теперь принимает `bot: Bot` в конструктор.
`ExpenseService.create()` принимает `chat_id: int | None = None` вместо Future —
REST API передаёт `None`, бот передаёт `message.chat.id`.

Хендлер становится простым:

```python
await service.create(..., chat_id=message.chat.id)
await message.answer("Сохранил: кофе — 150 ₽\nОпределяю категорию...")
# всё, хендлер завершился — категория придёт отдельным сообщением
```

---

## Часть 3. Абстракция репозитория через ABC

**Сейчас** `ExpenseService` зависит от конкретного `ExpenseRepository` (SQLAlchemy).
Хочется чтобы сервис не знал про базу данных вообще.

Разделение: `LLMProvider` — Protocol (внешняя зависимость, мы не контролируем
иерархию). Репозиторий — ABC (наша иерархия, мы контролируем).

### Что сделать

Создай `app/expenses/repository_base.py`:

```python
from abc import ABC, abstractmethod
from uuid import UUID

class ExpenseRepositoryBase(ABC):

    @abstractmethod
    async def create(
        self,
        user_id: UUID,
        title: str,
        amount_kopeiki: int,
        category: str | None = None,
    ) -> ExpenseOrm: ...

    @abstractmethod
    async def get_by_user_id(self, user_id: UUID, limit: int, offset: int): ...

    @abstractmethod
    async def update_category(self, expense_id: UUID, category: str) -> None: ...

    @abstractmethod
    async def get_or_create_user(self, telegram_id: int, username: str | None): ...

    # остальные методы по аналогии
```

`ExpenseRepository` наследует от `ExpenseRepositoryBase`.

`ExpenseService.__init__` принимает `repository: ExpenseRepositoryBase` — больше
не знает про SQLAlchemy.

---

## Часть 4. Второй транспорт — CLI

Цель: показать что сервис работает без FastAPI и без aiogram.

Создай `app/cli.py`:

```python
# python -m app.cli add "кофе" 150
# python -m app.cli list --telegram-id 12345
```

CLI создаёт `ExpenseService` напрямую (без DI-фреймворка), вызывает те же методы
что бот и REST API.

Это демонстрирует главное: один сервис, три транспорта (бот, HTTP, CLI) —
и сервис не знает ни про один из них.

Структура:

```python
# app/cli.py
import asyncio
import argparse
from app.db.session import get_session_factory
from app.expenses.repository import ExpenseRepository
from app.expenses.service import ExpenseService


async def cmd_add(args):
    async with get_session_factory()() as session:
        service = ExpenseService(
            repository=ExpenseRepository(session),
            classification_queue=NoOpClassificationQueue(),  # CLI не классифицирует
        )
        expense = await service.create(
            telegram_id=args.telegram_id,
            username=None,
            data=ExpenseCreate(title=args.title, amount_rubles=args.amount),
        )
        await session.commit()
    print(f"Добавлен: {expense.title} — {expense.amount_kopeiki // 100} ₽")

# argparse, main(), if __name__ == "__main__"
```

`NoOpClassificationQueue` уже есть в тестах — вынеси в `app/llm/queue.py` как
публичный класс.

---

## Часть 5. Inline keyboard при confidence < 0.6

### 5.1 FSM

Создай `app/bot/states.py`:

```python
from aiogram.fsm.state import State, StatesGroup

class ClassificationConfirm(StatesGroup):
    waiting_confirm = State()    # ждём Да/Нет
    waiting_category = State()   # ждём выбор категории
```

### 5.2 Изменить on_done в воркере

Если `confidence < 0.6` — вместо «Категория: X ✓» отправить inline-клавиатуру:

```
Похоже это «транспорт» — верно?
[Да]  [Нет, другое]
```

`confidence` нужно передавать вместе с категорией — измени `_classify_with_retries`
чтобы возвращал `tuple[str, float]`.

### 5.3 Обработчики

```python
@dp.callback_query(F.data == "confirm_yes")
async def on_confirm_yes(callback: CallbackQuery, state: FSMContext): ...

@dp.callback_query(F.data == "confirm_no")
async def on_confirm_no(callback: CallbackQuery, state: FSMContext):
    # показать список категорий кнопками
    ...

@dp.callback_query(F.data.startswith("category:"))
async def on_category_selected(callback: CallbackQuery, state: FSMContext):
    category = callback.data.removeprefix("category:")
    # вызвать repository.update_category(expense_id, category)
    ...
```

`expense_id` храни в FSM-контексте через `await state.update_data(expense_id=...)`.

---

## Часть 6. structlog

Установи `structlog`. Логи должны выглядеть так:

```json
{"event": "classified", "expense_id": "abc-123", "category": "транспорт", "confidence": 0.45, "low_confidence": true}
```

### 6.1 Настройка

Создай `app/core/logging.py`:

```python
import structlog

def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
    )

def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)
```

Вызови `configure_logging()` в `lifespan` до всего остального.

### 6.2 Использование

Везде где сейчас `logging.getLogger(__)` — заменить на `get_logger(__)`.

Обязательно логировать в воркере:

```python
logger.warning(
    "low_confidence_classification",
    expense_id=str(task.expense_id),
    category=category,
    confidence=confidence,
)
```

В воркере при любом исключении из классификатора:

```python
logger.exception(
    "classification_failed",
    title=task.title,
)
```

---

## Итоговая структура проекта

```
app/
├── core/
│   ├── config.py
│   └── logging.py          ← новый
├── db/
│   ├── base.py
│   └── session.py
├── expenses/
│   ├── models.py
│   ├── schemas.py
│   ├── repository_base.py  ← новый (ABC)
│   ├── repository.py       ← наследует ABC
│   ├── service.py          ← зависит от ABC, не от конкретного класса
│   ├── router.py
│   ├── dependencies.py
│   └── exceptions.py
├── llm/
│   ├── classifier.py       ← бросает исключения, не глотает
│   ├── gigachat.py         ← response_format
│   ├── json_models.py
│   └── queue.py            ← NoOpClassificationQueue публичный
├── bot/
│   ├── handlers.py         ← FSM, inline keyboard
│   ├── middleware.py       ← enqueue после commit
│   └── states.py           ← новый
├── cli.py                  ← новый
└── main.py
```

