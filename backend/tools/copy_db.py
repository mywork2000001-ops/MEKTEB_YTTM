"""Bazanı birbaşa köçürür (məs. Render PostgreSQL → Neon) – fayllar (file_blobs) DAXİL, hissə-hissə, yaddaşa yığmadan.

Bağlantılar repoya və söhbətə yazılmır – backend/.env.migrate faylında (gitignore):
    SOURCE_URL=postgresql://...@dpg-....frankfurt-postgres.render.com/muellim   (Render → muellim-db → External Database URL)
    TARGET_URL=postgresql://...@ep-....neon.tech/neondb?sslmode=require          (Neon → Connection string)

    python tools/copy_db.py            # yoxlama: hər cədvəlin sətir sayı (heç nə yazılmır)
    python tools/copy_db.py --copy     # köçürmə: hədəf boş olmalıdır; sonda sayların müqayisəsi

Köçürmə vaxtı saytda yazı olmasın (gecə); sonra Render → Environment → MK_DATABASE_URL = TARGET_URL."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CHUNK = 500
sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def _env() -> dict[str, str]:
    f = ROOT / '.env.migrate'
    if not f.is_file():
        raise SystemExit(f'{f} yoxdur – SOURCE_URL və TARGET_URL yazın (bax: faylın əvvəlindəki izah)')
    out = {}
    for line in f.read_text(encoding='utf-8-sig').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            k, v = line.split('=', 1)
            out[k.strip()] = v.strip().strip('"\'')
    for k in ('SOURCE_URL', 'TARGET_URL'):
        if not out.get(k):
            raise SystemExit(f'.env.migrate: {k} boşdur')
    if out['SOURCE_URL'] == out['TARGET_URL']:
        raise SystemExit('SOURCE_URL və TARGET_URL eynidir')
    return out


def _host(url: str) -> str:
    return url.split('@', 1)[-1].split('/', 1)[0]              # parol çap olunmur


def main(copy: bool) -> None:
    env = _env()
    os.environ['MK_DATABASE_URL'] = env['TARGET_URL']          # miqrasiyalar hədəfdə (app.db bu dəyəri götürür)
    from sqlalchemy import func, insert, select, text
    import app.models  # noqa: F401
    import app.storage  # noqa: F401  – file_blobs (fayllar) da köçsün
    from app.db import Base, make_engine
    src, dst = make_engine(env['SOURCE_URL']), make_engine(env['TARGET_URL'])
    tables = Base.metadata.sorted_tables
    print(f'Mənbə: {_host(env["SOURCE_URL"])}  →  hədəf: {_host(env["TARGET_URL"])}')
    with src.connect() as s:
        counts = {t.name: s.execute(select(func.count()).select_from(t)).scalar() for t in tables}
        size = s.execute(text('SELECT pg_size_pretty(pg_database_size(current_database()))')).scalar()             if src.dialect.name == 'postgresql' else '?'
    print(f'Mənbə bazanın həcmi: {size}; sətirlər: {sum(counts.values())}')
    for k, v in counts.items():
        if v:
            print(f'  {k}: {v}')
    if not copy:
        print('Yoxlama bitdi. Köçürmək üçün: python tools/copy_db.py --copy')
        return
    from alembic import command
    from alembic.config import Config
    cfg = Config(str(ROOT / 'alembic.ini'))
    cfg.set_main_option('script_location', str(ROOT / 'migrations'))
    command.upgrade(cfg, 'head')                                 # hədəfdə cədvəllər
    with dst.connect() as d:
        busy = [t.name for t in tables if d.execute(select(func.count()).select_from(t)).scalar()]
    if busy:
        raise SystemExit(f'Hədəf baza boş deyil ({", ".join(busy[:5])}) – yeni boş Neon bazası istifadə edin')
    snap = {'isolation_level': 'REPEATABLE READ'} if src.dialect.name == 'postgresql' else {}
    with src.connect().execution_options(**snap) as s, dst.begin() as d:   # mənbədən bir an; hədəfə bir tranzaksiya
        done: set[str] = set()
        later: list[tuple] = []                                  # dairəvi istinad (məs. schools.owner_id → users): sonra
        for t in tables:
            pk = list(t.primary_key.columns)
            defer = [c.name for c in t.columns for fk in c.foreign_keys
                     if fk.column.table.name not in done and c.nullable and len(pk) == 1]
            n = 0
            res = s.execution_options(stream_results=True, yield_per=CHUNK).execute(select(t))
            for part in res.mappings().partitions(CHUNK):
                rows = [dict(r) for r in part]
                for r in rows:
                    vals = {k: r[k] for k in defer if r[k] is not None}
                    if vals:
                        later.append((t, pk[0].name, r[pk[0].name], vals))
                        r.update({k: None for k in vals})
                d.execute(insert(t), rows)
                n += len(part)
            done.add(t.name)
            if n:
                print(f'  {t.name}: {n}')
        for t, key, kv, vals in later:
            d.execute(t.update().where(t.c[key] == kv).values(**vals))
        if later:
            print(f'  sonradan bərpa edilən istinadlar: {len(later)}')
        for t in tables if dst.dialect.name == 'postgresql' else []:
            if 'id' in t.c and len(t.primary_key.columns) == 1 and t.c.id.autoincrement is not False:
                d.execute(text(f"SELECT setval(pg_get_serial_sequence('{t.name}', 'id'), "
                               f"COALESCE((SELECT MAX(id) FROM {t.name}), 1))"))
    with dst.connect() as d:
        bad = {t.name: (counts[t.name], c) for t in tables
               if (c := d.execute(select(func.count()).select_from(t)).scalar()) != counts[t.name]}
    if bad:
        raise SystemExit(f'Say uyğun gəlmir: {bad}')
    print('Köçürmə tamamdır – bütün cədvəllərdə sətir sayı eynidir.')


if __name__ == '__main__':
    main('--copy' in sys.argv)
