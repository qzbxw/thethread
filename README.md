# Нить — AI Таро бот (Telegram)

Нить — это ИИ ассистент, который использует архетипы Таро как метафоры в диалоге. Без мистики — только смысл, структура и маленькие шаги.

## Возможности

- **Расклады**: Карта дня (бесплатно), Быстрый (3 карты), Глубокий (10 карт)
- **AI‑диалог** на базе Gemini (Google Generative AI)
- **Stripe**: покупка кристаллов, вебхук, success/cancel страницы
- **Инкогнито**: диалог без сохранения истории
- **Админ‑бот**: базовая статистика, начисление кристаллов, рассылка
- **Логи в админ‑чат**: ключевые события (новые пользователи, платежи, ошибки) отправляются в админ‑чат

## Архитектура

- `main.py` — локальный вход, запускает polling и БД
- `render_entry.py` — единый вход для Render Web Service: aiohttp сервер (Stripe) + polling в одном процессе
- `handlers/stripe_webhook.py` — aiohttp сервер: `/webhook`, `/success`, `/cancel`, `/healthz`
- `handlers/*.py` — обработчики Telegram (aiogram 3)
- `utils/gemini_utils.py` — генерация ответа по картам
- `utils/ui.py` — все клавиатуры, Active Message (`set_active_kb`)
- `models/database.py` — PostgreSQL (asyncpg), таблицы `users`, `transactions`, `checkout_sessions`, `active_messages`
- `Dockerfile`, `docker-compose.yml` — контейнеризация и локальная БД

### Логирование в админ‑бота

Логи отправляются в Telegram через отдельного бота (`ADMIN_BOT_TOKEN`). Если он не задан, используется основной бот как фоллбэк.

Настроить нужно два параметра в `.env`:

```
ADMIN_BOT_TOKEN=123:abc...
ADMIN_IDS=111111111,222222222
```

Проверка: при первом `/start` в основном боте админы получат сообщение `New user: ...`. Успешные платежи логируются как `Successful payment ...`.
## Быстрый старт (локально)

1) Клонировать репозиторий
2) Создать виртуальное окружение и установить зависимости
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```
3) Скопировать окружение
```bash
cp .env.example .env
# Заполнить значения: BOT_TOKEN, BOT_USERNAME, GEMINI_API_KEY, STRIPE_*, ADMIN_IDS, PUBLIC_BASE_URL
```
4) Запустить Postgres (через Docker Compose)
```bash
docker-compose up -d postgres
```
5) Запустить бота
```bash
python main.py
```

Админ‑бот (опционально) запускается отдельной командой:
```bash
python admin_bot.py
```

В админ‑боте работает универсальная отмена: `/cancel` (или `/Cancel`).

## Запуск в Docker полностью

```bash
docker-compose up -d  # поднимет postgres и бота (порт 8000 публикуется)
```
Переменная `DATABASE_URL` для сервиса `bot` задаётся в `docker-compose.yml` и указывает на контейнер `postgres`.

## Переменные окружения (`.env`)

Полный шаблон в `.env.example`.

- `BOT_TOKEN` — токен Telegram бота
- `BOT_USERNAME` — имя бота без `@` (для ссылок на Telegram из success‑страницы)
- `ADMIN_BOT_TOKEN` — токен админ‑бота (для логирования событий)
- `ADMIN_IDS` — список Telegram ID админов (через запятую)
- `DATABASE_URL` — строка подключения Postgres
- `GEMINI_API_KEY` — ключ Google Generative AI
- `STRIPE_SECRET_KEY` — секретный ключ Stripe
- `STRIPE_WEBHOOK_SECRET` — секрет подписи вебхука Stripe
- `PUBLIC_BASE_URL` — публичная базовая ссылка веб‑сервера (для success/cancel и навигации)

## Форматирование ответов (Markdown)

Ответы модели форматируются в Markdown (жирный акцент, короткие списки). Сообщения бота используют HTML (`parse_mode=HTML`). Если в ответе модели встречаются неподдерживаемые конструкции, Telegram может отклонить редактирование — в этом случае бот отправит новое сообщение.
