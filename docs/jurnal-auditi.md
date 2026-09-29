# «Jurnal» bölməsinin metodist auditi — 29.09.2026

Promt: `docs/jurnal-metodist-promtu.md`. Yoxlanan kod: `backend/app/api/journal.py`, `exams.py`, `plan.py` (rəsmi plan),
`frontend/src/pages/teacher/Journal.tsx`, `Exams.tsx`. Sübut: avtomatik testlər və 6 real planla brauzer yoxlaması.

## Tapıntılar və düzəlişlər

| № | Meyar | Tapıntı (əvvəl) | Risk | Düzəliş (indi) |
|---|---|---|---|---|
| 1 | Summativ nəticələr | KSQ/BSQ nəticəsi «tapşırıq üzrə» rejimdə yadda saxlananda **hələ yazmayan şagirdlərə** hamısı ✗ → 0 bal → **«2»** yazılırdı | Yarımil qiyməti səhv (ən ciddi) | Qeyd toxunulana qədər «·» (daxil edilməyib); «daxil et» və «təmizlə» düymələri; boş sətir qiymətə çevrilmir |
| 2 | Standart təhlili | KSQ yaradanda tapşırığa standart yazmaq mümkün deyildi – «Standartlar» təhlili həmişə boş idi | Diaqnostika və təkrar planlaşdırma mümkün deyil | Hər tapşırıq üçün standart seçimi: bu summativin əhatə etdiyi mövzuların (əvvəlki KSQ/BSQ-dan bu günə) plandakı standartları |
| 3 | Formativ rəy | Formativ qiymət yalnız rəqəm idi | Formativ qiymətləndirmənin mahiyyəti (rəy) itir | Hər qiymətə qısa **rəy** (300 simvol) – jurnalda saxlanır |
| 4 | Summativ gün | KSQ/BSQ dərsində heç bir xəbərdarlıq yox idi | Formativ və summativ qarışır | Sarı xəbərdarlıq: nəticələr «KSQ / BSQ» tabında yazılır, formativ qiymət adətən qoyulmur |
| 5 | Dərs qeydi | API-də `note` vardı, interfeysdə yox idi | Dərsin gedişi, fərdi iş qeyd olunmur | «Dərs qeydi» sahəsi |
| 6 | Planın icrası | «Mövzular» yalnız rəsmi siyahı idi | Hansı mövzunun keçilmədiyi görünmür | Hər mövzuda: keçildiyi tarix(lər) / işçi plan tarixi; status: keçilib / gecikir / gözlənilir; icra faizi; süzgəc |
| 7 | Jurnal səhifəsi | Klassik jurnal görünüşü (şagird × tarix) yox idi | Aylıq nəzarət və kağız jurnalla tutuşdurma çətin | Yeni **«Jurnal səhifəsi»** tabı: ay üzrə qiymətlər, q/ü/g, KSQ/BSQ sütunu (sarı), yazılmamış dərslər, orta və buraxma; mövzu + ev tapşırığı siyahısı; A4 albom çapı |
| 8 | Xülasə | Yalnız bütün il | Yarımil hesabatı çıxmır | I yarımil / II yarımil / bütün il seçimi, çapda dövr yazılır; gecikmə sayı |
| 9 | Görünüş | Qlobal CSS 3–4 sütunlu sətirləri 2 sütuna sıxırdı (Mövzular, Plan, jurnalın şagird sətri, Tənzimləmələr) | Oxunmur | `jrow cols` sinfi – sütunlar kompüterdə və telefonda ayrıca |

Əvvəlki auditdən qüvvədə olanlar (reqressiya testləri ilə): qayıb/üzrlü şagirdə qiymət yox; qayıbın ev tapşırığı yoxlanmır;
gələcək dərsə yalnız mövzu və ev tapşırığı; ev tapşırığı yalnız əvvəlki günlərdən yoxlanır; KSQ tarixi yarımil içində; yarımildə bir BSQ.

## Testlər
`test_journal_grid_plan_execution_and_feedback` (jurnal səhifəsi, planın icrası, rəy, dərs qeydi, «2» səhvi, standart təhlili),
`test_journal_methodology_rules`, `test_journal_entry_rules`. Cəmi 106 test keçir.

## Açıq qalan metodik qərarlar
1. KSQ/BSQ günü formativ qiyməti tam bloklamaq (indi yalnız xəbərdarlıq).
2. Onlayn testin nəticəsini bir düymə ilə formativ qiymət kimi jurnala köçürmək.
3. Summativi üzrlü səbəbdən buraxan şagird üçün «sonradan yazdı» tarixi.
