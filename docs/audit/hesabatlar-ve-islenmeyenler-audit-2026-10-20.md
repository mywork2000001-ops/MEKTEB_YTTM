# Audit: işlənməyən testlər tam görünmür + hesabatlar başqa bölmələrdədir (20.10.2026)

**Sifarişçi (müəllim):** «işlənməyən testlərin hamısı göstərilmir – audit; hesabatlar niyə başqa bölmələrdədir – **bütün hesabatlar
yalnız «Analitika və hesabat»da**; bölməni strukturlaşdır, peşəkar işlə».
**Rəhbər:** Claude (Opus) · **Metod:** kod izləmə (backend → API → UI), Explore agenti + rəhbər yoxlaması.
**Kartlar:** I – `docs/tasks/islenmeyenler-tam-siyahi.md`; II – `docs/tasks/analitika-bolmesi.md` (Mərhələ 2+3 + bu auditin əlavələri).

## I. Niyə işlənməyən testlərin hamısı görünmür
Mənbə zənciri: `test_stats.collect` → `student_report.class_matrix` → `class_missing` → `/api/results-center/class-missing` → `MissingReport.tsx`
(«Testlər → Nəticələr → Yazmayanlar» tabında, yalnız bir sinif).

| # | Səbəb | Yer | Qiymət | Nəticə müəllim üçün |
|---|---|---|---|---|
| M1 | Defolt süzgəc: `plan=late_open` + «Gözlənilənləri də göstər» söndürülüb (`only_missed=1`) | `MissingReport.tsx:58-59,72-75` | **əsas səbəb** | açıq/müddətsiz, plan günü gəlməmiş testlər gizlidir |
| M2 | Əsas səhifə və «hamısı PDF» başqa süzgəclə sayır (plan=all, gözlənilənlər daxil) | `student_report.py:678`, `results_center.py:406`, `Home.tsx:160` | xəta (uyğunsuzluq) | Ana səhifədə «5», hesabatda «2» |
| M3 | Dövr süzgəci testin **açılış** tarixinə görədir | `test_stats.py:131-133` | xəta | 10 sentyabrda açılıb hələ işlənməyən test «Bu ay / Semestr»də görünmür |
| M4 | «Semestr» hazır dövrü 27–31 yanvarda gələcək tarix verir | `MissingReport.tsx:38-41` | xəta | həmin günlərdə siyahı boşdur |
| M5 | Yalnız birinci sinif avtomatik seçilir, bütün siniflər görünüşü yalnız PDF-dədir | `ResultsCenter.tsx:238` | çatışmazlıq | digər siniflərin borcu görünmür |
| M6 | Batch-siz (köhnə/import) sınaq tapşırığı atılır | `test_stats.py:78` | ehtimal xəta | köhnə sınaq siyahıda yoxdur |
| M7 | «Yazmayanlar» nişanı/xroniki say yalnız **bağlanmış** testləri sayır | `results_center.py:93-99` | qəsdən, amma izahsız | müddətsiz test heç vaxt sayılmır |
| M8 | Yalnız `movzu` və `sinaq` növləri; növsüz tapşırıq (`kind=None`) toplanmır | `test_stats.py:21,86-93` | qəsdən, UI-də izah yoxdur | adi tapşırıq siyahıda yoxdur |
| M9 | Təkrar göndərmə surəti `AuditLog.copied_from` ilə kökə bağlanır; audit sətri yoxdursa ayrıca test sayılır | `test_stats.py:92-110` | kövrək | surət ayrıca sütun olur |
| — | Arxiv dərs, digər məkan (fərdi/məktəb), çıxmış şagird, üzrlü qeyd, hələ açılmamış test, hədəf şagird siyahısı | `test_stats.py:67-71`, `student_report.py:373,589-594` | qəsdən – saxlanır | hesabatda qeyd kimi izah olunur |

Testlərlə örtülməyən hallar: açılış tarixinə görə dövr, batch-siz sınaq, növsüz tapşırıq, Ana səhifə ↔ hesabat sayı, müddətsiz test.

## II. Analitika/hesabat başqa bölmələrdədir
Əvvəlki audit (`docs/analitika-bolmesi-audit-promtu.md`, A1–A15) təsdiqləndi; Mərhələ 2–3 icra olunmayıb. `Reports.tsx` – 460 sətir, 8 tab,
URL vəziyyəti və qrup səviyyəsi yoxdur. Əlavə tapıntılar:

| # | Tapıntı | Yer | Qərar |
|---|---|---|---|
| A16 | İşlənməyənlər hesabatı yalnız `Testlər → Nəticələr → Yazmayanlar` içindədir | `ResultsCenter.tsx:230` | → Analitika «Testlər və sınaqlar → İşlənməyənlər» (bütün siniflər + tək sinif) |
| A17 | Ana səhifədə «hamısı PDF» düyməsi və «Bu həftə diqqət» ayrı giriş nöqtələridir | `Home.tsx:153-172` | xülasə qalır, keçid → `/reports?g=tests&t=missing` |
| A18 | Məşğələ «Hesabatı çap et (tədris hissəsi üçün)» | `ExtraCourses.tsx:469` | → Analitika «Məşğələlər» + Çap mərkəzi |
| A19 | Sinif rəhbəri davamiyyəti | `HomeroomAttendance.tsx` | qeyd (əməliyyat) yerində; hesabat görünüşü → «Sinif rəhbəri» |
| A20 | Köçürmə şübhəlilər hesabatı (kağız) | `Exams.tsx:360,486` | → Çap mərkəzi siyahısı (keçid) |
| A21 | Giriş vərəqələri, sinif siyahısı, plan çapları | `SettingsRoster`, `ClassListPrint`, `Plan/Programs/DailyPlan` | rəsmi sənəd – yerində; Çap mərkəzində keçid |

**Prinsip (dəyişməz):** əməliyyat (yaratmaq, yazmaq, təyin, skan, qeyd) öz bölməsində; **hər hesabat, statistika, reytinq, analiz və
hesabat çapı – yalnız «Analitika və hesabat»da**. Köhnə yerdə ən çox 1 sətir xülasə + «📊 Analitikada ətraflı →». Hesablama köçürülmür –
komponent import olunur; köhnə URL-lər yönləndirilir.

## III. Hədəf quruluş – «Analitika və hesabat»
Yuxarıda ortaq: sinif (+ «Bütün siniflərim»), dövr. URL: `/reports?g=<qrup>&t=<tab>`.
1. **İcmal** – sinif icmalı, «diqqət» siyahısı.
2. **Akademik nəticələr** – Müvəffəqiyyət · Ümumi reytinq · Səviyyələr · Standartlar üzrə (A8) · Dərs sayı.
3. **Testlər və sınaqlar** – İşlənməyənlər (A16) · Kim nəyi işləyib (matris) · Test reytinqi · Sual təhlili (A10) · Sinif və qrup · Ümumi.
4. **Şagird** – Şagird hesabatı · Risk.
5. **Davamiyyət**.
6. **Məşğələlər** (A12, A18).
7. **Sorğu nəticələri** (A13).
8. **Sinif rəhbəri** (yalnız sinif rəhbərinə; A9, A19).
9. **Çap mərkəzi** – bütün sənədlər bir siyahıda (A4, A20, A21).
10. **Məktəb üzrə** (admin/müavin) – məktəb hesabatı, sertifikatlar.

## IV. İcra ardıcıllığı
1. Kart I (işlənməyənlər tam siyahı, M1–M8) → `kodcu` → review → merge → deploy.
2. Kart II Mərhələ 2 (skelet, A1–A7, A16–A17) → merge → deploy.
3. Kart II Mərhələ 3 (A8–A13, A18–A21) → merge → deploy.
Hər addım: aid pytest, `npm run build`, Chrome (1366 və 390), köçürmə cədvəli, audit sətri.
