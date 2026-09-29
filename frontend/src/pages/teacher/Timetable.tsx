// Həftəlik dərs cədvəli – məktəb cədvəli üslubunda: sətir = real vaxt (08:00, 08:50, …), sütun = gün,
// nahar fasiləsi ayrıca sətir, boş saat «Sərbəst», hər sinfin sabit rəngi, içində perspektiv plandan mövzu.
import { useMemo, useState } from 'react'
import { get } from '../../api'
import { ErrorBox, fmtDate, isoDate, Loading, Pill, Top, useLoad } from '../../ui'
import { esc, head, printDoc } from '../../print'

type Cell = { ta_id: number; class_name: string; subject: string; time: string | null; topic: string | null; assessment_type: string | null; held: boolean }
type Day = { date: string; weekday: string; periods: Record<string, Cell[]> }
type TT = { week_start: string; days: Day[] }
type Row = { kind: 'lesson'; time: string; start: number } | { kind: 'break'; time: string; start: number }

const DAY_FULL: Record<string, string> = { 'B.e.': 'Bazar ertəsi', 'Ç.a.': 'Çərşənbə axşamı', 'Ç.': 'Çərşənbə', 'C.a.': 'Cümə axşamı', 'C.': 'Cümə' }
const PALETTE = ['#3558C9', '#2F7A5F', '#9B3552', '#B7791F', '#6A4FC0', '#1F7F86', '#C05621', '#4A5165']
const toMin = (t: string) => { const [h, m] = t.split(':').map(Number); return h * 60 + m }
const startOf = (t: string) => toMin(t.replace('–', '-').split('-')[0].trim())
const endOf = (t: string) => toMin(t.replace('–', '-').split('-')[1].trim())

export default function Timetable() {
  const [date, setDate] = useState(isoDate(new Date()))
  const [d, err, loading] = useLoad<TT>(() => get('/api/timetable', { date }), [date])
  const [school] = useLoad<any>(() => get('/api/school'), [])
  const shift = (n: number) => { const x = new Date(date + 'T00:00'); x.setDate(x.getDate() + 7 * n); setDate(isoDate(x)) }
  const todayIso = isoDate(new Date())

  const { rows, byTime, colors, totals } = useMemo(() => {
    const byTime = new Map<string, Map<string, (Cell & { p: number })[]>>()   // vaxt -> tarix -> dərslər
    const times = new Set<string>()
    const classes: string[] = []
    const totals = new Map<string, number>()
    for (const day of d?.days || []) {
      for (const [p, cells] of Object.entries(day.periods)) {
        for (const c of cells) {
          const t = c.time || `${p}-ci saat`
          times.add(t)
          if (!byTime.has(t)) byTime.set(t, new Map())
          const m = byTime.get(t)!
          m.set(day.date, [...(m.get(day.date) || []), { ...c, p: Number(p) }])
          if (!classes.includes(c.class_name)) classes.push(c.class_name)
          totals.set(c.class_name, (totals.get(c.class_name) || 0) + 1)
        }
      }
    }
    for (const b of Object.values<string>(school?.bells || {})) if (b && /\d:\d\d/.test(b)) times.add(b)
    const sorted = [...times].filter(t => /\d:\d\d/.test(t)).sort((a, b) => startOf(a) - startOf(b))
    const rows: Row[] = []
    sorted.forEach((t, i) => {
      if (i > 0) {
        const gap = startOf(t) - endOf(sorted[i - 1])
        if (gap >= 20) {
          const f = (x: number) => `${String(Math.floor(x / 60)).padStart(2, '0')}:${String(x % 60).padStart(2, '0')}`
          rows.push({ kind: 'break', time: `${f(endOf(sorted[i - 1]))}–${f(startOf(t))}`, start: endOf(sorted[i - 1]) })
        }
      }
      rows.push({ kind: 'lesson', time: t, start: startOf(t) })
    })
    classes.sort((a, b) => a.localeCompare(b, 'az'))
    const colors = Object.fromEntries(classes.map((c, i) => [c, PALETTE[i % PALETTE.length]]))
    return { rows, byTime, colors, totals }
  }, [d, school])

  const weekTotal = [...totals.values()].reduce((a, b) => a + b, 0)
  const CellBox = ({ c }: { c: Cell & { p: number } }) => (
    <div className="ttc" style={{ ['--cc' as any]: colors[c.class_name] }}>
      <div className="ttc-h"><b>{c.class_name}</b><span>{c.p}-ci saat</span></div>
      {c.subject !== 'Riyaziyyat' && <div className="small">{c.subject}</div>}
      <div className="ttc-t">{c.topic || <span className="muted">plan yüklənməyib</span>}</div>
      {(c.assessment_type === 'KSQ' || c.assessment_type === 'BSQ' || c.held) && (
        <div className="row" style={{ gap: 4, marginTop: 4 }}>
          {(c.assessment_type === 'KSQ' || c.assessment_type === 'BSQ') && <Pill tone="warn">{c.assessment_type}</Pill>}
          {c.held && <Pill tone="info">mövzu saxlanılıb</Pill>}
        </div>)}
    </div>
  )

  return (
    <>
      <Top title="Həftəlik dərs cədvəli" sub={d ? `${fmtDate(d.days[0].date)} – ${fmtDate(d.days[4].date)} · həftədə ${weekTotal} dərs` : 'Mövzular perspektiv plandan'} />
      <div className="row no-print" style={{ marginBottom: 12 }}>
        <button className="btn sm" onClick={() => shift(-1)}>‹ Əvvəlki</button>
        <button className="btn sm ghost" onClick={() => setDate(isoDate(new Date()))}>Bu həftə</button>
        <button className="btn sm" onClick={() => shift(1)}>Növbəti ›</button>
        <button className="btn sm right" disabled={!d} onClick={() => d && printDoc({ landscape: true, title: `Həftəlik dərs cədvəli ${fmtDate(d.days[0].date)}–${fmtDate(d.days[4].date)}`, body: head('Həftəlik dərs cədvəli', `${fmtDate(d.days[0].date)} – ${fmtDate(d.days[4].date)}`) + `<table><thead><tr><th>Vaxt</th>${d.days.map(x => `<th>${esc(DAY_FULL[x.weekday] || x.weekday)}<br>${fmtDate(x.date).slice(0, 5)}</th>`).join('')}</tr></thead><tbody>${rows.map(r => r.kind === 'break' ? `<tr><td class="c">${esc(r.time)}</td><td colspan="5" class="c b">Nahar fasiləsi</td></tr>` : `<tr><td class="c b">${esc(r.time)}</td>${d.days.map(x => { const cs = byTime.get(r.time)?.get(x.date) || []; return `<td>${cs.map(c => `<b>${esc(c.class_name)}</b> (${c.p}-ci)${c.assessment_type === 'KSQ' || c.assessment_type === 'BSQ' ? ' <b>' + c.assessment_type + '</b>' : ''}<br>${esc(c.topic || '')}`).join('<hr>') || '<span class="muted">—</span>'}</td>` }).join('')}</tr>`).join('')}</tbody></table>` })}>Çap / PDF</button>
      </div>
      <ErrorBox error={err} />
      {loading && !d ? <Loading /> : d && (
        <>
          <div className="legend" style={{ marginBottom: 10 }}>
            {Object.entries(colors).map(([c, col]) => <span key={c}><i style={{ width: 12, height: 12, borderRadius: 3, background: col, display: 'inline-block' }} /> {c} – {totals.get(c)} saat</span>)}
          </div>

          {/* noutbuk / planşet: cədvəl */}
          <div className="tbl-wrap only-desk">
            <table className="ttable">
              <thead><tr><th className="tt-time">Vaxt</th>{d.days.map(x => (
                <th key={x.date} className={x.date === todayIso ? 'today' : ''}>{DAY_FULL[x.weekday] || x.weekday}<span>{fmtDate(x.date).slice(0, 5)}</span></th>))}</tr></thead>
              <tbody>
                {rows.map(r => r.kind === 'break' ? (
                  <tr key={'b' + r.time} className="tt-break"><td className="tt-time">{r.time}</td><td colSpan={5}>Nahar fasiləsi</td></tr>
                ) : (
                  <tr key={r.time}>
                    <td className="tt-time">{r.time.replace('–', '\n')}</td>
                    {d.days.map(x => {
                      const cells = byTime.get(r.time)?.get(x.date) || []
                      return <td key={x.date} className={x.date === todayIso ? 'today' : ''}>{cells.length ? cells.map(c => <CellBox key={c.ta_id} c={c} />) : <span className="tt-free">Sərbəst</span>}</td>
                    })}
                  </tr>))}
              </tbody>
            </table>
          </div>

          {/* telefon: gün-gün */}
          <div className="only-phone stack">
            {d.days.map(x => {
              const list = rows.filter(r => r.kind === 'lesson').flatMap(r => (byTime.get(r.time)?.get(x.date) || []).map(c => ({ c, time: r.time })))
              const today = x.date === todayIso
              return (
                <section key={x.date} className="panel" style={{ padding: 12, outline: today ? '2px solid var(--accent)' : undefined }}>
                  <h2 style={{ marginBottom: 6 }}>{DAY_FULL[x.weekday] || x.weekday} <small>{fmtDate(x.date)}{today ? ' · bu gün' : ''} · {list.length} dərs</small></h2>
                  {list.length === 0 ? <p className="muted small" style={{ margin: 0 }}>Dərs yoxdur</p> : list.map(({ c, time }) => (
                    <div key={c.ta_id + time} className="tt-prow">
                      <span className="tt-ptime">{time.split('–')[0]}<small>{time.split('–')[1]}</small></span>
                      <CellBox c={c} />
                    </div>))}
                </section>)
            })}
          </div>
        </>
      )}
    </>
  )
}
