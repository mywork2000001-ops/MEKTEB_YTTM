# Test nəticələri mərkəzi: iki hissəli reytinq, yazmayanlar, şagird/sinif/qrup/ümumi analitika, AI pedaqoji rəy

> Tarix: 04.10.2026. Müəllimin tapşırığı: «Reytinq iki hissəli olsun – mövzu testləri və sınaqlar; testi işləməyənlər üçün
> də bir iş görək; ayrı-ayrı şagirdlərin fəaliyyətinə (mövzu və ümumi sınaqlar) baxmaq imkanı; hesabat və analitika;
> süni zəka köməkçisinin pedaqoji rəyi – şagird, sinif, qrup və ümumi; hər yerdə PDF/çap».

## 0. Rol və çərçivə

Sən bu layihənin (FastAPI + SQLAlchemy + Alembic, React + Vite) aparıcı mühəndisi və təhsil analitiki kimi işləyirsən.
Mövcud qaydaları POZMA:

- mövzu testi (`OnlineTask.kind='movzu'`, `TestBatch.kind='movzu'`) formativ jurnala düşür; sınaq (`kind='sinaq'`) düşmür –
  iki reytinq heç vaxt bir cədvəldə qarışmır (docs/sinaq-ayrilmasi-promtu.md);
- məxfilik: müəllim yalnız öz dərslərinin (aktiv məkan – `ws_cond`) şagirdlərinin adını görür; admin sınaqda məktəbin
  hamısını görür (mövcud `_access`); fərdi (repetitor) məkan məktəblə qarışmır;
- arxivdəki (silinmiş) mövzu testləri və arxivdəki şagirdlər hesaba düşmür;
- çap – yalnız `print.ts` (`printDoc`, `head`, `table`, `kpis`, `signs`) – A4, ağ-qara, «Səhifə X / Y», imza;
- AI – yalnız müəllimin öz açarı (`lessonplans.ai_config`, `ai.complete_json`).

## 1. Məlumat modeli (vahid nəticə sətri)

`app/test_stats.py` – bütün hesablamaların mənbəyi:

`collect(db, user, kind, ta_ids?, date_from?, date_to?)` → testlər (`batch_id, title, kind, date, subject, grade,
classes, topic`) və nəticə sətirləri (`student_id, full_name, class_name, ta_id, task_id, batch_id, status,
pct, grade, points, place_class, place_all`).

- Faiz: sınaqda `exams_online.results` (cərimə daxil); mövzu testində də eyni funksiya (penalty=0 → düz/ümumi).
  Bir paketdə səviyyə variantları (Zəif/Orta/Güclü) ola bilər – şagird yalnız öz variantında sayılır.
- Status: `yazıb` | `yazır` | `yazmayıb` | `gözlənilir` (test hələ açılmayıb/açıqdır – yazmayan sayılmır).
- Görünmə: müəllimin öz dərslərindəki testlər (mövzu testi – yalnız öz dərsi; sınaq – `_access` qaydası, adsız sətirlər
  çıxarılır). Admin – sınaqda məktəb üzrə; mövzu testində yalnız öz dərsləri (jurnal məxfiliyi).
- Dövr: testin açılma tarixi (məktəb vaxtı). Filtrlər: növ, fənn, dərs (sinif/qrup), dövr.

## 2. İki hissəli reytinq

Səhifə **«Test nəticələri»** (müəllim menyusu, `/results-center`), tab «Reytinq» – üstdə seçici
**«Mövzu testləri» | «Sınaqlar»**. Hər hissə ayrıca hesablanır:

- şagird üzrə: yazdığı test sayı / ona verilən, orta %, son %, dinamika (son − əvvəlki), sinifdə yer, ümumi yer
  (bərabər orta – eyni yer, `rules.rank`);
- **iştirak əmsalı**: yazdığı / bağlanmış testlər; iştirak < 50% olan şagird reytinqdə «az iştirak» nişanı ilə göstərilir
  (ortası 1–2 testlə şişməsin) – yer verilir, amma işarələnir;
- siniflərin reytinqi (sinif ortası, iştirak %);
- «Ən çox irəliləyənlər» və «Diqqət tələb edənlər» (son iki nəticə düşüb və ya orta < 40%);
- «Sınaq imtahanları» bölməsindəki köhnə «Reytinq» də bu iki hissəli komponentə keçir (təkrar kod yox).
- Çap/PDF: hər hissə ayrıca, imza – fənn müəllimi + direktor müavini.

## 3. Testi yazmayanlar

Tab «Yazmayanlar» – yalnız bağlanmış testlər üzrə:

- şagird siyahısı: yazmadığı test sayı / verilən, son yazmadığı tarix, testlərin adları; sıralama – ən çox buraxan yuxarıda;
  **xroniki** (≥3 test və ya ≥50%) – qırmızı nişan;
- testlər üzrə: hər testdə neçə nəfər yazmayıb;
- əməliyyatlar:
  1. **Yenidən göndər** – seçilmiş şagirdlərə, seçilmiş testlərin surəti yeni vaxtla (mövcud `tasks.copy_task`, öz dərs;
     `student_ids` = həmin testi yazmayan seçilmişlər). Mövzu testinin surəti də mövzu testi kimi qalır; şagird portalında
     bildiriş özü çıxır (açıq test);
  2. **Valideynlə əlaqə qeydi** – şagird kartındakı «Valideynlə əlaqə»yə hazır mətn («N testi yazmayıb: …»);
  3. **Çap / PDF** – siyahı «Daxili istifadə üçün» möhürü ilə (telefonlar yox – onlar yalnız sinif rəhbərinə açıqdır).
- Müəllimə əsas səhifədə/analitikada xatırlatma tələb olunmur – tab sayğacı kifayətdir.

## 4. Şagird profili

Tab «Şagird» (və şagird kartında «Test nəticələri» düyməsi): şagird seçimi (öz siniflərim, axtarış).

- göstəricilər: mövzu testləri ortası, sınaq ortası, iştirak, sinifdə yer (hər hissə ayrıca), formativ orta (jurnaldan);
- dinamika qrafiki (SVG, iki xətt: mövzu testi və sınaq; sinif ortası – qırıq xətt);
- cədvəl: hər test – tarix, növ, ad/mövzu, faiz, qiymət, sinif ortası, fərq, yer, status;
- **mövzular üzrə**: mövzu testlərindən ən zəif və ən güclü 5 mövzu;
- AI pedaqoji rəy (§7), çap/PDF (fərdi hesabat – valideynə vermək üçün).

## 5. Sinif / qrup

Tab «Sinif və qrup»: dərs seçimi (sinif və ya tədris qrupu) + alt seçim «Bütün sinif | Zəif | Orta | Güclü» (səviyyə
qrupu – `LevelOverride`).

- göstəricilər (iki hissə ayrıca), testlər üzrə sinif ortası və iştirak, qiymət paylanması («5/4/3/2»),
- səviyyə qrupları müqayisəsi, ən zəif mövzular, yazmayanların sayı;
- AI rəy (sinif və ya seçilmiş səviyyə qrupu), çap/PDF.

## 6. Ümumi

Tab «Ümumi»: bütün dərslərim (aktiv məkan) – siniflərin müqayisəsi (mövzu testi və sınaq ortası, iştirak, test sayı,
xroniki yazmayan), ay üzrə dinamika, AI ümumi rəy, çap/PDF.

## 7. Süni zəka köməkçisinin pedaqoji rəyi

`POST /api/results-center/ai-review` `{scope: student|class|group|overall, ta_id?, student_id?, level?, kind?,
date_from?, date_to?}`.

- Kontekst – yalnız rəqəmlər (faizlər, dinamika, mövzular, iştirak). **Adlar provayderə göndərilmir**: «Ş-1, Ş-2…»
  kodları, cavabda server adları geri qoyur.
- Sistem promtu: təcrübəli metodist; Azərbaycan dilində; dəlilə əsaslan (rəqəm göstər); etiketləmə və mühakimə yox;
  formativ qiymətləndirmə dilində; konkret, ölçülə bilən, 2–4 həftəlik addımlar.
- JSON cavab: `xulase` (3–5 cümlə), `guclu` [], `zeif` [], `sebebler` [] (ehtimal, «ola bilər» dili),
  `tovsiyeler` [{ne, kim, muddet}], `valideyne` (şagird üçün; sinifdə boş), `diqqet` [] (risk/şagird kodları ilə).
- Nəticə `ai_reviews` cədvəlində saxlanır (müəllim, scope, açar, mətn, model, tarix) – sonuncu rəy səhifə açılanda
  göstərilir, «Yenilə» ilə təzədən. Çapa daxil edilir («Süni intellekt köməkçisinin rəyi – müəllim tərəfindən
  yoxlanmalıdır» qeydi ilə).
- AI qoşulmayıbsa – izahlı xəta (Tənzimləmələr → Süni intellekt).

## 8. Çap / PDF (hər yerdə)

Hər tab öz «Çap / PDF» düyməsinə malikdir: Reytinq (hər hissə), Yazmayanlar, Şagird hesabatı, Sinif/qrup hesabatı,
Ümumi hesabat. Hamısı `printDoc`/`printLater` ilə; başlıqda dövr və filtr; AI rəyi varsa ayrıca bölmə.

## 9. Mənim əlavələrim (müəllimin icazəsi ilə)

- iştirak əmsalı və «az iştirak» nişanı (ədalətli reytinq);
- «Diqqət tələb edənlər» siyahısı (düşən dinamika / < 40%);
- şagird kartından birbaşa profilə keçid; yazmayanlara valideyn əlaqə qeydi;
- şagird portalında «Nəticələrim»də öz mövzu testi ortası və sinifdə yeri (adsız, mövcud sınaq bölməsi kimi).

## 10. Mərhələlər

1. Backend: `test_stats.py` + `api/results_center.py` (reytinq, yazmayanlar, şagird, sinif/qrup, ümumi) + testlər.
2. Frontend: «Test nəticələri» səhifəsi – Reytinq (iki hissə) və Yazmayanlar (yenidən göndər, çap).
3. Şagird profili, sinif/qrup, ümumi – qrafik və çap; şagird kartından keçid; sınaq bölməsinin reytinqi.
4. AI pedaqoji rəy: miqrasiya `ai_reviews`, endpoint, UI, çap.
5. Şagird portalı: mövzu testləri üzrə öz yeri. Yoxlama: pytest, `npx tsc -b`, `npm run build`, brauzer (lokal demo).
6. Videoçarxlar (müəllim, fərdi hazırlıq, şagird) yeni imkanlarla yenilənir; qadın səsi bir az sürətli (`rate`).
