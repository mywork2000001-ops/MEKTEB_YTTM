# Müəllim köməkçisi — qaydalar

## Dil: hər dəyişiklikdə AZ / EN / RU (istifadəçi tələbi, 12.10.2026)
Tətbiqdə rusdilli şagird və müəllimlər var. Ona görə **hər yeni və ya dəyişdirilən interfeys mətni avtomatik tərcümə olunur** —
ayrıca xahiş gözlənilmir:
- Frontend: mətn `t('…')` (komponentdə `useT()`) və ya `tt('…')` (komponentdən kənar) ilə; lüğət `frontend/src/i18n.ts`
  (`'AZ mətni': ['English', 'Русский']`), dəyişən hissələr `{n}` yer tutucusu ilə: `t('{n} sual', { n })`.
- Sual / variant / izah mətni (`{az,ru,en}`) — `ml(x)` ilə (istifadəçinin dilində).
- Server mesajları şagirdə görünürsə — EN/RU qarşılığı da (docs/rus-dili-promtu.md, mərhələ 4).
- Rəsmi sənədlər (jurnal, perspektiv plan, rəsmi çap formaları) — yalnız Azərbaycan dilində.
- Yoxlama: **`npm run build`** (frontend qovluğunda; `tsc -b` – Render də məhz bunu işlədir). `npx tsc --noEmit -p .` HEÇ NƏ YOXLAMIR (kök tsconfig yalnız istinadlardır) – 12.10.2026-da buna görə 11 deploy uğursuz oldu. Lüğətdə təkrar açar (tək və ya cüt dırnaqla) xəta verir.

Ətraflı: `docs/rus-dili-promtu.md`.

## Mövzu testlərinin təyini – tək mühərrik (istifadəçi tələbi, 19.10.2026)
Perspektiv plandan mövzu testinin seçimi/təyini ilə bağlı **hər yeni imkan** (yeni bank mənbəyi, sinif/nömrə qaydası, variant,
səviyyə, öz rəqəmləri, paralel siniflər) yalnız `backend/app/plan_tests.py`-ə (RESOLVERS / POST_STEPS / opts) əlavə olunur;
skript `scripts/plan_tests.py`, API `/api/plan-tests/*`, düymə və gündəlik `auto_tests` onu oradan alır; test – `tests/test_plan_tests.py`.
Ətraflı: `docs/plan-testleri-skripti-promtu.md`.

## Agent sistemi (rollar, qənaət) – `docs/agent-sistemi-promtu.md`
- **Rəhbər** = Claude (Pro abunə, limit həftəlik): plan, tapşırıq kartı (`docs/tasks/`), riskli iş (skan, miqrasiya, canlı DB, deploy), review, main-ə birləşmə.
- **İcraçılar** (18.10.2026-dan yalnız Claude Pro; OpenRouter/`claude-ds`/Qwen silinib, QWEN.md – arxiv): Agent tool ilə bu sessiyadan –
  kod → `kodcu`, tərcümə → `tercumeci`, PDF → `pdf-oxuyucu`, cavab açarı → `cavab-yoxlayici`, mexaniki iş → `yigici`. Paralel iş – `isolation: "worktree"`, birləşdikdən sonra worktree və budaq silinir.
- **Pro limitinə qənaət:** Rəhbər kodu özü yazmır – dəqiq kart yazır; fayl hissə-hissə (Grep), i18n.ts heç vaxt tam; pytest yalnız aid testlər; uzun çıxış `tail`; ekran şəkli scale 0.5. Təkrar oxu, təkrar yoxlama və uzun izah yoxdur.
- Sessiya əvvəli: `docs/HANDOFF.md` (son sətirlər) + `git worktree list`.

## İcra auditi – hər sessiyanın sonunda (istifadəçi tələbi, 20.10.2026)
Sessiyanı bitirməzdən əvvəl `docs/audit/icra-YYYY-MM-DD.md`: hər istifadəçi istəyi ayrıca sətir, status (✅/🟡/⏳/❌/🔒) və **sübut**
(commit, test sayı, build, deploy, miqrasiya); tam pytest + build; açıq qalanlar P1/P2/P3. Növbəti sessiya əvvəlcə son auditin
«Açıq qalanlar» bölməsini oxuyur. Ətraflı: `docs/icra-auditi-promtu.md`.

## Bulud sessiyası (ikinci hesab, claude.ai/code) – yalnız PDF-dən testlər
Bu repoda İŞLƏMİR: o `HUB_EDUCAT-ON` (Documents\Claude\Projects) repoda `cloud/<slug>` budağında PR açır, PDF – `test-sources`.
Promt: `HUB_EDUCAT-ON/docs/cloud/PROMPT.md`. PR review, katalog, yoxlamalar, merge, deploy – əsas sessiya (bu).

## Telegram menyusu (25.10.2026)
Bot menyusundan gələn əmrlər (`/terminals`, `/send`, `/git`, `/build` …) – `docs/telegram-menyu-promtu.md` üzrə; cavab rusca, `reply` ilə.
Menyunu dəyişmək: `scripts/tg-menu.cjs` → `node scripts/tg-menu.cjs`.
