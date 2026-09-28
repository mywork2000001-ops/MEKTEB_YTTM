import { useState } from 'react'
import { get } from '../../api'
import { useAuth } from '../../auth'
import { ErrorBox, fmt, fmtDate, levelTone, Loading, PickFirst, Pill, riskTone, Seg, Stat, Top, useLoad } from '../../ui'
import { LessonSelect, useMyLessons, usePick } from './common'
import { useT } from '../../i18n'

const TABS = [['overview', 'İcmal'], ['rating', 'Reytinq'], ['levels', 'Güclü / orta / zəif'], ['risk', 'Risk'], ['attendance', 'Davamiyyət'], ['print', 'Çap / PDF']] as const

export default function Reports() {
  const t = useT()
  const [lessons, err0] = useMyLessons()
  const [ta, setTa] = usePick('reports')
  const [sem, setSem] = useState<'1' | '2' | 'all'>('1')
  const [tab, setTab] = useState<(typeof TABS)[number][0]>('overview')
  const params: Record<string, string> = sem === 'all' ? {} : { semester: sem }
  const [a, err, loading] = useLoad<any>(() => (ta ? get(`/api/analytics/${ta}`, params) : Promise.resolve(null)), [ta, sem])
  return (
    <>
      <Top title="Analitika və hesabat" sub={a ? `${a.class_name} · ${fmtDate(a.from)} – ${fmtDate(a.to)}` : 'Sinif seçin'} />
      <ErrorBox error={err0 || err} />
      <div className="toolbar no-print">
        <LessonSelect lessons={lessons} value={ta} onChange={setTa} />
        {ta && <Seg value={sem} onChange={setSem} options={[['1', 'I yarımil'], ['2', 'II yarımil'], ['all', 'Bütün il']]} />}
      </div>
      {!ta ? <PickFirst /> : loading && !a ? <Loading /> : a && (
        <>
          <div className="tabs no-print">{TABS.map(([k, l]) => <button key={k} aria-selected={tab === k} onClick={() => setTab(k)}>{t(l)}</button>)}</div>
          {tab === 'overview' && <Overview a={a} />}
          {tab === 'rating' && <Rating a={a} />}
          {tab === 'levels' && <Levels a={a} />}
          {tab === 'risk' && <Risk a={a} />}
          {tab === 'attendance' && <Attendance ta={ta} params={params} />}
          {tab === 'print' && <PrintView a={a} ta={ta} sem={sem} />}
        </>
      )}
    </>
  )
}

function Overview({ a }: { a: any }) {
  const o = a.overview
  const total = [5, 4, 3, 2].reduce((s, g) => s + (o.distribution[g] || 0), 0) || 1
  return (
    <div className="grid g2">
      <section className="panel"><h2>Göstəricilər</h2>
        <div className="kpis">
          <Stat value={o.students} label="şagird" /><Stat value={fmt(o.avg_grade, 2)} label="orta qiymət" /><Stat value={a.lessons_written} label="yazılmış dərs" />
          <Stat value={fmt(o.avg_attendance) + '%'} label="davamiyyət" /><Stat value={fmt(o.avg_homework) + '%'} label="ev tapşırığı" /><Stat value={fmt(o.avg_ksq_pct) + '%'} label="KSQ orta" />
        </div></section>
      <section className="panel"><h2>Qiymətlərin paylanması</h2>
        <div className="bar" style={{ height: 14 }}>{[5, 4, 3, 2].map(g => <i key={g} style={{ width: (o.distribution[g] || 0) * 100 / total + '%', background: `var(--${g === 5 ? 'ok' : g === 4 ? 'info' : g === 3 ? 'warn' : 'bad'})` }} />)}</div>
        <div className="legend" style={{ marginTop: 8 }}>{[5, 4, 3, 2].map(g => <span key={g}>«{g}» – {o.distribution[g] || 0}</span>)}</div>
        <h2 style={{ marginTop: 16 }}>Səviyyələr və risk</h2>
        <div className="row">{Object.entries(o.levels).map(([k, v]) => <Pill key={k} tone={levelTone(k)}>{k}: {v as number}</Pill>)}</div>
        <div className="row" style={{ marginTop: 8 }}>{Object.entries(o.risk).map(([k, v]) => <Pill key={k} tone={riskTone(k)}>{k}: {v as number}</Pill>)}
          {o.absence_warnings > 0 && <Pill tone="warn">25%+ buraxma: {o.absence_warnings}</Pill>}</div>
      </section>
    </div>
  )
}

function Rating({ a }: { a: any }) {
  const [mode, setMode] = useState<'total' | 'progress'>('total')
  const rows = [...a.students].sort((x: any, y: any) => mode === 'total'
    ? (x.place ?? 999) - (y.place ?? 999) : (x.progress_place ?? 999) - (y.progress_place ?? 999))
  return (
    <>
      <div className="row" style={{ marginBottom: 12 }}><Seg value={mode} onChange={setMode} options={[['total', 'Ümumi'], ['progress', 'İrəliləyiş']]} />
        <span className="small muted">Reytinq: qiymət 40% · KSQ 30% · ev tapşırığı 15% · davamiyyət 15%</span></div>
      <div className="tbl-wrap"><table><thead><tr><th>Yer</th><th>Şagird</th><th className="r">Reytinq</th><th className="r">İrəliləyiş</th><th className="r">Orta</th><th className="r">KSQ %</th><th className="r">Davamiyyət</th></tr></thead>
        <tbody>{rows.map((r: any) => (
          <tr key={r.student_id}><td className="num">{(mode === 'total' ? r.place : r.progress_place) ?? '—'}</td><td>{r.full_name}</td>
            <td className="r num"><b>{fmt(r.rating)}</b></td>
            <td className="r num" style={{ color: r.progress > 0 ? 'var(--ok)' : r.progress < 0 ? 'var(--bad)' : undefined }}>{r.progress == null ? '—' : (r.progress > 0 ? '▲ ' : r.progress < 0 ? '▼ ' : '') + fmt(Math.abs(r.progress))}</td>
            <td className="r num">{fmt(r.avg_grade, 2)}</td><td className="r num">{fmt(r.ksq_avg_pct)}</td><td className="r num">{fmt(r.attendance_pct)}%</td></tr>))}</tbody></table></div>
    </>
  )
}

function Levels({ a }: { a: any }) {
  return (
    <div className="grid g3">
      {['Güclü', 'Orta', 'Zəif'].map(k => {
        const rows = a.students.filter((r: any) => r.level === k)
        return (
          <section key={k} className="panel"><h2><Pill tone={levelTone(k)}>{k}</Pill><small>{rows.length}</small></h2>
            <ol style={{ margin: 0, paddingLeft: 18 }}>{rows.map((r: any) => <li key={r.student_id}>{r.full_name} <span className="small muted">{r.rating != null ? fmt(r.rating) : 'IX: ' + fmt(r.ix_math)}{r.baseline_level && r.baseline_level !== k ? ` (əvvəl: ${r.baseline_level})` : ''}</span></li>)}</ol>
          </section>)
      })}
      <p className="small muted" style={{ gridColumn: '1/-1' }}>Səviyyə nəticələrə görə avtomatik dəyişir (reytinq ≥ 70 – güclü, 40–70 – orta, &lt; 40 – zəif); nəticə yoxdursa IX sinif riyaziyyat balı götürülür.</p>
    </div>
  )
}

function Risk({ a }: { a: any }) {
  const rows = [...a.students].sort((x: any, y: any) => y.risk.score - x.risk.score)
  return (
    <div className="jlist">{rows.map((r: any) => (
      <details key={r.student_id} className="jrow" style={{ display: 'block' }}>
        <summary className="row" style={{ cursor: 'pointer' }}><b className="grow">{r.full_name}</b><Pill tone={riskTone(r.risk.status)}>{r.risk.status} · {r.risk.score}</Pill></summary>
        <ul className="small" style={{ margin: '8px 0 0' }}>{r.risk.factors.map((f: any) => <li key={f.amil}>{f.izah} {f.bal ? <b>(+{f.bal})</b> : ''}</li>)}</ul>
      </details>))}</div>
  )
}

function Attendance({ ta, params }: { ta: number; params: Record<string, string> }) {
  const [m, err] = useLoad<any>(() => get(`/api/analytics/${ta}/attendance`, params), [ta, JSON.stringify(params)])
  const cls: Record<string, string> = { var: 'var', yox: 'yox', 'üzrlü': 'uzrlu', gecikdi: 'gecikdi' }
  return (
    <>
      <ErrorBox error={err} />
      {m && (
        <>
          <div className="legend" style={{ marginBottom: 8 }}><span><i className="c var" style={{ width: 12, height: 12, display: 'inline-block', borderRadius: 3, background: 'var(--ok-soft)' }} /> var</span><span style={{ color: 'var(--bad)' }}>■ yox</span><span style={{ color: 'var(--warn)' }}>■ üzrlü</span><span style={{ color: 'var(--info)' }}>■ gecikdi</span><span>Hədd: {m.limit_pct}%</span></div>
          <div className="tbl-wrap"><table className="heat" style={{ minWidth: 0 }}>
            <thead><tr><th>Şagird</th><th className="r">Buraxıb</th>{m.columns.map((c: any, i: number) => <th key={i} title={`${fmtDate(c.date)} · ${c.period}-ci saat`}>{fmtDate(c.date).slice(0, 5)}</th>)}</tr></thead>
            <tbody>{m.rows.map((r: any) => (
              <tr key={r.student_id}><td style={{ textAlign: 'left', whiteSpace: 'nowrap' }}>{r.full_name}</td>
                <td className="r">{r.warning ? <Pill tone="bad">{fmt(r.missed_pct, 0)}%</Pill> : `${fmt(r.missed_pct, 0)}%`}</td>
                {r.cells.map((c: string | null, i: number) => <td key={i}><span className={'c ' + (c ? cls[c] : '')} title={c || 'qeyd yoxdur'} /></td>)}</tr>))}</tbody>
          </table></div>
        </>)}
    </>
  )
}

function PrintView({ a, ta, sem }: { a: any; ta: number; sem: string }) {
  const { me } = useAuth()
  return (
    <>
      <div className="row no-print" style={{ marginBottom: 12 }}>
        <button className="btn primary" onClick={() => window.print()}>Çap et / PDF kimi saxla</button>
        <a className="btn" href={`/api/reports/${ta}/xlsx${sem === 'all' ? '' : '?semester=' + sem}`}>Excel</a>
        <span className="small muted">A4 portret, ağ-qara (Canon üçün)</span>
      </div>
      <div className="paper" style={{ background: '#fff', color: '#000', padding: '12mm', maxWidth: '210mm', fontFamily: 'Times New Roman, serif' }}>
        <p style={{ textAlign: 'center', margin: 0, fontWeight: 700 }}>Tərtər şəhər Rafiq Nuriyev adına 6 nömrəli tam orta ümumtəhsil məktəbi</p>
        <p style={{ textAlign: 'center', margin: '4px 0 12px' }}>{a.class_name} sinfi – {a.subject} fənni üzrə hesabat ({fmtDate(a.from)} – {fmtDate(a.to)})</p>
        <table style={{ minWidth: 0, width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead><tr>{['Yer', 'Şagird', 'Orta', 'KSQ %', 'Ev tap. %', 'Davam. %', 'Reytinq', 'Səviyyə'].map(h => <th key={h} style={{ border: '1px solid #000', background: '#D9D9D9', color: '#000', padding: 4 }}>{h}</th>)}</tr></thead>
          <tbody>{a.students.map((r: any) => (
            <tr key={r.student_id}>{[r.place ?? '', r.full_name, fmt(r.avg_grade, 2), fmt(r.ksq_avg_pct), fmt(r.homework_pct), fmt(r.attendance_pct), fmt(r.rating), r.level || ''].map((v, i) =>
              <td key={i} style={{ border: '1px solid #000', padding: 4, fontWeight: i === 5 && r.absence_warning ? 700 : 400 }}>{v}</td>)}</tr>))}</tbody>
        </table>
        <p style={{ marginTop: 16, fontSize: 12 }}>Orta qiymət: {fmt(a.overview.avg_grade, 2)} · Davamiyyət: {fmt(a.overview.avg_attendance)}% · Güclü/orta/zəif: {a.overview.levels['Güclü']}/{a.overview.levels['Orta']}/{a.overview.levels['Zəif']}</p>
        <p style={{ marginTop: 24, fontSize: 12 }}>Müəllim: {me?.full_name} ____________</p>
      </div>
    </>
  )
}
