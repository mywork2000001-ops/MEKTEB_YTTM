# Tapşırıq: şagird hissəsi – audit düzəlişləri (A1–A6, A8)
- Tarix: 2026-10-19   Müəllif: Rəhbər (Claude)
- İcraçı: kodcu (Agent tool)
- Budaq: main (kiçik, ardıcıl düzəlişlər)
- Audit: docs/audit-sagird-hissesi-2026-10-19.md

## Məqsəd
Şagird nəticəni müəllim açmamış görməsin, giriş PIN-i təxminə qarşı qorunsun, sinif bir Wi-Fi-dan qeydiyyatdan keçə bilsin, rusdilli şagird hər mesajı öz dilində görsün.

## Nə etmək lazımdır
1. **A1** `backend/app/api/portal.py::results`: hər imtahan üçün `hidden = e.results_published_at is None and <şagirdin bu imtahanda ExamScan sətri var (istənilən status, istənilən source)>`.
   `hidden` olanda: `points/pct/grade/taken_on = None`, `items = []`, `weak_standards = []`, `gmap[e.id] = None`, sətirdə `'hidden': True` (əks halda False).
   Yarımil qiyməti: həmin yarımildə ən azı bir `hidden` imtahan varsa `semester_grades[k] = None`.
   `absent` və `card` (`_card` artıq özü gizlədir) olduğu kimi qalır.
   Frontend `Results.tsx`: `e.hidden` olanda bal xanasında `t('müəllim açanda görünəcək')` (kiçik, muted). `Analytics.tsx` printReport-da da hidden sətirdə «—».
2. **A2** `backend/app/api/auth.py::login`: IP üzrə səhv giriş limiti (invites.py-dəki `_attempts` üslubunda, modul səviyyəsində dict): 10 dəq. pəncərədə bu IP-dən 30 səhv giriş olubsa → 429 `'Çox səhv cəhd. 10 dəqiqədən sonra yenidən yoxlayın'`. Yalnız səhv cəhd əlavə olunur; IP: `request.client.host`. Lüğətdə köhnə mesajlar da olmalıdır (bənd 5).
3. **A3** `backend/app/api/invites.py::join`: limit `10` → `60` (10 dəq.), şərhdə səbəb (sinif bir Wi-Fi).
4. **A4** `portal.py`: şagirdə görünən bütün `HTTPException` mesajları `_L(user, az, ru, en)` ilə (`me_student` – `user` artıq var; `_task_for`, `_open_attempt`, `start`, `save_answers`, `review`, `upload_solution`, `solution_response` – lazım olsa `user`/dil parametri əlavə et; `_L` faylda artıq var – yuxarı köçür). `/me` → `personal` mətni də `_L` ilə (3 variant × 3 dil). Motivasiya frontenddə `tt()` ilə gedir – dəyişmə.
   `materials.py` şagird marşrutları (`my_materials`, `submit`, `get_file` şagird qolu) – mesajlar eyni üsulla (lokal `_L` köməkçisi, `user.language`).
5. **A4/A5** Frontend (`t()`/`tt()` + `frontend/src/i18n.ts` lüğəti, `'AZ': ['EN', 'RU']`, təkrar açar olmasın – əvvəl Grep et):
   - `Login.tsx`: «Müəllim», «Kim daxil olur», «məs. M-001», «Məsələn: XE-001», «4 rəqəm», «Xəta baş verdi»; xəta mesajı `tt(x.message)` (server mesajları: 'Login və ya parol səhvdir', 'Çox səhv cəhd. 15 dəqiqədən sonra yenidən yoxlayın', 'Çox səhv cəhd. 10 dəqiqədən sonra yenidən yoxlayın' lüğətə). Məktəb adı və «Müəllim köməkçisi» – AZ qalır.
   - `QrLogin.tsx`: «Daxil olunur…», «Kod və PIN ilə daxil ol», «QR kod işləmədi», server mesajı `tt()` (QR mesajı lüğətə).
   - `Join.tsx`: bütün mətnlər (başlıq, «{c} sinfi», form, gender seçimi – dəyər 'Qız'/'Oğlan' dəyişmir, yalnız etiket), uğur ekranı; server mesajları `tt(x.message)` + invites.py-dəki şagirdə görünən mesajlar lüğətə. Join səhifəsində dil seçimi yoxdur – Login-dəki `LANGS` chip-ləri kimi kiçik dil seçici əlavə et (App.tsx-də Login-ə necə `lang/setLang` ötürülürsə, eyni yolla; mümkün deyilsə – yalnız tərcümə, brauzer dili ilə).
   - `Materials.tsx`: «Material yoxdur.», «Son vaxt:», «gecikib».
   - `studentPrint.ts` və `Analytics.tsx::printReport`: bütün başlıq/sütun/qeyd mətnləri `tt()` ilə (şagirdin öz çapı – rəsmi sənəd deyil).
6. **A6** `materials.py::submit`: `text` > 5000 simvol → 400 (RU/EN ilə).
7. **A8** `materials.py::my_materials`: şagird cavabında `student_ids` açarı çıxarılsın (müəllim cavabı dəyişmir).

## Toxunma (dəyişmə)
- Müəllim marşrutları və müəllim səhifələri, `certificate.tsx`, `/portal/analytics` hesablaması (A7 – qərar gözləyir), DB sxemi (miqrasiya YOX).

## Kontekst (yalnız bunları oxu)
- `backend/app/api/portal.py` (results 678–726, _L 579, _card 480)
- `backend/app/api/auth.py`, `backend/app/api/invites.py:95–130`, `backend/app/api/materials.py:170–240`
- frontend fayllar yuxarıda; `frontend/src/i18n.ts` – yalnız Grep (tam oxuma!)
- Testlər: `backend/tests/test_api_portal.py`, `test_api_auth.py`, `test_api_materials.py`, `test_api_qr_login.py`

## Qəbul meyarları
- [ ] Yeni testlər: (a) skanı olan nəşr olunmamış imtahanda `/portal/results` bal/✓✗/yarımil qiyməti `None`/boş, nəşrdən sonra görünür; skansız (əl ilə) imtahan əvvəlki kimi görünür; (b) 30 səhv girişdən sonra eyni IP-dən 429, düzgün parol da 429; (c) RU dilli şagird – başlanmamış tapşırığa `start` → rus mesajı; (d) materials mətn > 5000 → 400; (e) `/portal/materials` cavabında `student_ids` yoxdur.
- [ ] Mövcud testlər: `pytest backend/tests/test_api_portal.py backend/tests/test_api_portal_method.py backend/tests/test_api_auth.py backend/tests/test_api_qr_login.py backend/tests/test_api_materials.py backend/tests/test_audit_appeal.py -q` ok (login limiti dict-i testlər arasında sıfırlansın – conftest/fixture).
- [ ] Yeni mətnlər AZ/EN/RU; lüğətdə təkrar açar yoxdur
- [ ] `npm run build` (frontend) ok

## Cavab formatı
Qısa: dəyişən fayllar, test nəticəsi (son sətirlər), build nəticəsi, açıq qalanlar. Commit ETMƏ.
