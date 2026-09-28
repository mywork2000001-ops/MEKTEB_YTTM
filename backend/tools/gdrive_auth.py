"""Google Drive-ı bir dəfə qoşmaq (kompüterdə işə salınır):

    python tools/gdrive_auth.py CLIENT_ID CLIENT_SECRET

1) Brauzer açılır – Google hesabınızla daxil olub icazə verirsiniz (yalnız tətbiqin ÖZ yaratdığı fayllara çıxış – drive.file).
2) Drive-da «Müəllim köməkçisi – çat faylları» qovluğu yaradılır.
3) Ekrana MK_GDRIVE_* dəyərləri çıxır – onları Render-də mühit dəyişənlərinə yazın (repoya YAZMAYIN)."""
import http.server
import secrets
import sys
import threading
import urllib.parse
import webbrowser

import httpx

SCOPE = 'https://www.googleapis.com/auth/drive.file'


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    cid, secret = sys.argv[1], sys.argv[2]
    state = secrets.token_urlsafe(16)
    got: dict = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get('state', [''])[0] == state and 'code' in q:
                got['code'] = q['code'][0]
                msg = 'Hazirdir. Bu pencereni baglayib terminala qayidin.'
            else:
                msg = 'Xeta: icaze alinmadi.'
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(msg.encode())

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(('127.0.0.1', 0), H)
    redirect = f'http://127.0.0.1:{srv.server_port}/'
    url = 'https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode({
        'client_id': cid, 'redirect_uri': redirect, 'response_type': 'code', 'scope': SCOPE,
        'access_type': 'offline', 'prompt': 'consent', 'state': state})
    t = threading.Thread(target=srv.handle_request)
    t.start()
    print('Brauzerdə icazə verin:\n', url)
    webbrowser.open(url)
    t.join(timeout=300)
    if 'code' not in got:
        sys.exit('İcazə alınmadı.')
    tok = httpx.post('https://oauth2.googleapis.com/token', data={
        'code': got['code'], 'client_id': cid, 'client_secret': secret, 'redirect_uri': redirect,
        'grant_type': 'authorization_code'}).json()
    if 'refresh_token' not in tok:
        sys.exit(f'Refresh token gəlmədi: {tok}')
    folder = httpx.post('https://www.googleapis.com/drive/v3/files', params={'fields': 'id'},
                        headers={'Authorization': f'Bearer {tok["access_token"]}'},
                        json={'name': 'Müəllim köməkçisi – çat faylları',
                              'mimeType': 'application/vnd.google-apps.folder'}).json()
    print('\nRender → Environment bölməsinə yazın:\n')
    print('MK_STORAGE=gdrive')
    print(f'MK_GDRIVE_FOLDER_ID={folder["id"]}')
    print(f'MK_GDRIVE_CLIENT_ID={cid}')
    print(f'MK_GDRIVE_CLIENT_SECRET={secret}')
    print(f'MK_GDRIVE_REFRESH_TOKEN={tok["refresh_token"]}')


if __name__ == '__main__':
    main()
