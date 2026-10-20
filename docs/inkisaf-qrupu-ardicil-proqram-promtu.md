# İnkişaf qrupu – V→IX «Sinif testləri» proqramı ardıcıl (promt, 20.10.2026)

**Sifarişçi:** müəllim: «inkişaf qrupunu sinif testləri proqramlarından ardıcıl doldur; hər dərsə bir mövzu; həftədə 3 dəfə 21:00–22:00;
proqram üzrə V sinifdən IX sinfə».
**Rəhbər:** Claude (Opus) · **İcraçı:** `kodcu` (worktree) · **Status:** növbəti sessiyada icra (istifadəçi: «ardıcıl işlə»).
**Qaydalar:** CLAUDE.md – mövzu testi seçimi YALNIZ `app/plan_tests.py` (RESOLVERS/opts); AZ/EN/RU; `npm run build` + aid pytest;
canlı tətbiq – ehtiyat nüsxə + önbaxış + istifadəçinin «hə»-si.

## 1. Hazırkı vəziyyət (kod)
- `backend/app/extra_programs.py`: inkişaf tipi = **qrupun sinfinin bir** proqramı (`dim-sinif-testleri-{grade}`) + əvvəlki sinfin 3 «Təkrar»
  mövzusu; temp sinfin perspektiv planı ilə paralel (`_class_dates`). V→IX zənciri **yoxdur**.
- Mənbə: `app/program_data/sinif_testleri.json` – mövzu sayı: V – 11, VI – 16 (1 təkrar), VII – 16, VIII – 23, IX – 17; **cəmi 83**.
- V–VIII bankı hələ yoxdur (`PENDING_GRADES`) – bu siniflərin mövzularında avtomatik test olmayacaq (yalnız mövzu); IX – bank var.
- Cədvəl `ExtraCourse.schedule` = `[{weekday, start, end, link}]`; məşğələlər `ExtraSession`.

## 2. Metodiki dizayn
1. **Ardıcıllıq (spiral yox, xətti zəncir):** Giriş diaqnostikası → V (11) → **V yekun yoxlama** → VI (15, «Təkrar» bölməsi çıxır – zəncirdə
   əvvəlki sinif elə indi keçilib) → VI yekun → VII (16) → VII yekun → VIII (23) → VIII yekun → IX (17) → **Çıxış testi**.
   Cəmi ≈ 83 mövzu + 1 giriş + 4 yekun + 1 çıxış = **≈ 89 məşğələ**.
2. **Hər məşğələyə bir mövzu**, sinfin planı ilə tempə bağlanmır (rejim `chain`). Mövzu adı şagirdə: «V sinif · 1. Natural ədədlər – Çoxluqlar»
   (sinif nişanı ilə; «zəif/inkişaf» sözü şagirdə görünmür – mövcud `LEAK` qaydası).
3. **Cədvəl:** həftədə 3 dəfə, 21:00–22:00, onlayn. Günlər – defolt **B.e., Ç., C.** (müəllim dəyişə bilər). 89 məşğələ ≈ 30 həftə:
   başlanğıc tarixindən **təxminən may sonuna** çatır; tədris ilinin sonuna sığmayan mövzu varsa – önbaxışda xəbərdarlıq (say).
   Bayram/tətil günləri məktəb təqvimindən varsa – keçilir, mövzu növbəti məşğələyə sürüşür.
4. **Testlər:** hər mövzu üçün test `plan_tests.py` (`r_extra_program`) ilə – IX-də bankdan, V–VIII-də «bank gözlənilir» işarəsi; yekun və çıxış
   testləri – IX bankı olmayan siniflərdə test yaradılmır, yalnız məşğələ başlığı (sonra bank gələndə `--missing` ilə doldurulur).
5. **İdempotentlik:** keçirilmiş və əl ilə yazılmış mövzulara toxunulmur; yenidən işə salma eyni nəticə verir; cədvəl dəyişəndə yalnız gələcək
   proqram məşğələləri yenidən hesablanır (mövcud qayda).

## 3. Texniki tələblər (kart üçün)
- `extra_programs.py`: rejim `chain` – `grades: [5..9]` zənciri; konfiqurasiya mövcud JSON sahəsində (`program_sections` və ya `audience`) –
  miqrasiyasız; yoxdursa ayrıca nullable sütun (miqrasiya yalnız yeni sütun).
- `api/extra.py` `POST /{cid}/program`: `{kind:'inkisaf', mode:'chain', grades:[5,9], dry}` → önbaxış (məşğələ sayı, ilk/son tarix,
  sığmayan say, sinif üzrə bölgü) və tətbiq.
- Frontend `ExtraCourses.tsx` proqram pəncərəsi: seçim «Ardıcıl V→IX (hər məşğələyə bir mövzu)», günlər və saat (21:00–22:00 defolt),
  önbaxış cədvəli (tarix · sinif · mövzu · test var/yox); AZ/EN/RU.
- Plan testləri: `plan_tests.py`-də yeni opsiya yalnız lazım olarsa (RESOLVERS/opts), skript `scripts/plan_tests.py` dəyişməz işləsin.
- Testlər `tests/test_extra_chain.py`: zəncir ardıcıllığı (V→IX, Təkrar çıxır, yekunlar yerində), bir məşğələ = bir mövzu, 3 gün/həftə tarixləri,
  21:00–22:00, sığmayan xəbərdarlığı, idempotentlik, keçirilmiş məşğələyə toxunmamaq.

## 4. İcra ardıcıllığı (növbəti sessiya)
1. Canlıda yalnız oxu: hansı qrup «inkişaf» (ad, şagird sayı, indiki cədvəl) – istifadəçidən qrupu təsdiqlət.
2. Kart `docs/tasks/inkisaf-zencir.md` → `kodcu` → review, pytest, build → merge → push → Render.
3. Canlıda: ehtiyat nüsxə → önbaxış (say/tarixlər istifadəçiyə) → «hə» → tətbiq → qrupda gözlə yoxlama (ilk 5 məşğələ, son tarix).
4. Audit sətri.

## 5. İstifadəçinin dəqiqləşdirməsi (20.10.2026) – §2-ni əvəz edir
- **Günlər:** həftənin 3, 4, 5-ci günləri (Ç., C.a., C. – çərşənbə, cümə axşamı, cümə), 21:00–22:00.
- **Müddət:** başlanğıc tarixindən **26.01.2027**-yə qədər (daxil) – yalnız bu aralıqdakı məşğələlər doldurulur.
- **Başlanğıc nöqtəsi:** qrup hazırda **V sinif, 2-ci yarımil** mövzularındadır → zəncir V sinfin 2-ci yarımilindən (bölmələr 3–6:
  Onluq kəsrlər, Həndəsə elementləri, Faiz, Statistika. Ehtimal – 6 mövzu) başlayır, sonra **V sinif illik test** (bir məşğələ), sonra VI → VII → …
  V sinfin 1-ci yarımili və giriş diaqnostikası buraxılır.
- 26.01.2027-yə qədər ≈ 14 həftə × 3 = **≈ 40–42 məşğələ** (tətillər çıxılır): V 2-ci yarımil (6) + V illik (1) + VI (15 + yekun) + VII (16 + yekun)
  ≈ 40 – yəni təxminən **VII sinfin sonuna** çatır. Dəqiq say önbaxışda; sığmayanlar növbəti dövrə qalır (xəbərdarlıq).
- Texniki: `chain` konfiqurasiyasında `start: {grade: 5, semester: 2}`, `end_date: 2027-01-26`, `weekdays: [2, 3, 4]`.

## 6. V sinif alt mövzuları – P001 (istifadəçi, 20.10.2026)
**Mənbə:** `C:\Users\Administrator\Documents\Claude\Projects\P001_Math_5_DIM\5dim_sinif_testi2025\` – 17 dərs (Lesson-1…17.html) + `quiz.html` (viktorina).
| P001 | Mövzu | P001 | Mövzu |
|---|---|---|---|
| L1 | Natural ədədlərin yazılması və oxunması | L10 | Faiz |
| L2 | Natural ədədlərin toplanması və çıxılması | L11 | (başlıqsız – faylın içindən təyin et) |
| L3 | Natural ədədlərin vurulması və bölünməsi | L12 | Tənliklər və bərabərsizliklər |
| L4 | Adi kəsrlər | L13 | Müstəvi fiqurlar |
| L5 | Adi kəsrlərin müqayisəsi | L14 | Fəza fiqurları |
| L6 | Adi kəsrlərin toplanması və çıxılması | L15 | Statistika və məlumatların təsviri |
| L7 | Adi kəsrlərin vurulması və bölünməsi | L16 | İkinci yarımil – yekunlaşdırıcı test |
| L8 | Onluq kəsrlər | L17 | İllik material – yekunlaşdırıcı test |
| L9 | Adi və onluq kəsrlər (qarışıq əməllər) | | |

**Qayda (hər məşğələ mövzusuna V sinif alt mövzusu):**
1. **V sinif mövzuları** (2-ci yarımil, §5): proqram mövzusu → uyğun P001 dərsinin **alt mövzuları** (dərs faylının `h2/h3` bölmələri)
   məşğələnin mövzu mətninə «Alt mövzular: …» kimi əlavə olunur + P001 dərsinə və viktorinaya keçid (material). Məs.: «Onluq kəsrlər» → L8 (+ L9),
   «Faiz» → L10, «Həndəsə elementləri» → L13, L14, «Statistika. Ehtimal» → L15; yarımil yekunu → L16, V illik → L17.
2. **VI–VII sinif mövzuları:** hər mövzuya **V sinifdən ilkin şərt (prerequisite) alt mövzusu** – «5-ci sinifdən təkrar: …» (məşğələnin
   ilk 10 dəqiqəsi). Uyğunluq cədvəli (`app/program_data/inkisaf_v_prereq.json`: VI/VII mövzu → P001 dərsi + alt mövzu) icraçı tərəfindən
   hazırlanır, önbaxışda müəllimə göstərilir, müəllim düzəldə bilər. Uyğun V mövzusu yoxdursa – boş qalır (uydurma yoxdur).
3. Alt mövzu adları AZ/EN/RU (`{az,ru,en}`; P001-də RU/EN varsa ondan, yoxdursa `tercumeci`).
4. Mövzu testi seçimi yenə yalnız `plan_tests.py`; P001 materialı test deyil, **material/keçid** kimi bağlanır (Materiallar).

**P001 viktorinasında ad və sertifikat silinir** (istifadəçi tələbi): `5dim_sinif_testi2025/quiz.html` – «Adınızı daxil edin» sorğusu,
«🏆 Sertifikat» düyməsi, `openCertificate()` axını və `../../_Shared_Core/certificate.js` qoşulması çıxarılır; nəticə/bal ekranı qalır.
P001 ayrıca repo (Projects) – dəyişiklik orada ayrıca commit; `_Shared_Core/certificate.js` faylının özünə toxunulmur (başqa layihələr istifadə edir).
Yoxlama: quiz.html brauzerdə açılır, sonda ad soruşulmur, sertifikat düyməsi yoxdur, konsolda xəta yoxdur.

## 7. Bir gündə 2 dərs (istifadəçi, 20.10.2026) – §2.2 və §5-i dəqiqləşdirir
- Hər məşğələ günü **2 dərs = 2 mövzu**: 21:00–21:30 (1-ci dərs) və 21:30–22:00 (2-ci dərs) – fərdi qrupdakı alt vaxtlar məntiqi kimi
  (`units`; mövcud `ferdi_units` üslubu, ayrıca mühərrik yazılmır). «Hər dərsə bir mövzu» qaydası qalır – günə iki mövzu düşür.
  V sinif ilkin şərt alt mövzusu (§6.2) hər dərsin əvvəlində qısa (≈ 5 dəq.).
- Hesablama: ≈ 14 həftə × 3 gün × 2 dərs ≈ **84 dərs**, qış tətili çıxılsa ≈ 76–80 → V 2-ci yarımil (6) + V illik (1) + VI (15+1) + VII (16+1) +
  VIII (23+1) = 64, qalan ≈ 12–16 dərs IX sinfə düşür → 26.01.2027-də **təxminən IX sinfin ortası**. Dəqiq say önbaxışda.
- Yekun/illik test günü: test bir dərsi tutur, ikinci dərs növbəti mövzudur.
