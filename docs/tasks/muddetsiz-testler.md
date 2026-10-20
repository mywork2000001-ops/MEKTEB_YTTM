# Tapşırıq: müddətsiz testlər (mövzu testləri və sınaqlar) – 20.10.2026

Promt: `docs/davam-promtu-2026-10-20.md` §2 Q2. İcraçı: `kodcu`. Miqrasiya YOXDUR.

## Model (miqrasiyasız)
- `OnlineTask.duration_min == 0` ⇒ taymer yoxdur. `OnlineTask.closes_at == NO_DEADLINE` (2100-01-01 00:00 UTC) ⇒ son tarix yoxdur.
- Yeni `backend/app/timing.py`: `NO_DEADLINE`, `UNLIMITED_MIN = 0`, `is_unlimited(t) -> bool` (closes_at >= NO_DEADLINE),
  `no_timer(t)`, `attempt_deadline(t, start)` (taymer yoxdursa → `t.closes_at`; yoxsa min(start+duration, closes_at)).
  `portal.py` (start/save/submit, `_status`), `ksq_online.py`, `exams_online.py`, `exam_series.py`, `extra.py` deadline hesabı – yalnız bu funksiyalarla.
  `MIN_TEST_MIN` yoxlamaları və «həll müddəti açıq qalma aralığından uzundur» yoxlaması 0 üçün keçməlidir.

## Defoltlar
- Mövzu testləri: `app/plan_tests.py` opts – `duration=0`, `closes_at=NO_DEADLINE` defolt (`--duration N`, `--days N` ilə məhdud da mümkün),
  `auto_tests.py`, `api/topic_tests.py` – eyni.
- Onlayn sınaqlar (`exams_online` TestCreate, `exam_series`): Pydantic-də `duration_min` 0-a icazə (`TestMinutes` tipini genişləndir: 0 və ya ≥MIN),
  `closes_at` optional → None = NO_DEADLINE; defolt müddətsiz. Seriya `window_hours` – 0 = müddətsiz.
- **KSQ/BSQ (`ksq_online.py`) dəyişmir** – 45 dəq. və son tarix qalır (rəsmi summativ).
- Viktorina/sorğu (`extra.py` quiz) – dəyişmir.

## Davranış
- Şagird portalı: müddətsiz testdə «Son tarix: yoxdur / Müddətsiz», taymer əvəzinə «Vaxt məhdudiyyəti yoxdur»; cavablar avtomatik saxlanır,
  çıxıb qayıdanda davam edir, «Təhvil ver» ilə bitir. `expire_due`/avtomatik təhvil müddətsiz testlərə toxunmur.
  Bildiriş mətnləri (`portal.py` ~552 «…-dək · N dəq.») müddətsizdə «Müddətsiz» (AZ/EN/RU).
- `show_answers='after_close'` müddətsiz testdə = şagird təhvil verdikdən sonra.
- Hesabat statusu: müddətsiz testi hələ təhvil verməyən şagird – **`işlənməyib`** (yazmayıb deyil, açıqdır). `collect`/`student_report`
  (`class_matrix`, və varsa `MISSING_STATUSES` / `class_missing`) – işlənməyənlər siyahısına daxil; «yazıb/təyin» hesabında «təyin» sayılır.
  Testi «yazmayıb» (0 bal) kimi jurnala/ortalamaya salan yer varsa – müddətsizdə salma.
- Müəllim formaları (test yaratma, sınaq, seriya, AssignTests/plan testləri): **«Müddətsiz» qutusu defolt işarəli**; işarə götürülsə – köhnə sahələr
  (dəq., bağlanma tarixi) görünür. Siyahılarda «Müddətsiz» nişanı. Müəllim istəsə testi əl ilə **«Bağla»** edə bilsin (closes_at = indi) –
  mövcud bağlama düyməsi varsa onu işlət, yoxdursa `POST /api/exams-online/{id}/close` (öz testi).
- Bir dəfəlik çevirmə (Rəhbər canlıda işlədəcək): `POST /api/admin/unlimit-tasks?dry=1|0` (yalnız admin) – bu tədris ili (opens_at ≥ 2026-09-15),
  hələ bağlanmamış (closes_at > indi), KSQ/BSQ olmayan, viktorina olmayan OnlineTask-lar → duration_min=0, closes_at=NO_DEADLINE; artıq başlanmış
  cəhdlərin `deadline`-ı da NO_DEADLINE (təhvil verilməmişsə). Cavab: say + siyahı (id, sinif, ad). Audit qeydi.
- Bütün UI/şagird mətnləri AZ/EN/RU.

## Testlər `tests/test_unlimited_tests.py`
müddətsiz test: başlat → 3 saat sonra (vaxtı saxta irəli çək) save/submit qəbul olunur; status `işlənməyib` → təhvildən sonra `yazıb`;
KSQ hələ 45 dəq. ilə bağlanır; unlimit-tasks dry=1 heç nə dəyişmir, dry=0 yalnız uyğunları dəyişir (bağlanmış və KSQ-ya toxunmur);
plan_tests defolt müddətsiz; after_close cavabları təhvildən sonra görünür. Mövcud aid testlər keçməlidir (portal, exams_online, exam_series,
plan_tests, class_matrix, student_report, auto_tests). Yoxlama: aid pytest + `npm run build`.
