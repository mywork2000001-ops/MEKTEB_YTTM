import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { get } from '../../api'
import { useAuth } from '../../auth'
import { useT } from '../../i18n'
import { ErrorBox, fmt, Icon, isoDate, longDateT, Pill, Stat, useLoad, wdT, hourN, lessonWhen } from '../../ui'

type Cell = { ta_id: number; class_name: string; subject: string; time: string | null; topic: string | null; assessment_type: string | null }
type TT = { days: { date: string; weekday: string; periods: Record<string, Cell[]> }[] }

const toMin = (s: string) => { const [h, m] = s.split(':').map(Number); return h * 60 + m }
function span(t: string | null) {
  if (!t) return null
  const [a, b] = t.replace('–', '-').split('-')
  return [toMin(a), toMin(b)] as const
}

export default function Home() {
  const { me } = useAuth()
  const t = useT()
  const nav = useNavigate()
  const [now, setNow] = useState(new Date())
  useEffect(() => { const i = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(i) }, [])
  const today = isoDate(now)
  const [tt, err1] = useLoad<TT>(() => get('/api/timetable', { date: today }), [today])
  const [ov, err2] = useLoad<any[]>(() => get('/api/overview'), [])
  const [prog] = useLoad<any[]>(() => get('/api/my/progress'), [])
  const [ap] = useLoad<{ open: number }>(() => get('/api/exam-appeals/open-count'), [])      // cavabsız KSQ/BSQ apelyasiyaları

  const lessons = useMemo(() => {
    const d = tt?.days.find(x => x.date === today)
    if (!d) return []
    return Object.entries(d.periods).flatMap(([p, cells]) => cells.map(c => ({ period: Number(p), ...c })))
      .sort((a, b) => (a.time || '').localeCompare(b.time || ''))
  }, [tt, today])

  const mins = now.getHours() * 60 + now.getMinutes() + now.getSeconds() / 60
  const cur = lessons.find(l => { const s = span(l.time); return s && mins >= s[0] && mins < s[1] })
  const next = lessons.find(l => { const s = span(l.time); return s && mins < s[0] })
  const curSpan = cur ? span(cur.time) : null
  const pct = curSpan ? Math.min(100, ((mins - curSpan[0]) / (curSpan[1] - curSpan[0])) * 100) : 0
  const first = (me?.full_name || '').split(' ')[1] || ''
  const hh = String(now.getHours()).padStart(2, '0'), mm = String(now.getMinutes()).padStart(2, '0'), ss = String(now.getSeconds()).padStart(2, '0')

  return (
    <>
      <section className="hero">
        <div className="hero-txt">
          <div className="hero-date">{wdT(now.getDay())} · {longDateT(today)}</div>
          <h1>{t('Salam, {name} müəllim', { name: first })}</h1>
          <div className="hero-chips">
            <button className="hchip solid" onClick={() => nav('/journal')}>{t('Jurnal')}</button>
            <button className="hchip" onClick={() => nav('/timetable')}>{t('Həftəlik cədvəl')}</button>
            {(ap?.open || 0) > 0 && <button className="hchip solid" onClick={() => nav('/journal')} title={t('KSQ/BSQ üzrə cavabsız apelyasiyalar')}>⚖ {t('Apelyasiyalar')}: {ap!.open}</button>}
          </div>
        </div>
        <div className="clock" aria-live="off">
          <div className="clk-time">{hh}:{mm}<span>:{ss}</span></div>
          <div className="clk-date">{longDateT(today)}</div>
          {cur ? (
            <div className="clk-st lesson"><b>{hourN(cur.period)} · {cur.class_name}</b><span>{cur.time} · {cur.topic || '—'}</span>
              <div className="clk-bar"><i style={{ width: pct + '%' }} /></div></div>
          ) : next ? (
            <div className="clk-st"><b>{t('Növbəti: {when} · {cls}', { when: hourN(next.period), cls: next.class_name })}</b><span>{next.time}</span></div>
          ) : (
            <div className="clk-st"><b>{lessons.length ? t('Bugünkü dərslər bitdi') : t('Bu gün dərs yoxdur')}</b></div>
          )}
        </div>
      </section>
      <ErrorBox error={err1 || err2} />
      <Weekly />
      <div className="grid g2">
        <section className="panel">
          <h2>{t('Bugünkü dərslər')} <small>{lessons.length}</small></h2>
          {lessons.length ? (
            <ol className="timeline">
              {lessons.map(l => (
                <li key={l.ta_id + '-' + l.period} className={span(l.time) && mins >= span(l.time)![1] ? 'done' : ''}>
                  <time>{l.time}</time>
                  <span><b>{lessonWhen(l.period, l.time)} · {l.class_name}</b> {l.assessment_type && ['KSQ', 'BSQ'].includes(l.assessment_type) && <Pill tone="warn">{l.assessment_type}</Pill>}<br />
                    <span className="muted small">{l.topic || t('Plan yüklənməyib')}</span></span>
                </li>))}
            </ol>
          ) : <p className="muted">{t('Bu gün dərsiniz yoxdur.')}</p>}
        </section>
        <section className="panel">
          <h2>{t('Siniflərim')}</h2>
          <div className="stack">
            {(ov || []).map(c => (
              <div key={c.ta_id} className="row" style={{ justifyContent: 'space-between', borderBottom: '1px solid var(--line)', paddingBottom: 8 }}>
                <span className="ctag">{c.class_name}</span>
                <span className="row small">
                  <span>{c.avg_grade != null ? <>{t('orta qiymət')} <b>{fmt(c.avg_grade, 2)}</b></> : <span className="muted">{t('qiymət yoxdur')}</span>}</span>
                  {c.risk?.['Qırmızı'] > 0 && <Pill tone="bad">{t('risk')} {c.risk['Qırmızı']}</Pill>}
                  {c.absence_warnings > 0 && <Pill tone="warn"><Icon name="bell" className="ico" /> 25%+ {c.absence_warnings}</Pill>}
                </span>
              </div>))}
            {ov && !ov.length && <p className="muted">{t('Hələ sinfə qoşulmamısınız – Tənzimləmələr → Siniflər.')}</p>}
          </div>
          {ov && ov.length > 0 && (
            <div className="kpis" style={{ marginTop: 12 }}>
              <Stat value={ov.reduce((a, c) => a + c.students, 0)} label={t('şagird')} />
              <Stat value={ov.reduce((a, c) => a + c.lessons_written, 0)} label={t('yazılmış dərs')} />
              <Stat value={ov.reduce((a, c) => a + (c.risk?.['Qırmızı'] || 0), 0)} label={t('yüksək risk')} />
            </div>)}
        </section>
      </div>
      {prog && prog.some(p => p.total) && (
        <section className="panel" style={{ marginTop: 16 }}>
          <h2>{t('Mövzu icrası')} <small>{t('rəsmi plana nisbətən')}</small></h2>
          <div className="stack" style={{ gap: 8 }}>{prog.filter(p => p.total).map(p => (
            <button key={p.ta_id} className="row" style={{ justifyContent: 'space-between', textAlign: 'left', background: 'none', border: 0, borderBottom: '1px solid var(--line)', padding: '0 0 8px', cursor: 'pointer', color: 'inherit' }}
              onClick={() => { try { sessionStorage.setItem('mk-pick-journal', String(p.ta_id)) } catch { /* yaddaş yoxdur */ } nav('/journal') }}>
              <span><span className="ctag">{p.class_name}</span> <span className="small muted">{p.next ? t('növbəti: №{seq} {topic}', { seq: p.next.seq, topic: p.next.topic }) : t('plan bitib')}</span></span>
              <span className="row small" style={{ gap: 6 }}>
                <b>{p.done}/{p.total}</b>
                {p.delta < 0 ? <Pill tone={p.delta <= -3 ? 'bad' : 'warn'}>{p.delta} {t('dərs')}</Pill> : p.delta > 0 ? <Pill tone="ok">+{p.delta}</Pill> : <Pill tone="ok">{t('plana uyğun')}</Pill>}
                {p.shortfall > 0 && <Pill tone="bad">{t('sığmır: {n}', { n: p.shortfall })}</Pill>}
              </span>
            </button>))}</div>
        </section>)}
    </>
  )
}

/** Həftəlik xülasə: qırmızı risk, 25%+ buraxanlar, son 7 gündə yazılmamış dərslər – həftə ərzində «Oxudum» ilə gizlənir. */
function Weekly() {
  const t = useT()
  const nav = useNavigate()
  const [w] = useLoad<any>(() => get('/api/my/weekly'), [])
  const key = w ? `mk-weekly-${w.week}` : ''
  const [closed, setClosed] = useState('')
  const seen = (() => { try { return !!key && localStorage.getItem(key) === '1' } catch { return false } })()
  if (!w || !w.items.length || seen || closed === key) return null
  const hide = () => { try { localStorage.setItem(key, '1') } catch { /* noop */ } setClosed(key) }
  return (
    <section className="panel weekly" style={{ marginBottom: 16 }}>
      <h2>{t('Bu həftə diqqət')} <small>{t('siniflərim üzrə')}</small><button className="btn sm ghost right" onClick={hide}>{t('Oxudum')}</button></h2>
      {w.items.map((x: any) => (
        <div key={x.ta_id} className="wk-row">
          <b>{x.class_name} <span className="small muted">{x.subject}</span></b>
          <div className="row" style={{ gap: 6 }}>
            {x.missing_week.length > 0 && <Pill tone="warn">{t('son 7 gündə yazılmayıb: {n} dərs', { n: x.missing_week.length })}</Pill>}
            {x.red.length > 0 && <Pill tone="bad">{t('qırmızı risk: {n}', { n: x.red.length })}</Pill>}
            {x.absence.length > 0 && <Pill tone="warn">{t('25%+ buraxır: {n}', { n: x.absence.length })}</Pill>}
          </div>
          {(x.red.length > 0 || x.absence.length > 0) && <p className="small muted" style={{ margin: '4px 0 0' }}>{[...new Set([...x.red, ...x.absence])].join(', ')}</p>}
        </div>))}
      <div className="row" style={{ marginTop: 10 }}>
        <button className="btn sm" onClick={() => nav('/journal')}>{t('Jurnala keç')}</button>
        <button className="btn sm" onClick={() => nav('/reports')}>{t('Analitika → Risk')}</button>
      </div>
    </section>
  )
}
