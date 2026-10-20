# Kart: vahid «Analitika və hesabat» bölməsi (promt: `docs/analitika-bolmesi-audit-promtu.md`)

**İcraçı:** `kodcu` (worktree, main-in işlənməyənlər hesabatı birləşmiş vəziyyətindən). Canlı DB, deploy, push, miqrasiya – YOX.
Promt §2 – hədəf quruluş, §3 – qəbul meyarları. Funksiyaları köçür, yenidən yazma: mövcud komponentləri (Overview, Performance,
Rating, Levels, Risk, Attendance, LessonCounts, PrintCenter, ResultsCenter tabları, ClassMatrix, StudentReport, SchoolReport,
CertificatesPanel) yeni qruplara bağla.

## Addımlar
1. `frontend/src/pages/teacher/Reports.tsx` → qrup + tab naviqasiyası (`g`, `t` URL parametrləri, ortaq sinif/dövr seçimi).
   Böyük fayl olarsa bölmələri ayrı fayllara çıxar (`reports/` qovluğu) – davranış dəyişmədən.
2. ResultsCenter tablarını `embedded` rejimdə «Testlər və sınaqlar» qrupuna qoş; «Reytinq» → «Test reytinqi», Reports «Reytinq» → «Ümumi reytinq»
   (alt yazıda formula). Şagird hesabatı → «Şagird» qrupu (`student` parametri).
3. «Çap mərkəzi»: sənəd siyahısı (ad, təsvir, format, düymə). Bu bölmənin sənədləri birbaşa; Jurnal / Plan / Sinif siyahısı / KSQ paketləri – öz
   səhifələrinə keçid (`navigate`).
4. `TestsHub.tsx`: «netice» bölməsini çıxar, yerinə «📊 Nəticələr → Analitika» düyməsi; `?s=netice…` → `/reports?g=tests&t=…` yönləndirməsi
   (student → `g=student&student=ID`). `Home.tsx` və digər daxili keçidlər (`grep "/tests?s=netice"`) birbaşa yeni URL-ə.
5. Telefon: qrup seçimi açılan siyahı, tablar sürüşən; mövcud CSS sinifləri (`tabs rtabs`, `hub-pick`).
6. Yeni mətnlər `t()` + `i18n.ts` (AZ/EN/RU, Grep, təkrar açar yox).

## Yoxlama
`cd frontend && npm run build 2>&1 | tail -5`; backend toxunulubsa aid pytest.
Hesabata **köçürmə cədvəli** yaz: köhnə yer → yeni yer (hər tab/düymə), itən funksiya olmamalıdır.
Hesabat: budaq, commit, fayllar, build, köçürmə cədvəli, edilməyənlər.

## Mərhələ 3 (promt §5–6; Mərhələ 2 birləşəndən sonra ayrıca icra)
- A8 Journal «Bölmələr üzrə icra» → Analitika «Akademik nəticələr → Standartlar üzrə»; Jurnalda qısa sətir + keçid.
- A9 Homeroom «Fənlər üzrə müvəffəqiyyət / Müvəffəqiyyət (şagird üzrə)» → «Sinif rəhbəri» qrupu (yalnız sinif rəhbərinə; `me` üzrə yoxla).
- A10 Tasks «Suallar üzrə» → «Testlər və sınaqlar → Sual təhlili» (test seçimi); Tasks-da keçid.
- A11 OnlineExams «Reytinq →» → `/reports?g=tests&t=rating`.
- A12 ExtraCourses «Statistika/Effekt» → «Məşğələlər» qrupu (müqayisə cədvəli); kursda qısa göstərici + keçid.
- A13 Surveys nəticə görünüşü → «Sorğu nəticələri» qrupu; yaratma Surveys-də.
- A14 Home rəqəmləri → uyğun tablara keçid.
Komponenti köçür (import et), məntiqi kopyalama; köhnə yerdə keçid. Köçürmə cədvəli hesabatda.
