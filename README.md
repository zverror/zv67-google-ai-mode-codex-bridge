# ZV67 · Google AI Mode Gateway

Локальный шлюз для Google AI Mode с OpenAI-совместимым API. Запускается на Mac, принимает запросы от Codex через OpenCodeX и управляет несколькими Google-аккаунтами из веб-панели. Chrome работает в headless-режиме: окна браузера при запросах не открываются.

[Установка и диагностика](docs/INSTALL.md) · [Презентация PDF](output/pdf/zv67-project.pdf) · [Архитектура](ARCHITECTURE.md) · [Проверки](docs/VERIFICATION.md)

![Панель ZV67 на демонстрационных данных](docs/screenshots/overview.png)

## Возможности

- Chat Completions и Responses API, включая SSE streaming.
- Модели Auto, 3.8 Flash и 4 Argon; локальная тестовая модель `zv67-mock`.
- Несколько аккаунтов, веса, лимиты параллельности и привязка диалога к аккаунту.
- Импорт cookies из Cookie-Editor JSON, Netscape и строки `name=value`.
- История диалогов, статистика, журнал запросов и административная панель.

В основе: FastAPI, SQLite, React и Chrome CDP. Данные аккаунтов и история шифруются локальным мастер-ключом. Подробности: [SECURITY.md](SECURITY.md).

## Что проверено

Auto отвечает через реальные Google-аккаунты; диалоги с контекстом и запросы из Codex CLI проверены. Для Flash и Argon реализован выбор через параметр Google `arv`, но на двух тестовых аккаунтах Google вернул дневной лимит. Успешная генерация этими двумя моделями пока не подтверждена.

**Tool calling не поддерживается.** Шлюз принимает определения инструментов от Codex и игнорирует их. Google-модели возвращают текст; выполнение команд и правка файлов инструментами Codex через эти модели не реализованы. Наличие модели в каталоге не доказывает её доступность для конкретного аккаунта.

## Быстрая установка на macOS

Проверено на Apple Silicon. Нужны Git, `uv`, Node.js 20.19+ или 22.12+ и Google Chrome для реальных запросов. Python 3.12 установщик создаст через `uv`. Для Node.js рекомендуется версия 24.

Если Homebrew уже установлен:

```bash
brew install git uv node@24
brew install --cask google-chrome
export PATH="$(brew --prefix node@24)/bin:$PATH"
```

Клонирование и запуск:

```bash
mkdir -p "$HOME/Projects"
cd "$HOME/Projects"
git clone https://github.com/zverror/zv67-google-ai-mode-codex-bridge.git
cd zv67-google-ai-mode-codex-bridge
./scripts/install.sh
./scripts/zv67 doctor
```

Репозиторий сейчас приватный. Для клонирования владелец должен предоставить вашему GitHub-аккаунту доступ; при необходимости используйте `gh auth login` и `gh repo clone zverror/zv67-google-ai-mode-codex-bridge`. Для открытого распространения отдельно требуются изменение видимости и выбор лицензии.

Установщик собирает панель, устанавливает backend и LaunchAgent `com.zv67.gateway`, запускает сервис на `127.0.0.1:18080`. База и ключ хранятся в `~/Library/Application Support/ZV67`. При первом запуске применяются миграции базы. Держите клон в постоянной папке: LaunchAgent ссылается на неё.

Откройте `http://127.0.0.1:18080/admin/` и задайте пароль администратора. Другой порт, обновление и резервные копии описаны в [docs/INSTALL.md](docs/INSTALL.md).

## Проверка без Google

```bash
curl -fsS http://127.0.0.1:18080/health
curl -fsS http://127.0.0.1:18080/v1/models
curl -fsS http://127.0.0.1:18080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"zv67-mock","messages":[{"role":"user","content":"Проверка связи"}]}'
```

Mock возвращает детерминированный тестовый ответ и не обращается к Google. С ним можно проверить установку до подключения аккаунта.

## Подключение Google-аккаунта

1. В панели откройте «Аккаунты» и создайте профиль. Название произвольное; подписку укажите вручную. Для начала оставьте вес `100` и параллельность `1`.
2. Нажмите `Credentials`. Вставьте полный экспорт cookies для Google: массив JSON из Cookie-Editor, текст Netscape или строку cookie-заголовка. Нажмите «Сохранить».
3. Выполните реальный запрос к `google-ai-mode` командой из раздела API ниже. Доступ определяется ответом Google; статус профиля сам по себе не гарантирует наличие квоты.

Cookies вводятся только в локальной панели. Пароль Google не нужен. Не сохраняйте cookies в клоне проекта и не прикладывайте их к issue.

## Модели

| ID для API ZV67 | Название | Состояние проверки |
|---|---|---|
| `zv67-mock` | Локальный mock | Тестовый ответ без Google |
| `google-ai-mode` | Google AI Mode / Auto | Реальные ответы получены |
| `google-ai-mode-3.8-flash` | Google AI Mode 3.8 Flash | Выбор передаётся; тестовые аккаунты вернули 429 |
| `google-ai-mode-4-argon` | Google AI Mode 4 Argon | Выбор передаётся; тестовые аккаунты вернули 429 |

В Codex через OpenCodeX к ID добавляется префикс провайдера: например, `zv67/google-ai-mode-4-argon`.

## Codex через OpenCodeX

Команды ниже сверены с OpenCodeX **2.92.0**. На новом Mac сначала установите Codex CLI и OpenCodeX:

```bash
npm install -g @openai/codex @bitkyc08/opencodex@2.92.0
```

Добавьте провайдера и все четыре модели:

```bash
ocx provider add zv67 \
  --adapter openai-chat \
  --base-url http://127.0.0.1:18080/v1 \
  --auth-mode local \
  --default-model google-ai-mode \
  --model google-ai-mode --text-only \
  --allow-private-network

ocx models add zv67 zv67-mock --display-name 'ZV67 Mock' --modalities text
ocx models add zv67 google-ai-mode --display-name 'Google AI Mode' --modalities text
ocx models add zv67 google-ai-mode-3.8-flash --display-name 'Google AI Mode 3.8 Flash' --modalities text
ocx models add zv67 google-ai-mode-4-argon --display-name 'Google AI Mode 4 Argon' --modalities text

ocx ensure
ocx sync
ocx models list
ocx provider test zv67 --model zv67-mock --yes
```

Если провайдер `zv67` уже есть, сначала проверьте его командой `ocx provider show zv67`. Повторное добавление с `--force` заменяет его настройки; не используйте этот флаг без проверки. Настройка OpenCodeX меняет пользовательскую интеграцию Codex; сохраните свои конфиги по [инструкции](docs/INSTALL.md#codex-и-opencodex).

Текстовый запрос из CLI:

```bash
codex exec -m zv67/google-ai-mode 'Назови столицу Франции одним словом'
```

Для Codex Desktop полностью завершите приложение через `Cmd+Q` после `ocx sync`, затем откройте снова. Ищите названия из таблицы моделей. Генерация через CLI проверялась; фактический выбор в интерфейсе Desktop автоматизированно не проверялся.

## API

Базовый адрес: `http://127.0.0.1:18080/v1`.

```bash
curl -fsS http://127.0.0.1:18080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"google-ai-mode","messages":[{"role":"user","content":"Столица Франции?"}]}'
```

Для SSE добавьте `"stream": true` и используйте `curl -N`. Также доступны `POST /v1/responses` и `GET /v1/models`. Если настроен `ZV67_API_KEY`, добавляйте заголовок `Authorization: Bearer <ключ>`.

## Управление

```bash
./scripts/zv67 status
./scripts/zv67 restart
./scripts/zv67 stop
./scripts/zv67 start
./scripts/zv67 logs
```

## Ограничения

Google AI Mode подключён через неофициальный веб-протокол. Доступ зависит от аккаунта, региона, cookies, квоты и изменений Google. Шлюз не гарантирует доступность Flash и Argon и не снимает лимиты. Точная статистика токенов Google недоступна. Входящие изображения и файлы не поддерживаются. Установка рассчитана на один локальный Mac; Linux и Windows этим установщиком не поддерживаются.

## Документация и презентация

- [Полная установка, обновление, резервная копия и диагностика](docs/INSTALL.md).
- [Архитектура](ARCHITECTURE.md), [границы реализации](docs/FEASIBILITY.md), [результаты проверок](docs/VERIFICATION.md).
- [Вертикальная PDF-презентация](output/pdf/zv67-project.pdf), [контактный лист](output/pdf/zv67-contact-sheet.jpg), [редактируемые исходники](docs/presentation/).

## Лицензия

Лицензия для распространения собственного кода пока не выбрана. Наличие кода на GitHub само по себе не даёт разрешения на его свободное использование и распространение. Лицензии двух шрифтов презентации находятся рядом с файлами шрифтов и относятся только к ним.
