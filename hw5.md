# Домашка 5 — Классификация расходов через GigaChat

## Контекст

Сейчас при создании расхода поле `category` в базе всегда остаётся `null`.
Твоя задача — автоматически определять категорию расхода с помощью GigaChat
и сохранять её при создании.

Поле `category` уже есть в модели `ExpenseOrm` и в схеме `ExpenseRead`.
Папка `app/llm/` уже создана, файл `classifier.py` пустой.

---

## Что нужно сделать

### 1. `app/llm/gigachat.py` — провайдер (клиент к API)

Создай класс `GigaChatProvider` с единственным публичным методом:

```python
async def complete(self, prompt: str) -> str:
    ...
```

Метод отправляет запрос в GigaChat API и возвращает текст ответа (строку).

Что должен делать класс:
- Принимать `api_key: str` в конструкторе
- Отправлять POST-запрос через `httpx.AsyncClient`
- URL, модель, формат запроса/ответа — смотри документацию GigaChat API
- Никакой бизнес-логики: только HTTP-запрос и возврат текста

Добавь `GIGACHAT_API_KEY` в `app/core/config.py` (Settings).

---

### 2. `app/llm/classifier.py` — сервис классификации

Создай класс `ExpenseCategoryClassifier` с методом:

```python
async def classify(self, title: str) -> str:
    ...
```

Метод определяет категорию расхода по его названию и возвращает одну из
допустимых категорий строкой.

Допустимые категории (например эти 10):

```
кафе, транспорт, жильё, одежда, продукты, здоровье, развлечения, связь, спорт, другое
```

Что должен делать класс:
- Принимать `provider: GigaChatProvider` в конструкторе
- Составлять промпт с чёткой инструкцией: одно слово из списка, без пояснений
- Вызывать `provider.complete(prompt)`
- Парсить ответ: если пришло что-то не из списка — возвращать `"другое"`

---

### 3. Интеграция в `ExpenseService`

Метод `create` должен при создании расхода:
1. Вызвать классификатор и получить категорию
2. Передать категорию в `repository.create`

Для этого нужно:
- Добавить `classifier: ExpenseCategoryClassifier` как аргумент конструктора
  `ExpenseService` (рядом с `repository`)
- Обновить `repository.create` — добавить параметр `category: str`
- Передавать `category` при сохранении в базу

---

### 4. Подключить в `ServiceMiddleware`

`ServiceMiddleware` сейчас создаёт `ExpenseService(ExpenseRepository(session))`.
Нужно также создавать `GigaChatProvider` и `ExpenseCategoryClassifier` и
передавать их в сервис.

`GigaChatProvider` создаётся один раз при старте приложения (в `lifespan`) и
передаётся через `dp.start_polling(bot, ..., gigachat_provider=provider)` —
аналогично тому, как сейчас передаётся `session_factory`.

---

### 5. Тесты

Напиши тесты в `tests/test_classifier.py`.

Что тестировать:
- Классификатор возвращает правильную категорию если провайдер вернул валидный ответ
- Классификатор возвращает `"другое"` если провайдер вернул что-то не из списка
- Классификатор возвращает `"другое"` если провайдер вернул пустую строку

Провайдер в тестах нужно замокать — не ходить в реальное API.

---

## Что не нужно делать

- Не трогай `app/expenses/models.py` — `category` уже есть
- Не добавляй новых HTTP-эндпоинтов
- Не обрабатывай ошибки сети внутри классификатора — пусть исключение идёт
  наверх, `ServiceMiddleware` его поймает

---

## Подсказки

- `httpx.AsyncClient` умеет работать как async context manager
- `response.raise_for_status()` — хороший способ упасть громко если API вернул ошибку
- GigaChat возвращает ответ в поле `choices[0].message.content`
- Промпт должен быть детерминированным: перечисли все 10 категорий прямо в нём
  и попроси вернуть ровно одно слово

---

## Критерии приёма

- [ ] `GigaChatProvider` в `app/llm/gigachat.py`, принимает `api_key`, имеет `async complete(prompt)`
- [ ] `ExpenseCategoryClassifier` в `app/llm/classifier.py`, принимает `provider`, имеет `async classify(title)`
- [ ] Если ответ не из списка — возвращает `"другое"`, не падает
- [ ] `ExpenseService.create` вызывает классификатор и сохраняет категорию
- [ ] `GigaChatProvider` создаётся в `lifespan`, передаётся через `start_polling`
- [ ] 3 теста в `tests/test_classifier.py`, провайдер замокан
