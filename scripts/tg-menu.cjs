// Telegram bot menyusu (rus dilində) – @ferid_claude_bot üçün.
// İşə salma: node scripts/tg-menu.cjs
// Menyu yalnız istifadəçinin çatına (scope=chat) yazılır: plugin hər başlanğıcda
// all_private_chats üçün öz 3 əmrini yazır, chat scope isə ondan üstündür və silinmir.
// Token ~/.claude/channels/telegram/.env-dən oxunur və heç yerdə çap olunmur.
const fs = require('fs');
const os = require('os');
const path = require('path');

const CHAT_ID = 1019324423; // access.json allowlist – istifadəçi
const COMMANDS = [
  ['menu', 'Показать это меню с пояснениями'],
  ['terminals', 'Список терминалов VS Code и сессий Claude'],
  ['send', 'Задача другой сессии: /send имя текст'],
  ['new_session', 'Открыть новый терминал с Claude'],
  ['now', 'Что сейчас делается (задачи, агенты)'],
  ['stop', 'Остановить текущую задачу или фоновый процесс'],
  ['procs', 'Процессы: claude, node, python, bun'],
  ['kill', 'Завершить процесс: /kill PID'],
  ['screen', 'Скриншот экрана (что видно в VS Code)'],
  ['git', 'Git: ветка, изменения, неотправленные коммиты'],
  ['build', 'Проверка: npm run build (frontend)'],
  ['tests', 'Запустить pytest и прислать итог'],
  ['push', 'Отправить коммиты на GitHub (git push)'],
  ['deploy', 'Статус деплоя Render и /api/health'],
  ['open_work', 'Открытые задачи из последнего аудита'],
  ['audit', 'Записать аудит сессии (docs/audit)'],
  ['help', 'Справка плагина'],
  ['status', 'Статус привязки к боту'],
].map(([command, description]) => ({ command, description }));

const envPath = path.join(os.homedir(), '.claude', 'channels', 'telegram', '.env');
const m = fs.readFileSync(envPath, 'utf8').match(/TELEGRAM_BOT_TOKEN=(\S+)/);
if (!m) { console.error('Token tapılmadı: ' + envPath); process.exit(1); }

const call = (method, body) =>
  fetch(`https://api.telegram.org/bot${m[1]}/${method}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(r => r.json());

(async () => {
  const scope = { type: 'chat', chat_id: CHAT_ID };
  const set = await call('setMyCommands', { commands: COMMANDS, scope });
  if (!set.ok) { console.error('setMyCommands xətası:', set.description); process.exit(1); }
  await call('setChatMenuButton', { chat_id: CHAT_ID, menu_button: { type: 'commands' } });
  const got = await call('getMyCommands', { scope });
  console.log(`OK: ${got.result.length} əmr yazıldı (chat ${CHAT_ID})`);
})();
