import { useState } from 'react'
import { del, get, post } from '../../api'
import { ml, tt, useT } from '../../i18n'
import { Drawer, ErrorBox, fmt, fmtDate, gradeTone, Loading, Pill, toast, useLoad } from '../../ui'
import { MathText } from '../../MathText'
import { downloadPackagePdf, type Pkg } from '../../packagePrint'

const LET = 'ABCDEFGH'

/** Nəticə paketi: bir ekranda kartın şəkli (böyüdülə bilən) + öz testin kağızdakı sıra ilə; hər sualın altında «Altmövzu: … · №n». */
export function ResultPackage({ examId, onClose }: { examId: number; onClose: () => void }) {
  const t = useT()
  const [p, err, , reload] = useLoad<any>(() => get(`/api/portal/exams/${examId}/package`), [examId])
  const [zoom, setZoom] = useState(false)
  const [form, setForm] = useState<{ slot: number; source: string } | null>(null)
  const [reason, setReason] = useState('')
  const [er2, setEr2] = useState<unknown>()
  const [busy, setBusy] = useState(false)
  const open = p && (!p.appeal_until || Date.now() <= new Date(p.appeal_until).getTime())
  const img = p?.scan.image ? `/api/portal/exam-card/${p.scan.scan_id}/image` : null
  const stName: Record<string, string> = { open: tt('gözləyir'), accepted: tt('qəbul olundu'), rejected: tt('rədd edildi') }
  const send = async () => {
    if (!form) return
    setEr2(undefined)
    try { await post(`/api/portal/exams/${examId}/appeals`, { ...form, reason }); setForm(null); setReason(''); reload() } catch (x) { setEr2(x) }
  }
  const pdf = async () => {
    setBusy(true)
    try { await downloadPackagePdf(p as Pkg, img, tt) } catch (x) { toast((x as Error).message) } finally { setBusy(false) }
  }
  return (
    <Drawer title={p ? `${p.exam.kind}-${p.exam.no}${p.exam.extra_seq ? ' · ' + tt('əlavə {n}', { n: p.exam.extra_seq }) : ''} · ${tt('Nəticə paketi')}` : tt('Nəticə paketi')} onClose={onClose}
      footer={p && <button className="btn" disabled={busy} onClick={pdf}>⬇ {busy ? tt('PDF hazırlanır…') : 'PDF'}</button>}>
      <ErrorBox error={err} />
      {!p && !err && <Loading />}
      {p && <>
        <div className="row" style={{ gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
          {p.total && <Pill tone={gradeTone(p.total.grade)}>{tt('Bal')}: {fmt(p.total.points, 1)} / {p.total.max}{p.total.grade ? ` → ${p.total.grade}` : ''}</Pill>}
          {p.appeal_until && <span className="small muted">⚖ {open ? tt('Apelyasiya müddəti: {d}-dək', { d: fmtDate(p.appeal_until) }) : tt('Apelyasiya müddəti bitib')}</span>}
        </div>
        {img ? <>
          <img src={img} alt={tt('Cavab kartımın şəkli')} loading="lazy" onClick={() => setZoom(true)} title={tt('Böyütmək üçün toxun')}
            style={{ width: '100%', maxWidth: 560, border: '1px solid var(--line)', borderRadius: 6, display: 'block', cursor: 'zoom-in', marginBottom: 12 }} />
          {zoom && <div role="dialog" aria-label={tt('Cavab kartımın şəkli')} onClick={() => setZoom(false)}
            style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.85)', zIndex: 1000, overflow: 'auto', cursor: 'zoom-out', display: 'grid', placeItems: 'center' }}>
            <img src={img} alt="" style={{ maxWidth: '100%', maxHeight: '100%' }} /></div>}
        </> : p.scan.online ? <p className="small">💻 {tt('Onlayn yazmısan – cavabların ekrandan götürülüb.')}</p> : null}
        <h3 style={{ margin: '8px 0' }}>{tt('Öz testin')}</h3>
        {p.questions.map((q: any) => {
          const ap = (p.appeals || []).find((x: any) => x.slot === q.slot && x.source === p.scan.source)
          return (
            <div key={q.n} style={{ borderBottom: '1px solid var(--line)', padding: '10px 0', opacity: q.void ? .6 : 1 }}>
              <div style={{ display: 'flex', gap: 8 }}><b>{q.n}.</b>
                <div className="grow" style={{ minWidth: 0 }}>
                  <MathText text={String(ml(q.text) ?? '')} />
                  {q.image && <img className="q-img" src={q.image} alt="" />}
                  {q.kind === 'mcq' && (q.options || []).map((o: any, i: number) => {
                    const mine = q.my_answer === LET[i], right = q.key === LET[i]
                    return <div key={i} style={{ marginTop: 3, color: right ? 'var(--ok)' : mine ? 'var(--bad)' : undefined, fontWeight: mine || right ? 600 : 400 }}>
                      {LET[i]}) <MathText text={String(ml(o) ?? '')} />{mine && (right ? ' ✓' : ' ✗')}{!mine && right ? ' ✓' : ''}</div>
                  })}
                  <div className="small" style={{ marginTop: 4 }}>
                    {tt('Sənin cavabın')}: <b style={{ color: q.ok ? 'var(--ok)' : 'var(--bad)' }}>{q.my_answer || tt('boş')}</b> · {tt('Düz cavab')}: <b style={{ color: 'var(--ok)' }}>{q.key}</b> ·{' '}
                    {q.void ? <span className="muted">{tt('sayılmır')}</span> : <>{q.ok ? <span style={{ color: 'var(--ok)' }}>✓</span> : <span style={{ color: 'var(--bad)' }}>✗</span>} {fmt(q.earned ?? 0, 1)} / {q.points}</>}
                  </div>
                  {q.topic && <div className="small muted" style={{ marginTop: 3 }}>{tt('Altmövzu')}: {q.topic}{q.topic_no ? ` · ${q.topic_no}` : ''}</div>}
                  {q.explanation && <div className="small muted" style={{ marginTop: 3 }}>{tt('İzah')}: <MathText text={String(ml(q.explanation) ?? '')} /></div>}
                  {ap ? <div className="small" style={{ marginTop: 4 }}><Pill tone={ap.status === 'accepted' ? 'ok' : ap.status === 'rejected' ? 'bad' : 'warn'}>⚖ {stName[ap.status]}</Pill>
                    {ap.teacher_reply && <span className="muted"> {ap.teacher_reply}</span>}
                    {ap.status === 'open' && <button type="button" className="btn sm ghost" onClick={async () => { await del(`/api/portal/exam-appeals/${ap.id}`); reload() }}>{tt('Geri götür')}</button>}</div>
                    : open && !q.void ? <button type="button" className="btn sm ghost" style={{ marginTop: 4 }} onClick={() => setForm({ slot: q.slot, source: p.scan.source })}>⚖ {tt('Apelyasiya')}</button> : null}
                </div></div>
            </div>)
        })}
      </>}
      {form && p && <div className="panel" style={{ position: 'sticky', bottom: 0, background: 'var(--bg, #fff)' }}>
        <b>⚖ {tt('Apelyasiya')} · №{form.slot}</b>
        <textarea className="sel" style={{ width: '100%', marginTop: 6 }} rows={3} maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} placeholder={t('Niyə cavabın düz olduğunu düşünürsən?')} />
        <ErrorBox error={er2} />
        <div className="row" style={{ gap: 6, marginTop: 6 }}><button className="btn sm primary" disabled={reason.trim().length < 3} onClick={send}>{tt('Göndər')}</button>
          <button className="btn sm ghost" onClick={() => { setForm(null); setEr2(undefined) }}>{tt('Ləğv et')}</button></div>
      </div>}
    </Drawer>
  )
}
