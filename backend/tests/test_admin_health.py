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


def test_ksq_archive_zip_and_purge(world):
    """KSQ arxivi: sinif/tarix qovluqları, variantlar, açar, nəticələr, kart şəkli; sonra şəkillər serverdən silinir."""
    import zipfile
    from .test_ksq_scan import ksq, photo
    admin, ta, e, pr = ksq(world)
    a = pr['sheets'][0]
    admin.post(f'/api/exam-scans/{ta}/{e["id"]}/upload', files=[('files', ('p.jpg', photo([a['qr']]), 'image/jpeg'))])
    r = admin.get('/api/exam-archive/zip', params={'ta_id': ta})
    assert r.status_code == 200 and r.headers['content-type'] == 'application/zip'
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    base = 'X e · Riyaziyyat/2026-10-20 KSQ-1/'
    assert {base + 'variantlar.json', base + 'acar.csv', base + 'neticeler.csv', base + f'kartlar/{a["code"]}.jpg'} <= set(names)
    data = json.loads(zipfile.ZipFile(io.BytesIO(r.content)).read(base + 'variantlar.json'))
    assert data['imtahan'] == 'KSQ-1' and len(data['variantlar']) == 3
    assert admin.post('/api/exam-archive/purge-images', params={'ta_id': ta}).json()['removed'] == 1
    names2 = zipfile.ZipFile(io.BytesIO(admin.get('/api/exam-archive/zip').content)).namelist()
    assert not any('kartlar/' in n for n in names2)
    assert world[0]('yad').get('/api/exam-archive/zip').status_code == 404


def test_ksq_edit_and_delete(world):
    from .test_ksq_scan import ksq, photo
    admin, ta, e, pr = ksq(world)
    admin.post(f'/api/exam-scans/{ta}/{e["id"]}/upload', files=[('files', ('p.jpg', photo([pr['sheets'][0]['qr']]), 'image/jpeg'))])
    ex = admin.get(f'/api/exams/{ta}').json()['exams'][0]
    r = admin.patch(f'/api/exams/{ta}/{e["id"]}', json={**{k: ex[k] for k in ('kind', 'no', 'semester', 'max_points', 'items')},
                                                       'date': '2026-10-21', 'title': 'Faiz'})
    assert r.status_code == 200 and r.json()['date'] == '2026-10-21'
    assert world[0]('yad').delete(f'/api/exams/{ta}/{e["id"]}').status_code in (403, 404)
    d = admin.delete(f'/api/exams/{ta}/{e["id"]}').json()
    assert d['variants'] == 3 and d['scans'] == 1 and admin.get(f'/api/exams/{ta}').json()['exams'] == []
