// «Sənədə daxil olsun» çap konfiqurasiyası: seçilən bölmələr bir sənəddə (köhnə Reports.tsx «Çap / PDF» tabı – davranış dəyişməyib).
import { useEffect, useMemo, useState } from 'react'
import { get } from '../../../api'
import { useAuth } from '../../../auth'
import { Loading, toast, useNarrow } from '../../../ui'
import { useMyLessons } from '../common'
import { docHtml, downloadPdf, esc, fmtD, fmtN, head, kpis, printDoc, printLater, SIGN, signs, table, type Doc } from '../../../print'
import { useT } from '../../../i18n'
import { semLabel, type Sem } from './common'

/* ---------------------------------------------------------------- çap mərkəzi: seçilən bölmələr bir sənəddə */
type Part = 'performance' | 'rating' | 'lessons' | 'attendance' | 'heatmap' | 'levels' | 'groups' | 'risk'
const PARTS: [Part, string][] = [['performance', 'Müvəffəqiyyət (rəsmi forma)'], ['rating', 'Reytinq'], ['lessons', 'Dərs sayı və yazılmamış dərslər'],
  ['attendance', 'Davamiyyət (yekun)'], ['heatmap', 'Davamiyyət xəritəsi (albom: tarix × şagird)'], ['levels', 'Güclü / orta / zəif (analitika)'],
  ['groups', 'Səviyyə qrupları (bölgü: bal və komponentlər)'], ['risk', 'Risk (daxili istifadə üçün)']]
type Extra = { a: any; perf: any; lessons: any; att: any; lv: any }

/** Bir sinif/qrup üçün çap məlumatı (bir dəfə yüklənir). */
async function loadExtra(ta: number, sem: Sem, a?: any): Promise<Extra> {
  const params: Record<string, string> = sem === 'all' ? {} : { semester: sem }
  const [aa, perf, lessons, att, lv] = await Promise.all([a ? Promise.resolve(a) : get<any>(`/api/analytics/${ta}`, params),
    get<any>(`/api/analytics/${ta}/performance`, params), get<any>(`/api/analytics/${ta}/lessons`), get<any>(`/api/analytics/${ta}/attendance`, params),
    get<any>(`/api/levels/${ta}`).catch(() => null)])
  return { a: aa, perf, lessons, att, lv }
}

const groupLine = (a: any) => (a.group ? ` · ${a.group.kind}${a.group.classes?.length ? ` (${a.group.classes.join(', ')})` : ''}` : '')

/** Bir sinif/qrup üçün sənədin gövdəsi: başlıq + seçilən bölmələr. */
function taBody(x: Extra, parts: Part[], sem: Sem, teacher: string) {
  const a = x.a
  return head(`${a.class_name}${a.group ? '' : ' sinfi'} – ${a.subject} fənni üzrə hesabat`,
    `${semLabel(sem)}: ${fmtD(a.from)} – ${fmtD(a.to)}${groupLine(a)} · müəllim: ${teacher}`) + parts.map(k => SECTIONS[k](a, x)).join('')
}

export function ClassPrint({ a, ta, sem }: { a: any; ta: number; sem: Sem }) {
  const t = useT()
  const { me } = useAuth()
  const narrow = useNarrow()
  const [lessons] = useMyLessons()
  const [on, setOn] = useState<Record<Part, boolean>>({ performance: true, rating: true, lessons: true, attendance: false, heatmap: false, levels: false, groups: false, risk: false })
  const [extra, setExtra] = useState<Extra | null>(null)
  const [busy, setBusy] = useState(false)
  const [batch, setBatch] = useState<string | null>(null)
  useEffect(() => {
    let live = true
    setBusy(true)
    loadExtra(ta, sem, a).then(x => { if (live) setExtra(x) }).finally(() => live && setBusy(false))
    return () => { live = false }
  }, [ta, sem, a])
  const parts = PARTS.filter(([k]) => on[k]).map(([k]) => k)
  const landscape = on.heatmap
  const teacher = me?.full_name || ''
  const doc = useMemo<Doc | null>(() => extra && ({
    title: `${a.class_name} – ${a.subject} hesabatı ${fmtD(a.from)}–${fmtD(a.to)}`, body: taBody(extra, parts, sem, teacher),
    internal: on.risk, landscape, signers: [SIGN.teacher(teacher), SIGN.deputy()],
  }), [a, extra, on, sem, teacher])
  /** Bütün sinif və qruplarım: hər biri yeni səhifədən, imza bloku hər birinin sonunda. */
  const printAll = async () => {
    const list = lessons || []
    const w = printLater()
    if (!w) return
    try {
      const bodies: string[] = []
      for (const [i, l] of list.entries()) {
        setBatch(`${i + 1} / ${list.length}: ${l.class_name}`)
        const x = await loadExtra(l.id, sem)
        bodies.push((i ? '<div class="pb"></div>' : '') + taBody(x, parts, sem, teacher) + signs([SIGN.teacher(teacher), SIGN.deputy()]))
      }
      w.show({ title: `Bütün sinif və qruplarım – ${semLabel(sem)}`, body: bodies.join(''), internal: on.risk, landscape })
    } catch (e) { w.fail((e as Error).message) } finally { setBatch(null) }
  }
  return (
    <>
      <section className="panel no-print" style={{ marginBottom: 12 }}>
        <h2>{t('Sənədə daxil olsun')}</h2>
        <div className="print-parts">{PARTS.map(([k, l]) => (
          <label key={k} className="check"><input type="checkbox" checked={on[k]} onChange={e => setOn({ ...on, [k]: e.target.checked })} />{t(l)}</label>))}</div>
        {on.risk && <p className="small" style={{ color: 'var(--warn)', margin: '6px 0 0' }}>{t('Risk göstəricisi daxili istifadə üçündür – sənədin üstündə «Daxili istifadə üçün» yazılacaq.')}</p>}
        {landscape && <p className="small muted" style={{ margin: '6px 0 0' }}>{t('Davamiyyət xəritəsi seçildiyi üçün sənəd albom (yatıq) A4 olacaq.')}</p>}
        <div className="row" style={{ marginTop: 12 }}>
          <button className="btn primary" disabled={!doc || !parts.length} onClick={() => doc && printDoc(doc)}>{t('Çap / PDF')}</button>
          <button className="btn" disabled={!doc || !parts.length} onClick={() => doc && downloadPdf(doc).catch(e => toast((e as Error).message))}>{t('PDF yüklə')}</button>
          <a className="btn" href={`/api/reports/${ta}/xlsx${sem === 'all' ? '' : '?semester=' + sem}`}>{t('Excel')}</a>
          <button className="btn" disabled={!parts.length || !!batch || !lessons?.length} onClick={printAll}>
            {batch ? t('Hazırlanır… {batch}', { batch }) : t('Bütün sinif və qruplarım ({x1})', { x1: lessons?.length ?? 0 })}</button>
        </div>
        <p className="small muted" style={{ margin: '8px 0 0' }}>{t('A4, ağ-qara · altbilgidə tarix və səhifə nömrəsi · «Bütün sinif və qruplarım» – seçilən bölmələr hər sinif və qrup üçün yeni səhifədən.')}</p>
      </section>
      {busy && !doc ? <Loading /> : doc && (
        <div className="paper-wrap"><iframe className={'pframe' + (narrow ? ' sm' : '') + (landscape ? ' land' : '')} title={t('Önbaxış')} srcDoc={docHtml(doc)} /></div>)}
    </>
  )
}

const NOTE = (t: string) => `<p class="note">${esc(t)}</p>`
const ATT_CELL: Record<string, string> = { var: '', yox: 'q', 'üzrlü': 'ü', gecikdi: 'g' }
const SECTIONS: Record<Part, (a: any, x: Extra) => string> = {
  performance: (_a, x) => {
    const p = x.perf, m = p.summary
    return `<h2>Müvəffəqiyyət</h2>` + kpis([[m.students, 'şagird'], [`${m.graded}`, 'qiymətləndirilib'], [fmtN(m.success_pct) + '%', 'müvəffəqiyyət'],
      [fmtN(m.quality_pct) + '%', 'keyfiyyət'], [fmtN(m.avg, 2), 'orta qiymət'], [fmtN(m.sou) + '%', 'təlim səviyyəsi (SOU)']]) +
      table(['«5»', '«4»', '«3»', '«2»', 'Qiymətləndirilməyib', 'O cümlədən az qiymət'], [[m.distribution[5], m.distribution[4], m.distribution[3], m.distribution[2], m.not_graded, m.few_marks || 0]], [0, 1, 2, 3, 4, 5]) +
      '<br>' + table(['№', 'Şagird', 'Qiymət', 'Mənbə', 'Formativ orta', 'Qiymət sayı', 'Yarımil'],
        p.students.map((r: any, i: number) => [i + 1, r.full_name, r.grade ?? '—', r.source || 'qiymət yoxdur', fmtN(r.formative_avg, 2), r.marks, r.semester_grade ?? '—']), [2, 4, 5, 6]) +
      NOTE(`Qiymət: yarımil qiyməti (KSQ×0,4 + BSQ×0,6) varsa o, yoxdursa formativ qiymətlərin ortası (ən azı ${m.min_marks} qiymət). Müvəffəqiyyət = «2» almayanlar / qiymətləndirilənlər; keyfiyyət = «4» və «5» / qiymətləndirilənlər; SOU = (100·n5 + 64·n4 + 36·n3 + 16·n2) / n.`)
  },
  rating: a => `<h2>Reytinq</h2>` + table(['Yer', 'Şagird', 'Orta', 'KSQ %', 'Ev tap. %', 'Davam. %', 'Sınaq %', 'Reytinq', 'İrəliləyiş', 'Səviyyə'],
    a.students.map((r: any) => [r.place ?? '', r.full_name, fmtN(r.avg_grade, 2), fmtN(r.ksq_avg_pct), fmtN(r.homework_pct),
      fmtN(r.attendance_pct) + (r.absence_warning ? ' *' : ''), fmtN(r.sinaq_pct), fmtN(r.rating), r.progress == null ? '—' : (r.progress > 0 ? '+' : '') + fmtN(r.progress), r.level || '']),
    [2, 3, 4, 5, 6, 7, 8]) + NOTE('Reytinq: qiymət 40% · KSQ 30% · ev tapşırığı 15% · davamiyyət 15%; sınaq reytinqə daxil deyil. * – dərslərin 25%-dən çoxunu buraxıb.'),
  lessons: (_a, x) => {
    const l = x.lessons, rows = [['I yarımil', l.semesters[0]], ['II yarımil', l.semesters[1]], ['Bütün il', l.year]] as [string, any][]
    return `<h2>Dərs sayı (${fmtD(l.today)} vəziyyəti)</h2>` + table(['Dövr', 'Həftədə', 'Planda', 'Cədvəldə', 'Keçilməli idi', 'Yazılıb', 'Yazılmayıb', 'Keçilən mövzu', 'Qalan', 'Geriləmə'],
      rows.map(([n, v]) => [n, v.weekly_hours, v.plan_total, v.timetable_total, v.due, v.written, v.missing, v.covered, v.remaining, v.lag]), [1, 2, 3, 4, 5, 6, 7, 8, 9]) +
      (l.year.missing_list.length ? NOTE('Yazılmamış dərslər: ' + l.year.missing_list.map((m: any) => `${fmtD(m.date)} (${m.period}-ci saat)`).join(', ')) : '')
  },
  attendance: (_a, x) => `<h2>Davamiyyət</h2>` + table(['Şagird', 'Qeyd olunan dərs', 'Buraxıb', 'O cümlədən qayıb', 'Gecikmə', 'Buraxma %'],
    x.att.rows.map((r: any) => [r.full_name, r.cells.filter((c: any) => c).length, r.missed, r.unexcused, r.late, fmtN(r.missed_pct) + (r.warning ? ' *' : '')]), [1, 2, 3, 4, 5]) +
    NOTE(`* – ${x.att.limit_pct}%-dən çox buraxıb. Yalnız bu fənnin jurnalda yazılmış dərsləri.`),
  heatmap: (_a, x) => {
    const cols = x.att.columns as any[]
    if (!cols.length) return '<h2>Davamiyyət xəritəsi</h2>' + NOTE('Bu dövrdə yazılmış dərs yoxdur.')
    const per = 26                                          // albom A4-də bir cədvəldə ən çox 26 dərs sütunu
    const chunks = Array.from({ length: Math.ceil(cols.length / per) }, (_, i) => i * per)
    return chunks.map((from, ci) => `<h2>Davamiyyət xəritəsi${chunks.length > 1 ? ` (${ci + 1}/${chunks.length})` : ''}</h2>` +
      `<table class="heat-p"><thead><tr><th>Şagird</th>${cols.slice(from, from + per).map((c: any) => `<th>${esc(fmtD(c.date).slice(0, 5))}<br>${c.period}</th>`).join('')}<th>%</th></tr></thead><tbody>` +
      x.att.rows.map((r: any) => `<tr><td>${esc(r.full_name)}</td>${r.cells.slice(from, from + per).map((c: string | null) => `<td class="c">${c ? ATT_CELL[c] : '·'}</td>`).join('')}<td class="r">${esc(fmtN(r.missed_pct, 0))}${r.warning ? ' *' : ''}</td></tr>`).join('') +
      '</tbody></table>').join('') + NOTE('q – qayıb, ü – üzrlü, g – gecikmə, · – qeyd yoxdur; boş – var. Sütun: tarix və dərs saatı. * – 25%-dən çox buraxıb.')
  },
  levels: a => `<h2>Güclü / orta / zəif (analitika)</h2>` + table(['Səviyyə', 'Say', 'Şagirdlər'], ['Güclü', 'Orta', 'Zəif'].map(k => {
    const r = a.students.filter((s: any) => s.level === k)
    return [k, r.length, r.map((s: any) => s.full_name).join(', ')]
  }), [1]),
  groups: (_a, x) => {
    if (!x.lv) return '<h2>Səviyyə qrupları</h2>' + NOTE('Səviyyə qrupları yüklənmədi.')
    const L: Record<string, string> = { buraxilis: 'IX', sinaq: 'sınaq', reytinq: 'reytinq', diaqnostik: 'diaqn.' }
    const comps = (c: any) => (c ? Object.entries(c).filter(([, v]) => v != null).map(([k, v]) => `${L[k] || k} ${fmtN(v as number, 0)}`).join(' · ') : '')
    return '<h2>Səviyyə qrupları (bölgü)</h2>' + ['Güclü', 'Orta', 'Zəif', 'Təyin edilməyib'].filter(k => (x.lv.groups[k] || []).length).map(k =>
      `<h3 class="grp">${esc(k)} – ${x.lv.groups[k].length} şagird</h3>` + table(['№', 'Şagird', 'Bal', 'Komponentlər', 'Mənbə'],
        x.lv.groups[k].map((m: any, i: number) => [i + 1, m.full_name, fmtN(m.score), comps(m.components), m.source === 'manual' ? 'müəllim' + (m.locked ? ' (kilidli)' : '') : m.source ? 'bölgü' : '—']), [2])).join('') +
      NOTE('Bölgü balı: IX buraxılış balı, sınaq ortası, fənn reytinqi və diaqnostik test (olanlar); ≥ 70 – güclü, 40–69,9 – orta, < 40 – zəif. Müəllimin qərarı kilidlidir.')
  },
  risk: a => `<h2>Risk (daxili istifadə üçün)</h2>` + table(['Şagird', 'Status', 'Bal', 'Amillər'],
    [...a.students].filter((r: any) => r.risk.status !== 'Yaşıl').sort((x: any, y: any) => y.risk.score - x.risk.score)
      .map((r: any) => [r.full_name, r.risk.status, r.risk.score, r.risk.factors.filter((f: any) => f.bal).map((f: any) => f.izah).join('; ')]), [2]),
}