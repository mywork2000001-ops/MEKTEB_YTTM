"""Video bələdçi (şagird və müəllim): lokal tətbiq + DEMO məlumat üzərində ekran yazısı (Playwright).

İş qaydası (docs/meshgele-proqram-ve-video-beledci-promtu.md, B):
  1. müvəqqəti SQLite bazası yaradılır (real ad YOX: «Test Müəllim», «Şagird Bir» …), lokal server qalxır (frontend/dist-dən);
  2. ssenari addımları (SCENARIOS) 1280x720 yazılır -> frontend/public/guide/{student|teacher}/NN-ad.webm;
  3. alt yazılar ssenaridəki mətnlərdən və addım vaxtlarından .az.vtt / .en.vtt / .ru.vtt kimi yazılır;
  4. video ffmpeg ilə ≤ 3 MB-a sıxılır.

İstifadə (backend qovluğunda, .venv python ilə):
  python scripts/guide_videos.py --check            # selektorlar mövcuddur? (yazı yoxdur)
  python scripts/guide_videos.py                    # hamısını yaz
  python scripts/guide_videos.py --only student/03-movzu-testi    # və ya --only 03-movzu-testi
  python scripts/guide_videos.py --export-ts        # frontend/src/guideData.ts (səhifə üçün ssenari siyahısı)
Tələb: Google Chrome (Playwright channel='chrome'), frontend/dist (yoxdursa `npm run build` işlədilir).
Yeni ssenari / addım əlavə etmək: yalnız SCENARIOS-a; sonra --export-ts və i18n.ts-də yeni mətnlər (AZ/EN/RU).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'backend'
FRONT = ROOT / 'frontend'
OUT = FRONT / 'public' / 'guide'
MAX_MB = 3.0

# ----------------------------------------------------------------------------------------- demo hesablar
TEACHER = {'login': 'M-901', 'password': 'demo-parol-1', 'name': 'Test Müəllim'}
STUDENT_NAMES = ['Şagird Bir', 'Şagird İki', 'Şagird Üç', 'Şagird Dörd', 'Şagird Beş', 'Şagird Altı']


def L(az: str, en: str, ru: str) -> dict:
    return {'az': az, 'en': en, 'ru': ru}


# ----------------------------------------------------------------------------------------- ssenarilər
# Addım: act = goto | nav | click | fill | scroll | hover | wait; sel = CSS selektor (nav-da – yol); value = mətn;
#        wait = hərəkətdən sonra gözləmə (ms, alt yazının oxunma vaxtı); cap = alt yazı (AZ/EN/RU, boş – yazısız addım).
# Ssenari: role, id (NN-ad), title, login=False (girişsiz başlayır), viewport (default 1280x720).
SCENARIOS: list[dict] = [
    # ============================================================ ŞAGİRD
    {'role': 'student', 'id': '01-giris', 'login': False,
     'title': L('Tətbiqə giriş', 'Signing in', 'Вход в приложение'),
     'steps': [
         {'act': 'goto', 'sel': '/', 'wait': 2500, 'sel_check': 'form',
          'cap': L('Tətbiqi brauzerdə aç. Giriş səhifəsi açılır.', 'Open the app in your browser. The sign-in page appears.',
                   'Открой приложение в браузере. Появится страница входа.')},
         {'act': 'click', 'sel': 'button:has-text("Şagird")', 'wait': 1800,
          'cap': L('«Şagird» seçimini bas.', 'Choose «Student».', 'Выбери «Ученик».')},
         {'act': 'click', 'sel': 'button.chip:has-text("Русский")', 'wait': 1800,
          'cap': L('İstədiyin dili seç: Azərbaycanca, English və ya Русский.', 'Pick your language: Azərbaycanca, English or Русский.',
                   'Выбери язык: Azərbaycanca, English или Русский.')},
         {'act': 'click', 'sel': 'button.chip:has-text("Azərbaycanca")', 'wait': 1200},
         {'act': 'fill', 'sel': 'input[autocomplete="username"]', 'value': 'XE-001', 'wait': 1800,
          'cap': L('Müəllimin verdiyi giriş kodunu yaz (məsələn: XE-001).', 'Type the sign-in code your teacher gave you (e.g. XE-001).',
                   'Введи код входа, который дал учитель (например: XE-001).')},
         {'act': 'fill', 'sel': 'input[inputmode="numeric"]', 'value': '1234', 'wait': 1800,
          'cap': L('4 rəqəmli PIN-i yaz. PIN-i heç kimə vermə.', 'Type your 4-digit PIN. Never share it.',
                   'Введи 4-значный PIN. Никому его не сообщай.')},
         {'act': 'wait', 'wait': 1500, 'cap': L('«Daxil ol» düyməsinə bas – hazırsan!', 'Press «Sign in» – you are in!',
                                                 'Нажми «Войти» – готово!')},
     ]},
    {'role': 'student', 'id': '02-ana-sehife',
     'title': L('Ana səhifə və menyu', 'Home page and menu', 'Главная страница и меню'),
     'steps': [
         {'act': 'goto', 'sel': '/', 'wait': 3500, 'sel_check': '.hero',
          'cap': L('Ana səhifə: bu günün dərsləri, tapşırıqları və xatırlatmalar burada görünür.',
                   'Home: today\'s lessons, tasks and reminders are here.', 'Главная: уроки, задания и напоминания на сегодня.')},
         {'act': 'nav', 'sel': '/lesson', 'wait': 3000,
          'cap': L('«Dərs» – bu günün dərsi və ev tapşırığı.', '«Lesson» – today\'s lesson and homework.', '«Урок» – сегодняшний урок и домашнее задание.')},
         {'act': 'nav', 'sel': '/tasks', 'wait': 3000,
          'cap': L('«Tapşırıqlar» – sənə verilmiş testlər.', '«Tasks» – the tests assigned to you.', '«Задания» – тесты, которые тебе назначили.')},
         {'act': 'nav', 'sel': '/results', 'wait': 3000,
          'cap': L('«Nəticələrim» – işlədiyin testlərin nəticələri.', '«My results» – the results of the tests you took.',
                   '«Мои результаты» – итоги пройденных тестов.')},
         {'act': 'nav', 'sel': '/guide', 'wait': 3000,
          'cap': L('«Bələdçi» – bu videolara istənilən vaxt qayıda bilərsən.', '«Guide» – come back to these videos any time.',
                   '«Гид» – к этим видео можно вернуться в любой момент.')},
     ]},
    {'role': 'student', 'id': '03-movzu-testi',
     'title': L('Mövzu testini işləmək', 'Taking a topic test', 'Как пройти тест по теме'),
     'steps': [
         {'act': 'nav', 'sel': '/tasks', 'wait': 3000, 'sel_check': '.panel',
          'cap': L('«Tapşırıqlar» bölməsində testi tap.', 'Find the test in «Tasks».', 'Найди тест в разделе «Задания».')},
         {'act': 'click', 'sel': 'button:has-text("Başla")', 'wait': 1500,
          'cap': L('«Başla» düyməsi ilə testə başla.', 'Press «Start» to begin the test.', 'Нажми «Начать», чтобы приступить к тесту.')},
         {'act': 'click', 'sel': 'button:has-text("Tam ekrana keç")', 'wait': 1500, 'optional': True},
         {'act': 'wait', 'wait': 2500,
          'cap': L('Müddətsiz testdə taymer yoxdur: «Vaxt məhdudiyyəti yoxdur». İstədiyin vaxt «Təhvil ver» edə bilərsən.',
                   'An untimed test has no timer: «No time limit». Submit whenever you are ready.',
                   'В тесте без срока нет таймера: «Без ограничения по времени». Сдать можно в любой момент.')},
         {'act': 'click', 'sel': '.q-opt >> nth=1', 'wait': 2200, 'optional': True,
          'cap': L('Düzgün hesab etdiyin variantı seç. Cavab avtomatik saxlanır.', 'Choose the option you think is right. Your answer is saved automatically.',
                   'Выбери вариант, который считаешь верным. Ответ сохраняется автоматически.')},
         {'act': 'wait', 'wait': 2500,
          'cap': L('Suallar arasında irəli-geri keçə bilərsən. Sonda «Təhvil ver» düyməsini bas.',
                   'Move between questions freely. At the end press «Submit».',
                   'Между вопросами можно свободно переходить. В конце нажми «Сдать».')},
     ]},
    {'role': 'student', 'id': '04-sinaq',
     'title': L('Sınaq və planlaşdırılmış imtahanlar', 'Mock exams and scheduled exams', 'Пробные и плановые экзамены'),
     'steps': [
         {'act': 'nav', 'sel': '/plan', 'wait': 3500, 'sel_check': 'main, .top',
          'cap': L('«Plan» bölməsində yaxınlaşan summativ və sınaqları gör.', 'In «Plan» see the upcoming summatives and mock exams.',
                   'В разделе «План» видны ближайшие суммативы и пробные экзамены.')},
         {'act': 'nav', 'sel': '/tasks', 'wait': 3000,
          'cap': L('Sınaq vaxtı gələndə o, «Tapşırıqlar»da açılır.', 'When the exam time comes, it opens in «Tasks».',
                   'Когда наступает время экзамена, он открывается в «Заданиях».')},
     ]},
    {'role': 'student', 'id': '05-netice',
     'title': L('Nəticələr və səhvlər üzərində iş', 'Results and working on mistakes', 'Результаты и работа над ошибками'),
     'steps': [
         {'act': 'nav', 'sel': '/results', 'wait': 3500, 'sel_check': '.top',
          'cap': L('«Nəticələrim»də bütün nəticələr tarix üzrə sıralanır.', '«My results» lists all results by date.',
                   'В «Моих результатах» все итоги по датам.')},
         {'act': 'click', 'sel': '.panel tbody tr >> nth=0', 'wait': 3500, 'optional': True,
          'cap': L('Nəticəni aç: səhv suallar, düzgün cavab və izah burada görünür.', 'Open a result: wrong questions, correct answers and explanations are here.',
                   'Открой результат: здесь неверные вопросы, правильные ответы и пояснения.')},
         {'act': 'wait', 'wait': 2500,
          'cap': L('Səhvlərə baxıb təkrar et. Razı deyilsənsə – apelyasiya yaza bilərsən.', 'Review your mistakes. If you disagree, you can send an appeal.',
                   'Разбери ошибки. Если не согласен – можно подать апелляцию.')},
     ]},
    {'role': 'student', 'id': '06-islemeli-testler',
     'title': L('İşləməli olduğun testlər', 'Tests you still have to take', 'Тесты, которые нужно пройти'),
     'steps': [
         {'act': 'nav', 'sel': '/tasks', 'wait': 3500, 'sel_check': '.top',
          'cap': L('«Tapşırıqlar»da hələ işləmədiyin testlər siyahıda görünür.', 'Tests you have not taken yet are listed in «Tasks».',
                   'Непройденные тесты показаны списком в «Заданиях».')},
         {'act': 'scroll', 'sel': '200', 'wait': 2500,
          'cap': L('Hər testin müddəti və bağlanma vaxtı yanında yazılıb.', 'Each test shows its duration and closing time.',
                   'Рядом с каждым тестом указаны длительность и время закрытия.')},
     ]},
    {'role': 'student', 'id': '07-material-meshgele',
     'title': L('Materiallar və əlavə məşğələlər', 'Materials and extra classes', 'Материалы и дополнительные занятия'),
     'steps': [
         {'act': 'nav', 'sel': '/materials', 'wait': 3500, 'sel_check': '.top',
          'cap': L('«Materiallar» – müəllimin yüklədiyi dərs materialları.', '«Materials» – lesson materials uploaded by your teacher.',
                   '«Материалы» – учебные материалы от учителя.')},
         {'act': 'nav', 'sel': '/extra', 'wait': 3500,
          'cap': L('«Əlavə məşğələlər» – qrupun cədvəli və proqramı.', '«Extra classes» – your group\'s schedule and programme.',
                   '«Доп. занятия» – расписание и программа группы.')},
     ]},
    {'role': 'student', 'id': '08-telefon', 'viewport': (390, 780),
     'title': L('Telefonda istifadə', 'Using it on a phone', 'Использование на телефоне'),
     'steps': [
         {'act': 'goto', 'sel': '/', 'wait': 3000, 'sel_check': '.hero',
          'cap': L('Tətbiq telefonda da eyni işləyir.', 'The app works the same on a phone.', 'Приложение так же работает на телефоне.')},
         {'act': 'goto', 'sel': '/tasks', 'wait': 3000,
          'cap': L('Aşağıdakı düymələrlə bölmələr arasında keç.', 'Use the bottom buttons to switch sections.',
                   'Нижние кнопки переключают разделы.')},
         {'act': 'goto', 'sel': '/results', 'wait': 2500,
          'cap': L('Əlavə bölmələr «Daha çox» düyməsindədir.', 'More sections are under the «More» button.', 'Остальные разделы – под кнопкой «Ещё».')},
     ]},
    # ============================================================ MÜƏLLİM
    {'role': 'teacher', 'id': '01-menyu',
     'title': L('Menyu və əsas səhifə', 'Menu and home page', 'Меню и главная страница'),
     'steps': [
         {'act': 'goto', 'sel': '/', 'wait': 3500, 'sel_check': 'h1',
          'cap': L('Əsas səhifədə «Bu həftə diqqət» və günün işləri görünür.', 'The home page shows «Needs attention this week» and today\'s work.',
                   'На главной показаны «Внимание на этой неделе» и дела дня.')},
         {'act': 'nav', 'sel': '/journal', 'wait': 3000,
          'cap': L('Sol menyu qruplara bölünüb: Dərs, Planlaşdırma, Qiymətləndirmə, Siniflər, Ünsiyyət.',
                   'The side menu is grouped: Lessons, Planning, Assessment, Classes, Communication.',
                   'Меню слева разбито на группы: Урок, Планирование, Оценивание, Классы, Общение.')},
         {'act': 'nav', 'sel': '/guide', 'wait': 3000,
          'cap': L('«Bələdçi» bölməsində bütün videolar var.', 'All videos are in the «Guide» section.', 'Все видео – в разделе «Гид».')},
     ]},
    {'role': 'teacher', 'id': '02-plan-testleri',
     'title': L('Perspektiv plan və plan testləri', 'Long-term plan and plan tests', 'Перспективный план и тесты по плану'),
     'steps': [
         {'act': 'nav', 'sel': '/plan', 'wait': 3500, 'sel_check': '.top',
          'cap': L('«Perspektiv plan»da dərslər mövzular üzrə sıralanır.', '«Long-term plan» lists lessons by topic.',
                   'В «Перспективном плане» уроки идут по темам.')},
         {'act': 'nav', 'sel': '/tests', 'wait': 3500,
          'cap': L('Plandakı mövzuya test «Testlər və sınaqlar» bölməsindən təyin olunur.', 'A test for a plan topic is assigned from «Tests and exams».',
                   'Тест по теме плана назначается в «Тестах и экзаменах».')},
     ]},
    {'role': 'teacher', 'id': '03-sinif-matrisi',
     'title': L('Sinif matrisi: kim nəyi işləyib', 'Class matrix: who did what', 'Матрица класса: кто что выполнил'),
     'steps': [
         {'act': 'nav', 'sel': '/classes', 'wait': 3500, 'sel_check': '.top',
          'cap': L('«Siniflər və qruplar»da sinfi seç.', 'Choose a class in «Classes and groups».', 'Выбери класс в «Классах и группах».')},
         {'act': 'click', 'sel': '.panel a[href*="/classes"], .panel tbody tr >> nth=0', 'wait': 3500, 'optional': True,
          'cap': L('Sinfin şagirdləri və hər birinin işlədiyi / işləmədiyi testlər görünür.', 'See the class students and which tests each has or has not done.',
                   'Видны ученики класса и какие тесты каждый выполнил или нет.')},
         {'act': 'wait', 'wait': 2500,
          'cap': L('İşlənməyənlər siyahısını çap edə və ya Excel-ə çıxara bilərsən.', 'You can print the list of undone tests or export it to Excel.',
                   'Список невыполненных можно распечатать или выгрузить в Excel.')},
     ]},
    {'role': 'teacher', 'id': '04-kagiz-test',
     'title': L('Kağız test (KSQ): vərəqə, skan, nəticə', 'Paper test (KSQ): sheet, scan, result', 'Бумажный тест (KSQ): бланк, скан, результат'),
     'steps': [
         {'act': 'nav', 'sel': '/tests', 'wait': 3500, 'sel_check': '.top',
          'cap': L('«Testlər və sınaqlar»da kağız test və KSQ bölməsini aç.', 'Open the paper test and KSQ section in «Tests and exams».',
                   'Открой раздел бумажных тестов и KSQ в «Тестах и экзаменах».')},
         {'act': 'wait', 'wait': 3500,
          'cap': L('Cavab vərəqəsini çap et, şagirdlər doldursun, sonra skan et – nəticə avtomatik hesablanır.',
                   'Print the answer sheet, let students fill it in, then scan it – the result is calculated automatically.',
                   'Распечатай бланк ответов, ученики заполнят его, затем отсканируй – итог посчитается автоматически.')},
     ]},
    {'role': 'teacher', 'id': '05-meshgele-qruplari',
     'title': L('Məşğələ qrupları və proqram', 'Extra-class groups and programme', 'Группы занятий и программа'),
     'steps': [
         {'act': 'goto', 'sel': '/classes?tab=extra', 'wait': 3500, 'sel_check': '.top',
          'cap': L('«Siniflər və qruplar» → «Məşğələ qrupları».', '«Classes and groups» → «Extra-class groups».',
                   '«Классы и группы» → «Группы занятий».')},
         {'act': 'wait', 'wait': 3500,
          'cap': L('Qrup yarat, şagirdləri əlavə et və qrupa proqram təyin et.', 'Create a group, add students and assign a programme to the group.',
                   'Создай группу, добавь учеников и назначь группе программу.')},
     ]},
    {'role': 'teacher', 'id': '06-jurnal-hesabat',
     'title': L('Jurnal və hesabatlar', 'Journal and reports', 'Журнал и отчёты'),
     'steps': [
         {'act': 'nav', 'sel': '/journal', 'wait': 3500, 'sel_check': '.top',
          'cap': L('«Jurnal»da davamiyyət və qiymətlər yazılır.', 'Attendance and grades are entered in the «Journal».',
                   'В «Журнале» отмечаются посещаемость и оценки.')},
         {'act': 'nav', 'sel': '/reports', 'wait': 3500,
          'cap': L('«Analitika və hesabat» – sinif və şagird üzrə statistika.', '«Analytics and reports» – statistics by class and student.',
                   '«Аналитика и отчёты» – статистика по классам и ученикам.')},
     ]},
]

# ----------------------------------------------------------------------------------------- CSS vurğusu
HIGHLIGHT_JS = """
(() => {
  const css = `
  #__cur{position:fixed;z-index:2147483647;width:18px;height:18px;margin:-9px 0 0 -9px;border-radius:50%;
    background:rgba(255,193,7,.55);border:2px solid #e65100;pointer-events:none;left:-50px;top:-50px;transition:left .05s,top .05s}
  .__ring{position:fixed;z-index:2147483647;width:20px;height:20px;margin:-10px 0 0 -10px;border-radius:50%;
    border:4px solid #e65100;pointer-events:none;animation:__r .7s ease-out forwards}
  @keyframes __r{from{transform:scale(.6);opacity:1}to{transform:scale(3.2);opacity:0}}`;
  const add = () => {
    if (document.getElementById('__cur')) return;
    const s = document.createElement('style'); s.textContent = css; document.documentElement.appendChild(s);
    const c = document.createElement('div'); c.id = '__cur'; document.documentElement.appendChild(c);
  };
  addEventListener('DOMContentLoaded', add); add();
  addEventListener('mousemove', e => { add(); const c = document.getElementById('__cur'); if (c) { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; } }, true);
  addEventListener('mousedown', e => {
    const r = document.createElement('div'); r.className = '__r __ring'; r.className = '__ring';
    r.style.left = e.clientX + 'px'; r.style.top = e.clientY + 'px'; document.documentElement.appendChild(r);
    setTimeout(() => r.remove(), 800);
  }, true);
})();
"""


# ----------------------------------------------------------------------------------------- yardımçılar
def pick(scn: dict) -> str:
    return f"{scn['role']}/{scn['id']}"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def vtt_time(sec: float) -> str:
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f'{h:02d}:{m:02d}:{s:02d}.{ms:03d}'


def write_vtt(path: Path, cues: list[tuple[float, float, str]]):
    lines = ['WEBVTT', '']
    for i, (a, b, text) in enumerate(cues, 1):
        lines += [str(i), f'{vtt_time(a)} --> {vtt_time(b)}', text, '']
    path.write_text('\n'.join(lines), encoding='utf-8')


def find_ffmpeg() -> str | None:
    p = shutil.which('ffmpeg')
    if p:
        return p
    base = Path(os.environ.get('LOCALAPPDATA', '')) / 'ms-playwright'
    for f in sorted(base.glob('ffmpeg-*/ffmpeg*')):
        if f.is_file() and f.suffix in ('.exe', ''):
            return str(f)
    return None


def compress(src: Path, dst: Path, ss: float = 0.0) -> float:
    """webm -> ≤ MAX_MB (VP8, 15 fps); crf artırılır."""
    ff = find_ffmpeg()
    if not ff:
        shutil.copy(src, dst)
        return dst.stat().st_size / 1e6
    for crf in (34, 38, 42, 46, 51):
        subprocess.run([ff, '-y', '-loglevel', 'error', '-ss', f'{ss:.2f}', '-i', str(src), '-an', '-r', '15', '-c:v', 'libvpx', '-b:v', '0',
                        '-crf', str(crf), '-cpu-used', '4', '-deadline', 'good', str(dst)], check=True)
        mb = dst.stat().st_size / 1e6
        if mb <= MAX_MB:
            return mb
    return mb


# ----------------------------------------------------------------------------------------- demo mühit
class Demo:
    """Müvəqqəti SQLite + uvicorn alt prosesi. Real məlumata toxunmur."""

    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='mk-guide-'))
        self.port = free_port()
        self.base = f'http://127.0.0.1:{self.port}'
        self.proc: subprocess.Popen | None = None
        self.env = {**os.environ, 'MK_DATABASE_URL': f'sqlite:///{(self.tmp / "demo.db").as_posix()}', 'MK_BANK_SYNC_MINUTES': '0',
                    'MK_UPLOAD_DIR': str(self.tmp / 'uploads'), 'MK_SECRET_KEY': 'guide-demo-secret', 'MK_ADMIN_PASSWORD': '',
                    'MK_CHROME_PATH': '', 'PYTHONPATH': str(BACKEND)}
        self.student_pins: dict[str, str] = {}

    def start(self):
        # 1) sxem: miqrasiyalar + demo istifadəçilər
        code = (
            "import datetime as dt\n"
            "from app.main import bootstrap\nbootstrap()\n"
            "from app.db import SessionLocal\nfrom app.models import School, AcademicYear, User, Role\nfrom app.security import hash_password\n"
            "with SessionLocal() as db:\n"
            "    s = School(name='Nümunə məktəb (demo)', utis='000'); db.add(s); db.flush()\n"
            "    db.add(AcademicYear(school_id=s.id, name='2026–2027', start=dt.date(2026, 9, 15), sem1_end=dt.date(2027, 1, 26),\n"
            "        sem2_start=dt.date(2027, 2, 1), end=dt.date(2027, 6, 14), is_current=True))\n"
            f"    db.add(User(role=Role.teacher, login={TEACHER['login']!r}, password_hash=hash_password({TEACHER['password']!r}),\n"
            f"        full_name={TEACHER['name']!r}, school_id=s.id, subjects=['Riyaziyyat']))\n"
            "    db.commit()\n")
        subprocess.run([sys.executable, '-c', code], cwd=BACKEND, env=self.env, check=True)
        # 2) server
        self.proc = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(self.port),
                                      '--log-level', 'warning'], cwd=BACKEND, env=self.env)
        import urllib.request
        for _ in range(80):
            try:
                urllib.request.urlopen(self.base + '/api/health', timeout=2)
                break
            except Exception:                                                  # noqa: BLE001
                time.sleep(0.5)
        else:
            raise RuntimeError('server qalxmadı')
        self.seed_via_api()

    def seed_via_api(self):
        import httpx
        c = httpx.Client(base_url=self.base, timeout=30)
        r = c.post('/api/auth/login', json={'login': TEACHER['login'], 'password': TEACHER['password']})
        r.raise_for_status()
        cid = c.post('/api/classes', json={'name': 'X e'}).json()['id']
        ta = c.post(f'/api/classes/{cid}/join', json={'subject': 'Riyaziyyat', 'weekly_hours': 3, 'slots': {'0': [2], '2': [3], '4': [1]}})
        ta.raise_for_status()
        for n in STUDENT_NAMES:
            r = c.post('/api/students', json={'full_name': n, 'class_id': cid, 'force': True})
            r.raise_for_status()
            j = r.json()
            self.student_pins[j['portal_code']] = j['initial_pin']
        self.first_student = sorted(self.student_pins)[0]
        # sınaq tapşırığı (öz sualları): şagirdin «Tapşırıqlar»ında görünsün
        ta_id = (ta.json().get('mine') or {}).get('ta_id')
        if not ta_id:
            raise RuntimeError(f'join cavabında assignment id yoxdur: {ta.text[:200]}')
        now = dt.datetime.now(dt.timezone.utc)
        body = {'title': 'Kvadrat tənliklər – mövzu testi', 'opens_at': (now - dt.timedelta(hours=1)).isoformat(),
                'shuffle': False,                       # müddətsiz test: closes_at və duration_min yoxdur
                'custom': [
                    {'kind': 'mcq', 'text': 'x² − 9 = 0 tənliyinin kökləri hansılardır?', 'options': ['3', '±3', '9', '−3'], 'correct': 1,
                     'explanation': 'x² = 9, deməli x = 3 və ya x = −3.'},
                    {'kind': 'mcq', 'text': '2 + 2 · 2 = ?', 'options': ['8', '6', '4', '10'], 'correct': 1,
                     'explanation': 'Əvvəl vurma: 2 · 2 = 4, sonra 2 + 4 = 6.'},
                    {'kind': 'open', 'text': 'x + 5 = 12 tənliyində x = ?', 'answer': '7'}]}
        timed = {**body, 'title': 'Tənliklər – vaxtlı test', 'closes_at': (now + dt.timedelta(days=7)).isoformat(), 'duration_min': 40}
        for b in (body, timed):
            r = c.post(f'/api/tasks/{ta_id}', json=b)
            if r.status_code >= 400:
                print('  XƏBƏRDARLIQ: demo tapşırıq yaradılmadı:', r.status_code, r.text[:200])
        import sqlite3                                                    # tapşırıq → «Mövzu testləri» bölməsində görünsün
        with sqlite3.connect(self.tmp / 'demo.db') as cx:
            cx.execute("UPDATE online_tasks SET kind='movzu'")

    def stop(self):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except Exception:                                                  # noqa: BLE001
                self.proc.kill()
        shutil.rmtree(self.tmp, ignore_errors=True)


# ----------------------------------------------------------------------------------------- icra
def ensure_dist():
    if (FRONT / 'dist' / 'index.html').exists():
        return
    print('frontend/dist yoxdur – npm run build …')
    subprocess.run('npm run build', cwd=FRONT, shell=True, check=True)


def login_api(page, demo: Demo, role: str):
    if role == 'teacher':
        body = {'login': TEACHER['login'], 'password': TEACHER['password']}
    else:
        body = {'login': demo.first_student, 'password': demo.student_pins[demo.first_student]}
    r = page.request.post(demo.base + '/api/auth/login', data=body)
    if not r.ok:
        raise RuntimeError(f'giriş alınmadı: {r.status} {r.text()[:120]}')


def settle(page):
    """Səhifə yüklənsin; arxa plan sorğuları (polling) sonsuz gözlətməsin."""
    try:
        page.wait_for_load_state('networkidle', timeout=3000)
    except Exception:                                                          # noqa: BLE001
        pass


def move_to(page, loc):
    box = loc.bounding_box()
    if box:
        page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2, steps=18)


def do_step(page, st: dict, check: bool) -> str | None:
    """Addımı icra edir. Selektor tapılmazsa xəta mətni qaytarır."""
    act, sel, val = st['act'], st.get('sel'), st.get('value')
    tmo = 6000 if check else 8000
    try:
        if act == 'goto':
            page.goto(sel)
            settle(page)
        elif act == 'nav':
            link = page.locator(f'.nav-sec a[href="{sel}"], aside a[href="{sel}"]').first
            if link.count() == 0:
                base = page.url.split('/', 3)[:3]
                page.goto('/'.join(base) + sel)
            else:
                if not link.is_visible():
                    page.locator(f'.nav-sec:has(a[href="{sel}"]) .nav-ghead').first.click()
                    page.wait_for_timeout(500)
                try:
                    move_to(page, link)
                    link.click(timeout=3000)
                except Exception:                                              # noqa: BLE001 – menyu bağlıdır/örtülüdür: birbaşa keç
                    page.goto(sel)
            settle(page)
        elif act in ('click', 'hover'):
            loc = page.locator(sel).first
            loc.wait_for(state='visible', timeout=tmo)
            move_to(page, loc)
            if act == 'click':
                loc.click(timeout=tmo)
        elif act == 'fill':
            loc = page.locator(sel).first
            loc.wait_for(state='visible', timeout=tmo)
            move_to(page, loc)
            loc.click()
            if not check:
                loc.press_sequentially(val, delay=120)
            else:
                loc.fill(val)
        elif act == 'scroll':
            page.mouse.wheel(0, int(sel))
        if st.get('sel_check') and check:
            page.locator(st['sel_check']).first.wait_for(state='attached', timeout=tmo)
    except Exception as e:                                                    # noqa: BLE001
        if st.get('optional'):
            return None
        return f'{act} {sel!r}: {str(e).splitlines()[0][:120]}'
    return None


def run_scenario(browser, demo: Demo, scn: dict, check: bool) -> tuple[Path | None, list[str]]:
    vw, vh = scn.get('viewport', (1280, 720))
    tmpv = demo.tmp / 'video' / scn['id']
    kw = dict(viewport={'width': vw, 'height': vh}, base_url=demo.base, locale='az-AZ')
    if not check:
        kw.update(record_video_dir=str(tmpv), record_video_size={'width': vw, 'height': vh})
    if vw < 600:
        kw.update(is_mobile=True, has_touch=False, device_scale_factor=1)
    ctx = browser.new_context(**kw)
    ctx.add_init_script(HIGHLIGHT_JS)
    ctx.add_init_script("try{localStorage.setItem('mk-welcome-guide','1')}catch(e){}")      # yeni giriş kartı videoya düşməsin
    page = ctx.new_page()
    t0 = time.monotonic()
    errs: list[str] = []
    cues = {'az': [], 'en': [], 'ru': []}
    try:
        if scn.get('login', True):
            login_api(page, demo, scn['role'])
        page.goto('/')
        settle(page)
        page.wait_for_timeout(600 if check else 1200)
        t_start = time.monotonic() - t0
        for st in scn['steps']:
            a = time.monotonic() - t0
            e = do_step(page, st, check)
            if e:
                errs.append(e)
            if not check:
                page.wait_for_timeout(st.get('wait', 1500))
            b = time.monotonic() - t0
            if st.get('cap') and not check:
                for lg in cues:
                    cues[lg].append((max(a - t_start, 0.0), b - t_start, st['cap'][lg]))
    finally:
        vid = page.video
        ctx.close()
    if check:
        return None, errs
    raw = Path(vid.path())
    d = OUT / scn['role']
    d.mkdir(parents=True, exist_ok=True)
    dst = d / f"{scn['id']}.webm"
    mb = compress(raw, dst, t_start)
    for lg in cues:
        write_vtt(d / f"{scn['id']}.{lg}.vtt", cues[lg])
    print(f'  {pick(scn)}: {mb:.2f} MB')
    return dst, errs


def export_ts():
    """frontend/src/guideData.ts – səhifə üçün ssenari siyahısı (AZ mətnləri; tərcümə t() ilə i18n.ts-dən)."""
    items = []
    for s in SCENARIOS:
        items.append({'role': s['role'], 'id': s['id'], 'title': s['title']['az'],
                      'steps': [x['cap']['az'] for x in s['steps'] if x.get('cap')]})
    txt = ('// AVTOMATİK: backend/scripts/guide_videos.py --export-ts (əl ilə dəyişmə). Mətnlər t() ilə tərcümə olunur.\n'
           'export type GuideItem = { role: \'student\' | \'teacher\'; id: string; title: string; steps: string[] }\n'
           'export const GUIDE: GuideItem[] = ' + json.dumps(items, ensure_ascii=False, indent=2) + '\n')
    (FRONT / 'src' / 'guideData.ts').write_text(txt, encoding='utf-8')
    print('yazıldı: frontend/src/guideData.ts')


def i18n_block() -> str:
    """i18n.ts üçün sətirlər (AZ açar -> [EN, RU]); təkrarlar atılır."""
    seen, out = set(), []
    for s in SCENARIOS:
        pairs = [s['title']] + [x['cap'] for x in s['steps'] if x.get('cap')]
        for p in pairs:
            if p['az'] in seen:
                continue
            seen.add(p['az'])
            out.append('  ' + json.dumps(p['az'], ensure_ascii=False) + ': [' + json.dumps(p['en'], ensure_ascii=False) + ', '
                       + json.dumps(p['ru'], ensure_ascii=False) + '],')
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='selektorları yoxla, yazma')
    ap.add_argument('--only', help='yalnız bu ssenari (məs. student/03-movzu-testi və ya 03-movzu-testi)')
    ap.add_argument('--export-ts', action='store_true', help='frontend/src/guideData.ts yaz')
    ap.add_argument('--print-i18n', action='store_true', help='i18n.ts üçün sətirləri çap et')
    ap.add_argument('--headed', action='store_true')
    a = ap.parse_args()
    if a.export_ts:
        export_ts()
        return
    if a.print_i18n:
        print(i18n_block())
        return
    todo = [s for s in SCENARIOS if not a.only or a.only in (pick(s), s['id'])]
    if not todo:
        sys.exit('belə ssenari yoxdur')
    ensure_dist()
    from playwright.sync_api import sync_playwright
    demo = Demo()
    bad = 0
    try:
        demo.start()
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='chrome', headless=not a.headed)
            for s in todo:
                _, errs = run_scenario(browser, demo, s, a.check)
                for e in errs:
                    bad += 1
                    print(f'  XƏTA {pick(s)}: {e}')
                if a.check and not errs:
                    print(f'  ok {pick(s)}')
            browser.close()
    finally:
        demo.stop()
    if not a.check:
        total = sum(f.stat().st_size for f in OUT.rglob('*.webm')) / 1e6 if OUT.exists() else 0
        print(f'cəmi video: {total:.1f} MB')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
