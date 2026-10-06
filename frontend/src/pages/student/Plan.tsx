import { useState } from 'react'
import { get } from '../../api'
import { useT } from '../../i18n'
import { azDT, ErrorBox, fmtDate, isoDate, Loading, Pill, Seg, Top, useLoad } from '../../ui'
import { useAuth } from '../../auth'
import { printPlan } from './studentPrint'

/** «KSQ-2», «BSQ-1», «Diaqnostik» – formativ dərsdə boş. */
export const examLabel = (l: any) => (!l.assessment_type || l.assessment_type === 'formativ' ? '' : l.exam_no ? `${l.assessment_type}-${l.exam_no}` : l.assessment_type)

/** Perspektiv planla əlaqə: dərslik səhifələri, rəsmi tarix (sürüşübsə), «mövzu davam edir», cədvəldən kənar dərs. */
export function PlanNotes({ l, compact }: { l: any; compact?: boolean }) {
  const moved = l.official_date && l.official_date !== l.date && l.date
  const notes = [
    l.tt_pages && `Dərslik: ${l.tt_pages}`,
    l.held && 'Mövzu növbəti dərsdə davam edir',
    moved && `Planda: ${fmtDate(l.official_date)}`,
    l.topic && l.plan_topic && l.topic !== l.plan_topic && `Plandakı mövzu: ${l.plan_topic}`,
    l.off_schedule && 'Cədvəldən kənar dərs',
  ].filter(Boolean)
  // X–XI: dərsin P0010 testi – yalnız dərsin tarixi və saatı çatanda açılır
  const p10 = l.p0010 ? <>{notes.length ? ' · ' : ''}Test: <a href={l.p0010.url} target="_blank" rel="noreferrer">{l.p0010.label}</a></>
    : l.p0010_opens_at ? <>{notes.length ? ' · ' : ''}🔒 Test dərs başlayanda açılır ({fmtDate(l.p0010_opens_at)}, {azDT(new Date(l.p0010_opens_at), { hour: '2-digit', minute: '2-digit' })})</> : null
  if (!notes.length && !p10) return null
  return compact ? <span className="sub small muted"><br />{notes.join(' · ')}{p10}</span>
    : <p className="small muted" style={{ margin: '0 0 8px' }}>{notes.join(' · ')}{p10}</p>
}

export default function Plan() {
  const t = useT()
  const { me } = useAuth()
  const [mode, setMode] = useState<'plan' | 'progress'>('plan')
  const [view, setView] = useState<'day' | 'week' | 'month' | 'semester'>('week')
  const [date, setDate] = useState(isoDate(new Date()))
  const [d, err, loading] = useLoad<any>(() => get('/api/portal/plan', { view, date }), [view, date])
  const step = (n: number) => {
    const x = new Date(date + 'T00:00')
    if (view === 'day') x.setDate(x.getDate() + n); else if (view === 'week') x.setDate(x.getDate() + 7 * n); else if (view === 'month') x.setMonth(x.getMonth() + n); else x.setMonth(x.getMonth() + 5 * n)
    setDate(isoDate(x))
  }
  let last = ''
  return (
    <>
      <Top title={t('Plan')} sub="Sinfinin perspektiv planı" />
      <div className="toolbar"><Seg value={mode} onChange={setMode} label="Bölmə" options={[['plan', t('Plan')], ['progress', t('Keçilən mövzular')]]} /></div>
      {mode === 'progress' ? <Progress /> : <>
      <div className="toolbar">
        <Seg value={view} onChange={setView} options={[['day', t('Gün')], ['week', t('Həftə')], ['month', t('Ay')], ['semester', t('Yarımil')]]} />
        <span className="row" style={{ gap: 6, flexWrap: 'nowrap' }}>
          <button className="btn sm" onClick={() => step(-1)} aria-label="Əvvəlki">‹</button><button className="btn sm" onClick={() => step(1)} aria-label="Növbəti">›</button>
          <button className="btn sm ghost" onClick={() => setDate(isoDate(new Date()))}>{t('Bu gün')}</button>
          <button className="btn sm" disabled={!d} onClick={() => d && printPlan(d, me, ({ day: 'Gün', week: 'Həftə', month: 'Ay', semester: 'Yarımil' } as const)[view], examLabel)}>Çap</button></span>
      </div>
      <ErrorBox error={err} />
      {loading && !d ? <Loading /> : (
        <div className="jlist">
          {d?.items.length === 0 && <div className="empty">Bu dövrdə dərs yoxdur.</div>}
          {d?.items.map((i: any, k: number) => {
            const show = i.date !== last; last = i.date
            return (
              <div key={k} className="jrow cols" style={{ ['--cols' as any]: '84px minmax(0,1fr) auto', ['--mcols' as any]: '64px minmax(0,1fr) auto', background: i.date === isoDate(new Date()) ? 'var(--accent-soft)' : undefined }}>
                <span className="small">{show ? <b>{i.weekday} {fmtDate(i.date).slice(0, 5)}</b> : ''}<br /><span className="muted">{i.time}</span></span>
                <span style={{ textAlign: 'justify', hyphens: 'auto', overflowWrap: 'anywhere' }}><b>{i.topic || '—'}</b>{i.taught && <span className="small" style={{ color: 'var(--ok)' }} title="jurnalda yazılıb"> ✓</span>}
                  <span className="sub small muted"> {i.subject}{i.group ? ' · ' + i.class_name : ''}{i.plan_seq ? ` · №${i.plan_seq}` : ''}</span>
                  <PlanNotes l={i} compact /></span>
                {examLabel(i) ? <Pill tone="warn">{examLabel(i)}</Pill> : <span />}
              </div>)
          })}
        </div>)}
      </>}
    </>
  )
}

type Subj = { ta_id: number; subject: string; class_name: string; group: boolean; teacher: string; total: number; done: number; expected: number; delta: number
  done_pct: number | null; plan_pct: number | null; review: { seq: number; topic: string }[]; recent: { seq: number; topic: string; done_on: string }[]
  next: { seq: number; topic: string; assessment_type: string; exam_no: number | null }[]; sections: { section: string; total: number; done: number }[] }

/** Fənlər üzrə: neçə mövzu keçilib, plana nisbətən harada olduğumuz, təkrar tövsiyə olunan və növbəti mövzular. */
function Progress() {
  const [rows, err] = useLoad<Subj[]>(() => get('/api/portal/progress'), [])
  if (!rows) return <><ErrorBox error={err} /><Loading /></>
  if (!rows.length) return <div className="empty">Hələ perspektiv plan yüklənməyib.</div>
  return (
    <div className="stack">{rows.map(r => (
      <section key={r.ta_id} className="panel">
        <h2>{r.subject}{r.group ? <small> · {r.class_name}</small> : null} <small>{r.teacher}</small></h2>
        <div className="row small" style={{ justifyContent: 'space-between' }}>
          <span>Keçilib <b>{r.done}</b> / {r.total} mövzu</span>
          {r.delta < 0 ? <Pill tone="warn">plandan {-r.delta} dərs geridə</Pill> : r.delta > 0 ? <Pill tone="ok">plandan {r.delta} dərs irəlidə</Pill> : <Pill tone="ok">plana uyğun</Pill>}
        </div>
        <div style={{ position: 'relative', height: 10, background: 'var(--sunk)', borderRadius: 5, overflow: 'hidden', margin: '6px 0 10px' }}
          role="img" aria-label={`${r.done_pct ?? 0}% keçilib, plan üzrə ${r.plan_pct ?? 0}%`}>
          <i style={{ position: 'absolute', inset: 0, width: `${r.done_pct ?? 0}%`, background: 'var(--accent)', borderRadius: 5 }} />
          {r.plan_pct != null && r.plan_pct > 0 && r.plan_pct < 100 && <i style={{ position: 'absolute', top: 0, bottom: 0, left: `calc(${r.plan_pct}% - 1px)`, width: 2, background: 'var(--ink)' }} />}
        </div>
        {r.review.length > 0 && <p className="small" style={{ margin: '0 0 6px' }}><b>Təkrar etməyi tövsiyə edirik:</b> {r.review.map(x => `№${x.seq} ${x.topic}`).join('; ')}</p>}
        {r.next.length > 0 && <p className="small" style={{ margin: '0 0 6px' }}><b>Növbəti mövzular:</b> {r.next.map(x => `№${x.seq} ${x.topic}${examLabel(x) ? ' (' + examLabel(x) + ')' : ''}`).join('; ')}</p>}
        {r.recent.length > 0 && <details><summary className="small" style={{ cursor: 'pointer' }}>Son keçilən mövzular</summary>
          <ul className="small" style={{ margin: '6px 0 0', paddingLeft: 18 }}>{r.recent.map(x => <li key={x.seq}>№{x.seq} {x.topic} <span className="muted">· {fmtDate(x.done_on)}</span></li>)}</ul></details>}
        {r.sections.length > 1 && <details><summary className="small" style={{ cursor: 'pointer' }}>Bölmələr üzrə</summary>
          <ul className="small" style={{ margin: '6px 0 0', paddingLeft: 18 }}>{r.sections.map((x, k) => <li key={k}>{x.section}: {x.done}/{x.total}</li>)}</ul></details>}
      </section>))}
      <p className="small muted">Qara xətt – plana görə bu günə qədər keçilməli olan yer.</p>
    </div>
  )
}
