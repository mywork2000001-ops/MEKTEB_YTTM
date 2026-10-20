# Növbəti sessiya promtu – 22.10.2026

**Rol:** Rəhbər – Claude (Opus). **İcraçılar:** `kodcu`, `tercumeci`, `yigici`. **Qayda:** ardıcıl işlə – bir addımı bitir, sonra növbəti.
Əvvəlcə oxu: `docs/audit/icra-2026-10-20c.md` → «Açıq qalanlar»; `git worktree list`; env-də xarici API açarları boş olmalıdır.
Push – istifadəçi `! git push origin main` (auto-mode push-u bloklayır).

## Ardıcıllıq
1. **İşlənməyənlər sürəti < 3 san.** (audit P1-1): ölç (canlı JS `fetch` vaxtı), kart → `kodcu` → `test_missing_perf.py` hədləri → deploy → yenidən ölç.
2. **Analitika yoxlaması:** Chrome-da 10 qrupun hər tabı açılır (1366 və 390 px), RU rejimində mətnlər (`tercumeci` ~90 açar), Çap mərkəzi düymələri dəqiq keçid (P2-5), vahid dövr qərarı (P2-4).
3. **Canlı əməliyyatlar** (istifadəçi «копия есть» yazdıqdan sonra): `unlimit-tasks?dry=0`, `POST ferdi-units`, `assign-programs?dry=0` → say yoxlaması.
4. **İnkişaf qrupu «Ardıcıl proqram»** – `docs/inkisaf-qrupu-ardicil-proqram-promtu.md` → kart → `kodcu`.
5. Sessiya sonu: tam pytest (`backend` qovluğundan) + build, `docs/audit/icra-2026-10-22.md`, HANDOFF, növbəti promt, istifadəçiyə `/compact` xatırlat.
