# Kart: Neon yatsın + bazanın sağlamlıq yoxlaması (18.10.2026)

Məqsəd: Neon (Launch, CU-saat ilə ödənişli) 5 dəq. sakitlikdən sonra yatır. Hazırda `ksq_scans` hər 2 dəq. bazaya
sorğu verir → server oyaq olan ~16 saat Neon heç yatmır. Yeni kartlar artıq yükləmə anında dərhal oxunur
(`read_pending(ids=...)`), fon işi yalnız ehtiyatdır.

Fayllar: `backend/app/scheduler.py`, `backend/app/config.py`, `backend/app/main.py`, `backend/app/api/exam_scans.py`,
`backend/app/api/ksq_online.py`, testlər `backend/tests/`. Frontend-ə toxunma.

## 1. config.py
- `active_hours: str = '8-18'` (MK_ACTIVE_HOURS) — dərs saatları (Bakı). Şərh: «bu saatlarda fon işləri tez-tez, qalanında saatda bir».

## 2. scheduler.py
- `_ksq_scan_job`: interval **2 → 10 dəq.** Modul səviyyəsində `_scan_hint = True` (start-da True) və `_scan_last_db = 0.0` (monotonic).
  İş: `if not _scan_hint and time.monotonic() - _scan_last_db < 3600: return` — bazaya getmədən çıx.
  Əks halda `read_pending(db)`; sonra `_scan_last_db = now`; `_scan_hint` = (hələ `pending` kart qaldımı — yəni
  `read_pending` limitə çatdı və ya `ai:` xətası ilə dayandı). Sadə yol: oxuduqdan sonra bir `select(ExamScan.id).where(status=='pending').limit(1)`.
  Funksiya `def hint_scans(): global _scan_hint; _scan_hint = True` — export.
- 15 dəqiqəlik işlər (`topic_journal`, `certificates`, `exam_series`, `auto_tests`) və `ksq_stale`: sarğı
  `_quiet(fn)` — `awake_now(settings().active_hours)` olanda həmişə işləyir; xaricində yalnız `datetime.now(Asia/Baku).minute < 15`
  olanda (yəni saatda ~bir dəfə). Gecə cron işləri (03:30, 03:50) və `bank_sync`, `keepalive` — dəyişmir.

## 3. Ipucu yerləri
- `api/exam_scans.py` yeni `ExamScan` yaradılan yerdə (~301) və `api/ksq_online.py` (~88) commit-dən sonra `scheduler.hint_scans()`.
  Dövri import olmasın (funksiya daxilində import).

## 4. main.py — `GET /api/health/db`
- `SELECT 1` (`SessionLocal`, `text('SELECT 1')`), uğurlu → `{'ok': True, 'db': True}`; xəta → HTTP 503 `{'ok': False, 'db': False}`
  (xəta mətni log-a, cavaba yox). `/api/health` olduğu kimi qalır (Render healthCheck — bazaya getməməlidir).

## 5. Testlər (`backend/tests/`)
- `/api/health/db` → 200 (sqlite test bazası).
- `_quiet`: active_hours xaricində minute=30 → fn çağırılmır; minute=5 → çağırılır; daxilində → çağırılır (`now` monkeypatch).
- `_ksq_scan_job`: hint=False və son yoxlama < 1 saat → `read_pending` çağırılmır (monkeypatch); `hint_scans()` → çağırılır.
- İşə sal: `cd backend && py -m pytest tests/test_admin_health.py tests/test_ksq_scan.py <yeni test faylı> -q` + bütün testlərin tez yoxlaması `py -m pytest -q -x 2>&1 | tail -3`.

## Qadağalar
Commit/push etmə, miqrasiya yazma, canlı bazaya qoşulma, `render.yaml` və `.github/` — toxunma (rəhbər edir).
Yeni UI mətni yoxdur. Hesabat: dəyişən fayllar, test nəticəsinin son 3 sətri.
