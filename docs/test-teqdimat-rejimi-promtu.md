# Test təqdimat rejimi (Google Meet üçün) – müəllimin testə baxışı və şagirdlərlə birlikdə işləmə

> Tarix: 04.10.2026. Təcili tapşırıq. Müəllimin sözü: «tətbiqdə testlərə müəllim üçün baxış imkanı – Google Meet-də testi
> şagirdlərlə işləyəndə şagirdlər görə bilsinlər (müəllim işləməyini paylaşa bilsin)».

## 0. Rol və məqsəd

Sən bu layihənin (FastAPI + SQLAlchemy, React + Vite, KaTeX) aparıcı mühəndisi və onlayn dərs üzrə UX mütəxəssisisən.
Məqsəd: müəllim istənilən testi **ayrıca, təmiz pəncərədə** açsın, onu Google Meet-də «Bu tabı paylaş» ilə göstərsin və
şagirdlərlə sual-sual həll etsin. Ekranda yalnız sual görünür. Düzgün cavab, izah və statistika yalnız müəllim düymə basanda
açılır. Şagird adları, PIN, giriş kodları və menyu ekranda heç vaxt görünmür.

Mövcud qaydaları POZMA:
- düzgün cavablar şagirdə getmir (yalnız `staff`);
- məxfilik (`own_assignment`, sınaqda `exams_online._access`, `ws_cond` – məktəb və fərdi məkan qarışmır);
- testin özü, cəhdlər və nəticələr bu rejimdə dəyişmir (yalnız oxuma).

Hazırda müəllimin testə baxışı yalnız redaktə (`GET /api/tasks/{ta}/{task}/full`) və «Kağız variant» (çap) şəklindədir.
Bunlar ekranda paylaşmaq üçün yararsızdır: kiçik şrift, cavablar açıq, menyu görünür.

## 1. Haradan açılır («Təqdim et (Meet)» düyməsi)

| Yer | Nə açılır |
|---|---|
| Onlayn tapşırıqlar – hər testin sətri | həmin test (səviyyə variantı varsa – variant seçimi) |
| Sınaq imtahanları – sınaq kartı / nəticələr pəncərəsi | sınağın sualları |
| Perspektiv plan – mövzunun «🧪» test vəziyyəti | həmin mövzu testi |
| Test bazası (BankPicker) – fayl önbaxışı | bazadakı fayl (test təyin etmədən də, dərsdə nümunə üçün) |
| Silinənlər (arxiv) | arxivdəki mövzu testi |

Düymə testi **yeni tabda** açır: `/present/task/{task_id}` və ya `/present/bank/{file_id}`. Bu marşrut tətbiqin ümumi
`Layout`-unu istifadə etmir: yan menyu, alt naviqasiya, istifadəçi adı və bildirişlər yoxdur. Müəllim Meet-də «Bu tabı
paylaş» seçir, öz tətbiqi isə başqa tabda gizli qalır.

## 2. Təqdimat ekranı

**Slayd:** bir sual bir ekranda.
- Böyük şrift: əsas ölçü 28–32 px, «A− / A+» ilə 3 ölçü.
- KaTeX (`MathText`), şəkil ekrana sığır.
- Variantlar A), B), C)…; açıq sualda «Cavab: ____» sahəsi.

**Yuxarı zolaq:** testin adı, «Sual 3 / 12», fənn və sinif. Şagird adı yoxdur.

**İdarə** (aşağıda, yarı şəffaf; paylaşılan tabda görünür, ona görə sadə olmalıdır):
- `←` / `→`, «Əvvəlki / Növbəti»;
- sual nömrələri zolağı (keçid);
- «Cavabı göstər» – düzgün variant yaşıl çərçivə ilə vurğulanır, açıq sualda cavab yazılır;
- «İzahı göstər» – bazadakı `explanation` (KaTeX ilə);
- «Statistika» – yalnız test bağlanandan sonra: bu sualı düz həll edənlərin faizi və variantların paylanması. Adsız: «A – 4, B – 12…»;
- «Taymer» – sual üçün 1/2/3/5 dəqiqə geri sayım (səs yoxdur, sonda yumşaq vurğu);
- «Tam ekran» (Fullscreen API, `F` düyməsi);
- «Qaranlıq / açıq» fon (Meet-də kontrast üçün);
- «Lövhə» (II mərhələ): sualın üstündə qələm, marker, silgi, «Təmizlə» (canvas, pointer events, planşet qələmi də). Yazılan
  hər sualda ayrıca qalır, yaddaşa yazılmır.

**Təhlükəsizlik (vacib):**
- cavab, izah və statistika açılışda **həmişə bağlıdır**; slayd dəyişəndə yenidən bağlanır;
- test **hələ açıqdırsa** (şagirdlər yazır) – «Cavabı göstər» və «Statistika» bağlıdır. Onları açmaq üçün təsdiq lazımdır:
  «Test hələ açıqdır – şagirdlər yazır. Cavabı göstərmək testi etibarsız edə bilər. Yenə də göstərilsin?» Bu hal
  audit jurnalına yazılır (`present_reveal_open`);
- şagird adları, giriş kodları, PIN, valideyn məlumatı bu səhifədə ümumiyyətlə yüklənmir (API qaytarmır);
- səhifə yalnız müəllimə (`staff`) açılır. Şagird linki açsa – 404.

**Sıra:** təqdimat bazadakı/testdəki əsl sıra ilə gedir. Şagirdlərdə suallar qarışdırılıbsa (`shuffle`), ekranda
qeyd olunur: «Şagirdlərdə sıra fərqlidir – sualı mətnindən tapın». Hər slaydda sualın ilk sözləri iri yazılır.

**Variantlar:** səviyyə variantlı (Zəif / Orta / Güclü) testdə yuxarıda variant seçimi.

**Klaviatura:** `←/→`, `Space` (növbəti), `C` (cavab), `E` (izah), `S` (statistika), `F` (tam ekran), `+/−` (şrift),
`Esc` (tam ekrandan çıxış).

**Telefon / planşet:** sürüşdürmə ilə slayd keçidi. Meet-i telefondan paylaşan müəllim üçün idarə düymələri aşağıda.

## 3. Backend

- `GET /api/present/task/{task_id}` – icazə: tapşırıq müəllimin öz dərsindədir (`own_assignment`) və ya sınaq paketinə
  çıxışı var (`_access`). Qaytarır:
  - `{title, subject, class_name, kind, opens_at, closes_at, state, shuffle, variant, questions: [{index, kind, text,
    options, image, correct, answer, explanation}]}`;
  - bir paketdə bir neçə variant varsa – `variants: [{task_id, label}]`.
- `GET /api/present/task/{task_id}/stats` – yalnız test bağlanandan sonra (və ya `?force=1` – audit ilə). Sual üzrə:
  `{index, correct_pct, of, options: {0: n, 1: n…}, blank}`. Ad yoxdur. Mövcud `tasks.task_results` → `per_q`-dan genişləndir.
- `GET /api/present/bank/{file_id}` – bazadakı faylın sualları (aktiv suallar, `n` sırası ilə), `correct` daxil.
- Audit: `present_open` (task/bank, id), `present_reveal_open` (açıq testdə cavab göstərildi).
- Testlər (pytest): icazə (yad müəllim 404, şagird 401/403, başqa məkan 404); açıq testdə `stats` bağlı, bağlıda var;
  cavabda şagird adı və kodu yoxdur; bank faylı; variant siyahısı.

## 4. Frontend

- `src/pages/teacher/Present.tsx` – `Layout`-suz marşrut (`App.tsx`-də müəllim marşrutlarından əvvəl).
- `src/present.css` – iri şrift, yüksək kontrast, `@media (prefers-color-scheme)` + əl ilə «qaranlıq / açıq».
- Düymələr: `Tasks.tsx` (sətir və `TaskActions`), `OnlineExams.tsx`, `Plan.tsx` (test vəziyyəti), `TaskEditor.tsx`
  (BankPicker önbaxışı), `ExtraCourses.tsx` (məşğələdə bağlı test/material varsa).
- Açılış: `window.open('/present/task/ID', '_blank')`. Pəncərə bloklanarsa – link göstər.
- Yoxlama: `npx tsc -b`, `npm run build`, brauzer 1920×1080 (Meet paylaşımı), 1366 və 360 px; Meet-də real «Bu tabı paylaş»
  sınağı (müəllim edir).

## 5. Qəbul meyarları

1. Hər üç yerdən (Onlayn tapşırıqlar, Sınaq imtahanları, Test bazası) bir kliklə ayrıca tabda açılır.
2. Açılışda heç bir cavab, izah, statistika, şagird adı görünmür. Menyu və istifadəçi adı yoxdur.
3. Açıq testdə cavab yalnız xəbərdarlıq və təsdiqdən sonra açılır, audit yazılır.
4. Bağlanmış testdə «Statistika» variantların paylanmasını adsız göstərir.
5. Riyaziyyat düsturları və şəkillər 1920×1080-də oxunaqlıdır. Klaviatura qısayolları işləyir.
6. Mövcud 196 test + yeni testlər keçir. Tip yoxlaması və build təmizdir.

## 6. Mərhələlər

1. Backend (`api/present.py`, 3 endpoint, audit) + testlər.
2. `Present.tsx`: slayd, naviqasiya, cavab / izah, tam ekran, şrift, fon, klaviatura.
3. Düymələr bütün giriş nöqtələrinə; açıq testdə xəbərdarlıq; statistika.
4. II mərhələ: «Lövhə» (qələm və marker), taymer.
5. Yoxlama (pytest, tsc, build, brauzer), commit, müəllim üçün izah səhifəsinə və videoya bir səhnə əlavəsi.

## 7. Açıq suallar (default seçimlərlə – müəllim dəyişə bilər)

- Açıq testdə cavabı göstərmək tam qadağan olsun, yoxsa təsdiqlə? **Default: təsdiqlə + audit.**
- Statistika test bağlanmamış göstərilsin? **Default: yox** (yalnız bağlanandan sonra).
- Lövhədəki yazılar saxlanılsın? **Default: yox** (yalnız ekranda; istəyə görə «PNG kimi yüklə»).
