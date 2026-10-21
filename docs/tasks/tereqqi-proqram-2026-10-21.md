# Kart: tərəqqi qrupu proqramı + məşğələ qruplarına avtomatik təyinat (21.10.2026)

**Sifarişçi:** müəllim: «məşğələ qruplarına dərs təyin edilməyib – özün icra et; tərəqqi qrupu üçün də proqramı hazırla və sistemə sal».
**Rəhbər:** Claude (Opus) · **İcraçı:** `kodcu` (worktree) · **Status:** ✅ main 5622f0f, deploy success.
**Qaydalar:** CLAUDE.md – AZ/EN/RU; mövzu testi seçimi YALNIZ `app/plan_tests.py`; `npm run build` + aid pytest.

## Vəziyyət (əvvəl)
- `app/extra_programs.py::_program`: tərəqqi qrup `PlanProgram(level='Güclü', grade, subject)` axtarır; yox idi → rejim `plan`.
- Canlıda kütləvi təyinat (`POST /api/extra/assign-programs?dry=0`) heç vaxt işə salınmamışdı → məşğələ mövzuları boş.

## 1. Daxili «Tərəqqi» proqramları (V–XI) – `app/programs.py::ensure_builtin`
- `PlanProgram(key=f'tereqqi-{g}', level='Güclü', subject='Riyaziyyat', grade=g, kind='adaptive', format 'course')`, idempotent.
- Mənbə `program_data/sinif_testleri.json`; «Təkrar…» bölmələri çıxır; mövzular eyni adla (bank ad üzrə tapır) + hər bölmənin sonunda
  «Bölmə üzrə mürəkkəb məsələlər» (adda «güclü/tərəqqi» sözü yoxdur – `LEAK`). IX, XI: `mock_every: 8`; hamısında `final_mock`.

## 2. Avtomatik təyinat – `app/scheduler.py::_extra_programs_job`
- Gündə 06:10 + açılışdan 2 dəq sonra: bütün arxivlənməmiş `ExtraCourse` → `assign_programs(apply=True)`, audit qeydi.
- İdempotent; keçirilmiş və əl ilə yazılmış mövzulara toxunulmur; tip `diger` / sinif tanınmayan qrup keçilir.

## 3. Testlər
`tests/test_extra_programs.py` (builtin idempotent, tərəqqi proqramı + scheduler idempotent, riyaziyyat balı); köhnə
`test_api_programs*.py` tərəqqi proqramlarını nəzərə alacaq şəkildə düzəldildi. Tam pytest: 534 passed.

## Əlavə 21.10 (istifadəçi)
1. Hibrid format: dərslər asinxron (şagird mövzunu onlayn keçir: material + test), həftədə 2 görüş (hər görüş – bir mövzunun/çətin
   məsələlərin təhlili). Mövzular həftəyə ≈2 görüşə düşür (mövcud «mövzu = cədvəl görüşü» qaydası); qrupun real cədvəli üstündür.
   Tərəqqi qrupu yaradılanda defolt 2 görüş (forma ikinci slotu özü əlavə edir); inkişaf – 3. Testlər plan_tests.py ilə (dublikat yoxdur).
2. Tərəqqi tərkibi: qrupun fənni (Riyaziyyat) üzrə bal ≥ 50 (`audience.min_score`, defolt 50; levels.py bölgü balı; LEVEL_HIGH=70 dəyişmir).
   `members()` min_score verilibsə səviyyə süzgəcini əvəz edir; balı olmayan düşür; min_score=0 – süzgəc yoxdur; əl ilə seçilmiş
   şagirdlərə (student_ids) tətbiq olunmur. Formada «Minimum bal» (AZ/EN/RU).
3. Testlər: test_tereqqi_members_by_math_score (55 – qrupda, 45 – yox, defolt 50, inkişaf toxunulmaz).   Köhnə tərəqqi qrupları (min_score yoxdur) də defolt 50 ilə (Rəhbər düzəlişi).
