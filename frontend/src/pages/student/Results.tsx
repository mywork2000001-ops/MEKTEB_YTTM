import { get } from '../../api'
import { useT } from '../../i18n'
import { ErrorBox, fmt, fmtDate, gradeTone, Loading, Pill, Stat, Top, useLoad } from '../../ui'
import { MathText } from '../../MathText'

const ml = (x: any) => (x ? (typeof x === 'string' ? x : x.az || x.ru || x.en || '') : '')

export default function Results() {
  const t = useT()
  const [d, err] = useLoad<any>(() => get('/api/portal/results'), [])
  if (!d) return err ? <ErrorBox error={err} /> : <Loading />
  return (
    <>
      <Top title={t('Nəticələrim')} />
      {d.badges.length > 0 && (
        <section className="panel" style={{ marginBottom: 16 }}><h2>{t('Nailiyyətlər')}</h2>
          <div className="row">{d.badges.map((b: any) => <Pill key={b.key} tone="acc">★ {b.title} – {b.text}</Pill>)}</div></section>)}
      {d.subjects.map((s: any, i: number) => (
        <section key={i} className="panel" style={{ marginBottom: 16 }}>
          <h2>{s.subject} <small>{s.class_name} · {s.teacher}</small></h2>
          <div className="kpis" style={{ marginBottom: 12 }}>
            <Stat value={fmt(s.avg_grade, 2)} label="orta qiymət" /><Stat value={fmt(s.attendance_pct) + '%'} label="davamiyyət" /><Stat value={fmt(s.homework_pct) + '%'} label="ev tapşırığı" />
          </div>
          <div className="row" style={{ marginBottom: 8 }}>
            {[1, 2].map(k => <Pill key={k} tone={gradeTone(s.semester_grades[k])}>{k}-ci yarımil: {s.semester_grades[k] ?? '—'}</Pill>)}
            <span className="small muted">= (KSQ ortası) × 0,4 + BSQ × 0,6</span>
          </div>
          {s.exams.length > 0 && (
            <div className="tbl-wrap"><table style={{ minWidth: 0 }}><thead><tr><th>İmtahan</th><th>Tarix</th><th className="r">Bal</th><th className="r">%</th><th className="r">Qiymət</th></tr></thead>
              <tbody>{s.exams.map((e: any, j: number) => (
                <tr key={j}><td>{e.kind}-{e.no} <span className="small muted">({e.semester}-ci yarımil)</span></td><td>{fmtDate(e.date)}</td>
                  <td className="r num">{e.absent ? 'yox idi' : e.points != null ? `${fmt(e.points, 1)} / ${e.max_points}` : '—'}</td><td className="r num">{fmt(e.pct)}</td>
                  <td className="r">{e.grade ? <Pill tone={gradeTone(e.grade)}>{e.grade}</Pill> : '—'}</td></tr>))}</tbody></table></div>)}
        </section>))}
      <section className="panel" style={{ marginBottom: 16 }}>
        <h2>Onlayn tapşırıqlar <small>{d.tasks.length}</small></h2>
        {d.tasks.length === 0 ? <p className="muted">Hələ təhvil verilmiş tapşırıq yoxdur.</p> : d.tasks.map((x: any) => (
          <div key={x.id} className="row" style={{ justifyContent: 'space-between', borderBottom: '1px solid var(--line)', padding: '6px 0' }}>
            <span>{x.title}{x.auto_submitted && <span className="small muted"> · vaxt bitdi</span>}</span>
            <Pill tone={gradeTone(x.grade)}>{x.correct}/{x.total} · {fmt(x.pct, 0)}% → {x.grade}</Pill></div>))}
      </section>
      <section className="panel">
        <h2>{t('Səhvlərim')} <small>{d.mistakes.length}</small></h2>
        {d.mistakes.length === 0 ? <p className="muted">Səhv yoxdur və ya cavablar hələ açılmayıb.</p> : d.mistakes.map((m: any, k: number) => (
          <details key={k} style={{ borderBottom: '1px solid var(--line)', padding: '8px 0' }}>
            <summary style={{ cursor: 'pointer' }}><MathText text={ml(m.text)} /> <span className="small muted">· {m.task}</span></summary>
            {m.image && <img className="q-img" src={m.image} alt="" />}
            <p className="small">Sizin cavab: <b style={{ color: 'var(--bad)' }}>{m.kind === 'mcq' ? (m.given != null ? <MathText text={ml(m.options?.[m.given])} /> : '—') : m.given || '—'}</b> · Düzgün: <b style={{ color: 'var(--ok)' }}>{m.kind === 'mcq' ? <MathText text={ml(m.options?.[m.correct])} /> : String(m.answer).split('|')[0]}</b></p>
            {m.explanation && <p className="small muted" style={{ whiteSpace: 'pre-wrap' }}><MathText text={ml(m.explanation)} /></p>}
          </details>))}
      </section>
    </>
  )
}
