"""Gündəlik dərs planı (ARTİ – Azərbaycan Respublikasının Təhsil İnstitutunun nümunəvi strukturu).

Mənbə – perspektiv plan (dəyişdirilməz): mövzu, standart kodları, inteqrasiya, resurslar, qiymətləndirmə,
test toplusunun səhifəsi və tapşırıq nömrələri. Süni intellekt yalnız DƏRSİN GEDİŞİNİ, təlim nəticələrini,
tapşırıqları və qiymətləndirmə meyarlarını hazırlayır; plandakı faktları dəyişmir və uydurmur.
Cavab JSON-dur (sxem aşağıda), server `normalize` ilə yoxlayır və plan faktlarını üstün tutur."""
from __future__ import annotations

LESSON_MIN = 45

SYSTEM = """Sən Azərbaycan Respublikasının ümumtəhsil məktəbləri üçün riyaziyyat (və digər fənlər) üzrə təcrübəli metodist-müəllimsən.
Vəzifən: verilən perspektiv plan sətrinə əsasən ARTİ (Azərbaycan Respublikasının Təhsil İnstitutu) tövsiyələrinə və
fənn kurikulumuna uyğun, müəllimin sinifdə birbaşa istifadə edə biləcəyi PEŞƏKAR GÜNDƏLİK DƏRS PLANI hazırlamaq.
Plan ARTİ-nin «Gündəlik planlaşdırma» formasına düşür: Altstandart(lar) → Təlim nəticəsi(ləri) → Qiymətləndirmə
meyar(lar)ı → Mövzu → Dərsin təşkili (şagirdlərin dərsə cəlbolunması, sual və tapşırıqlar) → İş üsulu / İş forması →
Refleksiya. Bu ardıcıllıq bir-birinə bağlı olmalıdır: altstandart → təlim nəticəsi → meyar → tapşırıq.

ƏSAS PRİNSİPLƏR
1. Perspektiv plan qanundur: mövzunu, altstandartların kodlarını, dərslik/test toplusu səhifələrini və tapşırıq
   nömrələrini (S – sinifdə, E – ev tapşırığı, M – müstəqil hazırlıq) OLDUĞU KİMİ istifadə et. Yeni səhifə, nömrə,
   dərslik adı UYDURMA. Planda olmayan məlumat lazımdırsa «[müəllim dəqiqləşdirir]» yaz.
2. Altstandartın kurikulumdakı rəsmi mətnini dəqiq bilmirsənsə, "metn" sahəsini BOŞ saxla – təxmini mətn yazma.
3. Təlim nəticələri şagird yönümlü, ölçülə bilən və yoxlanıla bilən olsun: «Şagird … hesablayır / izah edir /
   tətbiq edir / müqayisə edir / əsaslandırır» (Blum taksonomiyasının müxtəlif səviyyələri; «bilir», «anlayır» yox).
   Hər təlim nəticəsi altstandart koduna bağlansın. QİYMƏTLƏNDİRMƏ MEYARLARI (2–4) təlim nəticələrindən çıxır, müşahidə
   olunan davranışla yazılır («… düsturu tətbiq etməklə məsələ həll edir») və dərsdəki konkret tapşırıqla yoxlanır.
4. «Dərsin təşkili» interaktiv təlimin mərhələləri ilə qurulur (hər mərhələdə müəllimin konkret sualları və tapşırıqlar):
   a) Motivasiya, problemin qoyuluşu – əvvəlki ev tapşırığının qısa yoxlanması, həyati situasiya/problem, TƏDQİQAT SUALI;
   b) Tədqiqatın aparılması – qruplar/cütlər üçün konkret iş vərəqləri (hər qrupa ayrıca tapşırıq);
   c) Məlumat mübadiləsi – təqdimat;
   d) Məlumatın müzakirəsi və təşkili – müəllimin yönəldici sualları, qaydanın/düsturun çıxarılması;
   e) Nəticə və ümumiləşdirmə – tədqiqat sualının cavabı, qayda/tərif;
   f) Yaradıcı tətbiqetmə – planda göstərilən sinif tapşırıqları (S) və 1–2 məntiqi/həyati məsələ;
   g) Qiymətləndirmə – formativ, qiymətləndirmə meyarları üzrə (müşahidə, özünüqiymətləndirmə və s.);
   h) Refleksiya – 2–3 sual;
   i) Ev tapşırığı – planda E ilə verilən nömrələr (və M varsa – könüllü/müstəqil hazırlıq).
   Mərhələlərin vaxtları cəmi dəqiq {mins} dəqiqə olsun.
5. Riyazi məzmun DƏQİQ olmalıdır: hər nümunə tapşırığın cavabını özün yoxla və "cavab" sahəsinə yaz. Riyazi ifadələri
   Unicode simvolları ilə yaz (x², √, ≤, ≥, ≠, ∈, ∪, ∩, π, °, ·) – LaTeX işarələri ($, \\frac) İSTİFADƏ ETMƏ.
6. Diferensial yanaşma: zəif şagirdlər üçün dəstək (nümunə, addım-addım), güclü şagirdlər üçün çətinləşdirilmiş tapşırıq.
7. Sinifdə TOM (buraxılış/qəbul imtahanına hazırlıq) istiqaməti varsa, test toplusundakı test tiplərinə uyğun
   sürətli həll üsullarını və tipik səhvləri göstər.
8. Dərs summativ (KSQ/BSQ) və ya diaqnostik qiymətləndirmədirsə, YENİ MÖVZU KEÇİLMİR: mərhələlər – «Təşkilati hissə və
   təlimat», «Qiymətləndirmənin icrası», «İşlərin toplanması və refleksiya»; qiymətləndirmə bölməsində altstandartlar üzrə
   tapşırıq spesifikasiyası (hər altstandart üçün tapşırıq sayı, çətinlik səviyyəsi, bal) və 1–2 nümunə tapşırıq ver;
   ev tapşırığı – növbəti mövzuya hazırlıq (və ya «verilmir»).
9. Dil – ədəbi Azərbaycan dili, rəsmi-metodik üslub, orfoqrafiya qaydalarına uyğun; qısa və konkret, su yox.

CAVAB FORMATI – YALNIZ aşağıdakı sxemdə etibarlı JSON obyekti (başqa mətn yox):
{
  "standartlar": [{"kod": "1.1.4", "metn": ""}],
  "telim_neticeleri": ["Şagird …"],
  "acar_anlayislar": ["…"],
  "inteqrasiya": "…",
  "is_formalari": ["kollektiv", "qruplarla", "cütlərlə", "fərdi"],
  "is_usullari": ["beyin həmləsi", "…"],
  "resurslar": ["…"],
  "tedqiqat_suali": "…",
  "merheleler": [
    {"ad": "Motivasiya, problemin qoyuluşu", "vaxt": 5,
     "muellim": "müəllimin fəaliyyəti (konkret sözlər, suallar)",
     "sagird": "şagirdlərin fəaliyyəti",
     "tapsiriqlar": [{"metn": "konkret tapşırıq", "cavab": "yoxlanmış cavab"}]}
  ],
  "diferensial": {"destek": "…", "inkisaf": "…"},
  "qiymetlendirme": {
    "meyarlar": ["…"], "usul": "…", "vasite": "…",
    "spesifikasiya": [{"standart": "1.1.4", "tapsiriq_sayi": 2, "seviyye": "orta", "bal": 4}]
  },
  "refleksiya": ["…?"],
  "ev_tapsirigi": "…",
  "muellim_ucun_qeyd": "tipik səhvlər, vaxta qənaət, texniki hazırlıq"
}
"spesifikasiya" yalnız summativ/diaqnostik dərsdə doldurulur, formativ dərsdə boş massiv olsun."""

RES_LEGEND = ('Resurs işarələri: TT – DİM test toplusu (hissə), s. – səhifə; S – sinifdə, E – ev tapşırığı, '
              'M – müstəqil hazırlıq üçün test nömrələri; QT – DİM siniflər üzrə qiymətləndirmə tapşırıqları (sinif); '
              'D – dərslik (sinif).')

TASK_KIND = {'sinif': 'Sinifdə (S)', 'ev': 'Ev tapşırığı (E)', 'mustaqil': 'Müstəqil hazırlıq (M)'}


def tasks_text(tasks: list | None) -> str:
    out = []
    for t in tasks or []:
        rng = f"№ {t.get('start')}–{t.get('end')}" if t.get('end') and t.get('end') != t.get('start') else f"№ {t.get('start')}"
        out.append(f"{TASK_KIND.get(t.get('kind'), t.get('kind'))}: {(t.get('label') + ' ') if t.get('label') else ''}{rng}")
    return '; '.join(out)


def system_prompt(minutes: int = LESSON_MIN) -> str:
    return SYSTEM.replace('{mins}', str(minutes))


def user_prompt(c: dict) -> str:
    """c – `lessonplans._context` nəticəsi (hamısı perspektiv plandan və jurnaldan)."""
    L = [f"GÜNDƏLİK DƏRS PLANI ÜÇÜN MƏLUMAT (perspektiv plandan – dəyişdirilməz)",
         f"Məktəb: {c['school']}", f"Müəllim: {c['teacher']}", f"Fənn: {c['subject']}",
         f"Sinif: {c['class_name']}{' (bölünən qrup)' if c.get('group') else ''}; şagird sayı: {c['students']}; "
         f"növ: {'TOM (buraxılış/qəbul imtahanına hazırlıq)' if c.get('kind') == 'TOM' else 'adi sinif (TOM deyil – DİM test toplusu əsas deyil)'}",
         *([f"Sinfin səviyyə tərkibi: {', '.join(f'{k.lower()} – {v}' for k, v in c['levels'].items())}"] if c.get('levels') else []),
         *(["DİQQƏT: sinfin əksəriyyəti zəifdir – əsas bacarıqların təkrarı (5–7 dəq), addım-addım nümunə, sadə dil, "
            "tapşırıqlar üç pillədə (nümunə üzrə → oxşar → tətbiq), qısa məcburi ev tapşırığı + könüllü hissə; "
            "güclü/orta şagird cüt işində köməkçi olsun."]
           if c.get('levels') and c['levels'].get('Zəif', 0) * 2 > sum(c['levels'].values()) else []),
         f"Tarix: {c['date_text']} ({c['weekday']}), {c['period']}-ci dərs saatı{(' ' + c['time']) if c.get('time') else ''}; dərsin müddəti {c['minutes']} dəqiqə",
         f"Yarımil: {c['semester']}; perspektiv plan üzrə dərs № {c['seq']} / {c['total']}",
         f"Bölmə: {c['section'] or '—'}" + (f" (bölmənin {c['section_pos']}-ci dərsi, cəmi {c['section_len']})" if c.get('section_len') else ''),
         f"MÖVZU: {c['topic']}",
         f"Məzmun standartları (kodlar): {', '.join(c['standards']) or '—'}",
         f"Qiymətləndirmə növü: {c['assessment_type']}{('-' + str(c['exam_no'])) if c.get('exam_no') else ''}",
         f"Plandakı qiymətləndirmə: {c['assessment'] or '—'}",
         f"İnteqrasiya (plan): {c['integration'] or '—'}",
         f"Resurslar (plan): {(c['resources'] or '—').replace(chr(10), '; ')}",
         f"Test toplusu səhifələri: {c['tt_pages'] or '—'}",
         f"Tapşırıqlar (plan): {c['tasks'] or '—'}",
         RES_LEGEND]
    if c.get('p0010'):
        L.insert(-1, f"P0010 test bankı (mövzuya uyğun fayl, yoxlama/ev tapşırığı üçün): {c['p0010']}")
    if c.get('continues_from'):
        L.append('DİQQƏT: bu mövzu əvvəlki dərsdə başlanıb – bu, mövzunun DAVAMI (möhkəmləndirmə, tətbiq) dərsidir.')
    if c.get('continues_next'):
        L.append('DİQQƏT: mövzu növbəti dərsdə də davam edəcək – bu dərsdə mövzunun əsas hissəsini planla, tətbiqin bir hissəsini növbəti dərsə saxla.')
    L += [f"Əvvəlki dərsin mövzusu: {c['prev_topic'] or '—'}",
          f"Əvvəlki dərsdə verilmiş ev tapşırığı (jurnal): {c['prev_homework'] or 'qeyd yoxdur'}",
          f"Növbəti dərsin mövzusu: {c['next_topic'] or '—'}"]
    if c.get('next_exam'):
        L.append(f"Yaxın summativ qiymətləndirmə: {c['next_exam']}")
    if c.get('review_topics'):
        L.append(f"Təkrar tələb olunan əvvəlki mövzular (müəllimin qeydi): {'; '.join(c['review_topics'])} – "
                 "dərsin əvvəlinə (motivasiya/yoxlama mərhələsi) 3–5 dəqiqəlik qısa təkrar daxil et.")
    if c.get('notes'):
        L.append(f"MÜƏLLİMİN ƏLAVƏ İSTƏYİ (nəzərə al, plan faktlarına zidd olmasın): {c['notes']}")
    L.append('\nTAPŞIRIQ: yuxarıdakı dərs üçün ARTİ strukturuna uyğun gündəlik plan hazırla. YALNIZ sxemdəki JSON-u qaytar.')
    return '\n'.join(L)


def _s(v) -> str:
    return v.strip() if isinstance(v, str) else '' if v is None else str(v)


def _list(v) -> list:
    return v if isinstance(v, list) else [v] if v else []


def normalize(raw: dict, c: dict) -> tuple[dict, list[str]]:
    """Modelin JSON-u → təmiz sxem. Plan faktları üstündür (standart kodları, mövzu); xəbərdarlıqlar qaytarılır."""
    warn: list[str] = []
    texts = {}
    for s in _list(raw.get('standartlar')):
        if isinstance(s, dict) and _s(s.get('kod')):
            texts[_s(s.get('kod'))] = _s(s.get('metn'))
    std = [{'kod': k, 'metn': texts.get(k, '')} for k in c['standards']]
    extra = [k for k in texts if k not in c['standards']]
    if extra:
        warn.append(f"Model planda olmayan standart kodlarını əlavə etmişdi ({', '.join(extra)}) – çıxarıldı")
    stages = []
    for m in _list(raw.get('merheleler')):
        if not isinstance(m, dict):
            continue
        try:
            vaxt = int(round(float(m.get('vaxt') or 0)))
        except (TypeError, ValueError):
            vaxt = 0
        tasks = []
        for t in _list(m.get('tapsiriqlar')):
            if isinstance(t, dict):
                if _s(t.get('metn')):
                    tasks.append({'metn': _s(t.get('metn')), 'cavab': _s(t.get('cavab'))})
            elif _s(t):
                tasks.append({'metn': _s(t), 'cavab': ''})
        stages.append({'ad': _s(m.get('ad')) or 'Mərhələ', 'vaxt': vaxt, 'muellim': _s(m.get('muellim')),
                       'sagird': _s(m.get('sagird')), 'tapsiriqlar': tasks})
    if not stages:
        warn.append('Dərsin gedişi (mərhələlər) boşdur – yenidən hazırlayın')
    total = sum(s['vaxt'] for s in stages)
    if stages and total != c['minutes']:
        warn.append(f"Mərhələlərin vaxtı cəmi {total} dəq (olmalı: {c['minutes']}) – yoxlayın")
    q = raw.get('qiymetlendirme') if isinstance(raw.get('qiymetlendirme'), dict) else {}
    rub = [{'meyar': _s(r.get('meyar')), **{k: _s(r.get(k)) for k in ('I', 'II', 'III', 'IV')}}
           for r in _list(q.get('rubrika')) if isinstance(r, dict) and _s(r.get('meyar'))]
    spec = [{'standart': _s(r.get('standart')), 'tapsiriq_sayi': _s(r.get('tapsiriq_sayi')), 'seviyye': _s(r.get('seviyye')),
             'bal': _s(r.get('bal'))} for r in _list(q.get('spesifikasiya')) if isinstance(r, dict)]
    d = raw.get('diferensial') if isinstance(raw.get('diferensial'), dict) else {}
    out = {
        'standartlar': std,
        'telim_neticeleri': [_s(x) for x in _list(raw.get('telim_neticeleri')) if _s(x)],
        'acar_anlayislar': [_s(x) for x in _list(raw.get('acar_anlayislar')) if _s(x)],
        'inteqrasiya': _s(raw.get('inteqrasiya')) or c['integration'] or '',
        'is_formalari': [_s(x) for x in _list(raw.get('is_formalari')) if _s(x)],
        'is_usullari': [_s(x) for x in _list(raw.get('is_usullari')) if _s(x)],
        'resurslar': [_s(x) for x in _list(raw.get('resurslar')) if _s(x)],
        'tedqiqat_suali': _s(raw.get('tedqiqat_suali')),
        'merheleler': stages,
        'diferensial': {'destek': _s(d.get('destek')), 'inkisaf': _s(d.get('inkisaf'))},
        'qiymetlendirme': {'meyarlar': [_s(x) for x in _list(q.get('meyarlar')) if _s(x)], 'usul': _s(q.get('usul')),
                           'vasite': _s(q.get('vasite')), 'rubrika': rub, 'spesifikasiya': spec},
        'refleksiya': [_s(x) for x in _list(raw.get('refleksiya')) if _s(x)],
        'ev_tapsirigi': _s(raw.get('ev_tapsirigi')),
        'muellim_ucun_qeyd': _s(raw.get('muellim_ucun_qeyd')),
    }
    if not out['telim_neticeleri']:
        warn.append('Təlim nəticələri yazılmayıb')
    hw = c.get('homework_plan')
    if hw and not all(n in out['ev_tapsirigi'] for n in c.get('homework_nums') or [hw]):
        out['ev_tapsirigi'] = (out['ev_tapsirigi'] + ' ' if out['ev_tapsirigi'] else '') + f'(Plan üzrə: {hw})'
    return out, warn
