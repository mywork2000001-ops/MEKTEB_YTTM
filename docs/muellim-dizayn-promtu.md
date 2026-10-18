# Müəllim interfeysi — dizayn optimallaşdırması (18.10.2026)

Rol: sən UI/UX dizaynerisən və frontend mühəndisisən (React 19 + Vite, öz CSS-i `frontend/src/styles/app.css`, `extra.css`).
İstifadəçi: məktəb müəllimi, gündə 5–6 dərs, əsasən noutbuk (1366×768 və ya 1396×663 kimi alçaq ekran) və telefon.
Məqsəd: **hər gün lazım olan işə (jurnal, test, plan) daha az klik, daha az boş yer, bir dildə interfeys.**
Funksionallıq, API, URL-lər və DB DƏYİŞMİR. Yalnız görünüş, düzülüş və mətn.

## Canlı saytda tapılanlar (müəllim/admin, RU dili, 18.10 ekran şəkilləri)
1. **Dil qarışığı (ən böyük problem).** RU seçiləndə yarım ekran AZ qalır: menyu «Gündəlik plan», «Testlər və sınaqlar»;
   başlıq altı yazılar «Sinif və ya qrup seçin», «Mövzu testləri, sınaq imtahanları…», «Sinif, bölünmə qrupu…»;
   Əsas səhifə «Bu həftə diqqət», «son 7 gündə yazılmayıb», «qırmızı risk», «Oxudum», «Bu gün dərs yoxdur»;
   seçici «— Класс / группа seçin —» (yarım RU, yarım AZ: `common.tsx:29` `— {label} seçin —` şablonu);
   Analitika «Sinif / fənn», «Məktəb üzrə»; Testlər filtr sətri «Sinif və mövzu üzrə», «açıqdır», «Canlı izlə», «Redakte»…
2. **Boş ekranlar.** Jurnal və Analitika açılanda yalnız bir açılan siyahı və «Сделайте выбор выше» — ekranın 80 %-i boşdur,
   hər dəfə əlavə klik lazımdır.
3. **Menyu uzun və qruplaşmayıb** (13 bənd, alçaq ekranda «Tənzimləmələr» görünmür; «Классный руководитель» iki sətrə düşür).
4. **Sinif kartlarında təkrar**: hər kartda «Müəllim: Hasanov Farid Oktay oğlu (Riyaziyyat)» — müəllim özüdür, məlumat yoxdur.
5. Testlər səhifəsində iki filtr sətri (status + dövr) üst-üstə, səhifə başlığından əvvəl çox hündürlük gedir.

## Qərarlar (rəhbərin həlli — icra et)
A. **i18n tam əhatə (müəllim səhifələri + Layout + common).** Müəllimə görünən bütün AZ sabit mətnləri `t('…')` / `tt('…')`
   ilə, lüğətə EN+RU (CLAUDE.md qaydası). Seçici şablonu: `t('— {x} seçin —', { x: t(label) })` əvəzinə tam ifadə açarları
   (`'— Sinif / qrup seçin —'` və s.) — RU-da «— Выберите класс / группу —». Rəsmi çap formaları (jurnal çapı, perspektiv plan,
   ClassListPrint, JournalPrint, SchoolReport çapı) AZ qalır — toxunma.
B. **Menyu qrupları** (`TEACHER_NAV`-a `group` sahəsi, sidebar-da kiçik başlıqlar, telefonda «Daha çox» da qruplu):
   «Dərs» — Əsas səhifə, Jurnal, Gündəlik plan, Perspektiv plan, Həftəlik cədvəl;
   «Qiymətləndirmə» — Testlər və sınaqlar, Analitika və hesabat, Şagird sorğusu;
   «Siniflər» — Siniflər və qruplar, Sinif rəhbəri, Materiallar;
   «Ünsiyyət» — Çat, Tənzimləmələr. Naviqasiya bəndləri sıxlaşır (min-height 36px, nav scroll edə bilir, sidebar alt hissəsi
   həmişə görünür). Uzun adlar bir sətirdə (ellipsis + title).
C. **Sinif seçimi boş qalmasın** (Jurnal, Analitika və eyni `ClassPicker`/seçicini işlədən səhifələr): seçim yoxdursa
   select-in altında müəllimin sinif/qruplarının **sürətli seçim düymələri** (sinif rəngi `--cc` ilə chip); son seçilən sinif
   `localStorage`-da yadda qalır (try/catch) və növbəti açılışda avtomatik seçilir. Boş vəziyyət mətni: «Sinif seçin».
D. **Sinif kartı**: müəllim cari istifadəçidirsə «Müəllim» sətri əvəzinə «Siz»; ad yalnız başqa müəllimdirsə.
E. **Sıxlıq (alçaq ekran)**: `@media (max-height:760px)` — səhifə başlığı/padding kiçilir, topbar 52px, kartlar arası 12px.
   Testlər səhifəsində status chip-ləri və dövr seçicisi bir sətirdə (sığmasa wrap).
F. Rəng/şrift sistemi saxlanılır (yaşıl tema, Literata başlıqlar, Noto Sans). Yeni rəng kodu yox — yalnız mövcud tokenlər.
   Dark mode və `.big` şrift rejimi pozulmamalıdır; telefon (≤640px) tabbar dəyişmir.

## Yoxlama
- `cd frontend && npm run build` (tsc -b) — xətasız; lüğətdə təkrar açar yoxdur.
- Backend dəyişmir → pytest lazım deyil.
- Hesabat: dəyişən fayllar, əlavə edilən lüğət açarlarının sayı, qalan AZ mətnlər (əgər qəsdən saxlanılıbsa — niyə).
