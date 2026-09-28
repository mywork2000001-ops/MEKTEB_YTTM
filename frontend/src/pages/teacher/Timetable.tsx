import { useState } from 'react'
import { get } from '../../api'
import { ErrorBox, fmtDate, isoDate, Loading, Pill, Top, useLoad } from '../../ui'

type Cell = { ta_id: number; class_name: string; time: string | null; topic: string | null; assessment_type: string | null; held: boolean }
type TT = { week_start: string; days: { date: string; weekday: string; periods: Record<string, Cell[]> }[] }

export default function Timetable() {
  const [date, setDate] = useState(isoDate(new Date()))
  const [d, err, loading] = useLoad<TT>(() => get('/api/timetable', { date }), [date])
  const shift = (n: number) => { const x = new Date(date + 'T00:00'); x.setDate(x.getDate() + 7 * n); setDate(isoDate(x)) }
  const periods = d ? Array.from(new Set(d.days.flatMap(x => Object.keys(x.periods).map(Number)))).sort((a, b) => a - b) : []
  const times = (p: number) => d?.days.flatMap(x => x.periods[p] || []).find(c => c.time)?.time
  return (
    <>
      <Top title="Həftəlik cədvəl" sub="Sütun – gün, sətir – dərs saatı; içində perspektiv plandan mövzu" />
      <div className="row no-print" style={{ marginBottom: 12 }}>
        <button className="btn sm" onClick={() => shift(-1)}>‹ Əvvəlki həftə</button>
        {d && <b>{fmtDate(d.days[0].date)} – {fmtDate(d.days[4].date)}</b>}
        <button className="btn sm" onClick={() => shift(1)}>Növbəti həftə ›</button>
        <button className="btn sm ghost" onClick={() => setDate(isoDate(new Date()))}>Bu həftə</button>
        <button className="btn sm right" onClick={() => window.print()}>Çap et</button>
      </div>
      <ErrorBox error={err} />
      {d && (
        <div className="only-phone stack">
          {d.days.map(x => {
            const cells = Object.entries(x.periods).flatMap(([p, cs]) => cs.map(c => ({ p: Number(p), ...c }))).sort((u, v) => (u.time || '').localeCompare(v.time || ''))
            const today = x.date === isoDate(new Date())
            return (
              <section key={x.date} className="panel" style={{ padding: 12, outline: today ? '2px solid var(--accent)' : undefined }}>
                <h2 style={{ marginBottom: 8 }}>{x.weekday} <small>{fmtDate(x.date)}{today ? ' · bu gün' : ''}</small></h2>
                {cells.length === 0 ? <p className="muted small" style={{ margin: 0 }}>Dərs yoxdur</p> : cells.map(c => (
                  <div key={c.ta_id + '-' + c.p} style={{ display: 'grid', gridTemplateColumns: '64px minmax(0,1fr)', gap: 8, padding: '8px 0', borderTop: '1px solid var(--line)' }}>
                    <span className="small"><b>{c.p}-ci</b><br /><span className="muted">{c.time?.split('–')[0]}</span></span>
                    <span style={{ minWidth: 0 }}><b className="ctag">{c.class_name}</b>{c.assessment_type && c.assessment_type !== 'formativ' && <> <Pill tone="warn">{c.assessment_type}</Pill></>}
                      <span className="small" style={{ display: 'block', overflowWrap: 'anywhere' }}>{c.topic || '—'}</span></span>
                  </div>))}
              </section>)
          })}
        </div>)}
      {loading && !d ? <Loading /> : d && (
        <div className="tbl-wrap only-desk">
          <table className="tt" style={{ minWidth: 760 }}>
            <thead><tr><th style={{ width: 80 }}>Saat</th>{d.days.map(x => <th key={x.date}>{x.weekday} {fmtDate(x.date).slice(0, 5)}</th>)}</tr></thead>
            <tbody>
              {periods.length === 0 && <tr><td colSpan={6} className="empty">Bu həftə dərs yoxdur.</td></tr>}
              {periods.map(p => (
                <tr key={p}>
                  <th className="small">{p}-ci<br /><span className="muted">{times(p)}</span></th>
                  {d.days.map(x => (
                    <td key={x.date} style={{ verticalAlign: 'top', fontSize: 13 }}>
                      {(x.periods[p] || []).map(c => (
                        <div key={c.ta_id} className="tint" style={{ borderRadius: 8, padding: '6px 8px', marginBottom: 4 }}>
                          <b className="ctag">{c.class_name}</b>
                          {c.assessment_type && c.assessment_type !== 'formativ' && <> <Pill tone="warn">{c.assessment_type}</Pill></>}
                          <div className="small">{c.topic || '—'}</div>
                          {c.time && c.time !== times(p) && <div className="small muted">{c.time}</div>}
                        </div>))}
                    </td>))}
                </tr>))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
