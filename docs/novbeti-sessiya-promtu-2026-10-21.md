# Növbəti sessiya promtu – 21.10.2026

**Rol:** Rəhbər – Claude (Opus). **İcraçılar:** `kodcu`, `tercumeci`, `yigici`. **Qayda:** istifadəçi – «ardıcıl işlə: bir promtu bitir, sonra digəri».
Əvvəlcə oxu: `docs/audit/icra-2026-10-20b.md` → «Açıq qalanlar»; `git worktree list`; env-də xarici API açarları boş olmalıdır.

## Ardıcıllıq (hər addım bitmədən növbətiyə keçmə)
1. **Video tanıtım** – iş bitib (agent hesabatı 20.10 gec): budaq `worktree-agent-a176acbfd3a1719e2`, yeni worktree `.claude/worktrees/agent-a176-b` (köhnə `agent-a176acbfd3a1719e2` qovluğu pozulub – sil). Commit-lər e45d259 (kod), 2cb41e6 (ilk media ~54 MB – tarixçəni şişirdir), ce86bf3 (son media, cəmi 43,1 MB). **Squash-merge et** (`git merge --squash`), ki 54 MB-lıq aralıq media tarixçəyə düşməsin. Teacher posteri və pəncərə brauzerdə yoxlanmayıb; tam pytest işlədilməyib.
   Review: 2 poster + 3 kadra bax (titr, fəsil lövhəsi, spot), həcm ≤ 45 MB, aid pytest (`test_api_guide_seen`), `npm run build`
   → merge → push → Render success → canlıda `00-tanitim.az.mp4`, `.ru.mp4` 200, xoş gəldin pəncərəsi (müəllim + şagird) Chrome-da.
2. **Canlı əməliyyatlar** (istifadəçi «копия есть» yazdıqdan sonra): `unlimit-tasks?dry=0` (122), `POST ferdi-units` (4 qrup),
   `assign-programs?dry=0` (1 qrup) → hər birindən sonra say yoxlaması → auditə.
3. **İnkişaf qrupu – «Ardıcıl proqram» şablonu**: `docs/inkisaf-qrupu-ardicil-proqram-promtu.md` (§5–8 əsasdır) → kart `docs/tasks/inkisaf-zencir.md`
   → `kodcu` → review → merge → deploy → canlıda qrupu istifadəçi ilə təsdiqlə → önbaxış → «hə» → tətbiq. P001 viktorina (ad/sertifikat) – ayrı repo commit.
4. **Analitika bölməsi Mərhələ 2**, sonra **Mərhələ 3** (`docs/analitika-bolmesi-audit-promtu.md`, kart `docs/tasks/analitika-bolmesi.md`).
5. Sessiya sonu: tam pytest + build, `docs/audit/icra-2026-10-21.md`, HANDOFF sətri, növbəti promt.
