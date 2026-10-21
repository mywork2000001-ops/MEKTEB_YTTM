# Kart: tərəqqi qrupu proqramı + məşğələ qruplarına avtomatik təyinat (21.10.2026)

Tam mətn əsas qovluqda (docs/tasks/tereqqi-proqram-2026-10-21.md, commitsiz). İcra: ensure_builtin `tereqqi-5..11`, scheduler `extra_programs`.

## Əlavə 21.10 (istifadəçi)
1. Hibrid format: dərslər asinxron (şagird mövzunu onlayn keçir: material + test), həftədə 2 görüş (hər görüş – bir mövzunun/çətin
   məsələlərin təhlili). Mövzular həftəyə ≈2 görüşə düşür (mövcud «mövzu = cədvəl görüşü» qaydası); qrupun real cədvəli üstündür.
   Tərəqqi qrupu yaradılanda defolt 2 görüş (forma ikinci slotu özü əlavə edir); inkişaf – 3. Testlər plan_tests.py ilə (dublikat yoxdur).
2. Tərəqqi tərkibi: qrupun fənni (Riyaziyyat) üzrə bal ≥ 50 (`audience.min_score`, defolt 50; levels.py bölgü balı; LEVEL_HIGH=70 dəyişmir).
   `members()` min_score verilibsə səviyyə süzgəcini əvəz edir; balı olmayan düşür; min_score=0 – süzgəc yoxdur; əl ilə seçilmiş
   şagirdlərə (student_ids) tətbiq olunmur. Formada «Minimum bal» (AZ/EN/RU).
3. Testlər: test_tereqqi_members_by_math_score (55 – qrupda, 45 – yox, defolt 50, inkişaf toxunulmaz).