# Установка ZV67

Инструкция рассчитана на новый Mac. Рабочая конфигурация проверена на macOS с Apple Silicon; на Intel отдельная проверка не проводилась. Docker, серверная база и API-ключ Google не нужны.

## Требования

| Компонент | Требование |
|---|---|
| macOS | Нужен `launchd`; установщик проверяет платформу |
| Node.js | 20.19+ или 22.12+; рекомендуется 24 |
| Python | 3.12+; `uv` создаёт окружение на 3.12 |
| Git и uv | Доступны в `PATH` |
| Chrome | Google Chrome в `/Applications` либо Chromium; нужен для Google, mock работает без него |
| Google | Аккаунт с доступом к AI Mode и экспорт его cookies |
| GitHub | Доступ к приватному репозиторию |

Homebrew устанавливается отдельно по официальной инструкции: https://brew.sh/. Если он уже есть:

```bash
brew install git uv node@24
brew install --cask google-chrome
export PATH="$(brew --prefix node@24)/bin:$PATH"
node --version
uv --version
```

Добавьте строку `export PATH=...` в свой профиль shell, если хотите использовать Node.js 24 в новых терминалах. Системный Python установщик не меняет.

## Получение проекта

Доступ к репозиторию выдаёт его владелец. Один из вариантов клонирования:

```bash
mkdir -p "$HOME/Projects"
cd "$HOME/Projects"
git clone https://github.com/zverror/zv67-google-ai-mode-codex-bridge.git
cd zv67-google-ai-mode-codex-bridge
```

Для приватного репозитория удобно использовать GitHub CLI:

```bash
brew install gh
gh auth login
gh repo clone zverror/zv67-google-ai-mode-codex-bridge
cd zv67-google-ai-mode-codex-bridge
```

Выберите один способ, повторно клонировать не нужно. Каталог `~/Projects` позволяет избежать ограничений фонового доступа macOS к Desktop и Documents. После установки не перемещайте клон без повторного запуска установщика.

## Установка и первый запуск

Из корня клона:

```bash
./scripts/install.sh
./scripts/zv67 doctor
curl -fsS http://127.0.0.1:18080/health
```

Установщик проверяет ОС, инструменты, версию Node.js и порт. Затем создаёт `backend/.venv`, устанавливает Python-зависимости, выполняет `npm ci` и `npm run build`, формирует LaunchAgent и запускает его. Миграции базы применяются при старте backend. При обновлении существующий сервис перезапускается после успешной сборки.

Панель доступна по адресу `http://127.0.0.1:18080/admin/`. При первом входе создайте пароль администратора. Для теста выполните:

```bash
curl -fsS http://127.0.0.1:18080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"zv67-mock","messages":[{"role":"user","content":"Проверка"}]}'
```

Ожидается текст `Mock response from zv67-mock: Проверка`. Запрос не расходует квоту Google.

LaunchAgent запускается в пользовательской сессии после входа в macOS. Администраторские права для него не нужны. Установщик регистрирует один сервис с именем `com.zv67.gateway`; не запускайте несколько установок одновременно.

## Где лежат данные

| Путь | Содержимое |
|---|---|
| `~/Library/Application Support/ZV67/zv67.sqlite3` | Аккаунты, зашифрованная история, статистика, настройки |
| `~/Library/Application Support/ZV67/master.key` | Мастер-ключ, права `0600` |
| `~/Library/Application Support/ZV67/logs/` | stdout и stderr сервиса |
| `~/Library/LaunchAgents/com.zv67.gateway.plist` | Команда запуска и переменные окружения |
| `backend/.venv`, `frontend/dist` | Окружение backend и собранная панель в клоне |

LaunchAgent использует файловый ключ, чтобы запуск не зависел от диалогов Keychain. Сохраняйте базу и ключ вместе: они нужны для восстановления зашифрованных данных. Реальные cookies и локальную базу в Git добавлять не нужно.

## Google-аккаунты и cookies

1. Войдите в Google в своём обычном браузере и убедитесь, что AI Mode доступен.
2. Экспортируйте cookies Google. Поддерживаются массив объектов Cookie-Editor JSON, текст Netscape и строка `name=value; name2=value2`.
3. В панели ZV67 откройте «Аккаунты», создайте профиль, нажмите `Credentials`, вставьте экспорт целиком и сохраните.
4. Проверьте модель запросом к `google-ai-mode` из README.

Название профиля произвольное. «Подписка» служит ручной меткой и не определяется автоматически. Вес задаёт долю аккаунта при взвешенной маршрутизации; начните со `100`. Параллельность начните с `1`.

Для каждого активного аккаунта шлюз создаёт отдельный временный профиль Chrome. Используется `--headless=new`: видимое окно браузера не открывается. Пароль Google в ZV67 не вводится.

Кнопка проверки профиля не заменяет реальный запрос: подключение Chrome ещё не доказывает, что cookies актуальны и у аккаунта осталась квота. При истечении cookies повторите экспорт и замените credentials в панели.

## Codex и OpenCodeX

OpenCodeX является отдельным проектом: https://github.com/lidge-jun/opencodex. Приведённые команды сверены с CLI версии 2.92.0. Сначала сохраните существующие конфиги, если уже пользуетесь Codex или OpenCodeX:

```bash
backup_dir="$HOME/zv67-client-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -m 700 "$backup_dir"
if [ -f "$HOME/.codex/config.toml" ]; then
  cp -p "$HOME/.codex/config.toml" "$backup_dir/codex-config.toml"
fi
if [ -f "$HOME/.opencodex/config.json" ]; then
  cp -p "$HOME/.opencodex/config.json" "$backup_dir/opencodex-config.json"
fi
```

Установите инструменты и добавьте провайдера:

```bash
npm install -g @openai/codex @bitkyc08/opencodex@2.92.0
ocx provider add zv67 \
  --adapter openai-chat \
  --base-url http://127.0.0.1:18080/v1 \
  --auth-mode local \
  --default-model google-ai-mode \
  --model google-ai-mode --text-only \
  --allow-private-network
```

Флаг `--allow-private-network` разрешает OpenCodeX обратиться к локальному ZV67. API ZV67 по умолчанию работает без ключа на loopback. Если вы включили `ZV67_API_KEY`, настройте ключ у провайдера через интерактивный механизм своей версии OpenCodeX; не публикуйте его в командах или issue.

Добавьте модели:

```bash
ocx models add zv67 zv67-mock --display-name 'ZV67 Mock' --modalities text
ocx models add zv67 google-ai-mode --display-name 'Google AI Mode' --modalities text
ocx models add zv67 google-ai-mode-3.8-flash --display-name 'Google AI Mode 3.8 Flash' --modalities text
ocx models add zv67 google-ai-mode-4-argon --display-name 'Google AI Mode 4 Argon' --modalities text
ocx ensure
ocx sync
ocx models list
```

Проверка:

```bash
ocx provider test zv67 --model zv67-mock --yes
ocx provider test zv67 --model google-ai-mode --yes
codex exec -m zv67/google-ai-mode 'Назови столицу Франции одним словом'
```

Две последние команды отправляют реальный запрос Google и расходуют квоту. Для выбора другой модели используйте `zv67/google-ai-mode-3.8-flash` или `zv67/google-ai-mode-4-argon`. Шлюз возвращает HTTP 429, если Google сообщает об исчерпанном дневном лимите; успешная генерация этими двумя моделями в контрольных аккаунтах пока не подтверждена.

Если `zv67` уже зарегистрирован, посмотрите `ocx provider show zv67` и исправьте существующую запись. `--force` заменяет запись и не нужен для первой установки.

Для Desktop завершите Codex через `Cmd+Q` и откройте его после синхронизации. Изменение каталога не превращает текстовые модели в агентские: ZV67 не возвращает вызовы инструментов. Проверка текстового CLI и проверка выбора модели в интерфейсе Desktop являются разными проверками.

Удаление только провайдера:

```bash
ocx provider remove zv67
ocx sync
```

Эти команды меняют пользовательскую конфигурацию OpenCodeX. Удаление провайдера не удаляет данные ZV67.

## Другой порт или каталог данных

```bash
export ZV67_PORT=18081
export ZV67_DATA_DIR="$HOME/Library/Application Support/ZV67-Test"
./scripts/install.sh
./scripts/zv67 doctor
```

Параметры записываются в LaunchAgent. Для команд `scripts/zv67` сохраняйте эти переменные в текущем shell: без них скрипт проверяет стандартный порт и каталог. У провайдера OpenCodeX также замените порт в `--base-url`. Другой каталог данных создаёт отдельную базу и ключ; старые аккаунты автоматически не переносятся.

## Ключ клиентского API

По умолчанию API на loopback работает без ключа. Чтобы включить проверку ключа, введите его скрыто в терминале и повторите установку:

```bash
printf 'Новый API-ключ: '
IFS= read -r -s ZV67_API_KEY
printf '\n'
export ZV67_API_KEY
./scripts/install.sh
unset ZV67_API_KEY
```

Ключ передаётся через окружение и записывается в пользовательский LaunchAgent с правами `0600`. Он не попадает в Git. При обновлении установщик сохраняет ключ из прежнего plist, если переменная не задана. Для смены повторите ввод; для отключения выполните `ZV67_API_KEY='' ./scripts/install.sh`. Сохранённую копию plist считайте секретом.

После включения ключа обращения к `/v1/*` требуют `Authorization: Bearer <ключ>`. Проверки `/health` и `scripts/zv67 doctor` остаются доступны без него. У OpenCodeX также укажите ключ провайдера через механизм авторизации вашей версии.

## Управление сервисом

```bash
./scripts/zv67 status
./scripts/zv67 stop
./scripts/zv67 start
./scripts/zv67 restart
./scripts/zv67 logs
```

`start` загружает ранее остановленный LaunchAgent. Для уже запущенного сервиса используйте `restart`. Остановка не удаляет базу или cookies.

## Обновление и резервная копия

Сначала завершите активные запросы. Для стандартного каталога:

```bash
./scripts/zv67 stop
backup_dir="$HOME/zv67-data-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -m 700 "$backup_dir"
mkdir -m 700 "$backup_dir/data"
cp -pR "${ZV67_DATA_DIR:-$HOME/Library/Application Support/ZV67}/." "$backup_dir/data/"
cp -p "$HOME/Library/LaunchAgents/com.zv67.gateway.plist" "$backup_dir/gateway.plist"
git rev-parse HEAD > "$backup_dir/commit.txt"
git status --short
git pull --ff-only
./scripts/install.sh
./scripts/zv67 doctor
```

Сохраняйте базу и `master.key` вместе. Если есть ваши изменения в клоне, сначала сохраните их; не применяйте `reset --hard` ради обновления. Копия содержит также commit прежнего кода и LaunchAgent. Для собственного порта сохраните соответствующий `ZV67_PORT` в shell.

Для отката укажите фактическую папку резервной копии в первой строке. Из текущего клона создайте отдельный каталог с прежним кодом:

```bash
backup_dir="$HOME/zv67-data-backup-ДАТА-ВРЕМЯ"
rollback_dir="$HOME/Projects/zv67-rollback-$(date +%Y%m%d-%H%M%S)"
git worktree add --detach "$rollback_dir" "$(cat "$backup_dir/commit.txt")"
./scripts/zv67 stop || true
export ZV67_DATA_DIR="${ZV67_DATA_DIR:-$HOME/Library/Application Support/ZV67}"
mv "$ZV67_DATA_DIR" "${ZV67_DATA_DIR}.before-rollback-$(date +%Y%m%d-%H%M%S)"
mkdir -m 700 "$ZV67_DATA_DIR"
cp -pR "$backup_dir/data/." "$ZV67_DATA_DIR/"
cd "$rollback_dir"
uv venv --python 3.12 backend/.venv
uv pip install --python backend/.venv/bin/python -e './backend[dev]'
npm --prefix frontend ci
npm --prefix frontend run build
backend/.venv/bin/python - "$backup_dir/gateway.plist" "$rollback_dir" <<'PY'
import pathlib
import plistlib
import sys

backup, root = sys.argv[1:]
configuration = plistlib.loads(pathlib.Path(backup).read_bytes())
configuration["ProgramArguments"][0] = str(pathlib.Path(root, "backend/.venv/bin/python"))
configuration["WorkingDirectory"] = str(pathlib.Path(root, "backend"))
target = pathlib.Path.home() / "Library/LaunchAgents/com.zv67.gateway.plist"
target.touch(mode=0o600, exist_ok=True)
target.chmod(0o600)
with target.open("wb") as stream:
    plistlib.dump(configuration, stream, sort_keys=False)
PY
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.zv67.gateway.plist"
launchctl kickstart -k "gui/$(id -u)/com.zv67.gateway"
./scripts/zv67 doctor
```

Откат сохраняет переменные окружения из резервного plist, включая API-ключ, и меняет только пути к прежнему коду. Старый установщик не запускается: его версия может не поддерживать сохранение ключа. Для нестандартного порта и каталога данных используйте исходные значения из резервной копии.

Откат возвращает состояние данных на момент копии. Данные неудачного обновления сохраняются рядом в папке `.before-rollback-*`; текущий клон и его изменения тоже сохраняются. Если база содержит новые нужные записи, сначала отдельно решите их перенос. После отката LaunchAgent ссылается на `rollback_dir`, поэтому не удаляйте эту папку.

Чтобы отключить автозапуск, выполните `./scripts/zv67 stop` и удалите только `~/Library/LaunchAgents/com.zv67.gateway.plist`. Каталог данных удаляйте отдельно, только если он больше не нужен.

## Ручной запуск и разработка

Для работы без LaunchAgent остановите установленный сервис и из корня проекта выполните:

```bash
uv venv --python 3.12 backend/.venv
uv pip install --python backend/.venv/bin/python -e './backend[dev]'
npm --prefix frontend ci
npm --prefix frontend run build
cd backend
ZV67_MASTER_KEY_STORE=file \
ZV67_GOOGLE_AI_MODE_ENABLED=true \
ZV67_GOOGLE_BROWSER_HEADLESS=true \
.venv/bin/python -m uvicorn zv67.main:app --host 127.0.0.1 --port 18080
```

Для изолированной разработки задайте другой `ZV67_DATA_DIR`. Не запускайте две копии backend на одной базе. `ZV67_GOOGLE_AI_MODE_ENABLED=false` оставляет только mock. Playwright управляет установленным Chrome через CDP; отдельная команда `playwright install` для этого режима не требуется.

Проверки из корня клона:

```bash
(cd backend && .venv/bin/python -m pytest tests -q)
npm --prefix frontend run build
bash -n scripts/install.sh scripts/zv67
```

Для разработки панели используйте `npm --prefix frontend run dev`; Vite проксирует Management API на порт 18080.

## Диагностика

| Симптом | Что проверить |
|---|---|
| `Repository not found` | Доступ вашего GitHub-аккаунта и `gh auth status` |
| `missing required tool` | `command -v uv node npm`; PATH для Homebrew и Node.js |
| Неподходящая версия Node.js | `node --version`; установите 24 и проверьте PATH |
| Backend не стартует | `./scripts/zv67 logs`; совпадение путей клона в plist |
| `Operation not permitted` | Переместите клон в `~/Projects`, повторите установку |
| `Address already in use` | Выберите свободный `ZV67_PORT` либо остановите свою прежнюю копию |
| `Google Chrome was not found` | Chrome в `/Applications/Google Chrome.app` |
| 401 / аккаунт не авторизован | Обновите cookies и проверьте доступ к AI Mode в обычном браузере |
| 429 / дневной лимит | Используйте Auto или дождитесь восстановления квоты аккаунта |
| Модель не видна в Codex | `ocx models list`, `ocx sync`, полный перезапуск Desktop |
| Текст есть, инструменты не работают | Tool calling в ZV67 не реализован |

Перед отправкой диагностики уберите cookies, ключи, содержимое базы и конфиги с секретами. Для сообщения об ошибке обычно достаточно версии macOS/Node.js, команды и текста ошибки.

## Источники по инструментам

- uv: https://docs.astral.sh/uv/getting-started/installation/
- Требования Vite: https://vite.dev/guide/
- Codex CLI: https://developers.openai.com/codex/cli/reference/
- OpenCodeX: https://github.com/lidge-jun/opencodex

Фактические флаги OpenCodeX 2.92.0 сверены с `ocx provider add --help`, `ocx models add --help`, `ocx provider test --help`, `ocx provider remove --help`, `ocx sync --help` и `ocx ensure --help`. Параметр выбора модели Codex сверён с `codex exec --help` локального клиента.
