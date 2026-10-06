"""Şagird sorğusu (docs/muellim-sorgusu-promtu.md): hazır sorğu şablonu və nəticələrin hesablanması (saf funksiyalar).

Şkala: likert5 (1–5), scale10 (0–10 və ya 1–10), single / multi (variant indeksi), text (açıq cavab).
reverse – mənfi ifadəli sual: indeksdə bal 6 − x kimi sayılır (paylanma xam qalır)."""
from __future__ import annotations

import statistics

LIKERT = ['Tamamilə razı deyiləm', 'Razı deyiləm', 'Bilmirəm', 'Razıyam', 'Tamamilə razıyam']

SECTIONS = [
    {'key': 'A', 'title': 'Fənn bilgisi və izah'},
    {'key': 'B', 'title': 'Dərsin təşkili və metodika'},
    {'key': 'C', 'title': 'Qiymətləndirmə və geri bildirim'},
    {'key': 'D', 'title': 'Ünsiyyət və münasibət'},
    {'key': 'E', 'title': 'Motivasiya və inkişaf'},
    {'key': 'F', 'title': 'İntizam və peşəkar davranış'},
    {'key': 'G', 'title': 'Ümumi qiymət'},
    {'key': 'H', 'title': 'Açıq suallar'},
]
DEMO_SECTION = {'key': 'X', 'title': 'Özünüz haqqında (istəyə görə)'}


def _l(key, section, text, reverse=False):
    return {'key': key, 'section': section, 'kind': 'likert5', 'text': text, 'options': None, 'required': True,
            'reverse': reverse}


TEMPLATE_KEY = 'teacher_feedback_v1'
TEMPLATE = [
    _l('A1', 'A', 'Müəllim fənni dərindən bilir.'),
    _l('A2', 'A', 'Yeni mövzunu aydın və başa düşülən izah edir.'),
    _l('A3', 'A', 'Çətin mövzuları sadə misallarla izah edir.'),
    _l('A4', 'A', 'Suallarıma dəqiq və inandırıcı cavab verir.'),
    _l('A5', 'A', 'Müəllimin izahından sonra mövzunu çox vaxt yenə başa düşmürəm.', reverse=True),
    _l('B1', 'B', 'Dərslər planlı və mütəşəkkil keçir.'),
    _l('B2', 'B', 'Dərsin vaxtı səmərəli istifadə olunur.'),
    _l('B3', 'B', 'Müəllim müxtəlif üsullardan istifadə edir (təqdimat, test, qrup işi, praktika).'),
    _l('B4', 'B', 'Dərsdə maraqlı olur, diqqətim dağılmır.'),
    _l('B5', 'B', 'Tapşırıqların çətinliyi mənim səviyyəmə uyğundur.'),
    _l('C1', 'C', 'Qiymətləndirmə ədalətlidir və meyarlar aydındır.'),
    _l('C2', 'C', 'Testlər və imtahanlar keçilən mövzulara uyğundur.'),
    _l('C3', 'C', 'Səhvlərimi necə düzəltməli olduğumu izah edir.'),
    _l('C4', 'C', 'Ev tapşırıqları yoxlanılır və şərh verilir.'),
    _l('D1', 'D', 'Müəllim şagirdlərə hörmətlə yanaşır.'),
    _l('D2', 'D', 'Hər şagirdə bərabər münasibət göstərir.'),
    _l('D3', 'D', 'Sual verməyə və səhv etməyə çəkinmirəm.'),
    _l('D4', 'D', 'Müəllim səbirli və təmkinlidir.'),
    _l('D5', 'D', 'Müəllimlə danışmaq mənim üçün asandır.'),
    _l('D6', 'D', 'Müəllim bəzən şagirdləri başqalarının yanında utandırır.', reverse=True),
    _l('E1', 'E', 'Müəllim məni fənni öyrənməyə həvəsləndirir.'),
    _l('E2', 'E', 'Bu dərslərdə biliklərim nəzərəçarpacaq dərəcədə artıb.'),
    _l('E3', 'E', 'Müəllim imtahanlara (buraxılış / qəbul) hazırlaşmağıma kömək edir.'),
    _l('E4', 'E', 'Müəllim mənim güclü və zəif tərəflərimi bilir.'),
    _l('F1', 'F', 'Müəllim dərsə vaxtında gəlir və dərsi vaxtında bitirir.'),
    _l('F2', 'F', 'Sinifdə nizam-intizam qorunur.'),
    _l('F3', 'F', 'Müəllim verdiyi sözə əməl edir.'),
    _l('F4', 'F', 'Onlayn materiallar və testlər (tətbiqdə) faydalıdır.'),
    {'key': 'overall', 'section': 'G', 'kind': 'scale10', 'text': 'Ümumilikdə müəllimin işi sizcə necədir?',
     'options': {'min': 1, 'max': 10}, 'required': True, 'reverse': False},
    {'key': 'nps', 'section': 'G', 'kind': 'scale10',
     'text': 'Bu müəllimi dostlarınıza tövsiyə edərdinizmi?',
     'options': {'min': 0, 'max': 10}, 'required': True, 'reverse': False},
    {'key': 'H1', 'section': 'H', 'kind': 'text', 'text': 'Müəllimin işində sizə ən çox nə xoşdur?',
     'options': None, 'required': False, 'reverse': False},
    {'key': 'H2', 'section': 'H', 'kind': 'text', 'text': 'Nəyi dəyişməyi və ya yaxşılaşdırmağı təklif edərdiniz?',
     'options': None, 'required': False, 'reverse': False},
    {'key': 'H3', 'section': 'H', 'kind': 'text', 'text': 'Müəllimə demək istədiyiniz başqa bir fikir varmı?',
     'options': None, 'required': False, 'reverse': False},
]
DEMO = [
    {'key': 'X1', 'section': 'X', 'kind': 'single', 'text': 'Neçənci sinifdə oxuyursunuz?',
     'options': {'choices': ['IX', 'X', 'XI', 'Digər']}, 'required': False, 'reverse': False},
    {'key': 'X2', 'section': 'X', 'kind': 'single', 'text': 'Dərslərə nə qədər müntəzəm gəlirsiniz?',
     'options': {'choices': ['Həmişə', 'Bəzən buraxıram', 'Nadir hallarda gəlirəm']}, 'required': False, 'reverse': False},
]
KINDS = ('likert5', 'scale10', 'single', 'multi', 'text')

# Meyar zəif çıxanda sinifdə tətbiq olunan təlim strategiyaları (müəllim sinif üzrə strategiyanı dəyişsin)
STRATEGIES = {
    'A': ['Yeni mövzunu «model → birgə → müstəqil» ardıcıllığı ilə izah edin (I do – We do – You do)',
          'Hər izahdan sonra 1–2 dəqiqəlik yoxlama: çıxış bileti, «barmaqla 1–5» və ya mini-test',
          'Çətin anlayışı 2–3 həyati misal və vizual sxemlə verin; ən çox səhv edilən yeri ayrıca göstərin'],
    'B': ['Dərsin əvvəlində məqsədi və planı lövhədə yazın, sonda 3 dəqiqəlik yekun edin',
          'Metodları növbələyin: cüt iş, qrup işi, stansiyalar, rəqəmsal test – 15 dəqiqədən uzun monoloq olmasın',
          'Tapşırıqları 3 səviyyədə verin (əsas / orta / çətin) – şagird öz səviyyəsini seçsin'],
    'C': ['Qiymətləndirmə meyarlarını (rubrika) tapşırıqdan ƏVVƏL paylaşın, nümunə işi göstərin',
          'Hər yoxlama işindən sonra 2 güclü cəhət + 1 konkret addım şəklində qısa yazılı rəy verin',
          'Səhvlər üzərində iş dərsi: tipik səhvləri anonim təhlil edin, düzəliş tapşırığı verin'],
    'D': ['Sual verməyi təşviq edin: «səhv cavab yoxdur» qaydası, anonim sual qutusu / çatda sual',
          'Hər dərsdə fərqli şagirdlərə söz verin (təsadüfi seçim) – hamıya bərabər diqqət',
          'Tənqidi təkbətək, tərifi sinif qarşısında edin; səbirli, sakit ton saxlayın'],
    'E': ['Mövzunu real həyat və imtahan (buraxılış / qəbul) tapşırıqları ilə əlaqələndirin',
          'Şagirdin irəliləyişini görünən edin: fərdi hədəf, həftəlik nəticə qrafiki, kiçik uğurları qeyd edin',
          'Seçim imkanı verin: layihə, təqdimat və ya əlavə tapşırıq; güclülərə olimpiada tipli məsələ'],
    'F': ['Dərsi vaxtında başlayıb bitirin; sinif qaydalarını şagirdlərlə birlikdə razılaşdırın',
          'Verilən sözə (yoxlama, nəticə, məşğələ) əməl edin – müddəti əvvəlcədən elan edin',
          'Onlayn material və testləri həftəlik cədvəllə verin, keçidi və nəticəni dərsdə müzakirə edin'],
}


def pulse_pick(qs: list[dict], period: str | int) -> list[dict]:
    """Qısa həftəlik sorğu: hər bölmədən bir likert sualı (həftə nömrəsinə görə növbə ilə), «overall» hər həftə,
    «nps» 4 həftədə bir, açıq suallardan biri (növbə ilə, istəyə görə). 4–5 həftədə bütün suallar əhatə olunur."""
    if isinstance(period, int):
        w = period                                                     # qısa link: hər açılışda başqa variant
    else:
        try:
            w = int(period.split('W')[1])
        except (IndexError, ValueError):
            w = 0
    out, by_sec = [], {}
    for q in qs:
        if q['kind'] == 'likert5':
            by_sec.setdefault(q['section'], []).append(q)
    picked = {id(v[w % len(v)]) for v in by_sec.values()}
    texts = [q for q in qs if q['kind'] == 'text']
    pt = texts[w % len(texts)] if texts else None
    for q in qs:
        if id(q) in picked or q.get('key') == 'overall' or (q.get('key') == 'nps' and w % 4 == 0) or q is pt:
            out.append(q)
        elif q['kind'] in ('scale10', 'single', 'multi') and q.get('key') not in ('nps', 'overall') and q['section'] not in ('X',):
            out.append(q)                                              # müəllimin əlavə etdiyi digər suallar
    return out


def _r(v: float | None, d: int = 2) -> float | None:
    return None if v is None else round(v, d)


def adj(q: dict, v: int) -> int:
    return 6 - v if q.get('reverse') else v


def scale_range(q: dict) -> tuple[int, int]:
    o = q.get('options') or {}
    return int(o.get('min', 0)), int(o.get('max', 10))


def nps(values: list[int]) -> dict:
    n = len(values)
    if not n:
        return {'n': 0, 'score': None, 'promoters': 0, 'passives': 0, 'detractors': 0}
    p = sum(v >= 9 for v in values)
    d = sum(v <= 6 for v in values)
    return {'n': n, 'score': round((p - d) * 100 / n), 'promoters': p, 'passives': n - p - d, 'detractors': d}


def question_stats(q: dict, values: list) -> dict:
    """Bir sualın göstəriciləri: n, paylanma, orta (likert-də həm xam, həm çevrilmiş), razılıq faizi."""
    out = {'n': len(values)}
    if q['kind'] == 'likert5':
        a = [adj(q, v) for v in values]
        out.update(dist={str(i): values.count(i) for i in range(1, 6)}, mean=_r(statistics.mean(values)) if values else None,
                   adj_mean=_r(statistics.mean(a)) if a else None, median=statistics.median(values) if values else None,
                   agree_pct=_r(sum(x >= 4 for x in a) * 100 / len(a), 1) if a else None)
    elif q['kind'] == 'scale10':
        lo, hi = scale_range(q)
        out.update(dist={str(i): values.count(i) for i in range(lo, hi + 1)},
                   mean=_r(statistics.mean(values)) if values else None,
                   median=statistics.median(values) if values else None)
        if q.get('key') == 'nps':
            out['nps'] = nps(values)
    elif q['kind'] in ('single', 'multi'):
        ch = (q.get('options') or {}).get('choices') or []
        flat = [x for v in values for x in (v if isinstance(v, list) else [v])]
        out['dist'] = {c: flat.count(i) for i, c in enumerate(ch)}
    return out


def section_index(qs: list[dict], answers: list[dict]) -> dict[str, dict]:
    """Meyar indeksi: bölmənin bütün likert cavablarının (çevrilmiş) ortası və razılıq faizi."""
    out: dict[str, dict] = {}
    for q in qs:
        if q['kind'] != 'likert5':
            continue
        s = out.setdefault(q['section'], {'vals': []})
        s['vals'] += [adj(q, a[str(q['id'])]) for a in answers if isinstance(a.get(str(q['id'])), int)]
    return {k: {'index': _r(statistics.mean(v['vals'])) if v['vals'] else None,
                'agree_pct': _r(sum(x >= 4 for x in v['vals']) * 100 / len(v['vals']), 1) if v['vals'] else None,
                'n': len(v['vals'])} for k, v in out.items()}


def summary(qs: list[dict], answers: list[dict]) -> dict:
    """Bölmə indeksləri + ümumi qiymət + NPS (dalğaları və sinifləri müqayisə üçün qısa forma)."""
    by_key = {q.get('key'): q for q in qs}
    vals = lambda q: [a[str(q['id'])] for a in answers if isinstance(a.get(str(q['id'])), int)] if q else []
    ov = vals(by_key.get('overall'))
    return {'n': len(answers), 'sections': {k: v['index'] for k, v in section_index(qs, answers).items()},
            'overall': _r(statistics.mean(ov)) if ov else None, 'nps': nps(vals(by_key.get('nps')))['score']}


def validate(q: dict, v):
    """Şagirdin cavabını yoxlayır; boş cavab üçün None; səhv dəyər üçün ValueError."""
    if v is None or v == '' or v == []:
        return None
    k = q['kind']
    if k == 'likert5':
        if not isinstance(v, int) or isinstance(v, bool) or not 1 <= v <= 5:
            raise ValueError
        return v
    if k == 'scale10':
        lo, hi = scale_range(q)
        if not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi:
            raise ValueError
        return v
    ch = (q.get('options') or {}).get('choices') or []
    if k == 'single':
        if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v < len(ch):
            raise ValueError
        return v
    if k == 'multi':
        if not isinstance(v, list) or not all(isinstance(x, int) and 0 <= x < len(ch) for x in v):
            raise ValueError
        return sorted(set(v))
    if k == 'text':
        if not isinstance(v, str):
            raise ValueError
        import re
        t = re.sub(r'<[^>]*>', '', v)                                  # HTML yox – yalnız mətn
        t = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', t).strip()[:1000]
        return t or None
    raise ValueError
