# Qwen Code ilə paralel iş — promt (14.10.2026)

## Tələb (istifadəçi)
«Claude-un həftəlik limiti bitir – paralel işləmək üçün Qwen Code quraşdır, OpenRouter API açarını qoşmağın sxemini ver,
peşəkar promt yaz və icra et.»

## Görülən işlər
1. Qwen Code CLI: `npm install -g @qwen-code/qwen-code@latest` (v0.25.1); `%APPDATA%\npm` istifadəçi PATH-ə əlavə edildi.
2. Qwen ayarları `%USERPROFILE%\.qwen\settings.json` (köhnəsi: `settings.json.bak-20261014`):
   - `security.auth.selectedType = "openai"` (OpenAI-uyğun API),
   - `modelProviders.openai`: qwen/qwen3-coder (default), qwen3-coder-next, qwen3-coder-flash, qwen3-coder-30b-a3b-instruct
     + köhnə modellər; hamısı `baseUrl https://openrouter.ai/api/v1`, `envKey OPENROUTER_API_KEY`;
   - köhnə iki açar OpenRouter-də 401 verdi (etibarsız) → yer tutucu `PASTE-NEW-KEY-HERE`.
3. Açar skripti `%USERPROFILE%\.qwen\qwen-acar.ps1`: açarı gizli soruşur, OpenRouter-də yoxlayır (/api/v1/key), settings.json-a yazır.
4. Layihə qaydaları: `QWEN.md` (Qwen avtomatik oxuyur), iş jurnalı `docs/HANDOFF.md`.
5. Qwen üçün ayrıca git worktree `..\mk-qwen` (budaq `qwen/baza`), frontend asılılıqları quraşdırılıb.

## OpenRouter açarı – sxem
```
openrouter.ai → Keys → Create key (Credit limit: məs. 5 $) → sk-or-v1-...
        │
        ▼
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\.qwen\qwen-acar.ps1"   (açarı yapışdır → yoxlanır → saxlanır)
        │
        ▼
~/.qwen/settings.json:  env.OPENROUTER_API_KEY ──► modelProviders.openai[*].envKey
                         baseUrl = https://openrouter.ai/api/v1,  model = qwen/qwen3-coder
        │
        ▼
cd ..\mk-qwen  →  qwen   (model dəyişmək: /model)
```
Qiymət (14.10.2026, 1M token): qwen3-coder 0.30 $ / 1 $; coder-next 0.12 / 0.80; 30b-a3b 0.07 / 0.28.
Tətbiqin öz OpenRouter açarı (kart oxuyucu) ilə Qwen açarını AYRI saxlayın – biri digərinin limitini yeməsin.
