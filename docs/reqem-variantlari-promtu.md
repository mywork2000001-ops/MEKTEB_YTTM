# Hər şagirdə öz rəqəmləri – parametrli suallar (köçürməyə qarşı) · promt (19.10.2026)

## Problem
19.10.2026 XI-P sinfində KSQ keçirildi, şagirdlər bir-birindən köçürdü. Səbəb: KSQ P013 «sinif testləri»ndən
`same_for_all` rejimində (hamıya eyni variant, `api/exams.py::_make`) yaradılmışdı, ya da bankda mövzu üzrə sual azdır və
variantlar eyni suallardan qurulur. Bank böyüməyincə «tam fərqli suallar» qaydası (docs/ksq-bsq-kagiz-promtu.md) işləmir.

## Rol
Sən «Müəllim köməkçisi»nin baş mühəndisi və riyaziyyat qiymətləndirmə metodistisən. Məqsəd: **eyni sual, eyni çətinlik,
eyni bal – amma hər şagirdin öz ədədləri və öz düzgün cavabı**. Qonşunun cavabı başqa şagirdə yaramır.

## Həll (3 mərhələ)

### Mərhələ 1 – müstəqil Python skripti (DB-yə toxunmur) – `backend/scripts/reqem_variantlari.py`
1. **Şablon** (JSON, bir fayl = bir imtahan): hər sual üçün
   - `text`/`options`/`explanation` – `{az,ru,en}`, ədədlər yerində `{a}`, `{b}`… ; KaTeX olduğu kimi qalır;
   - `params` – `{"a": {"min": 2, "max": 9, "step": 1, "not": [0, 1]}, "k": {"choice": [2, 3, 5]}}`;
   - `where` – şərtlər (`"a != b"`, `"(b*b - 4*a*c) > 0"`, `"is_int(x1)"`) – cavab «gözəl» olsun (tam və ya sadə kəsr);
   - `answer` – sympy ifadəsi (`"(b + c) / a"`); `kind`: `mcq` | `open`; mcq üçün `distractors` – tipik səhv düsturları
     (işarə səhvi, kəsri çevirməmək və s.), hamısı bir-birindən və düz cavabdan fərqli olmalıdır;
   - `original` – mənbədəki ədədlər (`{"a": 3, "b": 5}`) və mənbədəki cavab.
2. **Açar yoxlaması (məcburi):** `original` ədədləri ilə hesablanan cavab mənbə cavabına bərabər deyilsə – şablon RƏDD
   olunur (formula səhvdir). Hesab yalnız `sympy` ilə, `eval` yoxdur (təhlükəsiz parser: `sympy.sympify` + icazəli adlar).
3. **Generasiya:** `seed = hash(imtahan kodu + şagird id + sual №)` – təkrar işə salanda eyni nəticə (vərəq itsə – eynisi).
   Sinif daxilində iki şagirdə eyni ədəd dəsti düşmür (qonşu sıralar üçün). Şərtlərə uyğun dəst 200 cəhddə tapılmasa – xəta,
   hansı sual olduğunu yaz.
4. **Açıq cavab** kartın xanasına yazıla bilməlidir: rəqəm, `-`, `,`, `/`, `;`, ≤ 8 simvol (mövcud qayda); kəsr ixtisar olunur;
   ondalıq – vergüllə (`2,5`). mcq – variantların yeri hər şagirddə qarışdırılır, düz cavabın hərfi də dəyişir.
5. **Çıxış:** `out/<kod>/` – hər şagirdə A4 HTML (suallar + kod), müəllim açarı (HTML + CSV: şagird, sual, cavab),
   `variants.json` (sonra tətbiqə idxal üçün `ExamVariant.questions` formatında).
6. **Şablon hazırlamaq:** mövcud sualdan şablonu `cavab-yoxlayici` agenti yazır (həll edir, ədədləri dəyişənə çevirir,
   şərtləri qoyur); skript `--check` ilə yoxlayır. Ədədləri dəyişmək olmayan suallar (şəkilli, nəzəri) – `fixed: true`,
   onlar dəyişmir, amma sırası qarışdırılır.
7. **Testlər:** `tests/test_reqem_variantlari.py` – açar yoxlaması, determinizm, 30 şagirddə təkrar dəst yoxdur,
   kart formatı, mcq distraktorları fərqli, səhv şablon rədd olunur.

### Mərhələ 1b – istənilən test üçün, süni intellektsiz (avtomatik şablon) – `backend/scripts/avto_reqem.py`
İstifadəçi tələbi (19.10.2026): şablonu insan / agent yazmadan, **istənilən testdən** avtomatik «öz rəqəmləri». Yalnız
Python + sympy, deterministik. Giriş: bank sualları (`BankQuestion` formatı: `kind, text{az,ru,en}, options, correct, answer`)
JSON-u və ya `variants.json`. Hər sual üçün ardıcıl 3 üsul, **birinci uğurlu** götürülür:
1. **Düstur sualı (sympy):** KaTeX hissəsi (`$…$`) sympy-yə çevrilir (`latex2sympy` olmadan – öz kiçik çevirici: `\frac`, `^`,
   `\sqrt`, `\cdot`, gizli vurma). Açar sözlə əməliyyat: həll edin/решите/solve → `solve`; hesablayın/вычислите/calculate →
   qiymət; sadələşdirin/упростите → `simplify`; qalıq/остаток/remainder → `rem`; köklərin cəmi/hasili, ən böyük/kiçik kök,
   `P(a)`, törəmə, inteqral, limit, ƏBOB/ƏKOB, faiz. Formuldakı ədədlər parametr olur.
2. **Mətn məsələsi (düstur axtarışı):** mətndəki ədədlər `n1…nk`; `+ − × ÷`, mötərizə, kvadrat, faiz ilə ≤ 3 əməllik bütün
   ifadələr yoxlanır; mənbə cavabını verən ifadə **tək** (və ya hamısı eyni sinifdə eyni nəticə verir) olarsa – o düsturdur.
3. **Dəyişmir:** üsul tapılmadı / çox düstur uyğun gəldi / şəkil var → `fixed`, yalnız variant yerləri qarışır.
Məcburi yoxlamalar: (a) mənbə ədədləri ilə üsul **mənbə cavabını** verməlidir, yoxsa sual `fixed`; (b) yeni ədədlər –
eyni işarə, eyni rəqəm sayı, tam ədəd tam qalır, sıfır/bir yaranmır, ədəd mətn daxilində də (iki dəfə yazılıbsa) eyni dəyişir;
(c) cavab «gözəl» və kart formatında; (d) mcq distraktorları: mənbə distraktoru ilə cavab arasındakı əlaqə (fərq, işarə,
əks kəsr, ×10) tapılıb yeni cavaba tətbiq olunur, alınmırsa – cavab ± kiçik addım, hamısı fərqli.
Çıxış: avtomatik şablon JSON (Mərhələ 1 formatı – müəllim baxa və düzəldə bilər) + hesabat: hər sual «🔢 sympy» /
«🔢 düstur a*b/c» / «⛔ dəyişmir (səbəb)»; sonra Mərhələ 1 generatoru ilə vərəqlər, açar, `variants.json`.
Testlər: kvadrat tənlik, Bezu qalığı, kəsr hesabı, faiz məsələsi, hərəkət məsələsi, şəkilli sual (fixed), səhv açar (fixed).

### Mərhələ 2 – tətbiqə qoşmaq (istifadəçinin razılığı ilə: miqrasiya + deploy)
- `BankQuestion.template` (JSON, boş ola bilər) – miqrasiya; KSQ yaradanda yeni seçim:
  «Hər şagirdə öz rəqəmləri» (AZ) / «Own numbers for each student» (EN) / «Каждому ученику свои числа» (RU).
- `ksq_variants`: şablonu olan sual seçilirsə – hər şagird üçün ədədlər yuxarıdakı qaydayla; açar `ExamVariant.questions`-a
  donmuş halda yazılır (skan, onlayn yazı, apelyasiya, «köçürmə şübhəsi – yeni variant» dəyişmədən işləyir; retake yeni ədəd verir).
- `same_for_all` + şablon = **eyni suallar, fərqli ədədlər** – DİM sinif testi formatı qalır, köçürmə işləmir.
- Müəllim ekranında hər sualın yanında nişan «🔢 rəqəmlər dəyişir»; ədalət hesabatı: hər şagirdin cavabının «gözəllik» yoxlaması.

### Mərhələ 3 – bank
- P013 XI (Çoxhədlilər A/B) və XI-P KSQ mövzuları – əvvəl bunların şablonu (`cavab-yoxlayici`), sonra digər siniflər.

## Qəbul meyarları
- Hər şablonda `original` ədədləri mənbə cavabını verir; 30 şagirdə 30 fərqli ədəd dəsti; açarlar sympy ilə təsdiqlidir.
- `pytest tests/test_reqem_variantlari.py` keçir; mərhələ 2-də `npm run build` + deploy statusu success; yeni mətnlər AZ/EN/RU.
