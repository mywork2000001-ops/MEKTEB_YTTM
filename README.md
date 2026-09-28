# Müəllim köməkçisi (MEKTEB_YTTM)

Tam orta məktəb (TOM) müəllimləri və şagirdləri üçün veb tətbiq: perspektiv plan, jurnal, KSQ/BSQ, onlayn tapşırıqlar, analitika, şagird portalı və daxili çat.

## Struktur
- `backend/` – FastAPI + SQLAlchemy (PostgreSQL; inkişaf üçün SQLite)
  - `app/domain/` – tədris təqvimi, qiymətləndirmə qaydaları (yarımil = KSQ ortası × 0,4 + BSQ × 0,6)
  - `app/importers/` – rəsmi perspektiv planlar (.docx), UTİS şagird siyahısı və DİM buraxılış balları (.xlsx)
  - `tests/` – pytest
- `docs/tetbiq-promtu.md` – tətbiqin tam spesifikasiyası

## Məxfilik
Repoda heç bir şagird məlumatı saxlanmır: Excel/Word faylları, maket və verilənlər bazası `.gitignore` ilə çıxarılıb.
Uşaq İD, şəxsiyyət vəsiqəsi, pinkod import zamanı oxunmur və heç yerdə saxlanmır.

## İşə salma (inkişaf)
```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt   # Linux/macOS: .venv/bin/pip
.venv/Scripts/python -m pytest -q
```
Mənbə faylları olmadıqda onlardan asılı testlər avtomatik ötürülür.
