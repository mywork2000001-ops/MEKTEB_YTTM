# Şagird hissəsinin funksional auditi — 29.09.2026

Yoxlanan hissələr: `backend/app/api/portal.py`, `materials.py` (şagird hissəsi), `journal.py` (mövzunun seçilməsi), `domain/plan.py`, `services.py`, şagird səhifələri (`frontend/src/pages/student/*`).
Üsul: kodun oxunması, avtomatik testlər (104), 6 real perspektiv planın yerli serverə yüklənib yoxlanması və telefon ölçüsündə brauzer yoxlaması (XE-001).

## 1. Dərslər perspektiv plana uyğundurmu? — əsas yoxlama

6 planın (X b, X b riyaziyyat qrupu, X c, X e, XI a, XI peşə) hər dərsinin plandakı tarixi tətbiqin həftəlik cədvəl və bayramlardan hesabladığı tarixlə müqayisə edildi:

| Sinif | Planda | Cədvəl yuvası | Tarixi fərqli | İlə sığmayan |
|---|---|---|---|---|
| X b | 172 | 172 | 0 | 0 |
| X b (riyaziyyat qrupu) | 168 | 168 | 0 | 0 |
| X c | 273 | 273 | 0 | 0 |
| X e | 237 | 237 | 0 | 0 |
| XI a | 239 | 239 | 0 | 0 |
| XI peşə sinfi | 133 | 133 | 0 | 0 |

**Nəticə: 1222 dərsin hamısı plandakı tarixə və sıraya uyğundur.** KSQ/BSQ günləri də (məs. X e: KSQ-1 05.10, KSQ-2 22.10) şagirdə plandakı gündə görünür.

Canlı saytdakı cədvəl sonradan dəyişdirilibsə, bunu artıq tətbiqin özü göstərir: **Analitika → Dərs sayı → «Planla tarix»** sütunu (hər şey düzdürsə, «uyğun»). Uyğunsuzluq olanda planda və cədvəldə nömrəsi və tarixi ilə siyahı çıxır.

## 2. Tapılan və düzəldilən səhvlər

| № | Səhv | Nəticəsi | Düzəliş |
|---|---|---|---|
| 1 | Keçmiş dərsin mövzusu jurnala yazılan plan dərsindən yox, **hazırkı** işçi plandan götürülürdü | Müəllim sonradan əvvəlki bir dərsdə «Mövzunu saxla» basanda və ya planı yenidən yükləyəndə şagird (və müəllimin jurnalı) keçmiş dərslərdə başqa mövzu görürdü | Yazılmış dərsdə jurnalda qeyd olunan plan dərsi əsasdır (`services.taught_lesson`); jurnal düzəldiləndə mövzu dəyişmir |
| 2 | Cədvəl dəyişəndə köhnə jurnal yazıları şagirdin «Dərs» və «Plan» bölməsindən itirdi | Qiymət, davamiyyət, ev tapşırığı görünmürdü | Cədvəldən kənar qalan yazılar da göstərilir («Cədvəldən kənar dərs» qeydi ilə) |
| 3 | Şagirdə plandan yalnız mövzu adı çatırdı | KSQ/BSQ nömrəsi, bölmə, dərslik səhifələri, plandakı dərs №, «mövzu davam edir» görünmürdü | «Dərs», «Plan», «Bu gün»: KSQ-1/BSQ-2, bölmə, «Dərslik: TT I, s.143», «planda №21», keçilən dərsdə ✓, tarix sürüşübsə «Planda: dd.mm», mövzu əl ilə dəyişibsə plandakı mövzu |
| 4 | Onlayn test: vaxt bitəndə avtomatik təhvil cavabları göndərmirdi, server də vaxtdan sonra gələn cavabı qəbul etmirdi | Son 0–5 saniyədə seçilən cavablar itirdi | Avtomatik təhvil son cavabları göndərir; server 10 saniyəlik şəbəkə gecikməsini qəbul edir |
| 5 | Test zamanı tətbiqdən çıxanda və ya ekran bağlananda son cavab göndərilmirdi | Son cavab itə bilərdi | Ekran gizlənəndə, səhifə bağlananda və testdən çıxanda cavablar dərhal göndərilir |
| 6 | Materiallarda fayl sahəsi `capture="environment"` idi | Telefonda birbaşa kamera açılır, PDF seçmək olmurdu | Kamera və fayl seçimi birlikdə təklif olunur |
| 7 | Arxivlənmiş sinfin materialları şagirddə görünürdü | Köhnə materiallar | Arxiv sinfi süzülür |
| 8 | «Bu gün»: ad bir sözdən ibarətdirsə «Salam, undefined!»; React açar xəbərdarlığı | Görünüş | Düzəldildi |

Yeni testlər: `test_student_lessons_follow_plan`, `test_submit_keeps_last_answers_at_deadline`, «Planla tarix» yoxlaması (`test_lesson_counts`).

## 3. Bölmələr üzrə yoxlama

| Bölmə | Vəziyyət | Qeyd |
|---|---|---|
| Giriş (kod + 4 rəqəmli PIN) | ✔ | Səhv cəhdlərdə kilid; PIN dəyişəndə ilkin PIN silinir |
| Bu gün | ✔ | Motivasiya (Bakı tarixi), imtahan sayğacı, günün dərsləri, KSQ/BSQ nişanı, açıq tapşırıqlar, müəllimlər |
| Dərs (gündəlik) | ✔ düzəldildi | Mövzu, bölmə, dərslik, ev tapşırığı, davamiyyət, qiymət, ev tapşırığının yoxlanması |
| Plan (gün/həftə/ay/yarımil) | ✔ düzəldildi | İşçi plan + jurnalda yazılan; bölünən qrupun dərsləri yalnız qrup üzvlərində |
| Tapşırıqlar (vaxtlı test) | ✔ düzəldildi | Taymer server vaxtı ilə; cavab açarı şagirdə göndərilmir; nəticə/izah yalnız icazə verilən vaxtda |
| Materiallar | ✔ düzəldildi | Başqa şagirdin cavab faylı açılmır (kodda yoxlanıb); qiymətlənmiş cavab dəyişdirilmir |
| Nəticələrim | ✔ | KSQ/BSQ bal → % → qiymət, yarımil qiyməti düsturla; səhvlərim yalnız cavablar açıldıqdan sonra |
| Analitika | ✔ | Sinif ortası adsızdır; yoldaşların adı və qiyməti göndərilmir |
| Çat | ✔ | Məxfilik testləri keçir |
| Tənzimləmələr | ✔ | PIN (yalnız 4 rəqəm), dil, rəng |

## 4. Qalan risklər və tövsiyələr (qərar tələb edir)

1. **Keçmiş tarixdə «Mövzunu saxla».** Yazılmış dərslər artıq dəyişmir, amma yazılmamış növbəti dərs eyni mövzunu yenidən göstərə bilər (işçi plan bir dərs sürüşür). Bu, qaydaya uyğundur, lakin «saxla»nı keçmiş tarixə basmamaq daha yaxşıdır.
2. **Tədris ilinin ortasında cədvəlin dəyişməsi** bütün il üçün yuvaları yenidən hesablayır. İndi uyğunsuzluq «Planla tarix» sütununda görünür; tam həll «cədvəlin qüvvəyə minmə tarixi» olardı (gələcək iş).
3. **Canlı sayt:** yuxarıdakı 0-fərq yoxlaması eyni plan və cədvəl ilə yerli bazada aparılıb. Canlı bazada müəllim bunu «Analitika → Dərs sayı → Planla tarix» sütununda görür.
4. Formativ qiymətlər onlayn test qiymətlərini avtomatik jurnala köçürmür. Bu, müəllimin qərarıdır, dəyişdirilməyib.
