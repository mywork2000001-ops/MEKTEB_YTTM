"""Şifrəli baza ehtiyat nüsxəsini Google Drive-a yükləyir (GitHub Action `db-backup.yml` işə salır).

    python backend/tools/backup_to_drive.py FAYL.dump.gpg

Mühit dəyişənləri (GitHub Secrets): MK_GDRIVE_CLIENT_ID, MK_GDRIVE_CLIENT_SECRET, MK_GDRIVE_REFRESH_TOKEN
(drive.file – yalnız tətbiqin öz yaratdığı fayllar), BACKUP_DRIVE_FOLDER_ID (boşdursa – qovluq yaradılır və id çap olunur;
istifadəçi onu «Backup silmek olmaz» qovluğuna sürüşdürür, id-ni secret kimi yazır).

Saxlama: həftəlik nüsxələr 8 həftə; ayın ilk nüsxəsi («-ayliq») – həmişəlik. Silinən yalnız bu skriptin adlandırdığı
həftəlik fayllardır (muellim_YYYY-MM-DD.dump.gpg)."""
import datetime as dt
import json
import os
import re
import sys

import httpx

API = 'https://www.googleapis.com/drive/v3/files'
UPLOAD = 'https://www.googleapis.com/upload/drive/v3/files'
FOLDER_NAME = 'Müəllim köməkçisi – baza nüsxələri (şifrəli)'
KEEP_WEEKLY_DAYS = 56
WEEKLY_RE = re.compile(r'^muellim_(\d{4}-\d{2}-\d{2})\.dump\.gpg$')


def token() -> str:
    r = httpx.post('https://oauth2.googleapis.com/token', data={
        'client_id': os.environ['MK_GDRIVE_CLIENT_ID'],
        'client_secret': os.environ['MK_GDRIVE_CLIENT_SECRET'],
        'refresh_token': os.environ['MK_GDRIVE_REFRESH_TOKEN'],
        'grant_type': 'refresh_token'}, timeout=30)
    r.raise_for_status()
    return r.json()['access_token']


def ensure_folder(h: dict) -> str:
    fid = os.environ.get('BACKUP_DRIVE_FOLDER_ID', '').strip()
    if fid:
        return fid
    r = httpx.post(API, headers=h, json={'name': FOLDER_NAME, 'mimeType': 'application/vnd.google-apps.folder'},
                   timeout=30)
    r.raise_for_status()
    fid = r.json()['id']
    print(f'::notice::Yeni qovluq yaradıldı: {fid} – onu «Backup silmek olmaz»-a sürüşdürün və '
          f'BACKUP_DRIVE_FOLDER_ID secret-inə yazın')
    return fid


def listing(h: dict, folder: str) -> list[dict]:
    out, page = [], None
    while True:
        r = httpx.get(API, headers=h, timeout=30, params={
            'q': f"'{folder}' in parents and trashed=false", 'fields': 'nextPageToken,files(id,name)',
            'pageSize': 200, **({'pageToken': page} if page else {})})
        r.raise_for_status()
        js = r.json()
        out += js.get('files', [])
        page = js.get('nextPageToken')
        if not page:
            return out


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    h = {'Authorization': f'Bearer {token()}'}
    folder = ensure_folder(h)
    files = listing(h, folder)
    today = dt.date.today()
    month = today.strftime('%Y-%m')
    monthly = not any(f['name'].startswith(f'muellim_{month}') and '-ayliq' in f['name'] for f in files)
    name = f'muellim_{today.isoformat()}{"-ayliq" if monthly else ""}.dump.gpg'

    meta = json.dumps({'name': name, 'parents': [folder]})
    with open(path, 'rb') as fh:
        body = fh.read()
    boundary = 'mkbackup'
    data = (f'--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n'
            f'--{boundary}\r\nContent-Type: application/octet-stream\r\n\r\n').encode() + body + \
        f'\r\n--{boundary}--'.encode()
    r = httpx.post(UPLOAD, params={'uploadType': 'multipart'}, content=data, timeout=600,
                   headers={**h, 'Content-Type': f'multipart/related; boundary={boundary}'})
    r.raise_for_status()
    print(f'Yükləndi: {name} ({len(body) / 1e6:.1f} MB)')

    for f in files:
        m = WEEKLY_RE.match(f['name'])
        if m and (today - dt.date.fromisoformat(m.group(1))).days > KEEP_WEEKLY_DAYS:
            httpx.delete(f'{API}/{f["id"]}', headers=h, timeout=30).raise_for_status()
            print('Köhnə həftəlik silindi:', f['name'])


if __name__ == '__main__':
    main()
