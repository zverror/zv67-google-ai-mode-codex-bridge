# ZV67 — Google AI Mode Agent Gateway

Локальный шлюз с OpenAI-совместимым API, мультиаккаунтным управлением, сессиями, статистикой и веб-панелью. Проект создан как основа для подключения Google AI Mode к Codex через OpenCodeX.

## Текущее состояние

Что работает и проверено:

- FastAPI-сервер на `127.0.0.1:18080`;
- Chat Completions, включая SSE streaming;
- Responses API с событиями streaming;
- детерминированный mock-провайдер `zv67-mock`;
- SQLite с миграциями Alembic;
- управление аккаунтами, лимитами параллельности и весами;
- стратегии round-robin, weighted round-robin, least-busy, manual и sticky-сессии;
- шифрование credentials и истории диалогов;
- административная панель с авторизацией, CSRF и аудитом;
- статистика запросов, ошибок и задержек;
- регистрация провайдера `zv67` в установленном OpenCodeX.
- реальный Google AI Mode через headless Chrome CDP;
- два Google-аккаунта с разными cookies;
- многошаговый диалог с сохранением контекста;
- выбор модели `zv67/google-ai-mode` и запросы из Codex CLI.

Что не работает:

- tool calling в ZV67: **UNSUPPORTED**. Codex получает текстовые ответы, но не может выполнять инструменты через Google AI Mode;
- выбор модели в нативном интерфейсе Codex Desktop: **NOT TESTED**. Приложение Codex Desktop недоступно для автоматизированной проверки интерфейса.

Модель `zv67-mock` не выдаётся за Google AI Mode. Модель `google-ai-mode` работает через неофициальный протокол Google и может перестать работать при изменении защиты.

## Архитектура

```text
Codex Desktop / CLI
        |
        v
     OpenCodeX
        |
        v
   ZV67 Gateway
   |          |
 API        Dashboard
   |
 Session Manager
   |
 Account Router
   |
 UpstreamProvider
   |
   google / mock
```

CLIProxyAPI в цепочку не входит и не изменялся.

Подробности: [ARCHITECTURE.md](ARCHITECTURE.md), [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md), [docs/FEASIBILITY.md](docs/FEASIBILITY.md).

## Установка

Требования: macOS на Apple Silicon, Python 3.12+, Node.js 20+.

```bash
cd /Users/orfeev/Desktop/Projects/ZV67
./scripts/install.sh
```

Установщик создаёт виртуальное окружение backend, собирает frontend, инициализирует базу в `~/Library/Application Support/ZV67`, устанавливает LaunchAgent и запускает сервис. LaunchAgent использует мастер-ключ в файле с правами `0600`, чтобы старт не зависел от диалогов Keychain.

Проверка:

```bash
./scripts/zv67 doctor
curl -s http://127.0.0.1:18080/health
```

Панель: `http://127.0.0.1:18080/admin/`. При первом открытии задаётся пароль администратора.

## Запуск вручную

```bash
cd backend
uv venv .venv
uv pip install --python .venv/bin/python -e '.[dev]'
.venv/bin/python -m uvicorn zv67.main:app --host 127.0.0.1 --port 18080
```

Для разработки панели:

```bash
cd frontend
npm install
npm run dev
```

Vite проксирует `/admin/api` на порт 18080.

## Настройка Google-аккаунтов

Откройте панель, раздел «Аккаунты», создайте профиль и нажмите «Credentials». Принимается JSON из Cookie-Editor, файл Netscape и строка `name=value; name2=value2`. Значение шифруется мастер-ключом; в журналы и Git оно не попадает.

Пример структуры:

```json
[{"name": "__Secure-1PSID", "value": "..."}]
```

Не вставляйте cookies в чат, issue, логи или файлы репозитория. Пароль Google не запрашивается.

После импорта cookies аккаунт готов к реальным запросам. Для каждого аккаунта создаётся отдельный временный профиль Chrome; браузер работает в headless-режиме и не открывает окно. Профиль удаляется при закрытии сессии.

## Подключение OpenCodeX

Провайдер уже добавлен в `~/.opencodex/config.json`:

```text
provider: zv67
adapter:  openai-chat
baseUrl:  http://127.0.0.1:18080/v1
models:   zv67-mock, google-ai-mode
```

Проверка:

```bash
ocx provider test zv67 --model google-ai-mode --yes
ocx models list
```

Перед изменением конфигурации создан backup: `~/.opencodex/config.json.backup-zv67-20261024`.

Отключение провайдера:

```bash
ocx provider remove zv67
```

Команда меняет общий конфигурационный файл; сначала сделайте backup.

## API

```bash
curl -s http://127.0.0.1:18080/health
curl -s http://127.0.0.1:18080/v1/models

curl -s -X POST http://127.0.0.1:18080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"google-ai-mode","messages":[{"role":"user","content":"Столица Франции?"}]}'
```

При заданном `ZV67_API_KEY` добавьте заголовок `Authorization: Bearer <key>`.

Streaming включается полем `"stream": true`. Responses API: `POST /v1/responses`.

## Панель

![Обзор](docs/screenshots/overview.png)

Скриншоты сняты на тестовом профиле с mock-провайдером. Аккаунты Google — демонстрационные записи; реальные cookies в репозиторий не попадали.

Разделы: обзор, аккаунты, модели, статистика, журнал, настройки, система. Данные приходят из Management API; фиктивных метрик нет.

## Безопасность

- сервер по умолчанию слушает только `127.0.0.1`;
- пароль администратора хранится как scrypt-хеш;
- сессия панели — HttpOnly cookie, SameSite=Strict;
- изменяющие запросы защищены CSRF-токеном;
- credentials и история шифруются Fernet-ключом; LaunchAgent использует файл `0600`;
- журналы не содержат промптов и cookies;
- удаление аккаунта удаляет его credentials и сессии.

Подробнее: [SECURITY.md](SECURITY.md).

## Обновление и управление

```bash
./scripts/zv67 start
./scripts/zv67 stop
./scripts/zv67 restart
./scripts/zv67 status
./scripts/zv67 logs
./scripts/zv67 doctor
```

## Известные ограничения

1. Google AI Mode использует неофициальный протокол; Google может изменить защиту или заблокировать сессию.
2. Tool calling не реализован; агентские действия Codex через Google AI Mode не подтверждены.
3. Codex Desktop может показывать модель из каталога OpenCodeX, но фактический выбор в UI не проверен; CLI работает с `-m zv67/google-ai-mode`.
4. Точная статистика токенов Google недоступна и не выдумывается.
5. Приложение рассчитано на один локальный Mac без контейнеров и внешних сервисов.

## Юридическое предупреждение

Google AI Mode не предоставляет официальный API для такого использования. Проект работает через неофициальный протокол и нарушает условия Google; ответственность за использование лежит на владельце аккаунтов.

## Лицензия

Собственный код проекта. Сторонний код XD06/google-ai-mode не копировался.

