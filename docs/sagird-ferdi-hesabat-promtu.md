# Şagirdin fərdi hesabatı – mövzu testləri və adı ilə sınaqlar · audit + promt (19.10.2026)

**Rol.** Sən «Müəllim köməkçisi»nin baş mühəndisi, qiymətləndirmə mütəxəssisi və riyaziyyat metodistisən. Məqsəd: hər şagird üçün
**bir yerdə tam hesabat** – mövzu testləri (mövzu nömrəsi və adı ilə), sınaqlar (konkret adı ilə: «ÜSİ-1», «MSİ-2», «Buraxılış
sınağı №3» …), KSQ/BSQ, yazılı (kağız, skan) nəticələr; trend, sinif ortası ilə müqayisə, zəif mövzular, tövsiyə; çap və valideyn
nüsxəsi.

## 0. Sabit qaydalar
- Məxfilik: hesabatı yalnız şagirdi görməyə haqqı olan (`can_see_student`) görür; fərdi məkanın nəticələri məktəb hesabatına düşmür;
  <5 şagirdli qrupda sinif ortası gizli (mövcud qayda); nəşr olunmamış skan balı şagirdə/valideynə görünmür.
- Mövcud reytinq, «Nəticələr» bölməsi və jurnal qiymətləri dəyişmir – hesabat yalnız oxuyur və birləşdirir.
- UI AZ/EN/RU; valideyn nüsxəsi AZ və ya RU (şagirdin dilinə görə); rəsmi çap – AZ.
- Yoxlama: aid pytest + `npm run build`. Canlı DB-yə yazı yoxdur (yalnız oxu).

## 1. Audit (kod, 19.10.2026)
| # | Tapıntı | Yer |
|---|---|---|
| H1 | Şagird profili (`/results/student/{sid}`) yalnız **onlayn** tapşırıqları (`OnlineTask`: `movzu`, `sinaq`) toplayır | `test_stats.collect`, `results_center._student_data` |
| H2 | Kağız/skan imtahanları (`Exam`, `ExamScore`, `ExamScan`: KSQ, BSQ, yazılı TEST/SINAQ, `ExamSeries`) şagird profilinə **düşmür** | `models.py:434–584` |
| H3 | Sınaq adı = tapşırığın/paketin sərbəst başlığı; seriya (`ExamSeries`) və bank faylının adı (ÜSİ-1, MSİ …) ilə vahid ad yoxdur – eyni sınaq müxtəlif siniflərdə müxtəlif adla görünə bilər | `collect` → `title` |
| H4 | Mövzu testində mövzu = plan dərsinin `topic` mətni; mövzu **nömrəsi** (bölmə.mövzu) və sinfi yoxdur – zəif mövzular siyahısı sıralanmır, təkrarlanan adlar qarışır | `_student_data.topics` |
| H5 | Trend (son N nəticə), sinif ortası ilə fərq var, amma sınaq seriyası üzrə irəliləyiş (1-ci → 2-ci → 3-cü sınaq) yoxdur | — |
| H6 | Çap / PDF / valideyn nüsxəsi və tövsiyə bloku yoxdur | — |

## 2. Həll
### 2.1 Vahid nəticə modeli (oxu qatı, miqrasiyasız)
`app/student_report.py` → `student_results(db, user, sid, date_from, date_to)` qaytarır:
- `topic_tests`: [{no: «2.3», grade, section, topic, title, date, pct, grade_5, class_avg, diff, attempts, source: onlayn|kağız}]
  – `no` və `grade` plan dərsindən (seq, bölmə nömrəsi, sinfə görə testlər promtundakı `lesson_grade`), yoxdursa boş.
- `mocks` (sınaqlar): [{name, series, no_in_series, date, score, max, pct, place_class, place_all, class_avg, by_part: {Cəbr, Həndəsə}}]
  – **ad qaydası**: `ExamSeries.name` + sıra («Buraxılış sınağı №2») → bank faylının etiketi (ÜSİ-1, MSİ-2 …) → tapşırıq başlığı.
  Ad normallaşdırılır (`sinaq_name()`): «usi 1», «ÜSİ-1 (yeni yer)», «ÜSİ 1» → «ÜSİ-1».
- `summatives`: KSQ/BSQ (kağız və onlayn) – №, tarix, bal, qiymət.
- `summary`: orta %, son %, trend (son 3), iştirak, buraxdığı testlər, sinifdə yer.
Mənbələr: `test_stats.collect` (onlayn) + `ExamScore`/`ExamScan` (yalnız nəşr olunmuş) + `Mark(kind='test')` jurnal qiymətləri (təkrar sayılmasın – eyni test bir dəfə).

### 2.2 API
- `GET /api/results/student/{sid}/report?from=&to=&format=json|pdf|docx&lang=az|ru|en` (müəllim).
- `GET /api/portal/my/report` – şagird özü (yalnız nəşr olunmuş, sinif ortası qaydası ilə).
- Mövcud `/results/student/{sid}` qalır; yeni bölmələr (`mocks`, `summatives`, `topic_tests.no`) ona da əlavə olunur (geriyə uyğun).

### 2.3 UI – «Şagird hesabatı» (Nəticələr → Şagird)
1. Başlıq: ad, sinif, dövr seçimi (rüb / yarımil / il / tarixlər), çap düyməsi.
2. **Mövzu testləri** cədvəli: № | mövzu | tarix | bal % | qiymət | sinif ortası | fərq (rəngli); bölmə üzrə qruplaşma; zəif
   mövzular yuxarıda (≤50%).
3. **Sınaqlar** – adı ilə: seriya üzrə xətt qrafiki (sınaq №1 → №N, şagird vs sinif ortası), cədvəl: ad | tarix | bal | % | sinifdə yer |
   Cəbr/Həndəsə.
4. **KSQ/BSQ** cədvəli.
5. **Tövsiyə** (qayda əsaslı, AI-sız): «Zəif: 2.3 Kvadrat tənliklər (40%) – təkrar testi təyin et» düyməsi (mövcud test təyinatı).
6. Çap: A4, AZ (rəsmi) / valideyn nüsxəsi AZ|RU – qısa: orta, trend, sınaqlar, 3 zəif mövzu, tövsiyə.

### 2.4 Sinif üzrə toplu
Nəticələr → Sinif: «Bütün şagirdlərin hesabatı (PDF)» – hər şagird ayrıca səhifə (valideyn iclası üçün).

## 3. Testlər (`tests/test_student_report.py`)
1. Onlayn mövzu testi + kağız KSQ + nəşr olunmuş skan sınaq → hesabatda üçü də, təkrar yoxdur.
2. Nəşr olunmamış skan şagird portalında görünmür, müəllimdə «nəşr olunmayıb» kimi.
3. Ad normallaşdırma: «usi 1», «ÜSİ-1 (yeni yer)» → «ÜSİ-1»; seriya adı üstündür.
4. Mövzu nömrəsi: plan dərsindən «2.3», sıralama nömrəyə görə.
5. Fərdi məkan şagirdi məktəb müəlliminin/adminin hesabatında yoxdur (404).
6. <5 şagird – sinif ortası `null`.

## 4. Əlavələr (metodist təklifi)
1. **Buraxılış balına proqnoz** (IX, XI): son 3 sınağın ortasından xətti proqnoz + etibarlılıq diapazonu, «təxmini» nişanı ilə.
2. **Mövzu xəritəsi**: bölmə × mövzu istilik xəritəsi (yaşıl/sarı/qırmızı) – kitab sırası ilə.
3. **Valideynə avtomatik aylıq hesabat** – müəllim təsdiqi ilə göndərilir (avtomatik göndəriş yox).
4. **Müqayisə dövrü**: «I yarımil vs II yarımil» fərqi.
5. **Təkrar testin effekti**: zəif mövzuya təyin olunan təkrar testdən sonra bal artımı.

## 5. Qəbul meyarları
- Şagird hesabatında onlayn və kağız nəticələr, sınaqlar adı ilə, mövzu testləri nömrə ilə; təkrar sayılma yoxdur.
- Məxfilik qaydaları testlə yoxlanıb; mövcud Nəticələr ekranlarında reqressiya yoxdur.
- PDF/çap A4-ə sığır; mətnlər AZ/EN/RU; aid testlər + `npm run build` keçir.

**İcra (kodcu):** 2.1 → 3 → 2.2 → 2.3 → 2.4. Əlavələr – istifadəçi seçəndə.
