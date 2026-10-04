// Jurnal çap mərkəzi: seçilən bölmələr bir sənəddə (jurnal kitabçası) – gündəlik dərs vərəqi, jurnal səhifələri (ay / yarımil / il),
// keçilən mövzular və ev tapşırıqları, yarımil qiymətləri, mövzu icrası, xülasə. Bir sinif/qrup və ya bütün sinif və qruplarım.
import { useState } from 'react'
import { get } from '../../api'
import { useAuth } from '../../auth'
import { AsyncBtn, Drawer, Seg, ord } from '../../ui'
import { esc, fmtD, fmtN, head, kpis, printLater, SIGN, signs, table } from '../../print'
import type { MyLesson } from './common'

type Part = 'day' | 'grid' | 'topics' | 'semester' | 'progress' | 'summary'
type Period = 'month' | 'sem1' | 'sem2' | 'year'
const PARTS: [Part, string][] = [['day', 'Gündəlik dərs vərəqi (seçilmiş gün)'], ['grid', 'Jurnal səhifələri (şagird × dərs, albom)'],
  ['topics', 'Keçilən mövzular və ev tapşırıqları'], ['semester', 'Yarımil qiymətləri (KSQ, BSQ)'], ['progress', 'Mövzu icrası (plana nisbətən)'],
  ['summary', 'Xülasə (orta qiymət, davamiyyət, ev tapşırığı)']]
const MN = ['Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'İyun', 'İyul', 'Avqust', 'Sentyabr', 'Oktyabr', 'Noyabr', 'Dekabr']
const ATT: Record<string, string> = { var: 'var', yox: 'q', 'üzrlü': 'ü', gecikdi: 'g' }
const PER_TABLE = 22                                  // albom A4-də bir cədvəldə ən çox dərs sütunu
const NOTE = (t: string) => `<p class="note">${esc(t)}</p>`

function months(a: string, b: string): string[] {
  const out: string[] = []
  let [y, m] = a.slice(0, 7).split('-').map(Number)
  const [y2, m2] = b.slice(0, 7).split('-').map(Number)
  while (y < y2 || (y === y2 && m <= m2)) { out.push(`${y}-${String(m).padStart(2, '0')}`); m++; if (m > 12) { m = 1; y++ } }
  return out
}
const monthName = (ym: string) => `${MN[Number(ym.slice(5)) - 1]} ${ym.slice(0, 4)}`

export default function JournalPrint({ ta, all, date, onClose }: { ta: MyLesson; all: MyLesson[]; date: string; onClose: () => void }) {
  const { me } = useAuth()
  const [on, setOn] = useState<Record<Part, boolean>>({ day: false, grid: true, topics: true, semester: true, progress: false, summary: true })
  const [period, setPeriod] = useState<Period>(() => (ta.semester === 2 ? 'sem2' : 'sem1'))
  const [blank, setBlank] = useState(false)
  const [scope, setScope] = useState<'one' | 'all'>('one')
  const [busy, setBusy] = useState('')
  const parts = PARTS.filter(([k]) => on[k]).map(([k]) => k)
  const teacher = me?.full_name || ''

  async function body(l: MyLesson): Promise<string> {
    const lc = await get<any>(`/api/analytics/${l.id}/lessons`)
    const [s1, s2] = lc.semesters
    const range = period === 'month' ? [date.slice(0, 7) + '-01', date] : period === 'sem1' ? [s1.from, s1.to] : period === 'sem2' ? [s2.from, s2.to] : [s1.from, s2.to]
    const ms = period === 'month' ? [date.slice(0, 7)] : months(range[0], range[1])
    const sems = period === 'year' ? [1, 2] : period === 'sem2' ? [2] : period === 'sem1' ? [1] : [Number(l.semester || 1)]
    const perLabel = period === 'month' ? monthName(date.slice(0, 7)) : period === 'year' ? 'tədris ili' : `${sems[0]}-ci yarımil`
    const kind = l.kind === 'qrup' ? ' · qrup' + (l.split_with ? ` (bölünür: ${l.split_with})` : '') : ''
    let html = head(`${l.class_name}${l.kind === 'qrup' ? '' : ' sinfi'} – ${l.subject}: jurnal`, `${perLabel} · müəllim: ${teacher}${kind}`)
    const grids = (on.grid || on.topics) ? await Promise.all(ms.map(m => get<any>(`/api/journal/${l.id}/grid`, { month: m }))) : []
    let started = false                          // ilk cədvəl başlıqla eyni səhifədə qalsın
    for (const k of parts) {
      if (k !== parts[0]) started = true
      if (k === 'day') {
        const d = await get<any>(`/api/journal/${l.id}/day`, { date })
        html += `<h2>Gündəlik dərs vərəqi – ${fmtD(date)}</h2>`
        if (!d.lessons.length) { html += NOTE('Bu gün dərs yoxdur (cədvəl, bayram və ya tətil).'); continue }
        for (const ls of d.lessons) {
          const e = ls.entry, empty = blank || !e.exists || e.auto
          const mk = (sid: number) => (e.marks || []).filter((m: any) => m.student_id === sid)
            .map((m: any) => m.kind === 'test' ? `${m.test_correct}/${m.test_total} → ${m.grade}` : `${m.grade} (${m.kind})`).join('; ')
          html += `<h3>${ord(ls.period)} saat${ls.time ? ` · ${esc(ls.time)}` : ''} – ${esc(ls.plan?.topic || e.topic || '—')}</h3>` +
            `<p class="note">Ev tapşırığı: ${esc((empty ? '' : e.homework) || '________________________________')}${ls.homework_to_check ? ` · yoxlanılacaq: ${esc(ls.homework_to_check)}` : ''}</p>` +
            table(['№', 'Şagird', 'Davamiyyət', 'Qiymət', 'Ev tapşırığı', 'Qeyd'], d.students.map((s: any, i: number) => [i + 1, s.full_name,
              empty ? '' : ATT[e.attendance?.[s.id]] || '', empty ? '' : mk(s.id), empty ? '' : e.homework_checks?.[s.id] || '', '']))
        }
        html += NOTE('Davamiyyət: var, q – qayıb, ü – üzrlü, g – gecikmə. ' + (blank ? 'Boş vərəq – əl ilə doldurmaq üçün.' : ''))
      }
      if (k === 'grid') {
        grids.forEach((g, gi) => {
          if (!g.columns.length) return
          for (let from = 0; from < g.columns.length; from += PER_TABLE) {
            const cols = g.columns.slice(from, from + PER_TABLE), last = from + PER_TABLE >= g.columns.length
            if (from || gi) started = true
            html += `${started ? '<div class="pb"></div>' : ''}<h2>Jurnal səhifəsi – ${monthName(ms[gi])}${g.columns.length > PER_TABLE ? ` (${from / PER_TABLE + 1})` : ''}</h2>` +
              table(['№', 'Şagird', ...cols.map((c: any) => (c.sinaq ? 'Sınaq ' : c.assessment ? c.assessment + ' ' : '') + fmtD(c.date).slice(0, 5)), ...(last ? ['Orta', 'Buraxıb'] : [])],
                g.rows.map((r: any, i: number) => [i + 1, r.full_name, ...r.cells.slice(from, from + PER_TABLE).map((c: any) =>
                  [...c.marks, c.att, c.exam && c.exam.split(': ')[1], c.sinaq].filter(Boolean).join(' ')), ...(last ? [fmtN(r.avg, 2), r.missed || ''] : [])]))
                .replace('<table>', '<table class="jg">')
          }
        })
        html += NOTE('q – qayıb, ü – üzrlü, g – gecikmə; KSQ/BSQ qiyməti həmin günün sütunundadır; «Sınaq» – sınaq imtahanının faizi (formativ ortaya daxil deyil). «Orta» və «Buraxıb» – ay üzrə.')
      }
      if (k === 'topics') {
        const rows = grids.flatMap(g => g.columns.filter((c: any) => c.written).map((c: any) => [fmtD(c.date), c.period, c.seq ?? '', (c.assessment ? c.assessment + ' · ' : '') + (c.topic || ''), c.homework || '']))
        html += '<h2>Keçilən mövzular və ev tapşırıqları</h2>' + (rows.length ? table(['Tarix', 'Saat', '№', 'Mövzu', 'Ev tapşırığı'], rows, [1, 2]) : NOTE('Bu dövrdə yazılmış dərs yoxdur.'))
      }
      if (k === 'semester') {
        if (!l.has_summative) { html += '<h2>Yarımil qiymətləri</h2>' + NOTE('Bu qrupda KSQ/BSQ keçirilmir – bütöv sinifdə keçirilir.'); continue }
        for (const s of sems) {
          const d = await get<any>(`/api/exams/${l.id}/semester/${s}`)
          html += `<h2>${s}-ci yarımil qiymətləri</h2>` + table(['№', 'Şagird', 'KSQ', 'KSQ orta', 'BSQ', 'Yarımil', ...(d.exams ? ['Sınaq orta %'] : [])],
            d.students.map((x: any, i: number) => [i + 1, x.full_name, x.ksq.map(([n, g]: [number, number | null]) => `${n}: ${g ?? '—'}`).join('  '),
              fmtN(x.ksq_avg, 2), x.bsq ?? '—', x.semester_grade ?? '—', ...(d.exams ? [fmtN(x.exam_pct)] : [])]), [3, 4, 5]) + NOTE(d.formula || '')
        }
      }
      if (k === 'progress') {
        const p = await get<any>(`/api/plan/${l.id}/progress`), s = p.summary
        const tps = p.topics.filter((t: any) => sems.includes(t.semester))
        html += '<h2>Mövzu icrası</h2>' + kpis([[`${s.done}/${s.total}`, 'keçilib'], [s.expected, 'bu günə qədər keçilməli'], [(s.delta > 0 ? '+' : '') + s.delta, 'fərq (dərs)'],
          [s.overdue, 'gecikir'], [p.forecast.shortfall, 'ilə sığmır']]) +
          table(['№', 'Mövzu', 'Rəsmi tarix', 'Status', 'Keçildi', 'Gecikmə (gün)'], tps.map((t: any) => [t.seq, (t.assessment_type !== 'formativ' ? t.assessment_type + ' · ' : '') + t.topic,
            fmtD(t.official_date), t.status, t.done_on ? fmtD(t.done_on) : '', t.delay_days ?? '']), [0, 5])
      }
      if (k === 'summary') {
        for (const s of (period === 'year' ? ['all'] : sems.map(String))) {
          const d = await get<any>(`/api/journal/${l.id}/summary`, s === 'all' ? {} : { semester: s })
          html += `<h2>Xülasə – ${s === 'all' ? 'tədris ili' : s + '-ci yarımil'}</h2>` + kpis([[d.lessons_written, 'yazılmış dərs'], [d.students.length, 'şagird']]) +
            table(['№', 'Şagird', 'Orta qiymət', 'Qiymət sayı', 'Test %', 'Davamiyyət %', 'Ev tapşırığı %', ...(d.exams ? ['Sınaq orta %'] : [])],
              d.students.map((x: any, i: number) => [i + 1, x.full_name, fmtN(x.avg_grade, 2), x.marks, fmtN(x.test_pct), fmtN(x.attendance_pct), fmtN(x.homework_pct),
                ...(d.exams ? [fmtN(x.exam_pct)] : [])]), [2, 3, 4, 5, 6, 7])
        }
      }
    }
    return html + signs([SIGN.teacher(teacher), SIGN.deputy()])
  }

  const run = async () => {
    const list = scope === 'all' ? all : [ta]
    const w = printLater()
    if (!w) return
    try {
      const out: string[] = []
      for (const [i, l] of list.entries()) {
        setBusy(`${i + 1} / ${list.length}: ${l.class_name}`)
        out.push((i ? '<div class="pb"></div>' : '') + await body(l))
      }
      w.show({ title: `Jurnal – ${scope === 'all' ? 'bütün sinif və qruplarım' : ta.class_name}`, body: out.join(''),
        landscape: on.grid })
    } catch (e) { w.fail((e as Error).message) } finally { setBusy('') }
  }

  return (
    <Drawer title={`Jurnal çapı – ${ta.class_name}`} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Bağla</button>
        <AsyncBtn className="btn primary" disabled={!parts.length || !!busy} onClick={run}>{busy ? `Hazırlanır… ${busy}` : 'Çap / PDF'}</AsyncBtn></>}>
      <div className="stack">
        <fieldset style={{ margin: 0 }}><legend>Sənədə daxil olsun</legend>
          {PARTS.map(([k, l]) => <label key={k} className="check"><input type="checkbox" checked={on[k]} onChange={e => setOn({ ...on, [k]: e.target.checked })} />{l}</label>)}
          {on.day && <label className="check" style={{ paddingLeft: 26 }}><input type="checkbox" checked={blank} onChange={e => setBlank(e.target.checked)} />boş vərəq (kağızda doldurmaq üçün – internet olmayanda)</label>}
        </fieldset>
        <div className="stack" style={{ gap: 5 }}><span className="small muted">Dövr (gündəlik vərəq – {fmtD(date)}, jurnalın «Gündəlik» tarixi)</span>
          <Seg value={period} onChange={setPeriod} options={[['month', 'Bu ay'], ['sem1', 'I yarımil'], ['sem2', 'II yarımil'], ['year', 'Bütün il']]} /></div>
        <div className="stack" style={{ gap: 5 }}><span className="small muted">Nəyi çap edək</span>
          <Seg value={scope} onChange={setScope} options={[['one', `Yalnız ${ta.class_name}`], ['all', `Bütün sinif və qruplarım (${all.length})`]]} /></div>
        <p className="small muted">{on.grid ? 'Jurnal səhifələri seçildiyi üçün sənəd albom (yatıq) A4 olacaq; hər ay yeni səhifədən, çox dərs olanda cədvəl hissələrə bölünür. ' : ''}
          A4, ağ-qara · altbilgidə tarix və səhifə nömrəsi · sonda fənn müəllimi və direktor müavininin imza yeri.</p>
      </div>
    </Drawer>
  )
}
