"""Şagird hesabatının çap formaları (docs/sagird-ferdi-hesabat-promtu.md §2.2/2.3): A4 HTML (PDF üçün – api/printing.render_pdf) və
Word (.docx, python-docx – plan_docx ilə eyni şrift). Rəsmi çap – AZ; valideyn nüsxəsi (parent=True) – qısa, AZ və ya RU.
Mətnlər burada, çünki sənəd serverdə qurulur (interfeysin t() lüğəti işləmir)."""
from __future__ import annotations

import io
from html import escape as _e

T: dict[str, tuple[str, str, str]] = {      # açar: (AZ, RU, EN)
    'title': ('Şagirdin fərdi hesabatı', 'Индивидуальный отчёт ученика', 'Individual student report'),
    'parent_title': ('Valideyn üçün qısa hesabat', 'Краткий отчёт для родителей', 'Short report for parents'),
    'student': ('Şagird', 'Ученик', 'Student'), 'class': ('Sinif', 'Класс', 'Class'),
    'period': ('Dövr', 'Период', 'Period'), 'all_time': ('bütün dövr', 'весь период', 'all time'),
    'summary': ('Yekun', 'Итоги', 'Summary'), 'avg': ('Orta, %', 'Средний, %', 'Average, %'),
    'last': ('Son nəticə, %', 'Последний, %', 'Latest, %'), 'trend': ('Trend (son 3)', 'Тренд (последние 3)', 'Trend (last 3)'),
    'part': ('İştirak, %', 'Участие, %', 'Participation, %'), 'place': ('Sinifdə yer', 'Место в классе', 'Class place'),
    'topics': ('Mövzu testləri', 'Тематические тесты', 'Topic tests'),
    'mocks': ('Sınaqlar', 'Пробные экзамены', 'Mock exams'),
    'summ': ('KSQ / BSQ', 'КСО / БСО', 'KSQ / BSQ'),
    'no': ('№', '№', '#'), 'topic': ('Mövzu', 'Тема', 'Topic'), 'date': ('Tarix', 'Дата', 'Date'),
    'pct': ('Bal, %', 'Балл, %', 'Score, %'), 'grade': ('Qiymət', 'Оценка', 'Grade'),
    'cavg': ('Sinif ortası', 'Среднее по классу', 'Class avg'), 'diff': ('Fərq', 'Разница', 'Diff'),
    'name': ('Ad', 'Название', 'Name'), 'score': ('Bal', 'Баллы', 'Points'),
    'kind': ('Növ', 'Вид', 'Type'), 'unpub': ('nəşr olunmayıb', 'не опубликовано', 'not published'),
    'weak': ('Zəif mövzular', 'Слабые темы', 'Weak topics'), 'recs': ('Tövsiyə', 'Рекомендации', 'Recommendations'),
    'none': ('Məlumat yoxdur', 'Нет данных', 'No data'),
    'r_repeat': ('Təkrar edin: {topic} ({pct}%) – təkrar testi təyin edin.',
                 'Повторите: {topic} ({pct}%) – назначьте повторный тест.', 'Revise: {topic} ({pct}%) – assign a repeat test.'),
    'r_part': ('İştirak aşağıdır ({pct}%) – buraxılmış testləri yazması təmin edilməlidir.',
               'Низкое участие ({pct}%) – нужно написать пропущенные тесты.', 'Low participation ({pct}%) – missed tests should be taken.'),
    'r_down': ('Son nəticələr enir ({delta} bal) – səbəbi aydınlaşdırın.', 'Последние результаты снижаются ({delta}) – выясните причину.',
               'Recent results are falling ({delta}) – find out why.'),
    'r_ok': ('Əsas çatışmazlıq yoxdur – eyni tempdə davam edin.', 'Существенных пробелов нет – продолжайте в том же темпе.',
             'No major gaps – keep going.'),
    'up': ('artır', 'растёт', 'rising'), 'down': ('azalır', 'снижается', 'falling'), 'flat': ('sabit', 'стабильно', 'steady'),
    'sign_teacher': ('Fənn müəllimi', 'Учитель-предметник', 'Subject teacher'),
}


def _lang(lang: str, parent: bool) -> int:
    if parent and lang not in ('az', 'ru'):
        lang = 'az'
    return {'az': 0, 'ru': 1, 'en': 2}.get(lang, 0)


def _n(v, d=1) -> str:
    return '—' if v is None else f'{v:.{d}f}'.replace('.', ',')


def _d(s: str | None) -> str:
    return '.'.join(s[:10].split('-')[::-1]) if s else '—'


def recommendations(rep: dict, i: int) -> list[str]:
    out = []
    for r in rep['recommendations']:
        if r['code'] == 'repeat_topic':
            out.append(T['r_repeat'][i].format(topic=(r['no'] + ' ' if r['no'] else '') + (r['topic'] or ''), pct=_n(r['pct'], 0)))
        elif r['code'] == 'participation':
            out.append(T['r_part'][i].format(pct=_n(r['pct'], 0)))
        elif r['code'] == 'trend_down':
            out.append(T['r_down'][i].format(delta=_n(r['delta'])))
    return out or [T['r_ok'][i]]


def _rows(rep: dict, i: int, parent: bool) -> dict:
    """Çap cədvəlləri: nəşr olunmamış bal valideyn nüsxəsində və rəsmi çapda göstərilmir (yalnız «nəşr olunmayıb»)."""
    t = lambda k: T[k][i]
    pub = lambda x: x['published']
    topics = [[x['no'] or '', x['topic'] or x['title'], _d(x['date']), _n(x['pct']), x['grade_5'] or '—', _n(x['class_avg']),
               _n(x['diff'])] for x in rep['topic_tests'] if pub(x)]
    mocks = [[x['name'], _d(x['date']), f"{_n(x['score'], 0 if x['max'] == 100 else 1)}/{_n(x['max'], 0)}", _n(x['pct']),
              x['place_class'] or '—', _n(x['class_avg'])] for x in rep['mocks'] if pub(x)]
    summ = [[f"{x['kind']}-{x['no']}" + (f" (+{x['extra_seq']})" if x['extra_seq'] else ''), _d(x['date']),
             f"{_n(x['points'])}/{_n(x['max'], 0)}", _n(x['pct']), x['grade_5']] if pub(x) else
            [f"{x['kind']}-{x['no']}", _d(x['date']), t('unpub'), '—', '—'] for x in rep['summatives']]
    if parent:
        topics = topics[:0]
    return {'topics': (['no', 'topic', 'date', 'pct', 'grade', 'cavg', 'diff'], topics),
            'mocks': (['name', 'date', 'score', 'pct', 'place', 'cavg'], mocks),
            'summ': (['name', 'date', 'score', 'pct', 'grade'], summ)}


def _sheet(rep: dict, lang: str, parent: bool) -> str:
    """Bir şagirdin səhifəsi (gövdə)."""
    i = _lang(lang, parent)
    t = lambda k: T[k][i]
    sm = rep['summary']
    tr = sm['trend']
    period = f"{_d(rep['period']['from'])} – {_d(rep['period']['to'])}" if rep['period']['from'] or rep['period']['to'] else t('all_time')
    kpi = [(t('avg'), _n(sm['avg_pct'])), (t('last'), _n(sm['last_pct'])),
           (t('trend'), t(tr['dir']) + (f" ({_n(tr['delta'])})" if tr['delta'] is not None else '') if tr['dir'] else '—'),
           (t('part'), _n(sm['participation'], 0)), (t('place'), sm['place_class'] or '—')]
    out = [f'<h1>{_e(t("parent_title") if parent else t("title"))}</h1>',
           f'<p><b>{t("student")}:</b> {_e(rep["student"]["full_name"])} · <b>{t("class")}:</b> {_e(rep["student"]["class_name"] or "—")}'
           f' · <b>{t("period")}:</b> {_e(period)}</p>',
           '<div class="kpi">' + ''.join(f'<span>{_e(k)}<b>{_e(str(v))}</b></span>' for k, v in kpi) + '</div>']
    rows = _rows(rep, i, parent)
    for key in ('topics', 'mocks', 'summ'):
        head, body = rows[key]
        if not body:
            continue
        out.append(f'<h2>{t(key)}</h2><table><thead><tr>' + ''.join(f'<th>{_e(t(h))}</th>' for h in head) + '</tr></thead><tbody>'
                   + ''.join('<tr>' + ''.join(f'<td>{_e(str(c))}</td>' for c in r) + '</tr>' for r in body) + '</tbody></table>')
    weak = rep['weak_topics'][:3] if parent else rep['weak_topics']
    if weak:
        out.append(f'<h2>{t("weak")}</h2><ul>' + ''.join(
            f'<li>{_e((w["no"] + " " if w["no"] else "") + (w["topic"] or ""))} – {_n(w["pct"], 0)}%</li>' for w in weak) + '</ul>')
    out.append(f'<h2>{t("recs")}</h2><ul>' + ''.join(f'<li>{_e(x)}</li>' for x in recommendations(rep, i)) + '</ul>')
    if not parent:
        out.append(f'<p class="sign">{t("sign_teacher")}: ______________________</p>')
    return ''.join(out)


def report_html(rep: dict, lang: str = 'az', parent: bool = False) -> str:
    """Tam HTML sənəd (A4, @page) – api/printing.render_pdf ilə PDF-ə çevrilir."""
    return report_html_many([rep], lang, parent)


def report_html_many(reps: list[dict], lang: str = 'az', parent: bool = False) -> str:
    """Bir neçə şagird – hər biri ayrıca səhifədən başlayır (sinif üzrə toplu çap, valideyn iclası üçün)."""
    i = _lang(lang, parent)
    brk = ' style="page-break-before:always"'
    pages = ''.join(f'<section{brk if n else ""}>{_sheet(r, lang, parent)}</section>' for n, r in enumerate(reps))
    return (f'<!doctype html><html lang="{("az", "ru", "en")[i]}"><head><meta charset="utf-8"><title>{_e(T["title"][i])}</title><style>'
            '@page{size:A4;margin:12mm 12mm 15mm}body{font:12px/1.4 "Times New Roman","Liberation Serif",serif;color:#000}'
            'h1{font-size:16px;text-align:center;margin:0 0 4px}h2{font-size:13.5px;margin:12px 0 5px;page-break-after:avoid}'
            'table{border-collapse:collapse;width:100%}th,td{border:1px solid #000;padding:2px 4px;text-align:left}'
            'th{background:#D9D9D9}.kpi{display:flex;margin:8px 0}.kpi span{flex:1;border:1px solid #000;padding:3px 6px;margin-left:-1px}'
            '.kpi b{display:block;font-size:14px}.sign{margin-top:28px}tr{page-break-inside:avoid}</style></head><body>'
            f'{pages}</body></html>')


def report_docx(rep: dict, lang: str = 'az', parent: bool = False) -> bytes:
    from docx import Document
    from docx.shared import Pt
    i = _lang(lang, parent)
    t = lambda k: T[k][i]
    doc = Document()
    st = doc.styles['Normal']
    st.font.name, st.font.size = 'Times New Roman', Pt(11)
    doc.add_heading(t('parent_title') if parent else t('title'), level=1)
    sm = rep['summary']
    doc.add_paragraph(f"{t('student')}: {rep['student']['full_name']} · {t('class')}: {rep['student']['class_name'] or '—'}")
    doc.add_paragraph(f"{t('avg')}: {_n(sm['avg_pct'])} · {t('last')}: {_n(sm['last_pct'])} · {t('part')}: {_n(sm['participation'], 0)} · "
                      f"{t('place')}: {sm['place_class'] or '—'}")
    rows = _rows(rep, i, parent)
    for key in ('topics', 'mocks', 'summ'):
        head, body = rows[key]
        if not body:
            continue
        doc.add_heading(t(key), level=2)
        tb = doc.add_table(rows=1, cols=len(head))
        tb.style = 'Table Grid'
        for c, h in zip(tb.rows[0].cells, head):
            c.text = t(h)
        for r in body:
            for c, v in zip(tb.add_row().cells, r):
                c.text = str(v)
    doc.add_heading(t('recs'), level=2)
    for x in recommendations(rep, i):
        doc.add_paragraph(x, style='List Bullet')
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
