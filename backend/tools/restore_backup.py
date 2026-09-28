"""Ehtiyat nüsxəni (Tənzimləmələr → Ehtiyat nüsxə, JSON) YENİ BOŞ bazaya yükləyir – məs. Render bazasından Neon-a köçmək:

    MK_DATABASE_URL=postgresql://... python tools/restore_backup.py muellim-komekcisi-20261001.json

Baza boş olmalıdır (əvvəlcə miqrasiyalar avtomatik icra olunur). PostgreSQL-də id ardıcıllıqları sonda düzəldilir."""
import base64
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _conv(col, v):
    if v is None:
        return None
    if isinstance(v, dict) and '$b64' in v:
        return base64.b64decode(v['$b64'])
    t = col.type.__class__.__name__
    if t == 'DateTime' and isinstance(v, str):
        return dt.datetime.fromisoformat(v)
    if t == 'Date' and isinstance(v, str):
        return dt.date.fromisoformat(v)
    return v


def restore(path: str, engine=None) -> dict:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import func, insert, select, text
    import app.models  # noqa: F401
    from app.db import Base, engine as default_engine
    engine = engine or default_engine
    if engine is default_engine:
        ini = Path(__file__).resolve().parents[1] / 'alembic.ini'
        cfg = Config(str(ini))
        cfg.set_main_option('script_location', str(ini.parent / 'migrations'))
        command.upgrade(cfg, 'head')
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('format') != 'muellim-komekcisi-backup':
        raise SystemExit('Bu fayl Müəllim köməkçisi ehtiyat nüsxəsi deyil')
    counts = {}
    with engine.begin() as conn:
        for t in Base.metadata.sorted_tables:
            if conn.execute(select(func.count()).select_from(t)).scalar():
                raise SystemExit(f'Baza boş deyil ({t.name}) – yalnız yeni bazaya yükləyin')
        for t in Base.metadata.sorted_tables:
            rows = data['tables'].get(t.name, [])
            if rows:
                conn.execute(insert(t), [{c.name: _conv(c, r.get(c.name)) for c in t.columns if c.name in r} for r in rows])
            counts[t.name] = len(rows)
        if engine.dialect.name == 'postgresql':
            for t in Base.metadata.sorted_tables:
                if 'id' in t.c and t.c.id.autoincrement is not False and len(t.primary_key.columns) == 1:
                    conn.execute(text(f"SELECT setval(pg_get_serial_sequence('{t.name}', 'id'), "
                                      f"COALESCE((SELECT MAX(id) FROM {t.name}), 1))"))
    return counts


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    c = restore(sys.argv[1])
    print('Yükləndi:', {k: v for k, v in c.items() if v})
