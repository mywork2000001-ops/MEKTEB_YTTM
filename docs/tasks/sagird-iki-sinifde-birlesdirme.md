# Tapşırıq kartı: iki sinifdə yazılmış şagirdlərin birləşdirilməsi (IX + X və s.)

**Tarix:** 19.10.2026 · **Sifarişçi:** müəllim (istifadəçi) · **Rəhbər:** Claude (Opus) · **İcraçı:** `kodcu` (kod), canlı DB – yalnız Rəhbər
**Status:** icrada (istifadəçi 19.10.2026: «Rəhbərin qərarları ilə icra et»)

## 0. Rəhbərin qərarları (istifadəçi təsdiqlədi)
1. **Saxlanan qeyd** = daha çox məlumatı olan (qiymət + test + davamiyyət cəmi); bərabərdirsə – yuxarı sinif (X).
   Əsas sinif = saxlananın sinfi, o biri – əlavə sinif.
2. **Avtomatik birləşdirilir** yalnız: ad sözləri tam eyni (yazılış fərqi daxil: Huseyn = Hüseyn), siniflər fərqli,
   doğum tarixləri ziddiyyətsiz. «Oxşar ad» (məs. «Elvin» ↔ «Elvin Əliyev») – birləşdirilmir, istifadəçiyə siyahı verilir.
3. **Ehtiyat nüsxə**: birləşdirmədən əvvəl `GET /api/admin/backup` (JSON) yerli diskə, git-ə getmir.
4. Canlı icra – Chrome-da admin sessiyası ilə mövcud `POST /api/students/merge` (yeni miqrasiya yoxdur).
5. Axtarışın gücləndirilməsi (addım 2) – `kodcu`, worktree; birləşdirmə ondan asılı deyil (canlıdakı cütlər əl ilə də yoxlanır).

## 1. Məqsəd
Bəzi şagirdlər iki sinifdə dərs alır (məs. **şagird A – IX və X**). Hazırda bazada onlar **iki ayrı şagird** kimi
yazılıb: iki ID kodu, iki PIN, qiymətlər/testlər/davamiyyət iki yerə bölünüb. Nəticə: **bir şagird = bir qeyd (bir ID, bir PIN),
iki sinifdə görünür** – əsas sinif `students.class_id`, əlavə sinif `group_members`-də.

## 2. Mövcud vəziyyət (yoxlanılıb, 19.10.2026)
- Birləşdirmə artıq var: `backend/app/api/students.py` – `GET /api/students/duplicates`, `POST /api/students/merge`,
  `merge_students()` (bütün FK cədvəlləri + JSON siyahıları köçürür, silinən qeyd arxivə, portal hesabı bağlanır,
  silinənin sinfi → saxlananın əlavə sinfi). UI: Sinif üzvləri → «Təkrar şagirdlər» (`ClassMembers.tsx::Duplicates`, yalnız admin).
- Miqrasiya `b3c5d7e9f1a2` (12.10) şagird A-nı **X + XI** kimi axtarırdı – istifadəçi indi **IX + X** deyir ⇒ çox güman
  heç nə etməyib («not found» / «ambiguous»). Render logunda `student merge:` sətrini yoxla.
- Axtarış zəifliyi: `name_tokens()` hərf variantlarını tanımır – «Huseyn» ≠ «Hüseyn», «Mammadov» ≠ «Məmmədov»,
  «İ/I/ı» (casefold «İ» → «i̇»). Belə cütlər siyahıya düşmür.

## 2a. Diaqnoz nəticəsi (canlı, 19.10.2026, yalnız oxu)
Təkrarlar **fərdi hazırlıq məkanındadır** (school_id 2), məktəb məkanında (1) yoxdur:
| Şagird (ad git-də yoxdur) | Qeyd A | Qeyd B | Problem | Qərar |
|---|---|---|---|---|
| Şagird A | id 111, «10-cu sinif» | id 96, «Buraxılış IX sinif» | doğum ili fərqli (yazı xətası) → `duplicates` göstərmir | saxla 111 (X əsas), 96 → əlavə sinif; d.t. istifadəçi yoxlasın |
| Şagird B | id 99, «11A» | id 116, «Buraxılış IX sinif» | «oxşar ad» (ata adı yoxdur); 12.10 miqrasiyası işləməyib | saxla 99 (11A əsas, istifadəçinin 12.10 qərarı) |
Birləşdirmə: `PUT /api/workspaces/active {school_id:2}` → `POST /api/students/merge` (keep/drop/confirm=saxlananın adı) → məkanı 1-ə qaytar.
Geri qaytarma yolu: Neon point-in-time restore (birləşdirmə vaxtını qeyd et).

## 3. Addımlar
### Addım 1 – Diaqnoz (yalnız oxu, canlı DB, Rəhbər)
- Canlı bazadan bütün ehtimal olunan təkrarları çıxar (`/api/students/duplicates` məntiqi + yeni normallaşdırma, bax addım 2).
- Cədvəl hazırla: ad | sinif A (ID, qiymət/test/davamiyyət sayı) | sinif B (eyni) | doğum tarixi | səviyyə.
- **Heç nə dəyişmə.** Cədvəli istifadəçiyə göstər; hər cüt üçün soruş: birləşdirilsin? **əsas sinif hansıdır?**
  (Default təklif: daha çox qiyməti/testi olan qeyd və ya şagirdin portalda işlətdiyi ID qalır.)

### Addım 2 – Axtarışın gücləndirilməsi (kodcu, worktree)
- `name_tokens()`-ə normallaşdırma: `ə→e, ü→u, ö→o, ı/İ→i, ş→s, ç→c, ğ→g`, unicode NFKD + birləşən işarələrin silinməsi;
  `oğlu/qızı/oglu/qizi` tanınsın. Mövcud qaydalar (sıra fərq etmir, doğum tarixi fərqlidirsə – təkrar deyil) qalır.
- Səviyyə: tam ad eyni amma yazılış fərqli → «ad və soyad eyni (yazılış fərqli)».
- Testlər `tests/test_api_students_multi.py`: «Huseyn Mammadov» ↔ «Məmmədov Hüseyn», «İlkin» ↔ «Ilkin», ata adı ilə/siz.

### Addım 3 – Birləşdirmə (Rəhbər, istifadəçinin hər cüt üzrə «hə» cavabından sonra)
- Birləşdirmə **UI və ya `POST /api/students/merge`** ilə, hər cüt ayrıca (təsdiq – saxlanan şagirdin adı).
  Yeni miqrasiya yazılmır (təkrar «ad axtarışı» riski).
- Əvvəl: Neon-da branch/snapshot və ya `pg_dump` yalnız `students`, `group_members` və FK cədvəllər üçün (geri qaytarma yolu).
- Hər birləşmədən sonra cavabdakı `moved / conflicts / json` sayını qeyd et.

### Addım 4 – Yoxlama (canlı)
- Şagird **hər iki sinfin** siyahısında, jurnalında, test nəticələrində, analitikada görünür; ikinci sinifdə «əlavə sinif» nişanı.
- Qiymət/davamiyyət sayı = iki köhnə qeydin cəmi − toqquşmalar.
- Köhnə ID ilə giriş bağlıdır, saxlanan ID + PIN ilə giriş işləyir; şagird portalında hər iki sinfin tapşırıqları var.
- Sinif rəhbəri vərəqəsi, çap formaları (jurnal), «<5 şagird – orta gizli» qaydası pozulmayıb.
- Təkrar `duplicates` çağırışı – həmin cüt artıq yoxdur.

## 4. Qadağalar / riskli yerlər
- Birləşdirmə **geri qaytarılmır** – istifadəçinin konkret cüt üzrə razılığı olmadan canlıda heç nə etmə.
- Doğum tarixləri fərqlidirsə – birləşdirmə (başqa uşaqdır), istifadəçiyə göstər.
- Arxivdəki şagird birləşdirilmir. Fərqli məktəbdəki qeydlərə toxunma.
- Silinən qeydin PIN-i ilə giriş dayanır – istifadəçiyə şagirdə **yeni ID/PIN-i** verməyi xatırlat (çap: giriş vərəqəsi).

## 5. Dil (CLAUDE.md)
Yeni/dəyişən UI mətnləri `t('…')` ilə, `frontend/src/i18n.ts`-ə AZ + EN + RU (məs. «yazılış fərqli» → «spelling differs» /
«написание отличается»). Server mesajı şagirdə görünmür – yalnız AZ.

## 6. Qəbul meyarları
- [ ] `npm run build` (frontend) OK; aid pytest (`tests/test_api_students_multi.py` və birləşdirmə testləri) keçir.
- [ ] Diaqnoz cədvəli istifadəçiyə göstərilib, hər cüt üzrə qərar alınıb.
- [ ] Təsdiqlənmiş cütlər birləşib; şagird A – bir ID, IX + X siniflərində.
- [ ] Addım 4 yoxlamaları canlıda keçib; Render deploy success; `docs/HANDOFF.md`-ə sətir.
- [ ] Worktree və budaq birləşmədən sonra silinib.
