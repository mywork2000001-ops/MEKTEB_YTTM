# Tapşırıq: Sinfin sektoru və yazılı imtahanın dili
- Tarix: 2026-10-24   Müəllif: Rəhbər (Claude)   İstifadəçi tələbi: «каждый класс мог выбирать свой сектор, например 6-й класс – русский сектор, но при письменном – азербайджанский язык»
- İcraçı: `kodcu` (kod + testlər); miqrasiya canlıda — Rəhbər (Neon backup branch-dan sonra)
- Budaq: `sektor-dil` (worktree)

## Məqsəd (müəllimin dili ilə)
Hər sinif üçün iki ayrı seçim: **sektor** (sinif hansı dildə oxuyur) və **yazılı imtahanın dili** (KSQ/BSQ və kağız testlər hansı dildə çap olunur).
Məsələn: VI sinif — rus sektoru, amma yazılı imtahan Azərbaycan dilində. Bir imtahanda lazım olarsa — imtahanın öz dili (istisna).

## İndiki vəziyyət (kodda yoxlanıb)
- `SchoolClass`-da (models.py:98-115) sektor/dil sahəsi **yoxdur**.
- KSQ/BSQ vərəqi hər şagirdin **interfeys dilinə** görə çap olunur: `api/exams.py:1039-1049` (`User.language` → `pick_lang`). Rus sektorunun şagirdi interfeysi AZ-a keçiribsə vərəq AZ olur və əksinə — sinif daxilində dil qarışır.
- Şagirdin nəticə paketi (`api/portal.py:702`, `student_package(..., user.language)`) də interfeys dilindədir.
- Kiril hərfli sinif adı («IХ а») `grade_of`-da tanınmır (docs/rus-sektor-9-sinaqlar-promtu.md, səbəb 2) — rus sektoru sinifləri sinif süzgəclərindən düşə bilər.

## Qərarlar (Rəhbər)
1. **İki sahə** `SchoolClass`-da (miqrasiya, nullable, məlumat dəyişmir):
   - `sector: 'az' | 'ru'` — defolt `'az'` (NULL = az).
   - `exam_language: 'sector' | 'az' | 'ru' | 'az_ru'` — defolt `'sector'` (NULL = sector). `az_ru` = ikidilli vərəq (əsas mətn AZ, altında kiçik şriftlə RU).
2. **İmtahan səviyyəsində istisna:** `Exam.language` (nullable) — imtahan yaradılanda/redaktədə «Sinfin qaydası (defolt) / AZ / RU / İkidilli». JSON sahəsi varsa (məs. `Exam.items`/ayarlar) miqrasiyasız ora; yoxdursa eyni miqrasiyada sütun.
3. **Dilin seçilmə sırası** (bir funksiya, `backend/app/domain/exam_lang.py`): `exam.language` → `class.exam_language` (`'sector'` → `class.sector`) → `'az'`. Şagirdin interfeys dili yazılı imtahan vərəqinə **təsir etmir**. Qrup sinfi (`parent_id`) öz dəyəri yoxdursa ana sinifdən götürür.
4. **Harada tətbiq olunur:** KSQ/BSQ vərəqləri və boş blank (`api/exams.py:1010-1050`), kağız testlər (`api/paper_exams.py`), paket/kart çapı (`frontend/src/ksqPrint.ts`, `packagePrint.ts`, `examCardPrint.ts` — dil serverdən gələn `lang`-dan), fərdi yazılı imtahan (docs/ferdi-yazili-imtahan-promtu.md — əgər ayrıca yoldursa), onlayn KSQ (`api/ksq_online.py`) — sual mətni də imtahan dilində (eyni imtahan, eyni dil).
5. **Nəticə paketi** (şagirdə): sual və variant mətnləri **imtahanın dilində** (şagird nə yazdısa onu görsün), interfeys sözləri (başlıqlar, düymələr) — şagirdin öz dilində.
6. **Tərcümə çatmırsa:** sualın RU mətni yoxdursa AZ çap olunur; çapdan əvvəl müəllimə xəbərdarlıq: «N sualın rus dilində mətni yoxdur – Azərbaycan dilində çap olunacaq» + siyahı (sual №). İkidillidə RU yoxdursa yalnız AZ.
7. **Vərəqin özü:** başlıq, təlimat, «Ad, soyad», «Variant», cavab cədvəli sözləri imtahan dilində (az/ru). Rəsmi jurnal və rəsmi çap formaları — həmişə AZ (CLAUDE.md qaydası), bu vərəqlərə aid deyil.
8. **Kiril sinif adı:** `domain/classes.py:grade_of` kiril І/Х/V/Ⅰ oxşar hərfləri latına çevirsin (test: `grade_of('IХ а') == 9`, `grade_of('VІ б') == 6`).
9. **Yeni şagird hesabı** rus sektoru sinfində yaradılanda interfeys dili defolt `ru` (sonra şagird özü dəyişə bilər). Mövcud hesablara toxunma.

## Nə etmək lazımdır
1. Model + miqrasiya (`backend/migrations/versions/`, tək head, downgrade; yalnız add_column).
2. `domain/exam_lang.py`: `exam_lang(db, exam, cls) -> 'az'|'ru'|'az_ru'` + `pick_lang` ikidilli rejimi (`{'main': az, 'sub': ru}` və ya iki sahə — çap kodu ilə uyğun).
3. API: sinif yaratma/redaktə (`api/classes.py`) `sector`, `exam_language`; imtahan yaratma/redaktə (`api/exams.py`) `language`; vərəq endpoint-i (`:1010-1050`) dili funksiyadan alır; `missing_translations` sayı cavaba əlavə.
4. Frontend:
   - Siniflər → «Məlumat» tabı: «Sektor: Azərbaycan / Rus», «Yazılı imtahanın dili: Sektora uyğun / Azərbaycan dili / Rus dili / İkidilli» (izah sətri: «Şagirdlərin interfeys dili vərəqə təsir etmir»).
   - Sinif siyahısında kiçik nişan «RU sektoru», imtahan dili sektordan fərqlidirsə «yazılı: AZ».
   - İmtahan formasında dil seçimi (defolt «Sinfin qaydası»); çapdan əvvəl tərcümə xəbərdarlığı.
   - Bütün yeni mətnlər AZ/EN/RU (`t()`).
5. `grade_of` kiril düzəlişi.

## Testlər
- `tests/test_exam_lang.py`: sıra (exam > class.exam_language > sector > az); qrup ana sinifdən götürür; `User.language='az'` olan rus sektoru şagirdinin vərəqi `exam_language='ru'`-da RU; `az_ru` iki mətn; RU yoxdursa AZ + `missing_translations`.
- Nəticə paketi: sual mətni imtahan dilində, interfeys açarları şagird dilində.
- `grade_of` kiril halları.
- Miqrasiya upgrade → downgrade → upgrade (müvəqqəti SQLite).
- `npm run build` + aid pytest; sonda tam pytest (Rəhbər).

## Toxunma
KSQ/BSQ qiymət şkalası, skan oxuma (variant hərfləri/sırası dildən asılı deyil — dəyişməməlidir), apelyasiya məntiqi, rəsmi çap formaları (yalnız AZ).

## Qəbul (müəllim nə görəcək)
- VI sinif: Sektor = Rus, Yazılı = Azərbaycan dili → KSQ vərəqləri hamısı AZ, şagirdlərin interfeysi RU qalır, nəticədə suallar AZ, düymələr RU.
- Bir imtahanda «Rus dili» seçiləndə yalnız o imtahan RU çap olunur.
- RU tərcüməsi olmayan suallar üçün çapdan əvvəl siyahı ilə xəbərdarlıq.
- Rus sektoru IX sinfi (kiril adla) sınaq/sinif süzgəclərində görünür.

## Cavab formatı
docs/agent-sistemi-promtu.md §7: dəyişən fayllar, miqrasiya revision/down_revision, i18n açarları, pytest, build, açıq suallar.
