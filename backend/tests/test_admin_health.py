"""A1–A3: «Son fon işləri», «Resurslar», böyük şəklin kiçildilməsi, 60 gündən köhnə kart kəsiklərinin silinməsi."""
import datetime as dt
import io
import json
import logging

from PIL import Image


def test_jobs_and_resources(world, monkeypatch):
    as_, S = world
    admin = as_('admin')
    from app import joblog
    from app.models import AppState
    monkeypatch.setattr('app.db.SessionLocal', S)                    # jurnal test bazasına yazılsın
    lg = logging.getLogger('joblog')
    lg.setLevel(logging.INFO)
    joblog.install()
    lg.info('sertifikat: %s', 3)
    rows = admin.get('/api/admin/jobs').json()
    assert rows[0]['msg'] == 'sertifikat: 3' and rows[0]['level'] == 'INFO'
    with S() as db:
        st = db.get(AppState, 'job_log')
        st.value = json.dumps([{'at': 'x', 'name': 'n', 'level': 'INFO', 'msg': str(i)} for i in range(200)])
        db.commit()
    lg.info('son')
    assert len(admin.get('/api/admin/jobs').json()) == joblog.KEEP
    r = admin.get('/api/admin/resources').json()
    assert r['scans_month'] == 0 and r['files_bytes'] >= 0 and 'db_bytes' in r
    assert as_('yad').get('/api/admin/jobs').status_code == 403


def test_big_photo_downscaled():
    from app.domain.ksq_scan import MAX_SIDE, images_from_upload
    buf = io.BytesIO()
    Image.new('L', (4000, 3000), 255).save(buf, 'JPEG')
    im = images_from_upload(buf.getvalue(), 'image/jpeg')[0]
    assert max(im.size) == MAX_SIDE


def test_old_crops_removed(world, monkeypatch):
    from .test_ksq_scan import ksq, photo
    from app import scheduler
    from app.models import ExamScan, now
    admin, ta, e, pr = ksq(world)
    admin.post(f'/api/exam-scans/{ta}/{e["id"]}/upload', files=[('files', ('p.jpg', photo([pr['sheets'][0]['qr']]), 'image/jpeg'))])
    S = world[1]
    with S() as db:
        sc = db.query(ExamScan).one()
        sc.created_at = now() - dt.timedelta(days=61)
        db.commit()
    monkeypatch.setattr(scheduler, 'SessionLocal', S)
    scheduler._scan_cleanup_job()
    with S() as db:
        assert db.query(ExamScan).one().crop_key is None
