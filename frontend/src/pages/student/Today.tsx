import { useNavigate } from 'react-router-dom'
import { get } from '../../api'
import { useT } from '../../i18n'
import { NextExtra } from './Extra'
import { examLabel } from './Plan'
import { ErrorBox, fmtDate, gradeTone, isoDate, Loading, longDate, Pill, useLoad, WD } from '../../ui'

export default function Today() {
  const t = useT()
  const nav = useNavigate()
  const [me, err] = useLoad<any>(() => get('/api/portal/me'), [])
  const [day] = useLoad<any>(() => get('/api/portal/day'), [])
  const [tasks] = useLoad<any[]>(() => get('/api/portal/tasks'), [])
  const [extra, , , reloadExtra] = useLoad<any[]>(() => get('/api/portal/extra'), [])
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
                {l.homework && <><br /><span className="small">Evə verildi: <b>{l.homework}</b></span></>}
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
      {(extra || []).filter(c => c.next).length > 0 && (
        <section className="panel" style={{ marginTop: 16 }}>
          <h2>Əlavə məşğələ</h2>
          {(extra || []).filter(c => c.next).map(c => (
            <div key={c.id} style={{ marginBottom: 8 }}><span className="small muted">{c.title} · {c.teacher}</span><NextExtra x={c.next} onJoined={reloadExtra} /></div>))}
          <button className="btn sm" onClick={() => nav('/extra')}>Məşğələlər</button>
        </section>)}
      <Prepare />
    </>
  )
}

/** Hazırlıq: növbəti dərsin ev tapşırığı və yaxınlaşan KSQ/BSQ – hansı mövzu və standartları təkrarlamalı. */
function Prepare() {
  const [u] = useLoad<any>(() => get('/api/portal/upcoming'), [])
  if (!u || (!u.homework.length && !u.exams.length)) return null
  const when = (n: number) => (n === 0 ? 'bu gün' : n === 1 ? 'sabah' : `${n} gün sonra`)
  return (
    <div className="grid g2" style={{ marginTop: 16 }}>
      {u.homework.length > 0 && (
        <section className="panel"><h2>Ev tapşırığı <small>növbəti dərsə</small></h2>
          {u.homework.map((h: any, i: number) => (
            <p key={i} style={{ margin: '0 0 8px' }}><b>{h.subject}</b> <span className="small muted">· {fmtDate(h.due)}{h.due_time ? ', ' + h.due_time : ''}</span><br />{h.homework}</p>))}
        </section>)}
      {u.exams.length > 0 && (
        <section className="panel"><h2>Hazırlaş <small>yaxınlaşan summativ</small></h2>
          {u.exams.map((e: any, i: number) => (
            <details key={i} open={i === 0} style={{ marginBottom: 8 }}>
              <summary style={{ cursor: 'pointer' }}><Pill tone="warn">{e.kind}{e.no ? '-' + e.no : ''}</Pill> <b>{e.subject}</b> · {fmtDate(e.date)} <span className="small muted">({when(e.days)})</span></summary>
              <p className="small muted" style={{ margin: '6px 0' }}>Təkrarlanacaq mövzular ({e.topics.length}):</p>
              <ol className="small" style={{ margin: 0, paddingLeft: 18, maxHeight: 260, overflowY: 'auto' }}>{e.topics.map((x: any) => <li key={x.seq}>{x.topic}{x.tt_pages && <span className="muted"> · {x.tt_pages}</span>}</li>)}</ol>
              {e.standards.length > 0 && <p className="small" style={{ margin: '6px 0 0' }}>Standartlar: <b>{e.standards.join(', ')}</b></p>}
            </details>))}
        </section>)}
    </div>
  )
}
