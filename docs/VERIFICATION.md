# Журнал проверок ZV67

**Дата:** 24 октября 2026.  
**Версия:** 0.1.0.  
**Провайдер:** mock.

## Автоматические тесты

Команда:

```bash
cd backend
.venv/bin/python -m pytest tests -q
```

Результат: **59 passed**, одно предупреждение Starlette о `httpx`/`httpx2`.

Покрыто:

- health и реестр моделей;
- Chat Completions, ошибки и лимиты;
- SSE streaming и Responses API;
- нормализация ролей и system/developer instructions;
- mock-провайдер без сети;
- SQLite-миграции, downgrade и повторный запуск;
- шифрование credentials и маскирование секретов;
- API keys, scrypt-пароль, CSRF и rate limit;
- аккаунты, sticky sessions, concurrency и cooldown;
- статистика и журнал запросов.

## Ручные проверки

| Проверка | Команда | Результат |
|---|---|---|
| Health | `curl /health` | PASS: `status=ok`, `mock=true` |
| Модели | `curl /v1/models` | PASS: `zv67-mock` |
| Chat Completions | `curl POST /v1/chat/completions` | PASS: детерминированный ответ |
| Streaming | `curl -N` с `stream=true` | PASS: SSE и `[DONE]` |
| Responses | `curl POST /v1/responses` | PASS: `response.completed` |
| Панель | `http://127.0.0.1:18080/admin/` | PASS: все разделы отрисованы |
| OpenCodeX | `ocx provider test zv67 --model zv67-mock --yes` | PASS: `ok=true`, wire model совпал |
| Каталог Codex | `~/.codex/opencodex-catalog.json` | PASS: `zv67/zv67-mock` присутствует |
| Codex CLI | `codex exec -m zv67-mock` | FAIL: tool calling не поддерживается |
| Codex Desktop UI | визуальный выбор модели | NOT TESTED: приложение закрыто для CUA |

## Установка и автозапуск

| Проверка | Команда | Результат |
|---|---|---|
| LaunchAgent | `launchctl print gui/$(id -u)/com.zv67.gateway` | PASS: загружен |
| Doctor | `./scripts/zv67 doctor` | PASS: venv, frontend, plist, data, health, dashboard |
| Перезапуск | `launchctl kickstart -k` | PASS: сервис вернулся, /health отвечает |
| Хранилище ключа | LaunchAgent c `ZV67_MASTER_KEY_STORE=file` | PASS: файл 0600, без диалогов Keychain |

Первый вариант автозапуска с Keychain завис на старте: LaunchAgent не может пройти интерактивную проверку доступа. Рабочая конфигурация использует файловый мастер-ключ с правами 0600.

## Проверка моделей OpenCodeX

| Провайдер | Модель | Результат |
|---|---|---|
| zv67 | zv67-mock | PASS |
| raya-auto | route | PASS, upstream `gemini-3.8-flash-high` |
| oMLX | Cyber-Tiel | FAIL: сеть, локальный сервер недоступен |
| opencode | kimi-k2.7-code | FAIL: HTTP 400 |
| ohh | 7 моделей | NOT TESTED: провайдер отключён |
| openai | 3 модели | NOT TESTED: forward-auth |

Эти результаты относятся к текущему состоянию установленного OpenCodeX и не являются обещанием доступности моделей.

## Google AI Mode

LIVE: **NOT TESTED**.  
Реальный аккаунт не использовался. Adapter: **UNSUPPORTED** по причинам из `docs/FEASIBILITY.md`.

## Что не доказано

- ответы Google AI Mode;
- сохранение контекста на стороне Google;
- выбор модели в Codex Desktop;
- агентский цикл Codex через Google AI Mode;
- tool calling.

