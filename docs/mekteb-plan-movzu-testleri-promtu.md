# Məktəb perspektiv planı – mövzu nömrəsinə uyğun mövzu testləri (bütün siniflər) · audit + promt (19.10.2026)

**Rol.** Sən «Müəllim köməkçisi»nin baş mühəndisi və riyaziyyat metodistisən. Məqsəd: məktəbin **bütün siniflərinin** (V–XI,
əsas və zəif qrup planları) perspektiv planında hər mövzu dərsinə **mövzu nömrəsinə və adına uyğun** mövzu testi avtomatik qoşulsun;
yanlış qoşulanlar düzəlsin; bankda olan, amma qoşulmayan testlər əlavə olunsun; olmayanlar hesabatda görünsün.
Baza: docs/sinfe-gore-testler-promtu.md (dərsin öz sinfi, sinif süzgəci, `bank/coverage`) – bu promt onun üzərində qurulur.

## 0. Sabit qaydalar
- **V–VIII «gözlənilir» (`pending`), istifadəçi qərarı 19.10.2026:** `PENDING_GRADES = {5,6,7,8}` (`bank/match.py`) – bu siniflərdə test
  tapılmayan mövzu «yoxdur» yox, «⏳ Gözlənilir» (Plan nişanı, hesabat, `bank/coverage`); IX–XI üçün «yoxdur» qalır.
- Müəllimin əl ilə seçimi (`LessonBankLink`, «Test yoxdur» seçimi daxil) heç vaxt dəyişmir.
- KSQ/BSQ, diaqnostik dərslərə mövzu testi qoşulmur (indiki qayda). Plan mətni, tarixlər, jurnal toxunulmaz.
- Bankda olmayan test uydurulmur. Mənbə PDF olmadan sual yazılmır.
- Fərdi məkan bu işə daxil deyil (orada «Sinif testləri» kursu – ayrıca promtlar).
- Canlı DB-yə yazı yalnız: (1) quru rejim hesabatı istifadəçiyə göstərilib, (2) istifadəçi razılıq verib.

## 1. Audit (kod, 19.10.2026)
| # | Tapıntı | Yer |
|---|---|---|
| M1 | Qoşulma yalnız **söz oxşarlığı** ilə (söz kökü + idf); mövzu nömrəsi nəzərə alınmır – oxşar adlı iki mövzu («Kvadrat tənliklər» / «Kvadrat tənliyə gətirilən tənliklər») səhv qoşula bilər | `bank/match.py` `Matcher.matches` |
| M2 | Plan dərsinin nömrəsi yoxdur: DİM «Sinif testləri» planlarında bölmə «1. Funksiya», mövzular sıralı – «1.2» hesablana bilər, amma saxlanmır; Word planlarında mövzu adında nömrə ola bilər («3.4. …») – oxunmur | `programs.expand`, `importers/plans.py` |
| M3 | Bank faylının etiketində/yolunda nömrə varsa (məs. «2.3 …», `f2/…`) – istifadə olunmur | `BankFile.label`, `lesson` |
| M4 | Uyğunluq həddi yoxdur: ən yaxşı nəticə zəif olsa da qoşulur (`best[0]`), müəllimə «şübhəli» deyilmir | `api/plan.py` linkləmə |
| M5 | Qoşulma hər plan açılışında yenidən hesablanır, nəticə saxlanmır – «nə qoşulub» hesabatı və canlı yoxlama çətindir | `api/plan.py` |
| M6 | Zəif qrup tempinin törəmə dərsləri (təkrar, möhkəmləndirmə) əsas mövzunun testini alır – düzgündür; qarışıq təkrar – test yoxdur (saxlanır) | `bank/match.py` `_BASE/_MIXED` |

## 2. Həll
### 2.1 Mövzu nömrəsi
- `topic_no(lesson, program)` → «bölmə.mövzu» (məs. «2.3»): (1) mövzu mətnindəki baş nömrə («3.4.», «§12»); (2) adaptive şablonda
  bölmə nömrəsi («2. Kvadrat tənliklər») + mövzunun bölmədəki sırası; (3) yoxdursa – None. Törəmə dərs əsas mövzunun nömrəsini alır.
- `bank_no(file)` → etiketdən/yoldan nömrə (varsa) + sinif (`grades`).
### 2.2 Uyğunluq balı (nömrə + ad + sinif)
`score = ad oxşarlığı (indiki) + nömrə bonusu (eyni sinifdə eyni nömrə və ad oxşarlığı ≥ minimum) − sinif cəzası (fərqli sinif –
qoşulmur)`. Hədd: `score ≥ T_ok` → avtomatik; `T_weak ≤ score < T_ok` → qoşulur, «şübhəli ⚠» nişanı; aşağı → qoşulmur, «tapılmadı».
Hədlər real bank adları üzərində kalibrlənir (aşağıdakı hesabatla).
### 2.3 Hesabat və düzəliş skripti – `backend/scripts/plan_test_audit.py`
- `--all` (bütün məktəb planları) / `--ta N`; defolt **quru rejim** (yalnız oxu): hər sinif üçün mövzu sayı, avtomatik qoşulan,
  şübhəli, tapılmayan, köhnə qoşulma ilə fərq (indi səhv qoşulanlar). CSV + qısa xülasə (sinif üzrə).
- `--apply` yoxdur: avtomatik qoşulma hər plan açılışında hesablanır, düzəliş kodda olur – DB yazısı lazım deyil; əl ilə linklər toxunulmaz.
- Eyni hesabat API: `GET /api/bank/plan-audit?ta_id=` (admin/müəllim) və Plan səhifəsində «Testləri yoxla» düyməsi.
### 2.4 «Lazımdırsa əlavə et»
- Bankda uyğun fayl var, amma planda test yoxdur → qoşulur (2.2).
- Mövzu testi tapşırığı (OnlineTask) yalnız müəllim «Avtomatik mövzu testi» (`ta.auto_tests`) açıbsa yaradılır – indiki qayda; hesabatda
  «avtomatik test açıq deyil» siyahısı.
- Bankda fayl yoxdur → «Bank boşluğu» siyahısı (sinif, nömrə, mövzu) → ayrıca kart: mənbə PDF ilə `pdf-oxuyucu` → `cavab-yoxlayici`.
  Qeyd: «Sinif testləri» kitabının sual PDF-i qovluqda yoxdur (yalnız `Mənbələr/Sinif testi cavablar5-11.pdf`) – istifadəçidən istənəcək.
### 2.5 UI
Plan səhifəsində test nişanı: «2.3 · Kvadrat tənliklər · P0010» – şübhəli ⚠ (sarı), tapılmadı (boz); başlıqda «Testlər: 54/60 · ⚠ 3 · yox 3».

## 3. Testlər (`tests/test_plan_topic_no.py`)
1. «Kvadrat tənliklər» və «Kvadrat tənliyə gətirilən tənliklər» – nömrə ilə düzgün fayl.
2. Nömrəsiz Word planı – ad oxşarlığı ilə köhnə nəticə (reqressiya).
3. Zəif uyğunluq → «şübhəli», çox zəif → qoşulmur.
4. Əl ilə seçim qorunur; KSQ/BSQ-yə test yoxdur.
5. Skript quru rejimdə DB-yə yazmır.

## 4. Əlavələr (metodist təklifi)
1. **Test çətinliyi**: hər faylın orta həll faizi (mövcud nəticələrdən) – nişanda «orta 62%».
2. **Paralel siniflərə eyni test**: eyni nömrəli mövzu üçün bütün paralel siniflərdə eyni fayl (müqayisə üçün).
3. **Mövzu testi həftəlik planı**: «Bu həftə 5 mövzu testi açılmalıdır» bloku Əsas səhifədə.

## 5. Qəbul meyarları
- Bütün məktəb siniflərinin planında hər mövzu dərsində: düzgün test, ya «şübhəli ⚠», ya «tapılmadı» – səssiz səhv qoşulma yoxdur.
- Quru rejim hesabatı canlıda (deploydan sonra, yalnız oxu) istifadəçiyə göstərilir; əl ilə seçimlər toxunulmaz.
- Aid testlər + `npm run build` keçir; mətnlər AZ/EN/RU.

**İcra (kodcu, «sinfə görə testlər» birləşdikdən sonra):** 2.1 → 2.2 → 3 → 2.3 → 2.5 → canlıda quru hesabat (Rəhbər).
