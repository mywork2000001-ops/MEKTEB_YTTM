# PROMT: «Riyaziyyat müəllimi köməkçisi» — backend + frontend tətbiq

> Bu mətni olduğu kimi süni intellekt proqramçı agentinə (Claude Code və s.) verin. Agent işə `C:\Users\Administrator\Desktop\Tom planlama` qovluğunda başlamalıdır.

---

## 1. Rol və məqsəd

Sən təcrübəli full-stack proqramçı və təhsil sahəsi üzrə məhsul dizaynerisən. Azərbaycan dilində işləyən, **lokal kompüterdə (Windows 11) oflayn işləyən**, peşəkar səviyyəli **müəllim köməkçisi** veb-tətbiqi hazırla.

İstifadəçi: **Həsənov Fərid Oktay oğlu**, riyaziyyat müəllimi, 2026–2027-ci tədris ili.

Tətbiq müəllimin gündəlik işini bir yerə toplamalıdır: şagirdlər, IX sinif buraxılış nəticələri, davamiyyət, qiymətlər, zəif şagirdlərlə iş, **rəsmi perspektiv plan əsasında gündəlik planlaşdırma**, tapşırıqlar üzrə qeydlər və reytinq.

**Əsas prinsip:** planlaşdırmanın yeganə rəsmi mənbəyi məktəbin təsdiq etdiyi **perspektiv planlardır**. Tətbiq plandakı mövzuları, standartları, resursları, qiymətləndirməni və tarixləri öz başına dəyişmir, yalnız onları göstərir, izləyir və müəllimin qeydləri ilə tamamlayır.

---

## 2. Müəssisələr və siniflər

| Sinif | Müəssisə | Növ | Həftəlik saat | Qeyd |
|---|---|---|---|---|
| X b – bütöv sinif | Tərtər şəhər Rafiq Nuriyev adına 6 nömrəli **tam orta** ümumtəhsil məktəbi | TOM | 5 | KSQ/BSQ (MSİ/ÜSİ) burada keçirilir |
| X b – riyaziyyat qrupu | eyni | TOM, bölünən qrup | 5 | **KSQ/BSQ keçirilmir**, bu saatlar DİM formatlı tapşırıq həllinə verilir. Qrupun şagirdləri bütöv sinfin alt çoxluğudur. |
| X c | eyni | TOM | 8 | |
| X e | eyni | TOM | 7 | Fayl adlarında «X-e», Excel vərəqində «X e» yazılıb; interfeysdə hər yerdə **«X e»** göstər |
| XI a | eyni | TOM | 7 | XI sinif buraxılış imtahanı **martdadır**, hazırlıq rejimi lazımdır |
| **XI peşə sinfi** | Tərtər şəhər Rafiq Nuriyev adına 6 nömrəli **ümumtəhsil məktəbi** | **Adi sinif (TOM DEYİL)** | 4 | Başlıqda «tam orta» və TOM layihəsi yazılmır. Resurs: dərslik «Riyaziyyat-11». DİM test toplusu istifadə edilmir. IX sinif buraxılış balı faylda yoxdur. |

- Regional idarə: Qarabağ Regional Təhsil İdarəsi. Direktor: İsmayılov R.
- Rəsmi sənədlərdə TƏSDİQ bloku və imzalar **yalnız üz qabığında** olur, hər səhifədə təkrarlanmır.

### Həftəlik dərs cədvəli (TOM, müəllim cədvəlindən, cəmi 32 saat)

| Saat | Vaxt | B.e. | Ç.a. | Ç. | C.a. | C. |
|---|---|---|---|---|---|---|
| 1 | 08:50–09:35 | — | X e | X c | X b | X c |
| 2 | 09:40–10:25 | X e | X c | X c | XI a | X b |
| 3 | 10:35–11:20 | X b (qrup) | X b (qrup) | X b | XI a | XI a |
| 4 | 11:25–12:10 | XI a | X c | XI a | X b | XI a |
| 5 | 12:15–13:00 | X b (qrup) | X e | XI a | X e | — |
| 6 | 13:35–14:20 | X c | X b (qrup) | X e | X c | X e |
| 7 | 14:25–15:10 | X e | X b (qrup) | X b | X c | — |

X b riyaziyyat qrupu: B.e. 3, 5; Ç.a. 3, 6, 7. X b bütöv sinif: Ç. 3, 7; C.a. 1, 4; C. 2.
XI peşə sinfinin cədvəli (planda belədir): B.e. 1, 2-ci saat; Ç.a. 1-ci saat; Ç. 1-ci saat. Bu ayrı müəssisədir, cədvəli ayrıca və redaktə edilə bilən saxla.
Cədvəl «Parametrlər» bölməsindən dəyişdirilə bilməlidir (yarımil ərzində dəyişə bilər).

### Tədris təqvimi 2026–2027

- Tədris ili: **15.09.2026 – 14.06.2027**. I yarımil 26.01.2027-də bitir, II yarımil 01.02.2027-də başlayır.
- Qeyri-iş və tətil günləri: 09.11, 10.11.2026; 30.12.2026–06.01.2027 (iş günləri); 20.01; 27–29.01; 08.03; 09–10.03 (Ramazan, təxmini); 19–26.03 (Novruz); 10.05; 17–18.05 (Qurban, təxmini); 28.05.2027.
- Mənbə: `05 Texniki (generator skriptləri)\build.py`, `OFF` lüğəti. Təqvim redaktə edilə bilən cədvəl kimi saxlanmalıdır, çünki təxmini bayram tarixləri dəqiqləşdiriləcək.
- Summativ: hər yarımildə **KSQ-1 … KSQ-6**. **BSQ-1: 26.01.2027**, **BSQ-2: 14.06.2027** (yarımilin son dərs günü). X b qrupunda KSQ/BSQ yoxdur.

---

## 3. Məlumat mənbələri (import)

Hamısı `C:\Users\Administrator\Desktop\Tom planlama` qovluğundadır.

1. **Rəsmi perspektiv planlar (ƏSAS MƏNBƏ):** `01 Aktual dərs proqramları 2026-2027\`
   - `X-b sinif – bütöv sinif – …docx`, `X-b sinif – riyaziyyat qrupu – …docx`, `X-c sinif – …docx`, `X-e sinif – …docx`, `XI-a sinif – …docx`, `XI peşə sinfi – …docx`
   - Cədvəlin 8 sütunu var: **Sıra №-si | Məzmun standartları | Mövzu | İnteqrasiya | Resurslar | Qiymətləndirmə | Saat | Tarix**.
   - Bölmələr «I BÖLMƏ – …» sətirləri ilə ayrılır. Tətil sətirlərinə saat yazılmır.
   - «Resurslar» sütununda DİM «Riyaziyyat. Test toplusu – 2025» səhifələri və tapşırıq nömrələri var: *Sinifdə / Ev tapşırığı / Müstəqil hazırlıq*. Bu mətni strukturlaşdır: mənbə, səhifə, nömrə aralıqları. Bir dərsdə sinifdə ən çoxu 20 test tapşırığı olur.
   - Parser `python-docx` ilə yazılsın. Hər sətir `plan_lesson` qeydinə çevrilsin: sinif, bölmə, sıra №, standart kodları, mövzu, inteqrasiya, resurs, qiymətləndirmə növü (KSQ/BSQ/formativ), saat, tarix.
   - **Import zamanı yoxlama:** cədvəldən (bölmə 2) və təqvimdən hesablanan dərs günləri plandakı tarixlərlə uyğun gəlməlidir. Uyğunsuzluq olsa hesabat ver, planı özbaşına düzəltmə.
   - Plan yenilənərsə təkrar import edilə bilsin. Müəllimin həmin dərsə yazdığı qeydlər itməsin: uyğunlaşdırma sinif + sıra № + mövzu ilə aparılsın.

2. **IX sinif buraxılış nəticələri:** `Şagirdlər\Buraxılış nəticələri - riyaziyyat (Həsənov F.).xlsx`
   - Vərəqlər: `X b`, `X c`, `X ə` (interfeysdə «X e»), `XI a` (5-ci sətirdən başlıq: №, Soyadı-adı-ata adı, Cins, Doğum tarixi, Tədris dili, Riyaziyyat, Xarici dil, Yekun bal, Riyaziyyat səviyyəsi, Sinifdə yer). Həmçinin `Ümumi` və `Riyaziyyat reytinqi` vərəqləri var.
   - Cəmi 75 şagird: X b – 20, X c – 20, X e – 17, XI a – 18.
   - Səviyyə həddləri: **Yüksək ≥ 70**, **Orta 40–69,9**, **Zəif < 40**.
   - Ehtiyat mənbə: `TOM-şagirdlər buraxılış balları (1).xlsx`, vərəq `Sheet1 (2)`.
3. **XI peşə sinfi və X b riyaziyyat qrupunun siyahısı:** əl ilə daxil edilir və ya Excel/CSV-dən import olunur. Qrup üzvləri X b siyahısından seçilir.
4. **Köhnə köməkçi:** `Şagirdlər\Mənbələr\Riyaziyyat köməkçisi.html` (localStorage açarı `riyaziyyat_komekcisi_v1`). Onun JSON ehtiyat nüsxəsini import edən miqrasiya əmri yaz, jurnal məlumatı itməsin.

### Məxfilik (MƏCBURİ)
- **Pinkod, Uşaq İD və müəssisə İD import edilməsin, bazada saxlanmasın, heç yerdə göstərilməsin.** Import zamanı həmin sütunları at.
- Tətbiq yalnız `127.0.0.1`-də işləsin. Heç bir xarici serverə məlumat göndərilməsin.
- Giriş müəllim PIN-i ilə olsun (bcrypt/argon2), avtomatik kilid 15 dəqiqə.

---

## 4. Texnologiya və arxitektura

- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2 + Alembic, SQLite (`data/komekci.db`, WAL rejimi), Pydantic v2. Import üçün openpyxl və python-docx, çap sənədləri üçün python-docx/openpyxl, PDF üçün WeasyPrint və ya ReportLab.
- **Frontend:** React 18 + TypeScript + Vite, TanStack Query, React Router, Tailwind CSS. Qrafiklər üçün Recharts. Formalar: React Hook Form + Zod.
- **Qovluq:** `Şagirdlər\Müəllim köməkçisi\` → `backend/`, `frontend/`, `data/`, `backups/`, `exports/`, `README.md`, `start.bat`.
- **Tək kliklə işə salma:** `start.bat` venv-i yoxlayır, miqrasiyaları tətbiq edir, backend-i başladır (frontend build statik fayl kimi FastAPI-dən verilir) və brauzeri `http://127.0.0.1:8765` ünvanında açır.
- **Avtomatik ehtiyat nüsxə:** hər gün ilk girişdə `backups\komekci-YYYY-MM-DD.db`, son 30 nüsxə saxlanılır. Bərpa düyməsi olsun.
- REST API `/api/v1/...`, OpenAPI sənədləşməsi. Bütün domen qaydaları backend-dədir, frontend yalnız göstərir.
- **Testlər:** pytest (import, qiymət çevrilməsi, risk balı, təqvim hesabı, reytinq), frontend üçün Vitest. Əsas qaydalar üçün ən azı 80% əhatə.

### Əsas verilənlər modeli (minimum)
`school`, `class_group` (sinif / qrup, növ: TOM | adi, həftəlik saat, parent_class), `student` (ad, cins, doğum tarixi, status: aktiv/köçüb), `group_membership`, `exam_result_ix` (tədris dili, riyaziyyat, xarici dil, yekun, səviyyə), `timetable_slot`, `calendar_day` (iş günü/tətil, səbəb), `plan_section`, `plan_lesson` (rəsmi, yalnız import ilə dəyişir), `lesson_log` (faktiki dərs: keçildi / təxirə salındı / əvəzləndi, müəllim qeydi), `attendance`, `grade` (növ: formativ | KSQ | BSQ | ev tapşırığı | sorğu), `summative` (maksimal bal, tapşırıq üzrə bal), `assignment`, `assignment_result`, `intervention` (zəif şagirdlə iş), `parent_contact`, `note`, `audit_log`.

---

## 5. Modullar

### 5.1. İdarə paneli (Bu gün)
- Bugünkü dərslər (cədvəl + təqvim), hər biri üçün **rəsmi plandakı mövzu**, sıra №, standart, sinif və ev tapşırığı nömrələri, qiymətləndirmə növü. «Dərsi başlat» düyməsi davamiyyət və jurnal ekranını açır.
- Xəbərdarlıqlar: yaxınlaşan KSQ/BSQ (7 gün qalmış), yoxlanmamış tapşırıqlar, planda geri qalma, üst-üstə 3 dərs qayıb olan şagirdlər, yeni «risk» statusuna düşən şagirdlər.
- XI a üçün martdakı buraxılış imtahanına geri sayım.

### 5.2. Şagirdlər
- Sinif / qrup üzrə siyahı, axtarış, filtr (səviyyə, risk, cins).
- **Şagird kartı:** IX sinif buraxılış balları (sinif ortası ilə müqayisə qrafiki), qiymət dinamikası, davamiyyət faizi, tapşırıq icrası, KSQ nəticələri tapşırıq üzrə, müdaxilə tarixçəsi, valideynlə əlaqə qeydləri, müəllimin şəxsi qeydləri.
- Köçmə/gəlmə: tarixlə status dəyişir, tarixçə silinmir.

### 5.3. Davamiyyət
- Hər dərs üçün sürətli işarələmə: **i** (iştirak), **q/ü** (üzrlü qayıb), **q** (üzrsüz qayıb), **g** (gecikmə). Susmaya görə hamı «iştirak»dır, bir kliklə dəyişir.
- Aylıq və yarımillik hesabat, sinif üzrə istilik xəritəsi.
- Qayda: yarımildə dərslərin **25%-dən çoxu** buraxılıbsa, xəbərdarlıq ver (hədd parametrdə dəyişə bilər).

### 5.4. Gündəlik planlaşdırma (rəsmi perspektiv plan əsasında)
- Dərs planı plan sətrindən **avtomatik yaranır**. Rəsmi sahələr (standart, mövzu, inteqrasiya, resurs, qiymətləndirmə, saat, tarix) **yalnız oxunur** və «Rəsmi plan» nişanı ilə göstərilir.
- Müəllimin əlavə edə biləcəyi sahələr: dərsin məqsədi, motivasiya/problem, iş formaları, diferensial tapşırıqlar (zəif / orta / yüksək qrup üçün, sinfin səviyyə bölgüsünə əsasən), refleksiya, faktiki keçilən tapşırıq nömrələri, qeyd.
- **Status:** keçildi / qismən / təxirə salındı / tətil səbəbindən keçirilmədi / əvəzlənib. Planla faktiki gedişat arasındakı fərqi göstər (məsələn «X c: plandan 2 dərs geridə»). Tarixləri avtomatik sürüşdürmə; yalnız tövsiyə ver.
- Həftəlik görünüş: təqvim + plan. Çap (bölmə 6).
- XI peşə sinfi üçün resurs sahəsində yalnız dərslik göstərilir, DİM toplusu təklif olunmur.

### 5.5. Qiymətləndirmə
- Formativ qiymətlər 2–5 şkalası ilə, dərs, tarix və meyar ilə birlikdə.
- **KSQ/BSQ:** tapşırıq üzrə bal daxil edilir, faiz hesablanır və qiymətə çevrilir: **0–30% → 2, 31–60% → 3, 61–80% → 4, 81–100% → 5** (hədlər parametrdə saxlanılsın).
- Tapşırıq/standart üzrə təhlil: sinfin ən çox səhv etdiyi tapşırıqlar, standart üzrə mənimsəmə faizi. X b qrupunun nəticəsi bütöv sinfin KSQ-sindən götürülür.
- Yarımil qiyməti formula ilə hesablanır. Formula parametr kimi saxlanılsın, çünki məktəbin qaydası dəqiqləşdirilə bilər. Hesablamanın izahı hər şagird üçün görünsün.

### 5.6. Tapşırıqlar üzrə qeyd
- Tapşırıq: sinif/qrup, plan sətri ilə əlaqə, mənbə (DİM toplusu səhifə və №-lər / dərslik / öz tapşırığı), verilmə və təhvil tarixi, səviyyə (hamı / zəif qrup / fərdi).
- Hər şagird üçün status: yerinə yetirib / qismən / etməyib / köçürüb (şübhə), bal, qeyd. Sinif üzrə sürətli daxiletmə cədvəli.
- İcra faizi və vaxtında təhvil statistikası. Sistematik tapşırıq etməyənlər siyahısı.

### 5.7. Zəif şagirdlər və müdaxilə
- **Risk balı (0–100)**, şəffaf və izahlı. Standart çəkilər (parametrdə dəyişir):
  - IX sinif riyaziyyat balı < 40 → 25
  - son 5 formativ qiymətin ortası < 3 → 25
  - son KSQ < 31% → 20
  - davamiyyət < 85% → 15
  - tapşırıq icrası < 60% → 15
- Statuslar: **Yaşıl** (0–29), **Sarı** (30–59), **Qırmızı** (60+). Kartda hansı amillərin bal verdiyi yazılsın.
- **Fərdi iş planı:** hədəf standartlar, əlavə tapşırıqlar, məsləhət saatı, müddət, nəticə. Müdaxilədən əvvəl və sonrakı nəticələrin müqayisəsi.
- **İrəliləyiş izlənməsi:** IX sinif səviyyəsindən cari səviyyəyə hərəkət (məsələn «Zəif → Orta»).
- Başlanğıc vəziyyət: buraxılış nəticəsinə görə 39 şagird zəifdir (X c – 16/20, XI a – 10/18). Bu siniflər paneldə önə çıxsın.

### 5.8. Reytinq
- Sinif daxilində və 4 TOM sinfi üzrə ümumi reytinq. Komponentlər və çəkilər parametrdə saxlanılır: cari qiymət ortası 40%, KSQ ortası 30%, tapşırıq icrası 15%, davamiyyət 15%.
- Ayrıca **«İrəliləyiş reytinqi»**: IX sinif buraxılış səviyyəsindən ən çox irəliləyənlər. Bu reytinq zəif şagirdləri həvəsləndirmək üçündür.
- Reytinq yalnız müəllim üçündür. Şagirdə göstərmək üçün adsız (yalnız yer) çap variantı olsun.

### 5.9. Valideynlə əlaqə
- Əlaqə jurnalı: tarix, səbəb, forma (zəng / görüş / mesaj), nəticə.
- Şagird üzrə qısa hesabat (davamiyyət, qiymətlər, tövsiyə) çap və ya kopyalama üçün, rəsmi üslubda və Azərbaycan dilində.

### 5.10. Hesabatlar və analitika
- Sinif müqayisəsi (buraxılış ortası: X b 49,4; X c 32,3; X e 46,4; XI a 44,4), səviyyə bölgüsü, qiymət paylanması, KSQ dinamikası, standart üzrə mənimsəmə.
- Yarımil və il sonu hesabatları: rəhbərliyə təqdim üçün hazır Word/PDF sənəd.
- Excel ixracı (openpyxl, formatlı başlıqlar).

### 5.11. Parametrlər
- Məktəb məlumatları, siniflər və qruplar, dərs cədvəli, təqvim, qiymət hədləri, risk və reytinq çəkiləri, yarımil qiyməti formulu, PIN dəyişmə, ehtiyat nüsxə və bərpa.

---

## 6. Çap və rəsmi sənədlər
- **Printer Canon ağ-qara çap edir.** Çap şablonlarında rəng istifadə etmə, yalnız boz fon və qalın şrift. Ekrandakı rəngli status nişanları çapda mətnə (məsələn «[Q] Qırmızı») çevrilsin.
- **A4 portret**, kitab formatı. Plan çapında yalnız 8 rəsmi sütun olsun.
- Başlıq müəssisəyə görə dəyişir: TOM sinifləri üçün «… 6 nömrəli tam orta ümumtəhsil məktəbi», XI peşə üçün «… 6 nömrəli ümumtəhsil məktəbi».
- Çap sənədləri: gündəlik/həftəlik dərs planı, davamiyyət vərəqi, qiymət cədvəli, KSQ təhlili, zəif şagirdlə iş planı, valideyn hesabatı.

---

## 7. UX tələbləri
- İnterfeysin bütün mətnləri Azərbaycan dilindədir, düzgün hərflərlə (ə, ı, İ, ş, ç, ğ, ö, ü). Sıralama Azərbaycan əlifbası ilə aparılsın (`Intl.Collator('az')`).
- Tarix formatı `GG.AA.İİİİ`, həftə B.e.-dən başlayır, onluq ayırıcı vergüldür.
- Noutbuk ekranında rahat işləsin. Planşet/telefon ölçüsündə davamiyyət və qiymət ekranları tam işləsin.
- Klaviatura ilə sürətli daxiletmə: jurnalda ox düymələri və 2–5 rəqəmləri.
- İşıqlı və qaranlıq rejim. Sakit, peşəkar dizayn.
- Hər dəyişiklik `audit_log`-a yazılsın. Silinən qeydlər 30 gün «Səbət»də saxlanılsın.

---

## 8. İş ardıcıllığı və təhvil
1. Mənbə fayllarını oxu, strukturunu təhlil et və qısa hesabat ver (plan sətirlərinin sayı, şagird sayı, uyğunsuzluqlar). Kodu bundan sonra yaz.
2. Model + miqrasiya + import (perspektiv planlar, buraxılış nəticələri, təqvim, cədvəl) + testlər.
3. API.
4. Frontend modulları. Ardıcıllıq: Bu gün → Davamiyyət → Qiymətləndirmə → Planlaşdırma → Tapşırıqlar → Zəif şagirdlər → Reytinq → Hesabatlar → Parametrlər.
5. Çap şablonları, ehtiyat nüsxə, `start.bat`, README (Azərbaycan dilində, müəllim üçün addım-addım təlimat).

### Qəbul meyarları
- `start.bat` ilə tətbiq təmiz Windows 11-də (Python 3.11 quraşdırılıb) işə düşür.
- 75 TOM şagirdi səviyyələri ilə birlikdə düzgün import olunur. Pinkod və Uşaq İD bazada yoxdur (test bunu yoxlayır).
- Bütün 6 perspektiv plan import olunur. 28.09.2026 (B.e.) üçün «Bu gün» ekranı cədvələ uyğun dərsləri (X e, X b qrup, XI a, X c) rəsmi mövzuları ilə göstərir.
- KSQ çevrilməsi, risk balı, reytinq və təqvim hesabları vahid testlərlə yoxlanılıb.
- Çap sənədləri ağ-qaradır, A4 portretdir və başlıqları müəssisəyə uyğundur.
- Köhnə `Riyaziyyat köməkçisi.html` JSON nüsxəsi import olunur.

Qeyri-müəyyən məqam olarsa (məsələn yarımil qiyməti formulu və ya plan tarixinin cədvəllə uyğunsuzluğu), özün qərar vermə. Parametr kimi saxla və müəllimə sual ver.

---

## 9. Maketdən qərarlar (28.09.2026) — yuxarıdakı bəndlərlə ziddiyyət olarsa, BU bölmə keçərlidir

Maket: `Şagirdlər\Müəllim köməkçisi\maket\Müəllim köməkçisi – maket.html` (bütün ekranlar və davranış nümunəsi).

- **Yerləşmə:** tətbiq İNTERNET üzərindən işləyən veb tətbiqdir (hostinq, HTTPS, domen). «Yalnız 127.0.0.1 / oflayn» tələbi (bölmə 3, 4) ləğv olunur. Məlumat qorunması: HTTPS, şifrələrin heşi, giriş cəhdlərinin məhdudlaşdırılması, gündəlik ehtiyat nüsxə, fayllar (çat: şəkil/PDF/səs) server yaddaşında.
- **Rollar:** admin (Həsənov Fərid) · müəllim · şagird. Admin: müəllim hesabları, məktəblər (UTİS kodunu admin yazır), şagird portalı, onlayn tapşırıqlar, əks əlaqə, şagird girişləri, tədris ili, dərs vaxtları, ümumi qaydalar. Müəllim: yalnız öz fənləri, sinifləri, şagirdləri, mövzuları (perspektiv plandan), jurnalı. Hər müəllimin məlumatı ayrıdır.
- **Məktəb:** müəllim məktəbini addan axtarıb seçir; eyni UTİS kodlu müəllimlər avtomatik birləşir → «Müəllim otağı» (məktəb daxili çat).
- **Məxfilik:** heç kim (admin də) başqasının yazışmasını görmür. Şagirdlərin şəxsi yazışmasını müəllim görmür, yalnız şagirdin «!» ilə bildirdiyi mesajı. Rəsmi Uşaq İD, pinkod saxlanmır.
- **Şagird girişi:** tətbiqin kodu sinfə görə avtomatik (məs. XC-001) + 4 rəqəmli PIN (şagird özü dəyişə bilər).
- **Redaktə:** bütün redaktə yalnız «Tənzimləmələr»də (giriş şifrəsi, 15 dəq avtomatik kilid). Silinən → arxiv (adı yazaraq təsdiq), geri qaytarma və həmişəlik silmə.
- **Filtr qaydası:** filtrli ekranlarda yuxarıda seçim edilənə qədər aşağı hissə boşdur.
- **Qiymətləndirmə:** KSQ/BSQ bal → faiz → qiymət (0–30→2, 31–60→3, 61–80→4, 81–100→5). **Yarımil qiyməti = (KSQ qiymətlərinin cəmi / KSQ sayı) × 0,4 + BSQ × 0,6**, adi yuvarlaqlaşdırma.
- **Jurnal:** mövzu perspektiv plandan tarix + dərs saatına görə avtomatik; hər dərs saatı ayrıca qeyd; bölünən qrup öz planı ilə ayrıca; ev tapşırığı sahəsi; testlər açılan siyahıdan (düz cavab sayı → faiz → qiymət avtomatik).
- **Geriləmə:** «Mövzunu saxla» — işçi plan təqvimdə sürüşür, rəsmi plan dəyişmir.
- **Dərs vaxtları:** məktəbin ümumi zəng cədvəli; sinif üçün ayrıca zəng vaxtı ola bilər. **XI peşə sinfi – öz zəngi:** 1-ci saat 08:00–08:45, 2-ci saat 08:50–09:35 (B.e. 1, 2; Ç.a. 1; Ç. 1). Müəllimin dərsləri real vaxt üzrə toqquşmaya yoxlanır.
- **Şagird portalı:** Bu gün (gündəlik motivasiya), Dərs (gündəlik: mövzu, ev tapşırığı, davamiyyət, qiymət), Tapşırıqlar (vaxtlı testlər: tarix + saat aralığı + həll müddəti, taymer, avtomatik təhvil), Plan (gün/həftə/ay/yarımil), Nəticələrim (test nəticələri, KSQ/BSQ, yarımil qiyməti, səhvlərim, nailiyyətlər), Çat (müəllim, sinif, sinif yoldaşı), Tənzimləmələr (PIN, rəng çaları).
- **Analitika və hesabat:** ümumi analitika, reytinq (ümumi və irəliləyiş), çap/PDF (A4, ağ-qara).
- **Görünüş:** telefon, planşet, noutbuk; 6 rəng çaları + işıqlı/qaranlıq rejim.
- **Məktəbin ortaq siyahısı:** siniflər və şagirdlər məktəbə (UTİS) aiddir. Bir müəllim sinif/şagird əlavə edəndə eyni məktəbin digər müəllimləri görür və sinfə «qoşulur» – təkrar yaradılmır (eyni adlı sinif; eyni ad + doğum tarixli şagird bloklanır). Şagird bütün müəllimlər üçün eyni ID və eyni portal kodu ilə tanınır. Jurnal, qiymət, mövzu, KSQ – hər müəllimin öz fənni üzrə ayrıca (müəllim–sinif–fənn bağlantısı). Tövsiyə: şəxsi məlumatı sinif rəhbəri və ya admin dəyişsin, dəyişikliklər jurnala yazılsın; təkrarlar üçün «birləşdirmə» aləti.
- **Dil:** interfeys Azərbaycanca / English / Русский (Tənzimləmələr → Görünüş; şagird öz portalında seçir). Rəsmi çap sənədləri Azərbaycan dilində.
- **Şagird portalı əlavə:** «Analitika» (dövr seçimi, test dinamikası sinif ortası ilə – adsız, mövzular üzrə mənimsəmə, davamiyyət, ev tapşırığı, «Hesabatım» A4); imtahan sayğacı (sinfin buraxılış tarixi, BSQ, növbəti KSQ); müəllimin adı sinif/qrup/dərsdə.
- **Əlavə modullar:** KSQ tapşırıq üzrə (✓/✗) + tapşırıq/standart təhlili; ev tapşırığının yoxlanması (etdi/qismən/etmədi/köçürüb); valideynlə əlaqə jurnalı; fərdi iş planı; davamiyyət hesabatı (istilik xəritəsi, 25%+).
- **Sinif adı:** «X e» (Excel vərəqində «X ə» yazılıb).

- **Çatda fayl göndərmə (istifadəçi, 29.09.2026):** şəkil, PDF, səs və video – **2 GB-a qədər**; server faylı diskə axınla (1 MB hissələrlə) yazır, yaddaşa bütöv yükləmir. Hostinqdə fayllar üçün daimi disk (volume) lazımdır.
