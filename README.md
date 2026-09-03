# Real-Time Task Broker & Notification Engine

Высокопроизводительный асинхронный сервис распределенной обработки фоновых задач и потоковой доставки статусов клиентам в реальном времени.

Архитектура построена по событийно-ориентированному паттерну (Event-Driven): неблокирующий HTTP REST API мгновенно принимает тяжелые вычислительные задачи, делегирует их пулу изолированных воркеров через Redis, а прогресс выполнения пушится клиенту через WebSockets с использованием шины Redis Pub/Sub без обращения к базе данных со стороны клиента.

---

## 🛠 Стек технологий

* **Язык и ядро:** Python 3.11+, `asyncio`
* **API и WebSockets:** FastAPI, Uvicorn, WebSockets
* **База данных и ORM:** PostgreSQL, SQLAlchemy 2.0, асинхронный драйвер `asyncpg`
* **Очереди задач и брокер сообщений:** Redis, Arq, Redis Pub/Sub
* **Валидация данных:** Pydantic V2, `pydantic-settings`
* **Контейнеризация:** Docker, Docker Compose

---

## 🏗 Архитектура системы

```text
[ Frontend / Client ]
      │               ▲
 1. POST /tasks       │ 5. Real-Time WS Updates
      │               │    (status: processing, completed)
      ▼               │
[ FastAPI Application ] ◄── 4. Subscribe (task_updates) ──┐
      │                                                   │
      ├─► Сохранение (status: pending) ─► [ PostgreSQL ]  │
      │                                                   │
      └─► Пуш в очередь задач ──────────► [ Redis Queue ] │
                                                 │        │
                                           Забор задачи   │
                                                 ▼        │
                                          [ Arq Worker ] ─┘
                                           3. Publish Event
```

---

## 🚀 Ключевые архитектурные решения

* **Decoupled-архитектура:** HTTP-сервер освобожден от тяжелых синхронных блокировок. Клиент получает немедленный ответ со статусом `202 Accepted` и `task_id`.
* **Асинхронный I/O слой:** Вся работа с реляционной базой данных построена на асинхронном движке `SQLAlchemy 2.0` и драйвере `asyncpg` с изолированным пулом соединений.
* **Исключение Client Polling:** Доставка статусов выполнения задач реализована через связку **Redis Pub/Sub** и постоянных соединений **WebSockets**. Это исключает паразитные повторные HTTP-запросы (`polling`) и разгружает СУБД.
* **Изолированный фоновый воркер:** Обработка задач запущена в отдельном системном процессе под управлением асинхронного брокера `Arq`.

---

## 🚦 Быстрый запуск

### Предварительные требования
* Установленный Docker и Docker Compose

### Развертывание

1. **Клонируйте репозиторий:**
   ```bash
   git clone [https://github.com/DavaToros/task-broker.git](https://github.com/DavaToros/task-broker.git)
   cd task-broker
   ```

2. **Создайте файл переменных окружения:**
   ```bash
   cp .env.example .env
   ```

3. **Запустите контейнеры:**
   ```bash
   docker compose up --build -d
   ```

Сервис запустится и автоматически выполнит миграции/создание таблиц:
* **Swagger UI / OpenAPI:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **REST API:** [http://localhost:8000](http://localhost:8000)

---

## 🧪 Проверка работы (End-to-End сценарий)

1. Откройте страницу документации [http://localhost:8000/docs](http://localhost:8000/docs).
2. Нажмите `F12` (откройте консоль браузера) и подключитесь к WebSocket:
   ```javascript
   const ws = new WebSocket("ws://localhost:8000/ws/user_test");
   ws.onopen = () => console.log("🟢 Подключено к WebSocket");
   ws.onmessage = (e) => console.log("📩 Новое событие:", JSON.parse(e.data));
   ```
3. В Swagger выполните эндпоинт **`POST /tasks/user_test`**:
   ```json
   {
     "title": "Генерация отчета",
     "work_duration": 4
   }
   ```
4. В ответ мгновенно вернется `202 Accepted` с `task_id`.
5. В консоли браузера отобразятся push-сообщения от воркера:
   * `status: processing`
   * `status: completed` (спустя 4 секунды)
6. С помощью **`GET /tasks/{task_id}`** можно убедиться, что финальный результат сохранен в PostgreSQL.
