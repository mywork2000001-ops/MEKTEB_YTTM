# Promt: məşğələ qruplarına proqram təyini + video bələdçi (şagird və müəllim) – 20.10.2026

**Sifarişçi:** müəllim («bütün hüquqları verirəm», 20.10) · **Rəhbər:** Claude (Opus) · **İcraçılar:** `kodcu` ×2 (worktree).
Əsas: audit `docs/audit-meshgele-qruplari-2026-10-20.md`, davam promtu `docs/davam-promtu-2026-10-20.md`.

## A. Məşğələ qruplarına proqram (inkişaf → «Sinif testləri» V–IX, tərəqqi → perspektiv proqram)

### Rəhbərin qərarları
1. **Model (auditin B variantı, miqrasiya – yalnız ADD COLUMN, start-da avtomatik):** `extra_courses.kind` (`inkisaf | tereqqi | diger`, null=diger),
   `program_id` (FK plan_programs, null), `program_sections` (JSON, null). `ExtraSession.topic_ref` (String, null) – idempotentlik üçün.
2. **Qrup tipinin tanınması** (kind boşdursa): `audience.levels` ⊇ {Zəif} və ya ad/məqsəddə «inkişaf|zəif» → inkisaf; {Güclü} və ya «tərəqqi|güclü» → tereqqi;
   qalanı – diger (toxunulmur). Müəllim formada tipi əl ilə dəyişə bilər. `add_members` `levels`-i sıfırlayanda tip `kind`-də qalır (audit bug №1).
3. **İnkişaf (V–IX):** proqram = `dim-sinif-testleri-{grade}` (grade – auditoriya sinfinin `grade`-i; bir neçə sinif – ən kiçik). Ardıcıllıq:
   ① **giriş diaqnostikası** (ilk məşğələ), ② əvvəlki sinfin prerekvizit mövzuları – yalnız proqramda «təkrar» bölməsi varsa,
   ③ proqram mövzuları sinfin perspektiv planı ilə **paralel tempdə** (məşğələ tarixinə qədər sinifdə keçilmiş və ya bu həftə keçiləcək mövzu
   prioritetlidir – dəstək məntiqi), ④ **çıxış testi** (son məşğələ). Test variantı A+B. V–VIII: test «⏳ Gözlənilir» (PENDING_GRADES), mövzu yenə yazılır.
4. **Tərəqqi:** proqram = sinfin perspektiv planı (əsas `ta.program_id` / PlanLesson ardıcıllığı) **1–2 həftə irəli**, eyni mövzu №-si ilə;
   proqramda «Güclü» səviyyəli proqram varsa (PlanProgram.level='Güclü', eyni sinif) – o seçilir. Test variantı B+C (və ya olimpiada/DİM formatı
   bankda varsa). Giriş/çıxış testi – eyni.
5. **Doldurma:** `programs.topic_sequence(db, program, ta)` → `extra.fill_from_program(course, overwrite=False)`: keçirilmiş (held) və müəllimin əl ilə
   yazdığı mövzulara toxunulmur; `topic_ref` ilə təkrar işlətmə dublikat yaratmır; cədvəl/bitmə tarixi dəyişəndə yenidən hesablanır.
   Mövzu testləri **yalnız `plan_tests.py`** vasitəsilə (yeni resolver `r_extra_program`, opts: variantlar, səviyyə) – layihə qaydası.
6. **Kütləvi təyinat:** `POST /api/extra/assign-programs?dry=1|0` (müəllim – öz qrupları; admin – hamısı): hər qrup üçün tip, sinif, seçilən proqram,
   doldurulacaq məşğələ sayı, xəbərdarlıqlar. UI: Məşğələ qrupları səhifəsində «📚 Proqramları təyin et» → önbaxış cədvəli → «Tətbiq et».
   Skript `backend/scripts/extra_programs.py --dry/--apply` (eyni funksiya). Canlıda Rəhbər deploydan sonra önbaxış → tətbiq (istifadəçi icazə verib).
7. **Audit P1 düzəlişləri:** `PUT /sessions` ilə `held` yalnız `mark_held` yolu ilə; `session_test` idempotent (köhnə batch-i səssiz əvəz etmir – 409 və ya
   «yenilə» bayrağı); `CoursePatch` cədvəl dəyişikliyi + yenidən qurma (keçirilmişlər qalır); **şagirdə «zəif/güclü» sızmasın** – portalda tip/level
   göstərilmir, ad «Zəif qrup» kimi yazılıbsa şagirdə neytral ad («Riyaziyyat – əlavə məşğələ»).
8. **P2:** `suggest_topics` bütün `ta_ids` üçün; `ExtraCourses.tsx` tərcümə olunmayan sətirlər; server `DAYS`/join mesajları AZ/EN/RU;
   statistika – giriş/çıxış testi fərqi (effekt), qrup arası keçid təklifi (çıxış ≥80% → tərəqqi, <50% tərəqqidə → inkişaf), yalnız təklif.
9. **P3 (sonraya):** N+1 sorğular, şagirdin iki məşğələsinin vaxt toqquşması, çap forması.
10. Testlər `tests/test_extra_programs.py`: tip tanınması; inkişaf V və IX – düzgün proqram; tərəqqi – sinif planı irəli; idempotent təkrar;
    held mövzuya toxunmur; dry=1 heç nə yazmır; şagird portalında level/tip yoxdur; held bug; session_test idempotent.

## B. Video bələdçi – şagird və müəllim üçün

### Rəhbərin qərarları
1. **Nə:** tətbiqin içində **«🎬 Bələdçi»** səhifəsi: şagird menyusunda (`/guide`) və müəllim menyusunda (Tənzimləmə yanında / kömək).
   Hər bölmə = qısa video (30–90 san.) + addım-addım mətn (AZ/EN/RU) + «Videonu tam ekran aç». İlk girişdə şagirdə bir dəfə
   «Tətbiqlə tanış ol – 3 dəqiqəlik video» kartı (bağlana bilər, yadda saxlanır – localStorage, try/catch).
2. **Videoların hazırlanması (AI-sız, pulsuz):** Python Playwright (quraşdırılıb) ilə **lokal tətbiq + demo məlumat** (real şagird adı YOX – demo
   «Şagird Bir», «Test Müəllim») üzərində ekran yazısı (`record_video_dir`, 1280×720) → `.webm`. Skript `scripts/guide_videos.py`
   (ssenarilər bir faylda: addım, gözləmə, alt yazı). Alt yazılar video üstündə HTML overlay deyil – **WebVTT** (`.vtt`, AZ/EN/RU), brauzer `<track>` ilə;
   dil tətbiqin dilinə görə seçilir. Kursor/klik vurğusu – səhifəyə yazı zamanı CSS ilə əlavə olunan dairə.
3. **Şagird videoları:** ① giriş (ID + PIN, dil seçimi), ② ana səhifə və menyu, ③ mövzu testini işləmək (müddətsiz, cavab saxlanır, təhvil), ④ sınaq,
   ⑤ nəticələr və **nəticə paketi** (səhv suallar, izah, apelyasiya), ⑥ **işləməli olduğun testlər** siyahısı, ⑦ materiallar və məşğələ, ⑧ telefonda istifadə.
4. **Müəllim videoları:** ① menyu və əsas səhifə («Bu həftə diqqət»), ② perspektiv plan və **plan testlərinin təyini**, ③ sinif matrisi «Kim nəyi işləyib» +
   **işlənməyənlər siyahısı və çapı**, ④ kağız test/KSQ: vərəqə, skan, nəticə paketi, ⑤ məşğələ qrupları və proqram təyini, ⑥ jurnal və hesabatlar.
5. **Yer:** `frontend/public/guide/{student|teacher}/NN-ad.webm` + `.vtt`; ölçü – hər video ≤ 3 MB (720p, aşağı fps); ümumi ≤ 40 MB.
   Video hazır deyilsə – bölmə yalnız addımlı mətnlə göstərilir (səhv deyil).
6. **i18n:** bütün səhifə mətnləri `t()`; alt yazılar üç dildə.
7. Testlər: build; `scripts/guide_videos.py --check` (bütün ssenari selektorları mövcuddur); Bələdçi səhifəsi video olmayanda da açılır.

## C. Ardıcıllıq və bitiş
1. Müddətsiz testlər (icrada) → merge. 2. A (kodcu, worktree) və B (kodcu, worktree) paralel → review → merge.
3. Aid pytest + `npm run build` → commit → **push** → Render statusu → `/api/health/db`.
4. Canlı (Chrome bağlıdırsa): ferdi-units, unlimit-tasks, extra assign-programs – önbaxış → tətbiq; bağlı deyilsə – HANDOFF-da «gözləyir».
5. HANDOFF + yaddaş → worktree-lər silinir → **kompüter söndürülür** (istifadəçi tələbi, `shutdown /s /t 60`).
