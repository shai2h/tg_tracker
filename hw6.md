# Домашка 6 — JSON-схема, очередь классификации, lifespan

## Контекст

После hw5 классификатор работает, но синхронно блокирует ответ пользователю.
Кроме того, GigaChat возвращает просто строку — без уверенности. Плюс в `main.py`
нет `lifespan`, провайдер создаётся в `ServiceMiddleware` каждый раз.

Три вещи, которые нужно сделать:

1. **JSON-схема** — переключить GigaChat на структурированный вывод: `category` + `confidence`
2. **Lifespan** — создавать `GigaChatProvider` один раз при старте FastAPI-приложения
3. **Очередь** — сохранять расход немедленно, классифицировать в фоне

---

## Часть 1. JSON-схема в классификаторе

### 1.1 Изменить промпт и парсинг в `classifier.py`

Вместо «верни одно слово» попроси GigaChat вернуть JSON: Почитай документацию GigaChat, там есть примеры как просить JSON,
нам нужна именно схема на стороне провайдера!

```json
{"category": "кафе", "confidence": 0.95}
```

Класс `ExpenseCategoryClassifier`:
- Промпт должен явно описывать схему ответа и запрещать любой текст вне JSON
- Парсить ответ через `json.loads`
- Если парсинг упал или поля не те — возвращать `("другое", 0.0)`
- Метод `classify` теперь возвращает `tuple[str, float]` — `(category, confidence)`

### 1.2 Обновить `ExpenseService`

Метод `create_from_bot` получает `(category, confidence)` от классификатора.
Поле `confidence` сейчас нигде не хранится — это нормально, используй его только
для логики переспроса (часть 3). В `repository.create` передавай только `category`.

### 1.3 Тесты в `tests/test_classifier.py`

Добавь тесты (провайдер мокать как и раньше):
- Провайдер вернул валидный JSON — классификатор возвращает правильную пару `(category, confidence)`
- Провайдер вернул невалидный JSON (просто текст) — возвращает `("другое", 0.0)`
- Провайдер вернул JSON с незнакомой категорией — возвращает `("другое", confidence)`
- Провайдер вернул пустую строку — возвращает `("другое", 0.0)`

---

## Часть 2. Lifespan в FastAPI

Сейчас `app/main.py` создаёт `FastAPI()` без lifespan — `GigaChatProvider` нигде
не живёт централизованно.

### Что нужно сделать

В `app/main.py` добавь `lifespan`:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    provider = GigaChatProvider(...)  # создаётся один раз
    app.state.gigachat_provider = provider
    yield
    # cleanup если нужен

app = FastAPI(lifespan=lifespan)
```

В `app/expenses/dependencies.py` функция `get_expense_service` должна получать
провайдер из `request.app.state.gigachat_provider` вместо того, чтобы создавать
его каждый раз.

Параметры провайдера берутся из `settings` (они уже есть в `config.py`).

---

## Часть 3. Фоновая очередь классификации

### Идея

Сейчас `add_expense` в боте ждёт пока GigaChat ответит — это может занять 2–5 секунд.
Нужно:

1. Сохранить расход немедленно с `category=None`
2. Ответить пользователю «сохранил» сразу
3. В фоне классифицировать расход и обновить `category` в базе
4. Отправить пользователю второе сообщение с категорией — как только классификация
   завершится, но **не позже чем через 3 секунды** после первого ответа

Если после 3 попыток категория так и не определена — сохранить `"неизвестно"`.

### 3.1 Очередь в `app/llm/queue.py`

Создай класс `ClassificationQueue`:

```python
class ClassificationQueue:
    def __init__(self, classifier: ExpenseCategoryClassifier): ...

    async def start(self): ...   # запускает фоновый воркер
    async def stop(self): ...    # graceful shutdown, дожидается текущей задачи

    async def enqueue(
        self,
        expense_id: UUID,
        title: str,
        on_done: Callable[[str], Awaitable[None]],
    ) -> None: ...
```

Внутри — `asyncio.Queue`. Воркер крутится в фоне (`asyncio.create_task`).

Логика воркера для каждой задачи:
- Попытаться классифицировать (до 3 раз, без задержки между попытками)
- Если все попытки упали — использовать `"неизвестно"`
- Вызвать `on_done(category)` — колбэк обновит базу и отправит сообщение

### 3.2 Интегрировать очередь в lifespan

В `lifespan` создай `ClassificationQueue`, запусти (`await queue.start()`),
останови при завершении (`await queue.stop()`).

Храни очередь в `app.state.classification_queue`.

### 3.3 Изменить `ExpenseService.create_from_bot`

Убрать прямой вызов классификатора. Метод теперь:
1. Сохраняет расход с `category=None`
2. Ставит задачу в очередь через `queue.enqueue(...)`
3. Возвращает расход сразу

`on_done` колбэк должен вызывать `repository.update_category(expense_id, category)`.
Добавь этот метод в `ExpenseRepository`.

Конструктор `ExpenseService` теперь принимает `queue: ClassificationQueue`
вместо `classifier: ExpenseCategoryClassifier`.

### 3.4 Изменить бота (`bot/handlers.py`)

Обработчик `add_expense` больше не получает категорию сразу — она придёт позже
через колбэк. Нужно:

1. Отправить первое сообщение сразу после сохранения:
   ```
   Сохранил: кофе — 150 ₽
   Определяю категорию...
   ```

2. Через `asyncio.wait_for(..., timeout=3.0)` дождаться результата классификации.
   Если успел — отправить второе сообщение:
   ```
   Категория: кафе ✓
   ```
   Если таймаут — не отправлять ничего (категория обновится в базе в фоне,
   пользователь увидит её в следующий раз в `/list`).

3. Если `confidence < 0.6` — вместо тихого подтверждения переспросить:
   ```
   Похоже это «транспорт» — верно?
   ```
   с inline-кнопками **Да** / **Нет, другое**. При «Нет» показать список
   категорий кнопками, пользователь выбирает сам. Сохранить выбор через
   `repository.update_category`.

Для переспроса нужен FSM (aiogram States). `on_done` колбэк должен уметь
пробудить ожидающую корутину в боте — используй `asyncio.Event` или
`asyncio.Future`, который создаётся в обработчике и передаётся как часть
`on_done`.

### 3.5 Тесты в `tests/test_queue.py`

- Задача классифицируется и колбэк вызывается с правильной категорией
- Если классификатор падает 3 раза — колбэк вызывается с `"неизвестно"`
- Колбэк вызывается ровно один раз (не дважды)

---

## Что не нужно делать

- Не добавляй персистентность очереди (Redis, база) — только in-memory
- Не добавляй rate limiting или exponential backoff — просто 3 попытки подряд
- Не обрабатывай случай когда бот перезапустился пока задача в очереди

---

## Подсказки

- `asyncio.wait_for(fut, timeout=3.0)` бросает `asyncio.TimeoutError` — лови его
- `asyncio.get_event_loop().create_future()` создаёт Future который можно
  разрешить из другой корутины через `fut.set_result(...)`
- FSM в aiogram: `StatesGroup`, `State`, `FSMContext` — состояние хранится
  per-user per-chat
- Inline keyboard в aiogram: `InlineKeyboardMarkup`, `InlineKeyboardButton`,
  `callback_query` handler с `F.data`
- `app.state` в FastAPI — просто объект, можно писать любые атрибуты

---

## Критерии приёма

- [ ] `classify` возвращает `tuple[str, float]`, парсит JSON из ответа GigaChat
- [ ] Если ответ не JSON или категория неизвестна — возвращает `("другое", 0.0)`
- [ ] `GigaChatProvider` создаётся в `lifespan`, живёт в `app.state`
- [ ] `ClassificationQueue` в `app/llm/queue.py`, воркер на `asyncio.Queue`
- [ ] Расход сохраняется немедленно с `category=None`
- [ ] Колбэк обновляет категорию в базе после классификации
- [ ] Бот отвечает пользователю сразу, категория приходит вторым сообщением (≤3 сек) или не приходит
- [ ] При `confidence < 0.6` бот переспрашивает с inline-кнопками
- [ ] 4 теста: 3 в `test_classifier.py` (новые для JSON), 3 в `test_queue.py`
