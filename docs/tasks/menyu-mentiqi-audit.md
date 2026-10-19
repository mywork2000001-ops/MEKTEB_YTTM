# Kart: menyu bölmələrinin məntiqi auditi və yenidən qruplaşdırma (19.10.2026)

İstifadəçi: «Ünsiyyət bölməsində Tənzimləmə niyə olsun? Məntiqi audit apar, hər bölməni uyğunlaşdır, öz əlavələrini et.»
Fayllar: `frontend/src/Layout.tsx` (TEACHER_NAV, STUDENT_NAV, TEACHER_TABS), `frontend/src/pages/teacher/Settings.tsx`,
`frontend/src/pages/teacher/Plan.tsx`, `frontend/src/pages/teacher/Classes.tsx`, `frontend/src/styles/extra.css`, `frontend/src/i18n.ts`.

## Audit – tapılan uyğunsuzluqlar
| № | Problem | Səbəb |
|---|---|---|
| A1 | «Tənzimləmələr» «Ünsiyyət» qrupundadır | Tənzimləmə ünsiyyət deyil; sadəcə siyahının sonuna düşüb |
| A2 | «Şagird sorğusu» «Qiymətləndirmə»dədir | Sorğu – şagirddən rəy (əks əlaqə), qiymət deyil → Ünsiyyət |
| A3 | «Materiallar» «Siniflər»dədir | Material – dərsə hazırlıq resursu, sinif idarəsi deyil → Planlaşdırma |
| A4 | «Dərs» qrupunda 5 bənd: gündəlik iş (Jurnal, Cədvəl) və planlaşdırma (Perspektiv, Gündəlik plan) qarışıqdır | İki fərqli iş növü |
| A5 | Tənzimləmədə 12 nişan bir sırada: şəxsi (Görünüş, Hesab, Kilid, AI), məktəb məlumatı (Məktəb, Siniflər, Şagirdlər, Proqramlar, Arxiv), admin (Müəllimlər, Test bazası, Audit) | Axtarmaq çətindir |
| A6 | «Proqramlar» yalnız Tənzimləmədədir, Perspektiv plandan keçid yoxdur; «Siniflər və qruplar» səhifəsindən sinif/şagird siyahısını redaktəyə keçid yoxdur | Müəllim harada olduğunu bilmir |
| A7 | Eyni ikonlar: Siniflər = Sinif rəhbəri (`classes`); şagirddə Uğurlarım = Sorğular (`star`) | Gözlə ayırmaq olmur |
| A8 | Telefon alt paneli (müəllim): Əsas, Jurnal, Çat, Hesabat – «Testlər» ən çox işlənən bölmələrdən biridir, yoxdur | |
| A9 | Şagird menyusu 12 bənd, qrupsuz | Müəllim menyusu ilə ziddiyyət |

## Yeni quruluş
**Müəllim (yan panel):**
- **Dərs:** Əsas səhifə · Jurnal · Həftəlik cədvəl
- **Planlaşdırma:** Perspektiv plan · Gündəlik plan · Materiallar
- **Qiymətləndirmə:** Testlər və sınaqlar · Analitika və hesabat
- **Siniflər:** Siniflər və qruplar · Sinif rəhbəri (ikon `students`)
- **Ünsiyyət:** Çat · Şagird sorğusu
- **Tənzimləmələr** – qrupsuz, yan panelin aşağısında, «Çıxış»ın üstündə sabit sətir (akkordeona düşmür); telefonda «Daha çox»un sonunda ayrıca.

Telefon alt paneli müəllim: Əsas · Jurnal · Testlər · Çat (+ Daha çox). Hesabat «Daha çox»-da qalır.

**Şagird (eyni NavGroups komponenti, qruplu):**
- **Bu gün:** Bu gün · Dərs · Tapşırıqlar
- **Öyrənmə:** Materiallar · Əlavə məşğələlər · Plan
- **İnkişafım:** Nəticələrim · Uğurlarım · Analitika
- **Ünsiyyət:** Çat · Sorğular
- **Tənzimləmələr** – qrupsuz, aşağıda (müəllimdəki kimi).
Defolt açıq qrup – «Bu gün» (müəllimdə «Dərs»); aktiv səhifənin qrupu həmişə açıq. Şagird alt paneli dəyişmir.
İkon: şagird Sorğular → `feedback` deyil (çat) – `mic` və ya `overview`; uyğun SVG-yə bax, Uğurlarım `star` qalır.

**Tənzimləmələr səhifəsi:** nişanlar 3 alt-başlıq altında (eyni sətir/nişan üslubu, kiçik qrup etiketi):
«Şəxsi» – Görünüş, Hesab, Kilid, Süni intellekt · «Məktəb məlumatları» – Məktəb/Fərdi məkan, Siniflər, Şagirdlər, Proqramlar, Arxiv ·
«Admin» (yalnız admin) – Müəllimlər, Test bazası, Audit jurnalı. Nişan açarları (`?tab=`) dəyişmir; kilid məntiqi dəyişmir.

**Keçidlər (A6):** Perspektiv plan başlığında kiçik düymə «Proqramlar» → `/settings?tab=programs`; «Siniflər və qruplar»
başlığında «Sinif və şagird siyahısı» → `/settings?tab=classes`.

## Qaydalar
- Marşrutlar, səhifə məzmunu, API dəyişmir – yalnız menyu quruluşu, ikonlar, nişan qruplaşması, 2 keçid düyməsi.
- Yeni mətnlər AZ/EN/RU (`i18n.ts`, təkrar açar yoxdur): Planlaşdırma / Planning / Планирование; Öyrənmə / Learning / Учёба;
  İnkişafım / My progress / Мой прогресс; Şəxsi / Personal / Личное; Məktəb məlumatları / School data / Данные школы;
  «Bu gün» qrup adı mövcud açardır; Proqramlar, Admin mövcuddursa yenidən əlavə etmə.
- Köhnə localStorage (`mk-nav-open`) açarları zərərsizdir.
- Yoxlama: `npm run build` (frontend) uğurlu.
