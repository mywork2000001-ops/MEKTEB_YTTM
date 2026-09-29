import { useNavigate } from 'react-router-dom'
import { get } from '../../api'
import { useT } from '../../i18n'
import { examLabel } from './Plan'
import { ErrorBox, fmtDate, gradeTone, isoDate, Loading, longDate, Pill, useLoad, WD } from '../../ui'

export default function Today() {
  const t = useT()
  const nav = useNavigate()
  const [me, err] = useLoad<any>(() => get('/api/portal/me'), [])
  const [day] = useLoad<any>(() => get('/api/portal/day'), [])
  const [tasks] = useLoad<any[]>(() => get('/api/portal/tasks'), [])
  if (!me) return err ? <ErrorBox error={err} /> : <Loading />
  const now = new Date()
  const open = (tasks || []).filter(x => ['açıq', 'həll edilir', 'gözlənilir'].includes(x.status))
  return (
    <>
      <section className="hero">
        <div className="hero-txt">
          <div className="hero-date">{WD[now.getDay()]} · {longDate(isoDate(now))}</div>
          <h1>{t('Salam')}, {me.full_name.split(' ')[1] || me.full_name}!</h1>
          <p>«{me.motivation}»</p>
          {me.personal && <p style={{ opacity: 0.95 }}>{me.personal}</p>}
        </div>
        {me.days_to_exam != null && (
          <div className="clock"><div className="clk-date">{t('İmtahana qalıb')}</div><div className="clk-time">{me.days_to_exam}<span> {t('gün')}</span></div><div className="clk-date">{fmtDate(me.exam_date)}</div></div>)}
      </section>
      <div className="grid g2">
        <section className="panel">
          <h2>{t('Dərs')} <small>{me.class_name}</small></h2>
          {!day ? <Loading /> : day.lessons.length === 0 ? <p className="muted">Bu gün dərs yoxdur.</p> : (
            <ol className="timeline">{day.lessons.map((l: any, i: number) => (
              <li key={i}><time>{l.time}</time><span><b>{l.subject}</b> · {l.topic || '—'}{examLabel(l) && <> <Pill tone="warn">{examLabel(l)}</Pill></>}
                {l.homework && <><br /><span className="small">Ev tapşırığı: <b>{l.homework}</b></span></>}
                {l.marks.map((m: any, j: number) => <span key={j}> <Pill tone={gradeTone(m.grade)}>{m.grade}</Pill></span>)}</span></li>))}</ol>)}
          <button className="btn sm" onClick={() => nav('/lesson')}>Ətraflı</button>
        </section>
        <section className="panel">
          <h2>{t('Tapşırıqlar')} <small>{open.length}</small></h2>
          {open.length === 0 ? <p className="muted">Açıq tapşırıq yoxdur.</p> : open.map(x => (
            <div key={x.id} className="row" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
              <span><b>{x.title}</b><br /><span className="small muted">{new Date(x.opens_at).toLocaleString('az-AZ', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })} – {new Date(x.closes_at).toLocaleTimeString('az-AZ', { hour: '2-digit', minute: '2-digit' })}</span></span>
              <Pill tone={x.status === 'gözlənilir' ? undefined : 'ok'}>{x.status}</Pill></div>))}
          <button className="btn sm" onClick={() => nav('/tasks')}>{t('Tapşırıqlar')}</button>
          <h2 style={{ marginTop: 16 }}>{t('Müəllimlərim')}</h2>
          {me.teachers.map(([n, s]: [string, string]) => <p key={n + s} style={{ margin: '0 0 4px' }}><b>{n}</b> <span className="muted small">{s}</span></p>)}
        </section>
      </div>
    </>
  )
}
