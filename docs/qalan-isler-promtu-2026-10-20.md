# Qalan işlər promtu – 20.10.2026 (audit əsasında)

**Rəhbər:** Claude (Opus) · **İcraçılar:** `kodcu`, `tercumeci`, `yigici` · **Qaydalar:** CLAUDE.md (AZ/EN/RU, tək mühərrik `plan_tests.py`, `npm run build`, sessiya sonu audit).

## 0. Audit nəticəsi (20.10.2026, yoxlanıb)
| Yoxlama | Vəziyyət |
|---|---|
| Git | main = origin/main = `3935c42` (push 2 edilib), worktree yalnız 1, artıq budaq yoxdur |
| Render deploy | `3935c42` – **success** |
| Canlı DB | `/api/health/db` → `{"ok":true,"db":true}` |
| Xarici API açarları (env) | boş ✅ |
| İki sinifdə şagird birləşdirmə | canlıda edilib (19.10, 111←96, 99←116); axtarış normallaşdırması c14dffa canlıda |
| Commit olunmamış | `docs/tasks/sagird-iki-sinifde-birlesdirme.md` – **şagird adı və doğum tarixi var**, bu halda git-ə getməməlidir |

## 1. P1 – canlı əməliyyatlar (istifadəçi əvvəlcədən icazə verib; Chrome admin sessiyası lazımdır)
Hər əməliyyatdan əvvəl `GET /api/admin/backup` yerli diskə (git-ə yox), sonra önbaxış → yalnız sonra tətbiq. Nəticə (say) audit faylına.
1. **Müddətsiz testlər:** `POST /api/admin/unlimit-tasks?dry=1` → siyahını istifadəçiyə göstər → `dry=0`. KSQ/BSQ 45 dəq. qalır.
2. **Fərdi görüş 2×45:** `GET /api/workspaces/ferdi-units` (önbaxış) → `POST` (tətbiq). Fərdi məkan school_id 2 – sonra aktiv məkanı 1-ə qaytar.
3. **Məşğələ qrupları:** Siniflər → Məşğələ qrupları → «📚 Proqramları təyin et» → önbaxış → «Tətbiq et».
4. Yoxlama: hər birindən sonra bir sinifdə/qrupda gözlə bax (test müddəti, plan dərsləri, proqram adı).

## 2. P1 – təhlükəsizlik/təmizlik
5. `docs/tasks/sagird-iki-sinifde-birlesdirme.md`: adları və doğum tarixlərini ID ilə əvəz et (`id 111 / id 96`), sonra commit. Alternativ – faylı `docs/private/` (git-ignore) altına köçür.

## 3. P2 – kod düzəlişləri (kart → `kodcu`, worktree; hər birinə test)
6. **İştirak 100% xətası:** heç bir test yazmayan şagirdə iştirak 100% görünür – `backend/app/results_center.py:375/406` (`GIVEN`). Gözlənilən: 0% və ya «—». Test: yazmayan şagird → 0.
7. **«Yenidən göndər» (`CopyIn`) müddətsiz rejimi** dəstəkləmir – `app/timing.py` qaydasını burada da tətbiq et.
8. **`exam_series` üçün test yoxdur** – əsas axın üçün ən azı 3 test.
9. **Tərcümə boşluqları** (`tercumeci` + `kodcu`): məşğələ mövzu mətni yalnız AZ; server `DAYS` yalnız AZ; `programs.py lessons_for` xəbərdarlıqları yalnız AZ → EN/RU (şagirdə/müəllimə görünən mesajlar).
10. **KSQ paketi server PDF** – hazırda PDF yalnız brauzerdə qurulur; lazımdırsa serverdə (qərar: istifadəçi – vacib deyilsə P3).

## 4. P2 – yoxlamalar (istifadəçinin iştirakı ilə)
11. **Planşet/telefon görünüşü** (900×700, 390×844): menyu akkordeonu, əsas səhifə, «Daha çox». Əvvəl istifadəçidən Chrome pəncərəsini kiçiltməsini xahiş et.
12. **RU/EN mətnlər canlıda gözlə:** müəllim interfeysi (skriptlə tərcümə – yarımçıq parçalar ola bilər, məs. «Qrupa əlavə et (»), Join/Materials, yeni «işlənməyənlər» siyahısı və çapı.
13. **PDF çapları gözlə:** `/missing-list?per_student=0|1`, KSQ paketi, ümumi A4 cavab vərəqəsi (real foto ilə «📷 Skan»).
14. **XI peşə KSQ-1** canlıda 15 sualdır – 18 qərarı tətbiq olunmayıb: istifadəçi təsdiq etsin (15 qalsın / 18-ə çatdır).
15. **Köhnə skanlı KSQ/BSQ** nəşr olunmayıbsa şagirdə gizlidir – müəllimə «Nəticəni şagirdlərə göstər» xatırlatması.

## 5. P2 – istifadəçinin girişi / tarixlər
16. **Həftəlik Drive backup sirləri** (Google OAuth + Neon read-only rol) – istifadəçi ilə birlikdə; açar çata yazılmır.
17. **Gemini açarı** – Google köhnə layihəni bağlayıb; istifadəçi yeni açar yaradıb Render env-ə özü yazsın (gündəlik plan üçün).
18. **~25.10** – Neon compute saatlarına bax; **27.10-dan sonra** `exam_*_backup_20261013` cədvəllərini sil (istifadəçinin «hə»-si ilə).
19. **«Öz rəqəmləri» canlı sınağı** – boş qrupda («X b riyaziyyat qrupu») əlavə KSQ yaratmaq üçün razılıq gözləyir.

## 6. P3 – sonraya
20. **H1 – yeni tədris ili ustası** (qərarlar hazırdır: siniflər avtomatik yuxarı, XI → arxiv, il/semestr sərhədləri; jurnal semestr sonu kilidlənir, il qiyməti = iki semestrin ortası, yarı-yuxarı yuvarlaq). Ayrıca kart lazımdır.
21. Məşğələ auditinin P3-ü: N+1 sorğular, şagirdin iki məşğələsinin vaxt toqquşması, çap forması.
22. Videoları RU interfeysdə də yazmaq (`scripts/guide_videos.py`).
23. V–VIII «Sinif testləri» – sual PDF-i gələndə bank (`pdf-oxuyucu` → `cavab-yoxlayici`); indi PENDING_GRADES.
24. Viktorina saytında 100 ballıq sistem (ayrı repo, öz yoxlayıcıları ilə).
25. Fərdi 3-cü görüş – istifadəçi özü yazacaq (vakant saxla).

## 7. İcra ardıcıllığı (təklif)
1) §2 (5) → 2) §1 (1–4, Chrome) → 3) §3 kartı, `kodcu` worktree (6–9) → review, aid pytest, `npm run build`, merge, push, Render success, `/api/health/db` → 4) §4 istifadəçi ilə → 5) sessiya sonu: tam pytest + build, `docs/audit/icra-YYYY-MM-DD.md`, HANDOFF sətri.
