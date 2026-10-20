# Davam promtu – 20.10.2026 (19.10 işlərinin tamamlanması + yeni tələblər)

**Sifarişçi:** müəllim · **Rəhbər:** Claude (Opus) · **İcraçılar:** `kodcu` (kod), Rəhbər – review, merge, push, canlı DB.
**Səbəb:** 19.10 axşam sessiya qəfil bitdi (enerji), 3 kodcu işi yarımçıq qaldı, main origin-dən 26 commit irəlidədir.

## 0. Vəziyyət (20.10 səhər, yoxlanılıb)
| Worktree / budaq | İş | Vəziyyət |
|---|---|---|
| `agent-a9ba…` | Sinif matrisi «kim nəyi işləyib» (`docs/tasks/sinif-test-matrisi.md`) | 1 commit (0e5cb05), commit olunmamış dəyişiklik yoxdur |
| `agent-ac32…` | Plan testləri – tək mühərrik `app/plan_tests.py` + skript + API + `AssignTests.tsx` (`docs/plan-testleri-skripti-promtu.md`) | **heç nə commit olunmayıb** (12 M + 6 yeni fayl) |
| `agent-a4d2…` | Kağız KSQ nəticə paketi + `/api/workspaces/ferdi-units` | 2 commit + commit olunmamış UI (ResultPackage.tsx, packagePrint.ts, Results.tsx, Exams.tsx) |
| main | 666f36d | push gözləyir (26 commit) |

## 1. Yeni tələblər (istifadəçi, 20.10)
1. **Müəllim işlənməyən mövzu testlərinin və sınaqların siyahısını görsün** (şagird üzrə: kim hansını hələ işləməyib).
2. **Testlərin icra vaxtı müddətsiz olsun.**

## 2. Rəhbərin qərarları
- **Q1 (siyahı).** Yeni ekran qurulmur – matris (a9ba) əsasdır: «Kim nəyi işləyib» nişanına **«Yalnız işlənməyənlər»** rejimi:
  sətir = şagird, yanında işləmədiyi mövzu testləri (№ + mövzu) və sınaqlar (adı ilə), say; boş olanlar gizlənir; çap/Excel (AZ).
  **Çap (istifadəçi, 20.10):** (a) **sinif üzrə** – bir vərəqdə bütün sinfin işlənməyənlər siyahısı (PDF/Excel, AZ);
  (b) **hər şagirdə ayrıca** – şagird üçün vərəqə «İşləməli olduğun testlər» (hər şagird ayrıca səhifə, toplu PDF; bir şagird – Şagird
  hesabatından da); şagird vərəqəsi AZ|RU (şagirdin dilinə görə, valideyn hesabatı kimi). Hər iki çap süzgəcə tabedir (Mövzu testləri / Sınaqlar / Hamısı, dövr).
  Müəllimin əsas səhifəsində «Bu həftə diqqət» blokunda sinif üzrə «N şagird – M işlənməmiş test» sətri, klik → həmin nişan.
- **Q2 (müddətsiz).** Miqrasiyasız: `duration_min = 0` ⇒ **taymer yoxdur**; `closes_at = NO_DEADLINE` (2100-01-01 UTC) ⇒ **son tarix yoxdur**.
  Ortaq sabitlər/funksiyalar bir yerdə (`app/timing.py`: `NO_DEADLINE`, `is_unlimited(t)`, `deadline_for(t, start)`), hamı oradan alır.
  - Defolt müddətsiz: mövzu testləri (`plan_tests.py`, `auto_tests.py`, topic_tests), onlayn sınaqlar/seriyalar (`exams_online`, `exam_series`).
  - **KSQ/BSQ – dəyişmir** (rəsmi summativ, 45 dəq. qalır). Müəllim formada istəsə vaxt/son tarix qoya bilər («Müddətsiz» qutusu defolt işarəli).
  - Şagird ekranında: taymer əvəzinə «Vaxt məhdudiyyəti yoxdur», siyahıda «Müddətsiz»; yarımçıq cavablar saxlanır, istədiyi vaxt təhvil verir.
  - Statuslar: müddətsiz testdə «yazmayıb» əvəzinə **«işlənməyib»** (açıq qalır); hesabatlar (matris, Yazmayanlar, şagird hesabatı) bunu nəzərə alır.
  - «Cavablar bağlandıqdan sonra» (`show_answers='after_close'`) müddətsiz testdə → **şagird təhvil verdikdən sonra** (yoxsa heç vaxt göstərilməz).
  - Mövcud açıq mövzu testləri/sınaqları (bu tədris ili, 15.09.2026-dan, hələ bağlanmamış) canlıda müddətsizə çevrilir – bir dəfəlik,
    önbaxış + tətbiq (`/api/admin/unlimit-tasks?dry=1`), istifadəçinin bu tələbi icazə sayılır; bağlanmışlara toxunulmur.
- **Q3.** Ardıcıllıq münaqişəyə görə: plan testləri (45 dəq. defoltu) əvvəl birləşir, sonra müddətsiz iş onun üstündə gedir.

## 3. Addımlar (ardıcıl)
1. **a9ba matris** – review, aid pytest, build → main-ə merge.
2. **ac32 plan testləri** – kodcu: işi tamamla, testlər + build, commit → Rəhbər review → merge.
3. **a4d2 KSQ paketi** – kodcu: UI-ni tamamla, testlər + build, commit → review → merge (miqrasiya 5b2d7e9f1a64 – yalnız yeni sütun/cədvəl olmalıdır, yoxla).
4. **Müddətsiz testlər (Q2)** – kodcu, kart `docs/tasks/muddetsiz-testler.md`.
5. **İşlənməyənlər siyahısı (Q1)** – kodcu, kart `docs/tasks/islenmeyenler-siyahisi.md`.
6. Tam pytest + `npm run build` → push (istifadəçi: `! git push origin main`) → Render statusu → `/api/health/db`.
7. Canlı: ferdi-units önbaxış → tətbiq (19.10 icazə); unlimit-tasks önbaxış → tətbiq; plan_tests `--missing` önbaxışı istifadəçiyə.
8. Bütün worktree və budaqlar silinir; HANDOFF + yaddaş.

Hər yeni mətn AZ/EN/RU (`t()`), rəsmi çap – AZ. Yoxlama – `npm run build` (frontend), `npx tsc --noEmit` yox.
