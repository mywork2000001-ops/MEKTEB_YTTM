# Davam promtu – 20.10.2026 (b)

**Rol:** Rəhbər – Claude (Opus). **İcraçılar:** `kodcu` (kod, worktree), `tercumeci` (AZ/EN/RU).
**Mənbə:** `docs/qalan-isler-promtu-2026-10-20.md` (P1–P3 siyahısı) + `docs/audit/icra-2026-10-20.md`.
**Dəyişməz qaydalar:** CLAUDE.md – hər yeni mətn AZ/EN/RU; mövzu testləri yalnız `app/plan_tests.py`; yoxlama `npm run build`
(frontend) + aid pytest; canlı DB yazısı yalnız istifadəçinin bu sessiyadakı «hə»-si ilə; sirlər git-ə getmir; sonda audit.

## 0. Başlanğıc vəziyyəti (yoxlanıb)
- main `408c4f9` origin-dən 4 commit irəlidədir (video bələdçi AZ/RU səs, şagird girişində video, promt). Push gözləyir.
- `frontend/src/GuideModal.tsx` – commit olunmamış: video yolu/alt yazı dili `guideData`-dan; build ✅.
- Köhnə worktree `agent-a327a2dc…` (budaq birləşib) – silinməlidir.
- `docs/tasks/sagird-iki-sinifde-birlesdirme.md` – yoxlandı, adlar artıq «Şagird A/B + id» ilə əvəzlənib (P1 §2 bağlıdır).

## 1. Bu sessiyada icra (ardıcıllıq)
1. GuideModal commit → worktree təmizliyi → push → Render deploy success → `/api/health/db`.
2. Kart `docs/tasks/kod-duzelisleri-2026-10-20.md` → `kodcu` (worktree): qalan işlər §3 bəndləri 6–9.
3. Review → aid pytest → `npm run build` → merge → push → deploy yoxlaması → worktree/budaq silinir.
4. Canlı əməliyyatlar (§1: müddətsiz testlər, fərdi 2×45, məşğələ qrupları) – əvvəl backup + önbaxış (`dry`),
   **tətbiq yalnız istifadəçinin təsdiqi ilə**.
5. Sessiya sonu: tam pytest + build, `docs/audit/icra-2026-10-20b.md`, HANDOFF sətri.

## 2. Bu sessiyada edilmir (istifadəçi lazımdır)
Planşet/telefon görünüşü (Chrome pəncərəsini kiçiltmək), RU/EN canlıda gözlə, PDF çapları, XI-P KSQ-1 15/18 qərarı,
Drive backup sirləri, Gemini açarı, «öz rəqəmləri» canlı sınağı, 25.10/27.10 tarixli işlər, H1 yeni tədris ili ustası.
