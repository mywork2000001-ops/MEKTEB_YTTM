# Perspektiv plandan mövzu testlərinin avtomatik təyini – vahid mühərrik + skript · audit + promt (19.10.2026)

**Rol.** Sən «Müəllim köməkçisi»nin baş mühəndisi və riyaziyyat metodistisən. Məqsəd: bir əmrlə (skript və ya tətbiqdə düymə)
perspektiv plana görə **bir sinfə, bir neçə sinfə və ya bütün siniflərə** uyğun mövzu testləri avtomatik təyin olunsun. Bütün test
təyini məntiqi **bir moduldadır**; gələcək əlavələr (yeni bank, variant, səviyyə, sınaq qaydası) yalnız ora əlavə olunur və skript,
düymə, gündəlik avtomatik rejim onları avtomatik alır.
Baza: docs/sinfe-gore-testler-promtu.md (birləşib: `lesson_grade`, `GradeMatcher`, `bank/coverage`),
docs/mekteb-plan-movzu-testleri-promtu.md (mövzu nömrəsi, uyğunluq həddi – bu işlə **birlikdə** icra olunur).

## 0. Sabit qaydalar
- Müəllimin əl ilə yaratdığı test və əl ilə seçdiyi fayl (`LessonBankLink`) toxunulmaz; testi olan dərsə ikinci test yaradılmır.
- KSQ/BSQ/diaqnostik dərsə mövzu testi yoxdur.
- **Tarixə görə çatışmayan testlər** (istifadəçi tələbi): keçilmiş dərslər (dövrün əvvəlindən bu günə qədər) testsizdirsə – `--missing`
  rejimi onları da doldurur: açılma – indi, bağlanma – açılmadan 3 gün sonra 22:00 (`missing_close_days`, defolt 3); hesabatda «çatışmayan» statusu.
- **İcra vaxtı – 45 dəqiqə** (istifadəçi tələbi): mühərriklə yaradılan bütün mövzu testlərinin `duration_min` defoltu 45 (əvvəl 20);
  açıq qalma aralığı 45 dəqiqədən qısa ola bilməz.
- Fərdi məkan ↔ məktəb qarışmır: `--all` yalnız işlədənin görə bildiyi siniflər (müəllim – öz dərsləri; admin – məktəbin dərsləri,
  fərdi məkanlar heç vaxt).
- **Defolt quru rejim** (heç nə yazmır, hesabat verir); yazı yalnız `--apply` / UI-da «Təsdiq et» ilə. Canlı DB-də ilk `--apply` –
  istifadəçinin razılığı ilə.
- Mətnlər AZ/EN/RU; aid pytest + `npm run build`.

## 1. Audit (kod, 19.10.2026)
| # | Tapıntı | Yer |
|---|---|---|
| T1 | Avtomatik test yalnız **bu günün** dərslərinə, gündəlik planlaşdırıcıdan yaranır; qabaqcadan (həftə/ay) toplu təyin yoxdur | `app/auto_tests.py` `run(day)` |
| T2 | Sual mənbəyi sərt kodlanıb: «Test toplusu» dərsi → P007, X–XI → P0010; **V–VIII və fərdi «Sinif testləri» kursu üçün heç nə** – yeni sinfə görə uyğunluq (`GradeMatcher`) istifadə olunmur | `auto_tests._questions` |
| T3 | Test təyini məntiqi üç yerdə təkrarlanır: əl ilə (`create_topic_test`), avtomatik (`auto_tests.run`), plan linkləri (`api/plan.py`) – yeni qayda birinə əlavə olunanda digərləri geri qalır | `api/topic_tests.py`, `auto_tests.py`, `api/plan.py` |
| T4 | Yalnız `ta.auto_tests` açıq siniflər; «bütün siniflərə bir dəfə təyin et» imkanı yoxdur | `auto_tests.run` |
| T5 | Nə yaradıldı / niyə yaradılmadı hesabatı yoxdur (sual yoxdur, şübhəli uyğunluq, test artıq var) | — |

## 2. Həll
### 2.1 Vahid mühərrik – `backend/app/plan_tests.py`
```
plan_items(db, ta, date_from, date_to) -> list[Item]   # işçi plana görə dərs yuvaları + mövzu (dərsin sonuncu yuvası)
resolve(db, ta, item) -> Choice                       # fayl/suallar: əl seçimi → toplu (P007 S/E/M) → GradeMatcher (sinif + nömrə + ad)
                                                       #   status: ok | weak | none | manual | has_test | summative | past | missing
build_task(db, ta, item, choice, opts) -> OnlineTask   # açılma: dərsin sonu; bağlanma: ertəsi gün 22:00; 45 dəq.; qarışıq; cavablar bağlanandan sonra; jurnala
assign(db, user, tas, date_from, date_to, opts, apply=False) -> Report
```
- `opts`: `n_questions` (15), `duration` (45), `missing` (False), `missing_close_days` (3), `close_rule` (ertəsi gün 22:00 | +N gün), `include_weak` (False – şübhəli uyğunluqda test
  yaradılmır, hesabatda «yoxlayın»), `levels` (gələcək: səviyyə variantları), `same_for_parallel` (gələcək).
- **Qeydiyyat (registry)**: sual mənbəyi seçiciləri sıralı siyahıdadır `RESOLVERS = [manual, toplu_p007, grade_matcher, ...]`;
  yeni mənbə/qayda = yeni funksiya + siyahıya bir sətir. Yaradılan tapşırığa son emal addımları `POST_STEPS = [own_numbers?, ...]`.
- `auto_tests.run` → `assign(..., d, d, apply=True)` (yalnız `auto_tests` açıq siniflər); `create_topic_test` toxunulmur (əl ilə), amma
  sual seçimi təklifi (`p0010_for_topic`) `resolve`-dan istifadə edir; `api/plan.py` linkləri də `resolve` ilə – bir mənbə.
- Hesabat (`Report`): sinif üzrə – yaradılacaq/yaradıldı, artıq var, şübhəli, sual yoxdur, summativ, keçmiş; hər sətir: sinif, tarix,
  № mövzu, mövzu, fayl, sual sayı, status, səbəb.

### 2.2 Skript – `backend/scripts/plan_tests.py`
```
python -m scripts.plan_tests --all                       # bütün siniflər, bu gündən 7 gün, QURU rejim – hesabat
python -m scripts.plan_tests --class "X a" --from 2026-10-20 --to 2026-11-30
python -m scripts.plan_tests --all --missing --from 2026-09-15   # tarixə görə çatışmayan testlər (keçilmiş dərslər)
python -m scripts.plan_tests --ta 42 --apply             # yazır (təsdiq sualı: «N test yaradılacaq. Davam? [y/N]»)
python -m scripts.plan_tests --all --apply --yes --include-weak --n 20 --out hesabat.csv
python -m scripts.plan_tests --teacher email@... --all   # admin: konkret müəllimin dərsləri
```
- DB `DATABASE_URL`-dən (lokal və ya canlı – canlı yalnız razılıqla); `--apply`-siz heç nə yazmır; təkrar işlədəndə dublikat yaratmır.
- Çıxış: konsolda sinif üzrə xülasə + CSV.

### 2.3 Tətbiqdə – «sistem üzərindən»
- `POST /api/plan-tests/preview` {ta_ids | all, from, to, opts} → hesabat (yazmır).
- `POST /api/plan-tests/assign` eyni body → yaradır, hesabat qaytarır (audit jurnalına bir yazı + hər tapşırıq).
- UI: Plan səhifəsində «🧪 Testləri təyin et» → pəncərə: siniflər (bu sinif / seçilənlər / bütün siniflərim), dövr (bu həftə / bu ay /
  tarixlər), «Çatışmayanları da (keçilmiş dərslər)», müddət (defolt 45 dəq.), sual sayı, «şübhəlilər də» seçimi → «Önbaxış» cədvəli (status rəngli) → «Təsdiq et». Admin üçün Tənzimləmə → «Bütün siniflər».

### 2.4 Gələcək əlavələr qaydası
Layihə CLAUDE.md-də qayda: **mövzu testinin seçimi/təyini ilə bağlı hər yeni imkan yalnız `app/plan_tests.py`-ə (RESOLVERS / POST_STEPS /
opts) əlavə olunur**; skript, API, gündəlik avtomatik rejim onu oradan alır; `tests/test_plan_tests.py`-ə test əlavə olunur.

## 3. Testlər (`tests/test_plan_tests.py`)
0. Defolt müddət 45 dəq.; `--missing` keçilmiş testsiz dərslərə «indi → +3 gün 22:00» testi yaradır, keçilmiş dərsdə testi olan – toxunulmur.
1. Quru rejim DB-yə yazmır; hesabat statusları düzgün (ok/weak/none/has_test/summative/past).
2. `--apply` iki dəfə – ikinci dəfə 0 yeni test.
3. V sinif (P001) və fərdi «Sinif testləri» kursu – öz sinfinin faylından test (T2 düzəlişi).
4. IX «Test toplusu» dərsi – P007 S/E/M aralığı (köhnə davranış); X–XI – P0010 (reqressiya).
5. Əl ilə seçilmiş fayl üstündür; əl ilə yaradılmış test varsa – `has_test`.
6. Müəllim yalnız öz dərslərini, admin məktəbin dərslərini görür; fərdi məkan admin `--all`-a düşmür.
7. `auto_tests.run` mühərrik vasitəsilə eyni nəticə verir.

## 4. Əlavələr (metodist təklifi)
1. **Paralel siniflərə eyni test** (`same_for_parallel`) – müqayisəli reytinq üçün bir `TestBatch`.
2. **Səviyyəyə görə variant** (`levels`) – Zəif/Orta/Güclü qruplara fərqli çətinlik (mövcud `variants` mexanizmi).
3. **Öz rəqəmləri** (`POST_STEPS`: `avto_reqem`) – eyni sinifdə köçürmənin qarşısı.
4. **Həftəlik avtomatik önbaxış** – bazar günü müəllimə «gələn həftə 8 test yaradılacaq, 1 şübhəli» bildirişi (yaratmadan).

## 5. Qəbul meyarları
- Bir əmr/düymə ilə seçilən siniflərin dövr üzrə mövzu testləri yaradılır; quru rejim və hesabat var; dublikat yoxdur.
- V–XI bütün siniflərdə (bankda varsa) test tapılır; tapılmayanlar hesabatda səbəbi ilə.
- Test seçimi məntiqi tək moduldadır; `auto_tests` və plan linkləri ondan istifadə edir; CLAUDE.md qaydası yazılıb.
- Aid testlər + `npm run build` keçir; mətnlər AZ/EN/RU.

**İcra (bir kodcu, mekteb-plan-movzu-testleri ilə birlikdə):** mekteb-plan §2.1–2.2 (nömrə + hədd) → bu promt 2.1 → 3 → 2.2 → 2.3 → mekteb-plan
§2.3 (audit skripti = `plan_tests --dry-run` hesabatının bir hissəsi, ayrıca skript lazım deyil) və §2.5 → 2.4.
