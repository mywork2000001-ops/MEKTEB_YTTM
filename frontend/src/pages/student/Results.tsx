import { useState } from 'react'
import { get } from '../../api'
import { useT } from '../../i18n'
import { ErrorBox, fmt, fmtDate, gradeTone, Loading, Pill, Stat, Top, useLoad } from '../../ui'
import { MathText } from '../../MathText'
import { useAuth } from '../../auth'
import { printMistakes, printResults } from './studentPrint'

const ml = (x: any) => (x ? (typeof x === 'string' ? x : x.az || x.ru || x.en || '') : '')

export default function Results() {
  const t = useT()
  const [d, err] = useLoad<any>(() => get('/api/portal/results'), [])
  const [ex] = useLoad<any>(() => get('/api/portal/exams'), [])
  const [allMistakes, setAllMistakes] = useState(false)
  const { me } = useAuth()
  if (!d) return err ? <ErrorBox error={err} /> : <Loading />
  return (
    <>
      <Top title={t('Nəticələrim')} actions={<span className="row no-print" style={{ gap: 6 }}>
        <button className="btn sm" onClick={() => printResults(d, ex, me, false)}>Çap / PDF</button>
        {d.mistakes.length > 0 && <button className="btn sm" onClick={() => printResults(d, ex, me, true)}>Səhvlərlə birlikdə</button>}</span>} />
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
                <tr key={j}><td>{e.kind}-{e.no} <span className="small muted">({e.semester}-ci yarımil)</span>
                  {e.items?.length > 0 && <div className="row" style={{ gap: 3, marginTop: 4 }}>{e.items.map((it: any) => <span key={it.n} className="small" title={it.standard ? 'standart ' + it.standard : ''} style={{ padding: '1px 5px', borderRadius: 4, background: it.ok ? 'var(--ok-soft)' : 'var(--bad-soft)', color: it.ok ? 'var(--ok)' : 'var(--bad)' }}>{it.n}{it.ok ? '✓' : '✗'}</span>)}</div>}
                  {e.weak_standards?.length > 0 && <div className="small" style={{ marginTop: 4 }}>Təkrarla – standart: <b>{e.weak_standards.join(', ')}</b></div>}</td>
                  <td>{fmtDate(e.date)}{e.taken_on && <div className="small muted">sonradan: {fmtDate(e.taken_on)}</div>}</td>
                  <td className="r num">{e.absent ? 'yox idi' : e.points != null ? `${fmt(e.points, 1)} / ${e.max_points}` : '—'}</td><td className="r num">{fmt(e.pct)}</td>
                  <td className="r">{e.grade ? <Pill tone={gradeTone(e.grade)}>{e.grade}</Pill> : '—'}</td></tr>))}</tbody></table></div>)}
        </section>))}
      {ex?.items?.length > 0 && (
        <section className="panel" style={{ marginBottom: 16 }}>
          <h2>Sınaq imtahanları <small>{ex.items.length}{ex.delta != null ? ` · son dinamika ${ex.delta > 0 ? '+' : ''}${fmt(ex.delta)}%` : ''}</small></h2>
          {ex.items.map((x: any) => (
            <div key={x.batch_id} style={{ borderBottom: '1px solid var(--line)', padding: '8px 0' }}>
              <div className="row"><b className="grow">{x.title}</b><span className="small muted">{fmtDate(x.opens_at)}</span></div>
              {!x.closed ? <span className="small muted">Nəticə və yer sınaq bağlandıqdan sonra görünəcək.</span>
                : x.status !== 'yazıb' ? <span className="small muted">Sınağı yazmamısan.</span> : (
                <div className="row" style={{ gap: 6, marginTop: 4 }}>
                  <Pill tone={x.pct >= 70 ? 'ok' : x.pct >= 40 ? 'warn' : 'bad'}>{fmt(x.pct)}% · {x.correct} düz, {x.wrong} səhv, {x.blank} boş</Pill>
                  <Pill tone="acc">sinifdə {x.place_class}/{x.class_count}</Pill>
                  <Pill tone="info">ümumi {x.place_all}/{x.all_count}</Pill>
                  <span className="small muted">orta {fmt(x.avg_pct)}% · ən yüksək {fmt(x.max_pct)}%</span>
                </div>)}
            </div>))}
        </section>)}
      <section className="panel" style={{ marginBottom: 16 }}>
        <h2>Onlayn tapşırıqlar <small>{d.tasks.length}</small></h2>
        {d.tasks.length === 0 ? <p className="muted">Hələ təhvil verilmiş tapşırıq yoxdur.</p> : d.tasks.map((x: any) => (
          <div key={x.id} className="row" style={{ justifyContent: 'space-between', borderBottom: '1px solid var(--line)', padding: '6px 0' }}>
            <span>{x.title}{x.auto_submitted && <span className="small muted"> · vaxt bitdi</span>}</span>
            <Pill tone={gradeTone(x.grade)}>{x.correct}/{x.total} · {fmt(x.pct, 0)}% → {x.grade}</Pill></div>))}
      </section>
      <section className="panel">
        <h2>{t('Səhvlərim')} <small>{d.mistakes.length}</small>{d.mistakes.length > 0 && <button className="btn sm right no-print" onClick={() => printMistakes(d, me, true)}>Səhv dəftəri – çap</button>}</h2>
        {d.mistakes.length === 0 ? <p className="muted">Səhv yoxdur və ya cavablar hələ açılmayıb.</p> : d.mistakes.slice(0, allMistakes ? undefined : 10).map((m: any, k: number) => (
          <details key={k} style={{ borderBottom: '1px solid var(--line)', padding: '8px 0' }}>
            <summary style={{ cursor: 'pointer' }}><MathText text={ml(m.text)} /> <span className="small muted">· {m.task}</span></summary>
            {m.image && <img className="q-img" src={m.image} alt="" />}
            <p className="small">Sizin cavab: <b style={{ color: 'var(--bad)' }}>{m.kind === 'mcq' ? (m.given != null ? <MathText text={ml(m.options?.[m.given])} /> : '—') : m.given || '—'}</b> · Düzgün: <b style={{ color: 'var(--ok)' }}>{m.kind === 'mcq' ? <MathText text={ml(m.options?.[m.correct])} /> : String(m.answer).split('|')[0]}</b></p>
            {m.explanation && <p className="small muted" style={{ whiteSpace: 'pre-wrap' }}><MathText text={ml(m.explanation)} /></p>}
          </details>))}
        {!allMistakes && d.mistakes.length > 10 && <button className="btn show-more" onClick={() => setAllMistakes(true)}>Hamısını göstər ({d.mistakes.length})</button>}
      </section>
    </>
  )
}
