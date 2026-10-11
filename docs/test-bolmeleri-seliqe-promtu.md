# Onlayn tapşırıqlar, Sınaq imtahanları, Test nəticələri – səliqə və optimallaşdırma promtu

**Rol:** UX dizayner + baş mühəndis. Məqsəd: müəllim üç bölmədə «nə harada?» sualını verməsin – hər bölmənin bir işi olsun,
eyni nəticə bir yerdə, eyni formada görünsün, ekranlar az klik və az düymə ilə işləsin, serverə yük azalsın.
Hər dəyişiklik: test → lokal brauzerdə (noutbuk + 393 px) yoxlama → commit. Qaydalar `docs/test-sinaq-audit-promtu.md`-dəki kimi.

## 0. Tapılan qarışıqlıq (11.10.2026, lokal test bazası: 3 sinif × 8 şagird, 5 mövzu testi, 4 sınaq)
1. **Onlayn tapşırıqlar** boş açılır – sinif seçmədən heç nə görünmür; 6 sinifli müəllim hər sinfi ayrıca açır.
   3 sıra filtr (sinif, «Mövzu testləri / Silinənlər», dövr); hər testdə 6 düymə; «+ Yeni» yoxdur (yalnız mətnlə izah).
2. **Eyni nəticə 3 yerdə 3 formada:** «Canlı izlə» (tapşırıq), «Sınaq jurnalı» (sınaq), «Test nəticələri → Reytinq».
   Sınaq üçün «Canlı izlə» cərimə­siz faiz və **qiymət** göstərir – sınaq jurnalı isə cərimə ilə, qiymətsiz.
3. **Reytinq iki yerdə:** «Sınaq imtahanları → Reytinq» və «Test nəticələri → Reytinq» (eyni panel).
4. **Sınaq jurnalı** nəticədən əvvəl «Testi idarə et» bloku (hər sinifə 5 düymə) – əsas məlumat aşağı düşür.
5. **Reytinq ədalətsizdir:** 4 testdən 2-ni yazan şagird 1-ci yer (xroniki yazmır nişanı ilə) – iştirak nəzərə alınmır.
6. Sınaq siyahısında vəziyyət filtri yoxdur (açıq / gözlənilir / bitib) – açıq sınaq siyahıda itir.
7. Server: sınaq siyahısı hər paket üçün 6–8 sorğu (N+1), tapşırıqlar hər test üçün ayrıca sorğu – Neon-da gecikmə.

## 1. Bölmələrin rolu (alt başlıqda bir cümlə)
- **Onlayn tapşırıqlar** – perspektiv planın mövzu testləri: təyin etmək (plandan), izləmək, idarə etmək.
- **Sınaq imtahanları** – plandan kənar sınaqlar və avtomatik seriyalar: yaratmaq, sınaq jurnalı.
- **Test nəticələri** – yeganə analitika yeri: reytinq, yazmayanlar, şagird, sinif, ümumi.

## 2. Onlayn tapşırıqlar
- [ ] Defolt **«Bütün siniflərim»** – bütün dərslərin mövzu testləri bir siyahıda (sinif nişanı ilə); sinif seçimi filtrdir.
- [ ] Vəziyyət çipləri sayla: **Açıq · Gözlənilir · Bağlanıb · Hamısı**; «Silinənlər» – siyahının altında kiçik keçid.
- [ ] Sətir: əsas düymə (**Canlı izlə** / **Nəticələr**) + **Link** + **⋯** (Yenidən göndər, Kağız variant, Redaktə, Sil).
- [ ] «+ Mövzu testi təyin et» → Perspektiv plan.
- [ ] Server: `GET /api/tasks/mine` – bir sorğu ilə bütün dərslər; təhvil sayı və orta bir qruplaşdırılmış sorğu ilə.

## 3. Sınaq imtahanları
- [ ] Bölmələr: **Sınaqlar · Avtomatik seriyalar** (Reytinq → «Test nəticələri»nə keçid düyməsi).
- [ ] Vəziyyət çipləri sayla (Açıq · Gözlənilir · Bitib · Hamısı).
- [ ] Sınaq jurnalı: əvvəl nəticə (KPI, jurnal); sinif idarəsi «Siniflər» bölməsində kompakt sətir + ⋯.
- [ ] «Canlı izlə» sınaqda: faiz cərimə ilə, qiymət yoxdur (jurnalla eyni).
- [ ] Server: siyahı – paketlər, tapşırıqlar, siniflər və cəhdlər toplu sorğularla (N+1 yox).

## 4. Test nəticələri
- [ ] Filtrlər bir sırada: Növ · Dövr · Sinif · Sıralama.
- [ ] Reytinqdə **yer yalnız verilən testlərin yarısından çoxunu yazana** (yarısını yazan «xroniki» sayılır – ziddiyyət olmasın); az yazan sonda, yersiz
      (həm mövzu testləri, həm sınaqlar; sinifdə yer də).
- [ ] «0,0 bənd» – səs-küy: dinamika 0 olanda sadə «0».

## 5. Yoxlama
- [ ] Backend testləri (yeni: `/api/tasks/mine`, reytinqdə iştirak qaydası, sınaqda Canlı izlə faizi), `tsc`, build.
- [ ] Brauzer: üç bölmə, noutbuk + 393 px, konsolda xəta yox; hesabat bu sənədin sonunda.

## Sual kimi saxlananlar
- Menyu adı «Onlayn tapşırıqlar» → «Mövzu testləri»? (İstifadəçi adı tanıyır – dəyişmirəm, alt başlıq izah edir.)
- Reytinq üçün iştirak həddi 50% – məktəb fərqli hədd istəsə, Parametrlərə çıxarmaq olar.

## Hesabat (12.10.2026 – icra olundu)
| Bölmə | Əvvəl | İndi |
|---|---|---|
| Onlayn tapşırıqlar | Boş ekran, sinif seçmək məcburi; 3 sıra filtr; hər testdə 6 düymə; «+ Yeni» yox | «Bütün siniflərim» defolt (sinif nişanı ilə); vəziyyət çipləri sayla; açıq testlər yuxarıda; 3 element (Canlı izlə/Nəticələr, Link, ⋯); «+ Mövzu testi təyin et»; «🗑 Silinənlər» altda |
| Sınaq imtahanları | Reytinq təkrarı; vəziyyət filtri yox; jurnalda əvvəl idarə bloku | «Reytinq →» Test nəticələrinə; vəziyyət çipləri; açıq sınaq yuxarıda; jurnal nəticə ilə açılır, idarə «Siniflər və idarə»də (⋯ ilə) |
| Canlı izlə (sınaq) | Cərimə­siz faiz + qiymət | Jurnalla eyni: cərimə ilə, qiymətsiz |
| Test nəticələri | Reytinqdə 4-dən 2-ni yazan 1-ci yer («xroniki» ilə); 3–4 sıra filtr; «0,0 bənd» | Yer – yarısından çoxunu yazana; filtrlər bir yerdə; 0 dinamika sadə «0»; `?kind=` keçidi |
| Server | Sınaq siyahısı N+1 (hər paket 6–8 sorğu); tapşırıqlar sinif-sinif | Sınaq siyahısı 3 toplu sorğu; `GET /api/tasks/mine` – bütün dərslər toplu sorğularla |

Testlər: `tests/test_api_tests_tidy.py` (bütün siniflər, iştirak qaydası, sınaqda Canlı izlə, toplu siyahı) – hamısı 221 keçir.
Brauzer (lokal test bazası, noutbuk): üç bölmə, ⋯ menyu, silmə → Silinənlər → geri qaytarma, sınaq jurnalı, Canlı izlə.
393 px brauzerdə yoxlanmadı (Chrome pəncərəsi kiçilmədi, iframe təhlükəsizlik başlığı ilə bağlıdır) – yeni elementlər `flex-wrap`, seçim ≤ 280 px, menyu ≤ ekran eni.
