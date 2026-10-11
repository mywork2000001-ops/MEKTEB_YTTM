# Sınaqlar: tarix və sinif üzrə tam düşməsi, təkrar sınaqlar, tarix filtri – audit və icra promtu

**Rol:** baş mühəndis + test bazası (viktorina) auditoru. Obyekt: `Claude/Projects/Sinaqlar` (35 sınaq, 2022/2025/2026),
`Claude/Projects/viktorina.html` (`SINAQLAR_LESSONS`, `IMPORT_SOURCES`), Müəllim köməkçisində test bazası sinxronizasiyası
(`app/bank/*`), sınaq yaratma/seriya/yenidən göndərmə (`api/exams_online.py`, `api/exam_series.py`, `api/tasks.py`).
Qayda: əvvəl uğursuz test → düzəliş → bütün testlər → lokal brauzer → commit → push.

## 0. Audit nəticələri (12.10.2026)
| № | Tapıntı | Nəticəsi |
|---|---|---|
| 1 | **Tarix bazada yoxdur** – yalnız etiketin mətnindədir («… (IX sinif, 27.09.2026)») | Sınaqları tarixə görə sıralamaq, süzmək mümkün deyil; seriya fayl nömrəsi sırası ilə gedir |
| 2 | 6 OBM sınağında sinif yoxdur (etiketdə də yox); Eltun – yalnız il, OBM – il, RF (2022) – tarix yoxdur | OBM sinfə avtomatik düşmür (təsdiq lazımdır); tarix dəqiqliyi fərqli |
| 3 | **«Yenidən göndər» / «Yazmayanlara yenidən göndər» hər dəfə YENİ sınaq paketi yaradır** | Siyahıda eyni sınaq 2–3 dəfə, nəticələr iki jurnala bölünür, reytinqdə ayrı sınaq sayılır, şagirddə iki sınaq |
| 4 | Təkrar sınaq yoxlaması yalnız fayl nömrəsinə görədir | Fayl viktorinada yerini/adını dəyişsə (yeni fayl), əvvəl verilmiş sınaq «verilməyib» sayılır |
| 5 | Mənbələr arası məzmun təkrarı – yoxlanıldı: 74 fayl (Sinaqlar + P012), yalnız Eyler IX/X/XI arasında 4–7 ümumi sual | Normaldır (eyni nəşriyyat, fərqli siniflər) – düzəliş tələb etmir |

## 1. Tarix
- [ ] `BankFile.held_on` (tarix) + `held_prec` (day | month | year): etiketdən – `dd.mm.yyyy` → gün; «sentyabr 2026» → ay;
      «(…, 2026)» / «2026 · …» → il. Sync hər dəfə yeniləyir; admin kilidi (`meta_locked`) toxunulmur.
- [ ] Viktorina: OBM etiketlərinə ay («sentyabr 2026», Sinaqlar/index.html-dəki meta ilə eyni).

## 2. Sınaq təyin edəndə filtr (istifadəçi əlavəsi)
- [ ] Sınaq seçicisində (Yeni sınaq, Avtomatik seriya): **Hamısı · İl · Ay · Həftə · Gün** + ‹ › dövr keçidi; sınaqlar
      tarixə görə (yenidən köhnəyə), hər faylda tarix nişanı; tarixi bilinməyən – «tarix yoxdur» (yalnız «Hamısı»da).
- [ ] Gün/həftə filtri yalnız günü bilinən sınaqları göstərir; ay/il – dəqiqliyə uyğun.

## 3. Təkrar sınaqlar
- [ ] «Yenidən göndər» sınağı **eyni paketə** əlavə edir (yeni sınaq yaranmır); sınaq jurnalında sinif üzrə şagirdin
      son cəhdi götürülür, «təkrar cəhd» nişanı; siyahıda bir sətir.
- [ ] Köhnə məlumat: miqrasiya – `copied_from` ilə yaranmış tək-tapşırıqlı sınaq paketləri mənbə paketinə birləşdirilir.
- [ ] «Verilib» yoxlaması məzmuna görə də: sualların mətni əvvəl verilmiş sınağın suallarının yarısından çoxu ilə üst-üstə
      düşürsə – verilmiş sayılır (fayl nömrəsi dəyişsə də).

## 4. Sinif
- [ ] OBM kimi sinfi göstərilməyən sınaqlar: seçicidə «sinfi göstərilməyib» (mövcud), admin `Tənzimləmələr → Test bazası`
      sinfi təyin edə bilər (mövcud – kilidlənir). **Sual:** OBM hansı sinif üçündür? (istifadəçi qərarı)

## 5. Yoxlama
- [ ] Testlər: tarix çıxarılması (bütün 35 etiket), filtr parametrləri, yenidən göndərmə eyni paketə, miqrasiya, məzmun təkrarı.
- [ ] Brauzer: Yeni sınaq → tarix filtri; yenidən göndərmədən sonra siyahıda bir sətir.
