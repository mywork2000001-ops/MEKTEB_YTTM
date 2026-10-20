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
