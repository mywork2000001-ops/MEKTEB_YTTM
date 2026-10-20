"""İşlənməyənlər hesabatının çap formaları (docs/islenmeyenler-hesabati-promtu.md §3):
H1 sinif hesabatı (A4 albom, PDF/Excel, yalnız AZ), H2 şagird vərəqəsi (PDF; şagirdin dili ru isə AZ|RU),
H3 «Bütün siniflərim» xülasəsi, H4 qrupa göndəriləcək mətn (AZ/EN/RU, ad rejimi). Mənbə – `student_report.class_missing`."""
from __future__ import annotations

import io
from html import escape as _e

from .class_matrix_print import KIND_LABEL, _d, period_text

DOC = 'İşlənməyən mövzu testləri və sınaqlar – sinif hesabatı'
STUDENT_DOC = ('İşləməli olduğun testlər', 'Тесты, которые нужно выполнить')
RISK_AZ = {'critical': 'Kritik', 'attention': 'Diqqət', 'ok': 'Normal'}
RISK_COLOR = {'critical': '#B00020', 'attention': '#C77700', 'ok': '#2E7D32'}
REASON_AZ = {'excused': 'Üzrlü', 'technical': 'Texniki problem', 'no_device': 'İnternet/cihaz yoxdur', 'forgot': 'Unudub',
             'refused': 'İmtina', 'other': 'Digər'}
CSS = ('@page{size:A4 landscape;margin:10mm}body{font:11px/1.35 "Times New Roman","Liberation Serif",serif;color:#000}'
       'h1{font-size:15px;text-align:center;margin:0 0 4px}h2{font-size:12.5px;margin:12px 0 3px}p{margin:3px 0}.c{text-align:center}'
       'table{border-collapse:collapse;width:100%;margin-top:5px}th,td{border:1px solid #444;padding:2px 4px;vertical-align:top}'
       'th{background:#E4E4E4;font-weight:bold}thead{display:table-header-group}tr{page-break-inside:avoid}.sign{margin-top:20px}'
       '.kpi td{text-align:center;font-size:13px;border:1px solid #888;padding:4px}.kpi small{display:block;font-size:9.5px;color:#333}'
       '.dot{font-size:13px;line-height:1}.small{font-size:10px;color:#222}.r{text-align:right}.sec{break-before:page}'
       'section.stu{page-break-inside:avoid}')
STUDENT_CSS = CSS.replace('A4 landscape', 'A4').replace('font:11px/1.35', 'font:12px/1.4')


def item_text(it: dict) -> str:
    return ((it['no'] + ' ') if it.get('no') else '') + (it['title'] or '')


def _short(it: dict) -> str:
    """Cədvəldə qısa ad: mövzu testi – nömrə (yoxdursa ad), sınaq/KSQ – ad."""
    return it['no'] if it.get('no') else (it['title'] or '')


def _split(row: dict) -> tuple[list[str], list[str]]:
    mv = [item_text(i) for i in row['items'] if i['kind'] == 'movzu']
    other = [item_text(i) for i in row['items'] if i['kind'] != 'movzu']
    return mv, other


def _n(v) -> str:
    return '—' if v is None else (f'{v:.1f}'.rstrip('0').rstrip('.') if isinstance(v, float) else str(v)).replace('.', ',')


def _items_mark(r: dict) -> tuple[str, str]:
    """Mövzu testləri və sınaqlar – qısa siyahı; gözləniləni «⏳»-siz mötərizə ilə ayırırıq (ağ-qara çapda da oxunur)."""
    def one(i):
        t = item_text(i)
        return t + (f' (gec. {i["late_days"]} g.)' if i.get('late_days') else ' (gözl.)' if i['status'] != 'yazmayıb' else '')
    mv = '; '.join(one(i) for i in r['items'] if i['kind'] == 'movzu')
    other = '; '.join(one(i) for i in r['items'] if i['kind'] != 'movzu')
    return mv, other


def _reason_text(r: dict) -> str:
    out = [REASON_AZ[x] + (f' ({n})' if n > 1 else '') for x, n in r.get('reasons', {}).items()]
    return ', '.join(out)


def _risk_cell(risk: str) -> str:
    return f'<span class="dot" style="color:{RISK_COLOR[risk]}">●</span> {RISK_AZ[risk]}'


def _head_block(m: dict, school: str, teacher: str) -> str:
    return (f'<p class="c"><b>{_e(school)}</b></p><h1>{_e(DOC)}</h1>'
            f'<p class="c">{_e(m["class_name"])} · {_e(m["subject"])} · {_e(KIND_LABEL[m["kind"]])} · dövr: {_e(period_text(m))}'
            f' · müəllim: {_e(teacher)}</p>')


def _kpi(m: dict) -> str:
    s = m['summary']
    cells = [(s['students_total'], 'şagird sayı'), (s['tests'], 'test sayı'),
             (_n(s['avg_rate']) + ('%' if s['avg_rate'] is not None else ''), 'orta icra'), (s['full'], 'tam icra edən'),
             (s['critical'], 'kritik'), (s['attention'], 'diqqət')]
    return '<table class="kpi"><tr>' + ''.join(f'<td><b>{_e(str(v))}</b><small>{_e(k)}</small></td>' for v, k in cells) + '</tr></table>'


def class_section(m: dict, school: str, teacher: str, brk: bool = False) -> str:
    """H1-in bədəni (başlıq, göstəricilər, Cədvəl 1–2, şərti işarələr, imza)."""
    body = []
    for n, r in enumerate(m['rows'], 1):
        mv, other = _items_mark(r)
        body.append(
            f"<tr><td class=\"c\">{n}</td><td>{_e(r['full_name'])}</td><td class=\"c\">{r['assigned']}</td><td class=\"c\">{r['done']}</td>"
            f"<td class=\"c\">{r['missed']}</td><td class=\"c\">{r['pending']}</td><td class=\"c\">{_n(r['rate'])}</td>"
            f"<td class=\"c\">{r['late_days'] or '—'}</td><td>{_risk_cell(r['risk'])}</td><td>{_e(mv) or '—'}</td><td>{_e(other) or '—'}</td>"
            f"<td>{_e(_reason_text(r)) or '—'}</td><td>{_e(r['advice'] or '')}</td></tr>")
    if not body:
        body.append('<tr><td colspan="13" class="c">Bu dövrdə bütün şagirdlər testləri işləyib.</td></tr>')
    tests = ''.join(
        f"<tr><td class=\"c\">{n}</td><td class=\"c\">{_e(_d(t['date']))}</td><td>{_e(item_text(t))}</td><td class=\"c\">{t['assigned']}</td>"
        f"<td class=\"c\">{t['done']}</td><td class=\"c\">{_n(t['rate'])}</td><td class=\"c\">{t['missed']}</td><td class=\"c\">{t['pending']}</td></tr>"
        for n, t in enumerate(m['tests'], 1)) or '<tr><td colspan="8" class="c">Test yoxdur.</td></tr>'
    reasons = m['summary'].get('reasons') or {}
    rs = ('<p class="small"><b>Səbəblər üzrə:</b> ' + _e('; '.join(f'{REASON_AZ[k]} – {v}' for k, v in reasons.items())) + '</p>') if reasons else ''
    return (
        f'<section class="{"sec" if brk else ""}">' + _head_block(m, school, teacher) + _kpi(m) +
        '<h2>Cədvəl 1. Şagird üzrə</h2><table><thead><tr><th>№</th><th>Şagird</th><th>Verilib</th><th>İşləyib</th><th>Yazmayıb</th>'
        '<th>Gözlənilir</th><th>İcra, %</th><th>Gecikmə (gün)</th><th>Risk</th><th>Mövzu testləri</th><th>Sınaqlar</th><th>Səbəb</th>'
        '<th>Tövsiyə</th></tr></thead><tbody>' + ''.join(body) +
        f'<tr><td></td><td><b>Cəmi: {m["students"]} şagird</b></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>'
        f'<td></td><td></td><td class="r"><b>{m["total"]}</b></td></tr></tbody></table>' + rs +
        '<h2>Cədvəl 2. Test üzrə</h2><table><thead><tr><th>№</th><th>Tarix</th><th>Test</th><th>Verilib</th><th>İşləyib</th><th>İcra, %</th>'
        '<th>Yazmayıb</th><th>Gözlənilir</th></tr></thead><tbody>' + tests + '</tbody></table>'
        '<p class="small"><b>Şərti işarələr:</b> <span style="color:#B00020">●</span> Kritik – icra &lt; 50% və ya ardıcıl ≥ 3 buraxma; '
        '<span style="color:#C77700">●</span> Diqqət – 50–79%; <span style="color:#2E7D32">●</span> Normal – ≥ 80%. '
        '«gec.» – plan günündən neçə gün keçib; «gözl.» – test açıqdır, hələ təhvil verilməyib. İcra faizi: işlədiyi / ona verilmiş testlər '
        '(üzrlü səbəbli testlər çıxılır).</p>'
        f'<p class="sign">Fənn müəllimi: {_e(teacher)} ______________ (imza)</p></section>')


def _doc(inner: str, css: str = CSS, title: str = DOC) -> str:
    return f'<!doctype html><html lang="az"><head><meta charset="utf-8"><title>{_e(title)}</title><style>{css}</style></head><body>{inner}</body></html>'


def class_html(m: dict, school: str, teacher: str) -> str:
    return _doc(class_section(m, school, teacher))


def all_classes_html(ms: list[dict], school: str, teacher: str, period: str = '') -> str:
    """H3: hər sinif bir sətir (xülasə), sonra hər sinfin H1-i ayrıca səhifədə."""
    rows = ''.join(
        f"<tr><td class=\"c\">{n}</td><td>{_e(m['class_name'])}</td><td>{_e(m['subject'])}</td><td class=\"c\">{m['summary']['students_total']}</td>"
        f"<td class=\"c\">{m['summary']['tests']}</td><td class=\"c\">{_n(m['summary']['avg_rate'])}</td>"
        f"<td class=\"c\">{m['summary']['critical']}</td><td class=\"c\">{m['summary']['attention']}</td></tr>"
        for n, m in enumerate(ms, 1)) or '<tr><td colspan="8" class="c">Sinif yoxdur.</td></tr>'
    head = (f'<p class="c"><b>{_e(school)}</b></p><h1>Bütün siniflərim – işlənməyənlər üzrə xülasə</h1>'
            f'<p class="c">müəllim: {_e(teacher)}' + (f' · dövr: {_e(period)}' if period else '') + '</p>')
    summary = (head + '<table><thead><tr><th>№</th><th>Sinif</th><th>Fənn</th><th>Şagird</th><th>Test</th><th>Orta icra, %</th>'
               '<th>Kritik</th><th>Diqqət</th></tr></thead><tbody>' + rows + '</tbody></table>'
               f'<p class="sign">Fənn müəllimi: {_e(teacher)} ______________ (imza)</p>')
    return _doc(summary + ''.join(class_section(m, school, teacher, brk=True) for m in ms), title='Bütün siniflərim – xülasə')


def class_xlsx(m: dict, school: str, teacher: str, deputy: str = '') -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    thin = Side(style='thin', color='000000')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    grey = PatternFill('solid', fgColor='D9D9D9')
    wb = Workbook()
    ws = wb.active
    ws.title = 'Şagirdlər'
    heads = ['№', 'Şagird', 'Verilib', 'İşləyib', 'Yazmayıb', 'Gözlənilir', 'İcra, %', 'Gecikmə (gün)', 'Risk', 'Mövzu testləri',
             'Sınaqlar', 'Səbəb', 'Tövsiyə']
    for i, (txt, bold, size) in enumerate([(school, True, 11), (DOC, True, 12),
                                           (f'{m["class_name"]} · {m["subject"]} · {KIND_LABEL[m["kind"]]} · {period_text(m)} · müəllim: {teacher}', False, 10)], 1):
        ws.cell(i, 1, txt).font = Font(bold=bold, size=size)
        ws.merge_cells(start_row=i, start_column=1, end_row=i, end_column=len(heads))
        ws.cell(i, 1).alignment = Alignment(horizontal='center')
    hr = 5

    def head_row(sheet, row: int, hs: list):
        for j, h in enumerate(hs, 1):
            c = sheet.cell(row, j, h)
            c.font, c.fill, c.border = Font(bold=True), grey, border
            c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

    def put(sheet, row: list, centered=(1,)):
        sheet.append(row)
        for c in sheet[sheet.max_row]:
            c.border = border
            c.alignment = Alignment(wrap_text=True, vertical='top', horizontal='center' if c.column in centered else 'left')

    head_row(ws, hr, heads)
    for n, r in enumerate(m['rows'], 1):
        mv, other = _items_mark(r)
        put(ws, [n, r['full_name'], r['assigned'], r['done'], r['missed'], r['pending'], r['rate'], r['late_days'] or None,
                 RISK_AZ[r['risk']], '\n'.join(mv.split('; ')) if mv else '', '\n'.join(other.split('; ')) if other else '',
                 _reason_text(r), r['advice'] or ''], centered=(1, 3, 4, 5, 6, 7, 8))
    put(ws, ['', f'Cəmi: {m["students"]} şagird'] + [''] * 10 + [m['total']], centered=(1,))
    last = ws.max_row + 2
    for role, name in (('Fənn müəllimi', teacher), ('Direktor müavini (tədris işləri üzrə)', deputy)):
        ws.cell(last, 1, f'{role}:')
        ws.cell(last, 4, '______________ (imza)')
        ws.cell(last, 10, name or '______________')
        last += 2
    for col, w in zip('ABCDEFGHIJKLM', (5, 30, 9, 9, 10, 11, 9, 11, 10, 34, 30, 22, 30)):
        ws.column_dimensions[col].width = w
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = f'{hr}:{hr}'

    wt = wb.create_sheet('Testlər')
    head_row(wt, 1, ['№', 'Tarix', 'Test', 'Verilib', 'İşləyib', 'İcra, %', 'Yazmayıb', 'Gözlənilir', 'Plan günü'])
    for n, t in enumerate(m['tests'], 1):
        put(wt, [n, _d(t['date']), item_text(t), t['assigned'], t['done'], t['rate'], t['missed'], t['pending'], _d(t.get('plan_date'))],
            centered=(1, 2, 4, 5, 6, 7, 8, 9))
    for col, w in zip('ABCDEFGHI', (5, 12, 44, 9, 9, 9, 10, 11, 12)):
        wt.column_dimensions[col].width = w
    wt.page_setup.orientation = 'portrait'
    wt.page_setup.paperSize = wt.PAPERSIZE_A4
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


_STATE_AZ = {'late_open': 'Plan günü keçib', 'not_due': 'Gözlənilir', None: ''}
_STATE_RU = {'late_open': 'Срок по плану прошёл', 'not_due': 'Ожидается'}


def students_html(m: dict, school: str, teacher: str) -> str:
    """H2 – hər şagird ayrıca səhifə. lang=ru – başlıq və qeydlər AZ | RU."""
    pages = []
    for n, r in enumerate(m['rows']):
        ru = r.get('lang') == 'ru'

        def b(az: str, rus: str) -> str:
            return _e(az) + (f' / {_e(rus)}' if ru else '')
        trs = ''
        for i, it in enumerate(r['items'], 1):
            st = (f'{_STATE_AZ["late_open"]}: {it["late_days"]} g.' if it.get('late_days') else _STATE_AZ.get(it.get('state'), ''))
            if ru:
                st += ' / ' + (f'{_STATE_RU["late_open"]}: {it["late_days"]} дн.' if it.get('late_days') else _STATE_RU.get(it.get('state'), ''))
            trs += (f"<tr><td class=\"c\">{i}</td><td>{_e(item_text(it))}</td><td class=\"c\">{_e(_d(it.get('plan_date') or it['date']))}</td>"
                    f"<td>{_e(st)}</td></tr>")
        if not trs:
            trs = f'<tr><td colspan="4" class="c">{b("İşləməli test yoxdur.", "Нет тестов к выполнению.")}</td></tr>'
        brk = ' style="page-break-before:always"' if n else ''
        head = _e(STUDENT_DOC[0]) + (f' / {_e(STUDENT_DOC[1])}' if ru else '')
        rate = f' · <b>{b("İcra", "Выполнение")}:</b> {_n(r["rate"])}%' if r.get('rate') is not None else ''
        pages.append(
            f'<section class="stu"{brk}>'
            f'<p class="c"><b>{_e(school)}</b></p><h1>{head}</h1>'
            f'<p><b>{b("Şagird", "Ученик")}:</b> {_e(r["full_name"])}</p>'
            f'<p><b>{b("Sinif", "Класс")}:</b> {_e(r.get("class_name", m["class_name"]))} · <b>{b("Fənn", "Предмет")}:</b> {_e(r.get("subject", m["subject"]))}'
            f' · <b>{b("Dövr", "Период")}:</b> {_e(period_text(m))}{rate}</p>'
            f'<table><thead><tr><th>№</th><th>{b("Mövzu / sınaq", "Тема / пробный экзамен")}</th><th>{b("Plan tarixi", "Дата по плану")}</th>'
            f'<th>{b("Vəziyyət", "Состояние")}</th></tr></thead><tbody>{trs}</tbody></table>'
            f'<p>{b("Necə tapmaq: portalda daxil ol → Tapşırıqlar / Testlər bölməsi.", "Как найти: войдите в портал → раздел «Задания / Тесты».")}</p>'
            f'<p>{b("Müəllim qeydi", "Заметка учителя")}: ____________________________________________</p>'
            f'<p class="sign">{b("Fənn müəllimi", "Учитель")}: {_e(teacher)} ______________ ({b("imza", "подпись")})</p>'
            f'<p>{b("Valideyn", "Родитель")}: ______________________ ({b("imza", "подпись")}) &nbsp; {b("Tarix", "Дата")}: ____________</p></section>')
    return _doc(''.join(pages), STUDENT_CSS, STUDENT_DOC[0])


# ---------------------------------------------------------------- H4: qrupa göndəriləcək mətn
NAMES = ('full', 'short', 'none')
_TXT = {
    'az': {'avg': 'Orta icra', 'miss': 'yazmayan şagird', 'tests': 'Hələ işlənməyən testlər', 'who': 'Yazmayanlar', 'ok': 'Bu dövrdə bütün şagirdlər testləri işləyib 👏',
           'period': 'Dövr', 'cnt': 'test', 'left': 'yazmayıb', 'pend': 'gözlənilir', 'cta': 'Zəhmət olmasa portalda «Testlər» bölməsindən tamamlayın.', 'due': 'plan günü'},
    'en': {'avg': 'Average completion', 'miss': 'students have not taken tests', 'tests': 'Tests still not taken', 'who': 'Not taken', 'ok': 'In this period all students have taken the tests 👏',
           'period': 'Period', 'cnt': 'test(s)', 'left': 'not taken', 'pend': 'pending', 'cta': 'Please complete them in the portal, «Tests» section.', 'due': 'planned day'},
    'ru': {'avg': 'Среднее выполнение', 'miss': 'учеников не писали тесты', 'tests': 'Тесты, которые ещё не написаны', 'who': 'Не писали', 'ok': 'За этот период все ученики выполнили тесты 👏',
           'period': 'Период', 'cnt': 'тест(ов)', 'left': 'не писали', 'pend': 'ожидается', 'cta': 'Пожалуйста, выполните их на портале, раздел «Тесты».', 'due': 'день по плану'},
}


def short_name(full: str) -> str:
    """«Soyad Ad [Ata adı]» → «Ad S.» (ad + soyadın baş hərfi)."""
    p = full.split()
    return f'{p[1]} {p[0][0]}.' if len(p) >= 2 else full


def share_text(m: dict, lang: str = 'az', names: str = 'short') -> str:
    if lang not in _TXT:
        lang = 'az'
    if names not in NAMES:
        raise ValueError('names')
    T = _TXT[lang]
    rows = [r for r in m['rows'] if r['items']]
    head = f'📋 {m["class_name"]} · {m["subject"]}\n{T["period"]}: {period_text(m)}'
    if not rows:
        return f'{head}\n{T["ok"]}'
    lines = [head, f'{T["avg"]}: {_n(m["summary"]["avg_rate"])}% · {len(rows)} {T["miss"]}', '', f'{T["tests"]}:']
    for t in m['tests']:
        if t['missed'] or t['pending']:
            lines.append(f'• {item_text(t)} ({_d(t["date"])}) – {t["missed"]} {T["left"]}' + (f', {t["pending"]} {T["pend"]}' if t['pending'] else ''))
    if names != 'none':
        lines += ['', f'{T["who"]}:']
        for r in rows:
            nm = r['full_name'] if names == 'full' else short_name(r['full_name'])
            lines.append(f'• {nm} – {len(r["items"])} {T["cnt"]}')
    lines += ['', T['cta']]
    return '\n'.join(lines)


# ---------------------------------------------------------------- «Tələb et» mesajı (şagirdin dilində)
_REQ = {
    'az': ('Salam! {name}, aşağıdakı testləri hələ işləməmisən:', 'Yeni son tarix: {d}.', 'Zəhmət olmasa portalda «Testlər» bölməsindən tamamla.'),
    'en': ('Hello! {name}, you have not yet taken these tests:', 'New deadline: {d}.', 'Please complete them in the portal, «Tests» section.'),
    'ru': ('Здравствуйте! {name}, вы ещё не выполнили эти тесты:', 'Новый срок: {d}.', 'Пожалуйста, выполните их на портале, раздел «Тесты».'),
}


def request_text(lang: str, name: str, items: list[dict], deadline: str | None = None, message: str | None = None) -> str:
    a, b, c = _REQ.get(lang, _REQ['az'])
    lst = '\n'.join(f'• {item_text(i)}' for i in items)
    if message and message.strip():
        return f'{message.strip()}\n\n{lst}' + (f'\n{b.format(d=deadline)}' if deadline else '')
    return f'{a.format(name=name)}\n{lst}' + (f'\n{b.format(d=deadline)}' if deadline else '') + f'\n{c}'


# ---------------------------------------------------------------- «Test üzrə yazmayanlar» (hər test ayrıca blok)
BY_TEST_DOC = 'Test üzrə yazmayanlar'


def by_test_blocks(m: dict) -> list[dict]:
    """Hər test üçün: test məlumatı + yazmayanlar (ad, status, gecikmə günü, səbəb). Yalnız `m['tests']` (süzgəc tətbiq olunub)."""
    out = []
    for t in m['tests']:
        lst = []
        for r in m['rows']:
            it = next((i for i in r['items'] if i['key'] == t['key']), None)
            if it:
                st = ('Yazmayıb' if it['status'] == 'yazmayıb' else 'Gözlənilir') + (
                    ' (plan günü keçib)' if it.get('state') == 'late_open' and it['status'] != 'yazmayıb' else '')
                lst.append({'name': r['full_name'], 'status': st, 'late_days': it.get('late_days'),
                            'reason': (REASON_AZ[it['reason']] if it.get('reason') else '') + (f' – {it["note"]}' if it.get('note') else '')})
                continue
            ex = next((e for e in r.get('excused', []) if e['key'] == t['key']), None)
            if ex:
                lst.append({'name': r['full_name'], 'status': 'Üzrlü', 'late_days': None,
                            'reason': REASON_AZ['excused'] + (f' – {ex["note"]}' if ex.get('note') else '')})
        out.append({'test': t, 'students': lst})
    return out


def _t_line(t: dict) -> str:
    return (f'verilib: {t["assigned"]} · işləyib: {t["done"]} · icra: {_n(t["rate"])}{"%" if t["rate"] is not None else ""} · '
            f'yazmayıb: {t["missed"]} · gözlənilir: {t["pending"]}')


def by_test_html(m: dict, school: str, teacher: str) -> str:
    blocks = []
    for n, b in enumerate(by_test_blocks(m)):
        t = b['test']
        rows = ''.join(f"<tr><td class=\"c\">{i}</td><td>{_e(x['name'])}</td><td>{_e(x['status'])}</td>"
                       f"<td class=\"c\">{x['late_days'] if x['late_days'] is not None else '—'}</td><td>{_e(x['reason']) or '—'}</td></tr>"
                       for i, x in enumerate(b['students'], 1)) or '<tr><td colspan="5" class="c">Bu testi yazmayan yoxdur.</td></tr>'
        blocks.append(
            f'<section class="{"sec" if n else ""}"><p class="c"><b>{_e(school)}</b></p><h1>{_e(BY_TEST_DOC)}</h1>'
            f'<p class="c">{_e(m["class_name"])} · {_e(m["subject"])} · müəllim: {_e(teacher)}</p>'
            f'<h2>{_e(item_text(t))}</h2>'
            f'<p>Tarix: <b>{_e(_d(t["date"]))}</b> · plan günü: <b>{_e(_d(t.get("plan_date")))}</b> · {_e(_t_line(t))}</p>'
            '<table><thead><tr><th>№</th><th>Şagird</th><th>Status</th><th>Gecikmə (gün)</th><th>Səbəb qeydi</th></tr></thead><tbody>'
            f'{rows}</tbody></table><p class="sign">Fənn müəllimi: {_e(teacher)} ______________ (imza)</p></section>')
    if not blocks:
        blocks.append(f'<p class="c">{_e(BY_TEST_DOC)}: test seçilməyib.</p>')
    return _doc(''.join(blocks), title=BY_TEST_DOC)


def by_test_xlsx(m: dict, school: str, teacher: str) -> bytes:
    """Excel: hər test ayrıca vərəq (vərəq adı ≤ 31 simvol, təkrarsız)."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    thin = Side(style='thin', color='000000')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    grey = PatternFill('solid', fgColor='D9D9D9')
    wb = Workbook()
    wb.remove(wb.active)
    used: set[str] = set()
    empty = {'test': {'no': None, 'title': 'Test yoxdur', 'date': None, 'plan_date': None, 'assigned': 0, 'done': 0, 'rate': None,
                      'missed': 0, 'pending': 0}, 'students': []}
    for n, b in enumerate(by_test_blocks(m) or [empty], 1):
        t = b['test']
        base = ''.join(ch for ch in f'{n}. {item_text(t)}' if ch not in '[]:*?/\\')[:28] or f'Test {n}'
        name, k = base, 1
        while name in used:
            k += 1
            name = f'{base[:26]}~{k}'
        used.add(name)
        ws = wb.create_sheet(name)
        head = [(school, True), (f'{BY_TEST_DOC} – {m["class_name"]} · {m["subject"]} · müəllim: {teacher}', True),
                (f'{item_text(t)} · tarix: {_d(t["date"])} · plan günü: {_d(t.get("plan_date"))}', False), (_t_line(t), False)]
        for i, (txt, bold) in enumerate(head, 1):
            ws.cell(i, 1, txt).font = Font(bold=bold)
            ws.merge_cells(start_row=i, start_column=1, end_row=i, end_column=5)
        for j, h in enumerate(['№', 'Şagird', 'Status', 'Gecikmə (gün)', 'Səbəb qeydi'], 1):
            c = ws.cell(6, j, h)
            c.font, c.fill, c.border = Font(bold=True), grey, border
        for i, x in enumerate(b['students'], 1):
            ws.append([i, x['name'], x['status'], x['late_days'], x['reason']])
            for c in ws[ws.max_row]:
                c.border = border
                c.alignment = Alignment(wrap_text=True, vertical='top')
        ws.cell(ws.max_row + 2, 1, f'Fənn müəllimi: {teacher}   ______________ (imza)')
        for col, w in zip('ABCDE', (5, 32, 26, 14, 40)):
            ws.column_dimensions[col].width = w
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
