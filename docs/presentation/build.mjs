import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire('/Users/orfeev/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/');
const { createCanvas, GlobalFonts, loadImage } = require('@napi-rs/canvas');
const { PDFDocument } = require('pdf-lib');
const PptxGenJS = require('pptxgenjs');

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, '../..');

// Register fonts
GlobalFonts.registerFromPath(path.join(__dirname, 'fonts/RussoOne-Regular.ttf'), 'Russo One');
GlobalFonts.registerFromPath(path.join(__dirname, 'fonts/PTMono-Regular.ttf'), 'PT Mono');

console.log('Fonts registered:', {
  russoOne: GlobalFonts.has('Russo One'),
  ptMono: GlobalFonts.has('PT Mono'),
});

const WIDTH = 1440;
const HEIGHT = 2560;

const C = {
  bg: '#161A26',
  card: '#0C3F52',
  cardBorder: '#16536B',
  surfaceDark: '#083B4E',
  strip: '#0B5D73',
  orange: '#FF4001',
  cyan: '#4DDBFF',
  green: '#27C93F',
  red: '#FF5F56',
  yellow: '#FFBD2E',
  textPrimary: '#FFFFFF',
  textSecondary: '#E8EDF0',
  textMuted: '#8EA3B0',
  circuitLine: '#2C3648',
  circuitDot: '#0B5D73'
};

function drawCircuitBackground(ctx, w, h) {
  ctx.fillStyle = C.bg;
  ctx.fillRect(0, 0, w, h);

  ctx.save();
  ctx.strokeStyle = C.circuitLine;
  ctx.lineWidth = 2.5;
  ctx.globalAlpha = 0.22;

  const tracks = [
    [[40, 80], [180, 80], [240, 140], [240, 320]],
    [[100, 20], [100, 120], [160, 180], [360, 180]],
    [[20, 260], [140, 260], [200, 320], [200, 500]],
    [[w - 40, 100], [w - 200, 100], [w - 280, 180], [w - 280, 360]],
    [[w - 120, 40], [w - 120, 220], [w - 300, 400]],
    [[30, 800], [160, 800], [240, 880], [240, 1200]],
    [[50, 1300], [180, 1300], [260, 1380], [380, 1380]],
    [[w - 50, 900], [w - 180, 900], [w - 260, 980], [w - 260, 1240]],
    [[w - 30, 1400], [w - 200, 1400], [w - 300, 1500]],
    [[40, 1800], [160, 1800], [240, 1880], [240, 2200]],
    [[60, 2100], [200, 2100], [280, 2180], [280, 2480]],
    [[w - 40, 1900], [w - 180, 1900], [w - 260, 1980], [w - 260, 2300]],
    [[w - 80, 2200], [w - 220, 2200], [w - 320, 2300], [w - 320, 2500]],
  ];

  for (const track of tracks) {
    ctx.beginPath();
    ctx.moveTo(track[0][0], track[0][1]);
    for (let i = 1; i < track.length; i++) {
      ctx.lineTo(track[i][0], track[i][1]);
    }
    ctx.stroke();

    const last = track[track.length - 1];
    ctx.fillStyle = C.circuitDot;
    ctx.beginPath();
    ctx.arc(last[0], last[1], 5, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.restore();
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.arcTo(x + w, y, x + w, y + r, r);
  ctx.lineTo(x + w, y + h - r);
  ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
  ctx.lineTo(x + r, y + h);
  ctx.arcTo(x, y + h, x, y + h - r, r);
  ctx.lineTo(x, y + r);
  ctx.arcTo(x, y, x + r, y, r);
  ctx.closePath();
}

function drawCard(ctx, x, y, w, h, opt = {}) {
  const bg = opt.bg || C.card;
  const border = opt.border || C.cardBorder;
  const radius = opt.radius || 24;
  const shadow = opt.shadow !== false;

  ctx.save();
  if (shadow) {
    ctx.shadowColor = 'rgba(0, 0, 0, 0.45)';
    ctx.shadowBlur = 24;
    ctx.shadowOffsetY = 10;
  }
  ctx.fillStyle = bg;
  roundRect(ctx, x, y, w, h, radius);
  ctx.fill();

  ctx.shadowColor = 'transparent';
  if (border) {
    ctx.strokeStyle = border;
    ctx.lineWidth = opt.borderWidth || 2;
    ctx.stroke();
  }
  ctx.restore();
}

function drawPill(ctx, x, y, text, opt = {}) {
  const bg = opt.bg || C.orange;
  const fg = opt.fg || C.textPrimary;
  const fontSize = opt.fontSize || 24;
  const fontFam = opt.font || 'Russo One';
  const h = opt.height || 48;

  ctx.save();
  ctx.font = String(fontSize) + 'px "' + fontFam + '"';
  const textW = ctx.measureText(text).width;
  const padX = opt.padX || 28;
  const w = textW + padX * 2;
  const r = h / 2;

  ctx.fillStyle = bg;
  roundRect(ctx, x, y, w, h, r);
  ctx.fill();

  if (opt.border) {
    ctx.strokeStyle = opt.border;
    ctx.lineWidth = 2;
    ctx.stroke();
  }

  ctx.fillStyle = fg;
  ctx.textBaseline = 'middle';
  ctx.fillText(text, x + padX, y + h / 2 + 1);
  ctx.restore();
  return w;
}

function drawCheckBullet(ctx, x, y, title, subtitle, opt = {}) {
  ctx.save();
  const r = opt.radius || 18;
  ctx.fillStyle = opt.checkBg || C.orange;
  ctx.beginPath();
  ctx.arc(x + r, y + r, r, 0, Math.PI * 2);
  ctx.fill();

  ctx.strokeStyle = opt.checkFg || '#FFFFFF';
  ctx.lineWidth = 3.5;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.beginPath();
  ctx.moveTo(x + r - 6, y + r);
  ctx.lineTo(x + r - 1, y + r + 5);
  ctx.lineTo(x + r + 7, y + r - 5);
  ctx.stroke();

  const textX = x + r * 2 + 18;
  ctx.fillStyle = C.textPrimary;
  ctx.font = String(opt.titleSize || 28) + 'px "Russo One"';
  ctx.textBaseline = 'top';
  ctx.fillText(title, textX, y);

  if (subtitle) {
    ctx.fillStyle = C.textSecondary;
    ctx.font = String(opt.subSize || 22) + 'px "PT Mono"';
    ctx.fillText(subtitle, textX, y + (opt.subOffset || 36));
  }
  ctx.restore();
}

function drawHeader(ctx, tag, line1, line2, subtitle) {
  drawPill(ctx, 80, 110, tag, { bg: C.orange, fg: '#FFFFFF', fontSize: 24 });

  ctx.textBaseline = 'top';
  ctx.font = '72px "Russo One"';
  ctx.fillStyle = C.textPrimary;
  ctx.fillText(line1, 80, 185);

  if (line2) {
    ctx.fillStyle = C.orange;
    ctx.fillText(line2, 80, 265);
  }

  if (subtitle) {
    ctx.fillStyle = C.textSecondary;
    ctx.font = '26px "PT Mono"';
    ctx.fillText(subtitle, 80, 360);
  }
}

function drawCodeBox(ctx, x, y, w, h, code, opt = {}) {
  drawCard(ctx, x, y, w, h, { bg: C.surfaceDark, border: C.cardBorder, radius: 16 });
  ctx.save();
  ctx.fillStyle = opt.fg || C.cyan;
  ctx.font = String(opt.fontSize || 22) + 'px "PT Mono"';
  ctx.textBaseline = 'middle';
  ctx.fillText(code, x + 24, y + h / 2);
  ctx.restore();
}

function drawArrowDown(ctx, x, y, length = 32) {
  ctx.save();
  ctx.strokeStyle = C.orange;
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.lineTo(x, y + length);
  ctx.stroke();

  ctx.fillStyle = C.orange;
  ctx.beginPath();
  ctx.moveTo(x - 8, y + length);
  ctx.lineTo(x + 8, y + length);
  ctx.lineTo(x, y + length + 10);
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

// ----------------- SLIDE 1: COVER -----------------
async function renderSlide1() {
  const canvas = createCanvas(WIDTH, HEIGHT);
  const ctx = canvas.getContext('2d');
  drawCircuitBackground(ctx, WIDTH, HEIGHT);

  drawHeader(ctx, 'ШЛЮЗ АГЕНТА CODEX', 'ZV67: GOOGLE', 'AI MODE GATEWAY', 'Бесшовный доступ к Google AI Mode из Codex без API-ключей');

  const cardX = 80, cardY = 430, cardW = 1280, cardH = 880;
  drawCard(ctx, cardX, cardY, cardW, cardH, { bg: C.card, border: C.cardBorder, radius: 24 });

  // Browser top bar
  ctx.fillStyle = '#092B38';
  roundRect(ctx, cardX, cardY, cardW, 64, 24);
  ctx.fill();
  ctx.fillRect(cardX, cardY + 32, cardW, 32);

  const dotY = cardY + 32;
  ctx.fillStyle = C.red; ctx.beginPath(); ctx.arc(cardX + 36, dotY, 9, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = C.yellow; ctx.beginPath(); ctx.arc(cardX + 66, dotY, 9, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = C.green; ctx.beginPath(); ctx.arc(cardX + 96, dotY, 9, 0, Math.PI * 2); ctx.fill();

  ctx.fillStyle = '#061D26';
  roundRect(ctx, cardX + 150, cardY + 14, cardW - 300, 36, 18);
  ctx.fill();
  ctx.fillStyle = C.textSecondary;
  ctx.font = '20px "PT Mono"';
  ctx.textBaseline = 'middle';
  ctx.textAlign = 'center';
  ctx.fillText('http://localhost:18080/dashboard', cardX + cardW / 2, cardY + 32);
  ctx.textAlign = 'left';

  const imgPath = path.join(projectRoot, 'docs/screenshots/overview.png');
  const img = await loadImage(imgPath);
  const imgW = 1200;
  const imgH = 630;
  const imgX = cardX + (cardW - imgW) / 2;
  const imgY = cardY + 84;
  ctx.drawImage(img, imgX, imgY, imgW, imgH);

  const statusY = imgY + imgH + 24;
  ctx.fillStyle = C.green;
  ctx.beginPath();
  ctx.arc(cardX + 48, statusY + 14, 8, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = C.textSecondary;
  ctx.font = '22px "PT Mono"';
  ctx.textBaseline = 'middle';
  ctx.fillText('ШЛЮЗ АКТИВЕН  •  ХОСТ LOCALHOST:18080  •  СЕССИЯ ГОТОВА', cardX + 72, statusY + 14);

  const gridY1 = 1350, gridY2 = 1820, gridW = 620, gridH = 440;
  const col1X = 80, col2X = 740;

  // Grid 1
  drawCard(ctx, col1X, gridY1, gridW, gridH);
  drawPill(ctx, col1X + 32, gridY1 + 32, 'API :18080', { bg: C.strip, fontSize: 20, height: 42 });
  ctx.fillStyle = C.textPrimary;
  ctx.font = '32px "Russo One"';
  ctx.fillText('OPENAI API', col1X + 32, gridY1 + 120);
  ctx.font = '22px "PT Mono"';
  ctx.fillStyle = C.textSecondary;
  ctx.fillText('• Стандартный эндпоинт completions', col1X + 32, gridY1 + 180);
  ctx.fillText('• Потоковая передача через SSE', col1X + 32, gridY1 + 230);
  ctx.fillText('• Прозрачный роутер OpenCodeX', col1X + 32, gridY1 + 280);
  ctx.fillText('• Нулевые задержки вызова', col1X + 32, gridY1 + 330);

  // Grid 2
  drawCard(ctx, col2X, gridY1, gridW, gridH);
  drawPill(ctx, col2X + 32, gridY1 + 32, 'HEADLESS CDP', { bg: C.orange, fontSize: 20, height: 42 });
  ctx.fillStyle = C.textPrimary;
  ctx.font = '32px "Russo One"';
  ctx.fillText('БЕЗ ОКОН БРАУЗЕРА', col2X + 32, gridY1 + 120);
  ctx.font = '22px "PT Mono"';
  ctx.fillStyle = C.textSecondary;
  ctx.fillText('• Chrome в режиме --headless=new', col2X + 32, gridY1 + 180);
  ctx.fillText('• Управление через сокеты CDP', col2X + 32, gridY1 + 230);
  ctx.fillText('• Фокус окон и мыши не перебивается', col2X + 32, gridY1 + 280);
  ctx.fillText('• Фоновое исполнение в macOS', col2X + 32, gridY1 + 330);

  // Grid 3
  drawCard(ctx, col1X, gridY2, gridW, gridH);
  drawPill(ctx, col1X + 32, gridY2 + 32, 'MULTI-ACCOUNT', { bg: C.strip, fontSize: 20, height: 42 });
  ctx.fillStyle = C.textPrimary;
  ctx.font = '32px "Russo One"';
  ctx.fillText('МУЛЬТИАККАУНТЫ', col1X + 32, gridY2 + 120);
  ctx.font = '22px "PT Mono"';
  ctx.fillStyle = C.textSecondary;
  ctx.fillText('• Изоляция профилей Chrome', col1X + 32, gridY2 + 180);
  ctx.fillText('• Раздельные cookies и cache', col1X + 32, gridY2 + 230);
  ctx.fillText('• Балансировка и ротация', col1X + 32, gridY2 + 280);
  ctx.fillText('• Обход персональных квот', col1X + 32, gridY2 + 330);

  // Grid 4
  drawCard(ctx, col2X, gridY2, gridW, gridH);
  drawPill(ctx, col2X + 32, gridY2 + 32, 'FERNET 0600', { bg: C.cyan, fg: C.card, fontSize: 20, height: 42 });
  ctx.fillStyle = C.textPrimary;
  ctx.font = '32px "Russo One"';
  ctx.fillText('ШИФРОВАНИЕ КУК', col2X + 32, gridY2 + 120);
  ctx.font = '22px "PT Mono"';
  ctx.fillStyle = C.textSecondary;
  ctx.fillText('• Симметричный шифр Fernet (AES)', col2X + 32, gridY2 + 180);
  ctx.fillText('• Права 0600 на ключ в ~/.zv67/', col2X + 32, gridY2 + 230);
  ctx.fillText('• Куки расшифровываются в RAM', col2X + 32, gridY2 + 280);
  ctx.fillText('• Полное исключение из Git', col2X + 32, gridY2 + 330);

  drawCard(ctx, 80, 2300, 1280, 110, { bg: C.surfaceDark, border: C.strip, radius: 20 });
  ctx.fillStyle = C.textSecondary;
  ctx.font = '24px "PT Mono"';
  ctx.textAlign = 'center';
  ctx.fillText('ПРИВАТНЫЙ РЕПОЗИТОРИЙ  •  РАСПРОСТРАНЕНИЕ СТРОГО ПО ПРИГЛАШЕНИЮ', 80 + 1280 / 2, 2358);
  ctx.textAlign = 'left';

  return canvas.toBuffer('image/png');
}

// ----------------- SLIDE 2: ARCHITECTURE -----------------
async function renderSlide2() {
  const canvas = createCanvas(WIDTH, HEIGHT);
  const ctx = canvas.getContext('2d');
  drawCircuitBackground(ctx, WIDTH, HEIGHT);

  drawHeader(ctx, 'АРХИТЕКТУРА И ДАТАФЛОУ', 'ПОЛНЫЙ ПАЙПЛАЙН', 'ОБРАБОТКИ ЗАПРОСА', 'Сквозной маршрут от вызова модели в Codex до потокового ответа');

  const cardW = 1280, cardX = 80;

  // Step 1
  drawCard(ctx, cardX, 430, cardW, 220);
  drawPill(ctx, cardX + 32, 455, 'ШАГ 1 • КЛИЕНТ', { bg: C.strip, fontSize: 20, height: 38 });
  ctx.fillStyle = C.textPrimary; ctx.font = '30px "Russo One"';
  ctx.fillText('CODEX DESKTOP / CLI', cardX + 32, 525);
  ctx.fillStyle = C.textSecondary; ctx.font = '22px "PT Mono"';
  ctx.fillText('Пользователь выбирает модель zv67/*. Клиент отправляет стандартный JSON-запрос', cardX + 32, 570);
  ctx.fillText('нативного формата chat/completions с системным промптом и списком tools.', cardX + 32, 605);

  drawArrowDown(ctx, cardX + cardW / 2, 660, 25);

  // Step 2
  drawCard(ctx, cardX, 695, cardW, 220);
  drawPill(ctx, cardX + 32, 720, 'ШАГ 2 • РОУТЕР', { bg: C.strip, fontSize: 20, height: 38 });
  ctx.fillStyle = C.textPrimary; ctx.font = '30px "Russo One"';
  ctx.fillText('OPENCODEX PROXY', cardX + 32, 790);
  ctx.fillStyle = C.textSecondary; ctx.font = '22px "PT Mono"';
  ctx.fillText('Распознаёт префикс zv67/ и перенаправляет трафик на локальный эндпоинт', cardX + 32, 835);
  ctx.fillText('http://localhost:18080/v1 без изменения структуры сообщений диалога.', cardX + 32, 870);

  drawArrowDown(ctx, cardX + cardW / 2, 925, 25);

  // Step 3 (Highlight)
  drawCard(ctx, cardX, 960, cardW, 270, { border: C.orange, borderWidth: 3 });
  drawPill(ctx, cardX + 32, 985, 'ШАГ 3 • ЯДРО ШЛЮЗА (КЛЮЧЕВОЙ УЗЕЛ)', { bg: C.orange, fontSize: 20, height: 38 });
  ctx.fillStyle = C.textPrimary; ctx.font = '30px "Russo One"';
  ctx.fillText('ZV67 GATEWAY (FASTAPI :18080)', cardX + 32, 1055);
  ctx.fillStyle = C.textSecondary; ctx.font = '22px "PT Mono"';
  ctx.fillText('Перехватывает и нейтрализует tools (предотвращая ошибку 400 у веб-моделей).', cardX + 32, 1100);
  ctx.fillText('Выбирает активный Google-аккаунт, расшифровывает куки в RAM и управляет пулом.', cardX + 32, 1135);
  ctx.fillText('Логирует тайминги, метрики и ведёт учёт использования в базе SQLite.', cardX + 32, 1170);

  drawArrowDown(ctx, cardX + cardW / 2, 1240, 25);

  // Step 4
  drawCard(ctx, cardX, 1275, cardW, 220);
  drawPill(ctx, cardX + 32, 1300, 'ШАГ 4 • БРАУЗЕР', { bg: C.strip, fontSize: 20, height: 38 });
  ctx.fillStyle = C.textPrimary; ctx.font = '30px "Russo One"';
  ctx.fillText('CHROME CDP SESSION MANAGER', cardX + 32, 1370);
  ctx.fillStyle = C.textSecondary; ctx.font = '22px "PT Mono"';
  ctx.fillText('Управляет процессом Google Chrome с флагом --headless=new через сокеты CDP.', cardX + 32, 1415);
  ctx.fillText('Изолирует профиль в отдельной папке и эмулирует действия авторизованного юзера.', cardX + 32, 1450);

  drawArrowDown(ctx, cardX + cardW / 2, 1505, 25);

  // Step 5
  drawCard(ctx, cardX, 1540, cardW, 220);
  drawPill(ctx, cardX + 32, 1565, 'ШАГ 5 • ИСТОЧНИК', { bg: C.strip, fontSize: 20, height: 38 });
  ctx.fillStyle = C.textPrimary; ctx.font = '30px "Russo One"';
  ctx.fillText('GOOGLE AI MODE WEB (SSE)', cardX + 32, 1635);
  ctx.fillStyle = C.textSecondary; ctx.font = '22px "PT Mono"';
  ctx.fillText('Выполняет веб-поиск и синтез ответа в интерфейсе Google AI Mode.', cardX + 32, 1680);
  ctx.fillText('Транслирует Server-Sent Events обратно в шлюз, который стримит токены в Codex.', cardX + 32, 1715);

  // Bottom Summary Box
  drawCard(ctx, cardX, 1800, cardW, 610, { bg: C.surfaceDark, border: C.strip, radius: 24 });
  ctx.fillStyle = C.textPrimary;
  ctx.font = '34px "Russo One"';
  ctx.fillText('ПРЕИМУЩЕСТВА СВЯЗКИ ДЛЯ РАЗРАБОТЧИКА:', cardX + 40, 1860);

  drawCheckBullet(ctx, cardX + 40, 1920, 'ПРОЗРАЧНОСТЬ ДЛЯ CODEX', 'Для Codex шлюз выглядит как официальный OpenAI-провайдер с поддержкой стриминга.');
  drawCheckBullet(ctx, cardX + 40, 2030, 'ЗАЩИТА ОТ БЛОКИРОВОК', 'Google видит естественные сетевые запросы живого браузера без признаков бота.');
  drawCheckBullet(ctx, cardX + 40, 2140, 'ЛОКАЛЬНЫЙ КОНТРОЛЬ', 'Все сокеты и сессии крутятся на вашей машине localhost без внешних посредников.');
  drawCheckBullet(ctx, cardX + 40, 2250, 'АВТОНОМНОСТЬ', 'Фоновый демон launchd гарантирует доступность сервиса при каждом старте системы.');

  return canvas.toBuffer('image/png');
}

// ----------------- SLIDE 3: SECURITY & ACCOUNTS -----------------
async function renderSlide3() {
  const canvas = createCanvas(WIDTH, HEIGHT);
  const ctx = canvas.getContext('2d');
  drawCircuitBackground(ctx, WIDTH, HEIGHT);

  drawHeader(ctx, 'БЕЗОПАСНОСТЬ И УЧЁТНЫЕ ДАННЫЕ', 'ИЗОЛЯЦИЯ И ЗАЩИТА', 'GOOGLE-АККАУНТОВ', 'Гибкий импорт кук, симметричное шифрование и раздельные профили Chrome');

  const cardW = 1280, cardX = 80;

  // Card 1: Import formats
  drawCard(ctx, cardX, 430, cardW, 560);
  drawPill(ctx, cardX + 36, 460, 'УНИВЕРСАЛЬНЫЙ ИМПОРТ', { bg: C.strip, fontSize: 20, height: 40 });
  ctx.fillStyle = C.textPrimary; ctx.font = '32px "Russo One"';
  ctx.fillText('ПОДДЕРЖКА ВСЕХ ФОРМАТОВ КУК', cardX + 36, 535);

  drawCheckBullet(ctx, cardX + 36, 590, 'Cookie-Editor JSON', 'Нативный экспорт массива объектов [{"domain": ".google.com", "name": "SID", ...}]');
  drawCheckBullet(ctx, cardX + 36, 680, 'Netscape cookies.txt', 'Стандартный табулированный текстовый формат wget / curl / browser extensions');
  drawCheckBullet(ctx, cardX + 36, 770, 'Сырая строка Header', 'Прямая строка заголовка запроса вида Cookie: SID=...; HSID=...; SSID=...');

  drawCodeBox(ctx, cardX + 36, 880, cardW - 72, 70, '✓ Автоматическое распознавание формата при вставке в веб-панели', { fg: C.cyan, fontSize: 21 });

  // Card 2: Encryption
  drawCard(ctx, cardX, 1020, cardW, 560);
  drawPill(ctx, cardX + 36, 1050, 'КРИПТОГРАФИЧЕСКАЯ ЗАЩИТА', { bg: C.orange, fontSize: 20, height: 40 });
  ctx.fillStyle = C.textPrimary; ctx.font = '32px "Russo One"';
  ctx.fillText('ШИФРОВАНИЕ КУК НА ДИСКЕ', cardX + 36, 1125);

  drawCheckBullet(ctx, cardX + 36, 1180, 'Симметричный шифр Fernet', 'Стандарт AES-128-CBC с аутентификацией сообщений HMAC-SHA256');
  drawCheckBullet(ctx, cardX + 36, 1270, 'Права доступа 0600', 'Ключ генерируется в ~/.zv67/key.bin и доступен только текущему пользователю');
  drawCheckBullet(ctx, cardX + 36, 1360, 'Безопасность репозитория', 'Файл базы credentials.db и ключи намертво исключены из Git через .gitignore');

  drawCodeBox(ctx, cardX + 36, 1470, cardW - 72, 70, '✓ Расшифровка происходит исключительно в RAM при запуске сессии CDP', { fg: C.cyan, fontSize: 21 });

  // Card 3: Chrome Profile Isolation
  drawCard(ctx, cardX, 1610, cardW, 560);
  drawPill(ctx, cardX + 36, 1640, 'РАЗДЕЛЬНЫЕ СРЕДЫ CHROME', { bg: C.cyan, fg: C.card, fontSize: 20, height: 40 });
  ctx.fillStyle = C.textPrimary; ctx.font = '32px "Russo One"';
  ctx.fillText('ПОЛНАЯ ИЗОЛЯЦИЯ ПРОФИЛЕЙ', cardX + 36, 1715);

  drawCheckBullet(ctx, cardX + 36, 1770, 'Отдельные User Data Dir', 'Каждый добавленный аккаунт получает свою изолированную директорию профиля');
  drawCheckBullet(ctx, cardX + 36, 1860, 'Независимый кэш и хранилище', 'Исключены коллизии авторизации, перемешивание cookie jar и сброс сессий');
  drawCheckBullet(ctx, cardX + 36, 1950, 'Параллельные сессии', 'Шлюз независимо балансирует входящие запросы между доступными профилями');

  drawCodeBox(ctx, cardX + 36, 2060, cardW - 72, 70, '✓ Сбои или лимиты одного аккаунта никак не затрагивают остальные', { fg: C.cyan, fontSize: 21 });

  // Bottom Notice
  drawCard(ctx, cardX, 2200, cardW, 220, { bg: C.surfaceDark, border: C.strip, radius: 20 });
  ctx.fillStyle = C.textPrimary; ctx.font = '28px "Russo One"';
  ctx.fillText('СТРОГО ЛОКАЛЬНЫЙ КОНТУР БЕЗОПАСНОСТИ', cardX + 36, 2250);
  ctx.fillStyle = C.textSecondary; ctx.font = '22px "PT Mono"';
  ctx.fillText('Все учётные записи, зашифрованные куки и сокеты управления браузером', cardX + 36, 2295);
  ctx.fillText('остаются внутри вашей системы macOS. Никакой телеметрии и утечек в сеть.', cardX + 36, 2335);
  ctx.fillText('Каталог данных: ~/.zv67/ (credentials.db, logs, sessions, key.bin).', cardX + 36, 2375);

  return canvas.toBuffer('image/png');
}

// ----------------- SLIDE 4: MODELS & VERIFICATION -----------------
async function renderSlide4() {
  const canvas = createCanvas(WIDTH, HEIGHT);
  const ctx = canvas.getContext('2d');
  drawCircuitBackground(ctx, WIDTH, HEIGHT);

  drawHeader(ctx, 'МОДЕЛИ И СТАТУС ТЕСТОВ', 'СТАТУС МОДЕЛЕЙ', 'И ПРОВЕРКА В CODEX', 'Тестовая матрица, живая работа с Google и нейтрализация ошибок');

  const cardW = 1280, cardX = 80;

  // Model 1: zv67-mock
  drawCard(ctx, cardX, 430, cardW, 360);
  drawPill(ctx, cardX + 36, 455, 'ZV67 / ZV67-MOCK', { bg: C.strip, fontSize: 22, height: 42 });
  drawPill(ctx, cardX + cardW - 220, 455, '100% PASS', { bg: C.cyan, fg: C.card, fontSize: 20, height: 42 });
  ctx.fillStyle = C.textSecondary; ctx.font = '22px "PT Mono"';
  ctx.fillText('Локальный заглушечный провайдер для тестирования конвейера без интернета', cardX + 36, 525);
  drawCheckBullet(ctx, cardX + 36, 565, '68 ТЕСТОВ БЭКЕНДА ПРОЙДЕНО', 'Полный набор pytest tests/ подтверждает корректность роутинга и БД');
  drawCheckBullet(ctx, cardX + 36, 640, 'СКВОЗНАЯ ИНТЕГРАЦИЯ С CODEX', 'Проверена связка Codex Desktop → OpenCodeX → ZV67 FastAPI');
  drawCheckBullet(ctx, cardX + 36, 715, 'МГНОВЕННЫЙ ЭХО-ОТВЕТ', 'Идеален для диагностики портов, демона launchd и проверки доступности');

  // Model 2: google-ai-mode
  drawCard(ctx, cardX, 815, cardW, 360, { border: C.green, borderWidth: 2 });
  drawPill(ctx, cardX + 36, 840, 'GOOGLE-AI-MODE', { bg: C.strip, fontSize: 22, height: 42 });
  drawPill(ctx, cardX + cardW - 270, 840, 'LIVE: РАБОТАЕТ', { bg: C.green, fg: '#0F1523', fontSize: 20, height: 42 });
  ctx.fillStyle = C.textSecondary; ctx.font = '22px "PT Mono"';
  ctx.fillText('Основная модель Google AI Mode через живую сессию Chrome CDP', cardX + 36, 910);
  drawCheckBullet(ctx, cardX + 36, 950, 'АВТОРИЗАЦИЯ ПО КУКАМ ПРИНЯТА', 'Успешно проверены форматы Cookie-Editor JSON и Netscape cookies.txt');
  drawCheckBullet(ctx, cardX + 36, 1025, 'ПОЛНЫЙ ДИАЛОГ В ИНТЕРФЕЙСЕ CODEX', 'Запрос успешно отправлен, ответ принят и отображён в окне чата');
  drawCheckBullet(ctx, cardX + 36, 1100, 'ФОНОВАЯ РАБОТА БЕЗ ОКОН', 'Chrome работает в --headless=new и не перебивает фокус в системе');

  // Model 3: 3.8 Flash & 4 Argon
  drawCard(ctx, cardX, 1200, cardW, 360);
  drawPill(ctx, cardX + 36, 1225, '3.8 FLASH & 4 ARGON', { bg: C.strip, fontSize: 22, height: 42 });
  drawPill(ctx, cardX + cardW - 290, 1225, 'ГОТОВО В UI / 429', { bg: C.orange, fontSize: 20, height: 42 });
  ctx.fillStyle = C.textSecondary; ctx.font = '22px "PT Mono"';
  ctx.fillText('Селектор целевых моделей Google AI Mode через веб-интерфейс', cardX + 36, 1295);
  drawCheckBullet(ctx, cardX + 36, 1335, 'ПЕРЕКЛЮЧАТЕЛЬ МОДЕЛЕЙ В АДМИНКЕ', 'Реализован выбор моделей и маппинг внутренних параметров Google');
  drawCheckBullet(ctx, cardX + 36, 1410, 'ПРОБРОС В КАТАЛОГ OPENCODEX', 'Модели автоматически появляются в общем списке моделей Codex');
  drawCheckBullet(ctx, cardX + 36, 1485, 'ОГРАНИЧЕНИЕ КВОТЫ GOOGLE (429)', 'На тестовых аккаунтах веб-интерфейс Google возвращает квоту 429');

  // Highlight Box: Tool Calling Neutralization
  drawCard(ctx, cardX, 1590, cardW, 830, { border: C.orange, borderWidth: 3 });
  drawPill(ctx, cardX + 36, 1620, 'КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ ДЛЯ CODEX', { bg: C.orange, fontSize: 20, height: 40 });
  ctx.fillStyle = C.textPrimary; ctx.font = '34px "Russo One"';
  ctx.fillText('НЕЙТРАЛИЗАЦИЯ ОШИБКИ TOOL CALLING (400)', cardX + 36, 1700);

  // Problem Box
  drawCard(ctx, cardX + 36, 1735, cardW - 72, 300, { bg: C.surfaceDark, border: C.cardBorder, radius: 18 });
  drawPill(ctx, cardX + 60, 1755, 'ПРОБЛЕМА', { bg: C.red, fontSize: 18, height: 34 });
  ctx.fillStyle = C.textSecondary; ctx.font = '21px "PT Mono"';
  ctx.fillText('Codex Desktop автоматически добавляет в каждый запрос системные tools.', cardX + 60, 1815);
  ctx.fillText('При передаче такого запроса модель выдавала фатальную ошибку 400:', cardX + 60, 1855);
  ctx.fillStyle = C.orange;
  ctx.fillText('{"error": {"message": "tool calling is not implemented for this model"}}', cardX + 60, 1905);
  ctx.fillStyle = C.textMuted;
  ctx.fillText('В результате работа с моделью полностью блокировалась в интерфейсе Codex.', cardX + 60, 1955);

  // Solution Box
  drawCard(ctx, cardX + 36, 2060, cardW - 72, 330, { bg: C.surfaceDark, border: C.strip, radius: 18 });
  drawPill(ctx, cardX + 60, 2080, 'РЕШЕНИЕ ZV67', { bg: C.green, fg: '#0F1523', fontSize: 18, height: 34 });
  ctx.fillStyle = C.textSecondary; ctx.font = '21px "PT Mono"';
  ctx.fillText('Шлюз ZV67 перехватывает входящий массив tools и автоматически нормализует', cardX + 60, 2140);
  ctx.fillText('тело запроса перед отправкой в веб-интерфейс Google AI Mode.', cardX + 60, 2180);
  ctx.fillText('Codex получает чистый потоковый текстовый ответ без ошибок 400.', cardX + 60, 2220);
  ctx.fillStyle = C.cyan;
  ctx.fillText('✓ Полная прозрачность и стабильность вызова из десктопного приложения', cardX + 60, 2280);
  ctx.fillText('✓ Совместимо со всеми версиями Codex Desktop и OpenCodeX', cardX + 60, 2320);

  return canvas.toBuffer('image/png');
}

// ----------------- SLIDE 5: HEADLESS & LAUNCHD -----------------
async function renderSlide5() {
  const canvas = createCanvas(WIDTH, HEIGHT);
  const ctx = canvas.getContext('2d');
  drawCircuitBackground(ctx, WIDTH, HEIGHT);

  drawHeader(ctx, 'СИСТЕМНАЯ ИНТЕГРАЦИЯ', 'ЧИСТЫЙ HEADLESS', 'И СЕРВИС LAUNCHD', 'Фоновое исполнение процессов и автоматическое управление в macOS');

  const cardW = 1280, cardX = 80;

  // Feature 1
  drawCard(ctx, cardX, 430, cardW, 560);
  drawPill(ctx, cardX + 36, 460, 'РЕЖИМ БРАУЗЕРА', { bg: C.strip, fontSize: 20, height: 40 });
  ctx.fillStyle = C.textPrimary; ctx.font = '32px "Russo One"';
  ctx.fillText('CHROME --HEADLESS=NEW', cardX + 36, 535);

  drawCheckBullet(ctx, cardX + 36, 590, 'Никаких всплывающих окон', 'Браузер запускается в современном нативном headless-режиме Chromium');
  drawCheckBullet(ctx, cardX + 36, 680, 'Фокус ввода не сбивается', 'Вы можете спокойно писать код и печатать в терминале без прерываний');
  drawCheckBullet(ctx, cardX + 36, 770, 'Управление по сокету CDP', 'Шлюз управляет сессией через Chrome DevTools Protocol в фоне');

  drawCodeBox(ctx, cardX + 36, 880, cardW - 72, 70, 'google-chrome --headless=new --remote-debugging-port=0 --disable-gpu', { fg: C.cyan, fontSize: 20 });

  // Feature 2
  drawCard(ctx, cardX, 1020, cardW, 560);
  drawPill(ctx, cardX + 36, 1050, 'СИСТЕМНЫЙ ДЕМОН', { bg: C.orange, fontSize: 20, height: 40 });
  ctx.fillStyle = C.textPrimary; ctx.font = '32px "Russo One"';
  ctx.fillText('ДЕМОН MACOS LAUNCHD', cardX + 36, 1125);

  drawCheckBullet(ctx, cardX + 36, 1180, 'Автозапуск при старте системы', 'Служба com.zv67.gateway запускается при входе пользователя');
  drawCheckBullet(ctx, cardX + 36, 1270, 'KeepAlive восстановление', 'Система автоматически поднимает шлюз при аварийном завершении');
  drawCheckBullet(ctx, cardX + 36, 1360, 'Ротация логов в ~/.zv67/logs', 'Консольный вывод и ошибки пишутся в выделенные файлы журналов');

  drawCodeBox(ctx, cardX + 36, 1470, cardW - 72, 70, 'launchctl load ~/Library/LaunchAgents/com.zv67.gateway.plist', { fg: C.cyan, fontSize: 20 });

  // Feature 3
  drawCard(ctx, cardX, 1610, cardW, 560);
  drawPill(ctx, cardX + 36, 1640, 'СИНХРОНИЗАЦИЯ МОДЕЛЕЙ', { bg: C.cyan, fg: C.card, fontSize: 20, height: 40 });
  ctx.fillStyle = C.textPrimary; ctx.font = '32px "Russo One"';
  ctx.fillText('АВТОМАТИЧЕСКИЙ OCX SYNC', cardX + 36, 1715);

  drawCheckBullet(ctx, cardX + 36, 1770, 'Интеграция с OpenCodeX', 'Команда scripts/zv67 ocx-sync прописывает провайдер в конфиг OCX');
  drawCheckBullet(ctx, cardX + 36, 1860, 'Модели сразу в меню Codex', 'Все зарегистрированные модели zv67/* мгновенно появляются в списке');
  drawCheckBullet(ctx, cardX + 36, 1950, 'Мягкая перезагрузка демона', 'Отправка сигнала SIGHUP серверу OpenCodeX без прерывания сессий');

  drawCodeBox(ctx, cardX + 36, 2060, cardW - 72, 70, './scripts/zv67 ocx-sync && killall -HUP opencode-server', { fg: C.cyan, fontSize: 20 });

  // Bottom Status
  drawCard(ctx, cardX, 2200, cardW, 220, { bg: C.surfaceDark, border: C.strip, radius: 20 });
  ctx.fillStyle = C.textPrimary; ctx.font = '28px "Russo One"';
  ctx.fillText('ТИХАЯ ФОНОВАЯ СЛУЖБА', cardX + 36, 2250);
  ctx.fillStyle = C.textSecondary; ctx.font = '22px "PT Mono"';
  ctx.fillText('После однократной настройки проект не требует внимания.', cardX + 36, 2295);
  ctx.fillText('Шлюз стабильно обрабатывает запросы, пока вы работаете в кодовой базе.', cardX + 36, 2335);
  ctx.fillText('Управление процессами осуществляется через одну утилиту ./scripts/zv67.', cardX + 36, 2375);

  return canvas.toBuffer('image/png');
}

// ----------------- SLIDE 6: QUICK START & CLI -----------------
async function renderSlide6() {
  const canvas = createCanvas(WIDTH, HEIGHT);
  const ctx = canvas.getContext('2d');
  drawCircuitBackground(ctx, WIDTH, HEIGHT);

  drawHeader(ctx, 'РАЗВЁРТЫВАНИЕ', 'БЫСТРЫЙ СТАРТ', 'И КОМАНДЫ CLI', 'Пошаговая установка на Mac и единый инструмент управления проектом');

  const cardW = 1280, cardX = 80;

  // Setup Steps
  drawCard(ctx, cardX, 430, cardW, 710);
  ctx.fillStyle = C.textPrimary; ctx.font = '32px "Russo One"';
  ctx.fillText('ПОШАГОВЫЙ ПЛАН УСТАНОВКИ', cardX + 36, 485);

  // Step 1
  drawPill(ctx, cardX + 36, 525, 'ШАГ 1', { bg: C.orange, fontSize: 18, height: 36 });
  ctx.fillStyle = C.textPrimary; ctx.font = '26px "Russo One"';
  ctx.fillText('КЛОНИРОВАНИЕ И ЗАПУСК ИНСТАЛЛЯТОРА', cardX + 130, 550);
  drawCodeBox(ctx, cardX + 36, 580, cardW - 72, 60, 'git clone <repo-url> && cd zv67 && ./scripts/install.sh', { fg: C.cyan, fontSize: 20 });
  ctx.fillStyle = C.textSecondary; ctx.font = '20px "PT Mono"';
  ctx.fillText('Скрипт проверяет зависимости (uv, Node 24, Chrome), создаёт venv и настраивает launchd.', cardX + 36, 665);

  // Step 2
  drawPill(ctx, cardX + 36, 705, 'ШАГ 2', { bg: C.orange, fontSize: 18, height: 36 });
  ctx.fillStyle = C.textPrimary; ctx.font = '26px "Russo One"';
  ctx.fillText('ДОБАВЛЕНИЕ УЧЁТНЫХ ДАННЫХ В ВЕБ-ПАНЕЛИ', cardX + 130, 730);
  drawCodeBox(ctx, cardX + 36, 760, cardW - 72, 60, 'open http://localhost:18080', { fg: C.cyan, fontSize: 20 });
  ctx.fillStyle = C.textSecondary; ctx.font = '20px "PT Mono"';
  ctx.fillText('Вставьте экспортированные куки (Cookie-Editor JSON / Netscape) и нажмите «Сохранить».', cardX + 36, 845);

  // Step 3
  drawPill(ctx, cardX + 36, 885, 'ШАГ 3', { bg: C.orange, fontSize: 18, height: 36 });
  ctx.fillStyle = C.textPrimary; ctx.font = '26px "Russo One"';
  ctx.fillText('ВЫБОР МОДЕЛИ В ИНТЕРФЕЙСЕ CODEX', cardX + 130, 910);
  drawCodeBox(ctx, cardX + 36, 940, cardW - 72, 60, 'Модель: zv67/google-ai-mode  (или zv67/zv67-mock для теста)', { fg: C.cyan, fontSize: 20 });
  ctx.fillStyle = C.textSecondary; ctx.font = '20px "PT Mono"';
  ctx.fillText('Откройте меню моделей Codex, выберите zv67/google-ai-mode и начинайте диалог.', cardX + 36, 1025);
  ctx.fillText('Шлюз автоматически передаст запрос в AI Mode и вернёт потоковый ответ.', cardX + 36, 1060);

  // CLI Cheatsheet
  drawCard(ctx, cardX, 1170, cardW, 760);
  ctx.fillStyle = C.textPrimary; ctx.font = '32px "Russo One"';
  ctx.fillText('ЕДИНАЯ УТИЛИТА УПРАВЛЕНИЯ SCRIPTS/ZV67', cardX + 36, 1225);

  const cmds = [
    ['./scripts/zv67 status', 'Отображает статус шлюза, порт 18080, launchd и процессы Chrome'],
    ['./scripts/zv67 doctor', 'Полная диагностика: зависимости, права 0600, порты и сокеты CDP'],
    ['./scripts/zv67 restart', 'Перезапускает фоновый демон шлюза через системный launchctl'],
    ['./scripts/zv67 logs -f', 'Выводит журнал запросов и событий шлюза в режиме реального времени'],
    ['./scripts/zv67 ocx-sync', 'Синхронизирует модели с OpenCodeX и обновляет каталог моделей']
  ];

  for (let i = 0; i < cmds.length; i++) {
    const cy = 1260 + i * 115;
    drawCodeBox(ctx, cardX + 36, cy, 420, 52, cmds[i][0], { fg: C.cyan, fontSize: 20 });
    ctx.fillStyle = C.textSecondary; ctx.font = '21px "PT Mono"';
    ctx.fillText(cmds[i][1], cardX + 480, cy + 32);
  }

  drawCodeBox(ctx, cardX + 36, 1840, cardW - 72, 60, 'Утилита доступна из корня проекта: ./scripts/zv67 [команда]', { fg: C.textSecondary, fontSize: 20 });

  // Bottom Access Card
  drawCard(ctx, cardX, 1960, cardW, 480, { border: C.orange, borderWidth: 3 });
  drawPill(ctx, cardX + 36, 1990, 'ПРАВИЛА ДОСТУПА', { bg: C.orange, fontSize: 20, height: 40 });
  ctx.fillStyle = C.textPrimary; ctx.font = '34px "Russo One"';
  ctx.fillText('ПРИВАТНЫЙ РЕПОЗИТОРИЙ GITHUB', cardX + 36, 2075);

  drawCheckBullet(ctx, cardX + 36, 2130, 'ДОСТУП СТРОГО ПО ПРИГЛАШЕНИЮ', 'Репозиторий закрыт от публичного просмотра. Доступ выдается индивидуально.');
  drawCheckBullet(ctx, cardX + 36, 2220, 'ИЗОЛЯЦИЯ УЧЁТНЫХ ДАННЫХ', 'Куки и токены хранятся строго локально на машине каждого пользователя.');
  drawCheckBullet(ctx, cardX + 36, 2310, 'БЕЗОПАСНОСТЬ СЕРВЕРОВ', 'Никакие общие сервера или третьи лица не имеют доступа к вашим сессиям.');

  drawCodeBox(ctx, cardX + 36, 2380, cardW - 72, 50, 'https://github.com/zverror/zv67-google-ai-mode-codex-bridge', { fg: C.cyan, fontSize: 22 });

  return canvas.toBuffer('image/png');
}

// ----------------- MAIN BUILD FUNCTION -----------------
async function main() {
  console.log('Starting presentation build...');

  const outputDir = path.join(projectRoot, 'output/pdf');
  const slidesDir = path.join(outputDir, 'slides');
  fs.mkdirSync(slidesDir, { recursive: true });

  const slides = [
    { name: 'slide_01.png', render: renderSlide1 },
    { name: 'slide_02.png', render: renderSlide2 },
    { name: 'slide_03.png', render: renderSlide3 },
    { name: 'slide_04.png', render: renderSlide4 },
    { name: 'slide_05.png', render: renderSlide5 },
    { name: 'slide_06.png', render: renderSlide6 },
  ];

  const pngBuffers = [];
  for (let i = 0; i < slides.length; i++) {
    console.log('Rendering ' + slides[i].name + '...');
    const buf = await slides[i].render();
    const filePath = path.join(slidesDir, slides[i].name);
    fs.writeFileSync(filePath, buf);
    pngBuffers.push(buf);
    console.log('Saved ' + filePath + ' (' + buf.length + ' bytes)');
  }

  // Create PDF
  console.log('Generating PDF zv67-project.pdf...');
  const pdfDoc = await PDFDocument.create();
  for (const buf of pngBuffers) {
    const pngImage = await pdfDoc.embedPng(buf);
    const page = pdfDoc.addPage([720, 1280]);
    page.drawImage(pngImage, {
      x: 0,
      y: 0,
      width: 720,
      height: 1280
    });
  }

  const pdfBytes = await pdfDoc.save();
  const pdfPath = path.join(outputDir, 'zv67-project.pdf');
  fs.writeFileSync(pdfPath, pdfBytes);
  console.log('Saved PDF: ' + pdfPath + ' (' + pdfBytes.length + ' bytes)');

  // Create PPTX
  console.log('Generating PPTX zv67-project.pptx...');
  const pptx = new PptxGenJS();
  pptx.defineLayout({ name: 'CUSTOM_VERTICAL', width: 7.5, height: 13.333 });
  pptx.layout = 'CUSTOM_VERTICAL';

  for (let i = 0; i < slides.length; i++) {
    const slide = pptx.addSlide();
    const slidePath = path.join(slidesDir, slides[i].name);
    slide.addImage({
      path: slidePath,
      x: 0,
      y: 0,
      w: 7.5,
      h: 13.333
    });
  }

  const pptxPath = path.join(projectRoot, 'docs/presentation/zv67-project.pptx');
  await pptx.writeFile({ fileName: pptxPath });
  console.log('Saved PPTX: ' + pptxPath);

  console.log('Presentation build completed successfully!');
}

main().catch(err => {
  console.error('Error building presentation:', err);
  process.exit(1);
});
