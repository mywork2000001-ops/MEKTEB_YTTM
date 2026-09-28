// Şagird: vaxtlı tapşırıqlar. Taymer serverin vaxtına görə; cavablar avtomatik saxlanılır; vaxt bitəndə avtomatik təhvil.
import { useEffect, useRef, useState } from 'react'
import { ApiError, get, post, put } from '../../api'
import { useT } from '../../i18n'
import { AsyncBtn, Drawer, ErrorBox, gradeTone, Loading, Pill, toast, Top, useLoad } from '../../ui'
import { MathText } from '../../MathText'

const ml = (x: any) => (x ? (typeof x === 'string' ? x : x.az || x.ru || x.en || '') : '')
const hm = (s: string) => new Date(s).toLocaleString('az-AZ', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })

export default function Tasks() {
  const t = useT()
  const [list, err, loading, reload] = useLoad<any[]>(() => get('/api/portal/tasks'), [])
  const [solving, setSolving] = useState<number | null>(null)
  const [review, setReview] = useState<number | null>(null)
  if (solving) return <Solver id={solving} onDone={() => { setSolving(null); reload() }} />
  return (
    <>
      <Top title={t('Tapşırıqlar')} sub="Vaxtlı testlər – açılma və bağlanma vaxtına diqqət edin" />
      <ErrorBox error={err} />
      {loading && !list ? <Loading /> : (
        <div className="jlist">
          {list?.length === 0 && <div className="empty">Tapşırıq yoxdur.</div>}
          {list?.map(x => (
            <div key={x.id} className="jrow">
              <span><b>{x.title}</b><span className="sub small muted"><br />{x.subject} · {x.teacher} · {hm(x.opens_at)} – {hm(x.closes_at).slice(-5)} · {x.duration_min} dəq · {x.questions} sual</span></span>
              <span className="row">{x.result ? <Pill tone={gradeTone(x.result.grade)}>{x.result.correct}/{x.result.total} → {x.result.grade}</Pill> : <Pill tone={x.status === 'açıq' || x.status === 'həll edilir' ? 'ok' : x.status === 'buraxılıb' ? 'bad' : undefined}>{x.status}</Pill>}</span>
              <span>{(x.status === 'açıq' || x.status === 'həll edilir') && <button className="btn primary sm" onClick={() => setSolving(x.id)}>{x.status === 'açıq' ? t('Başla') : 'Davam et'}</button>}
                {x.can_review && <button className="btn sm" onClick={() => setReview(x.id)}>Cavablara bax</button>}</span>
            </div>))}
        </div>)}
      {review && <Review id={review} onClose={() => setReview(null)} />}
    </>
  )
}

function Solver({ id, onDone }: { id: number; onDone: () => void }) {
  const t = useT()
  const [d, setD] = useState<any>(null)
  const [err, setErr] = useState<unknown>()
  const [ans, setAns] = useState<Record<string, any>>({})
  const [i, setI] = useState(0)
  const [left, setLeft] = useState(0)
  const offset = useRef(0)
  const dirty = useRef<Record<string, any>>({})
  useEffect(() => {
    post(`/api/portal/tasks/${id}/start`).then(r => {
      offset.current = Date.parse(r.server_time) - Date.now()     // cihazın saatı səhv olsa da, server vaxtı əsasdır
      setD(r); setAns(r.answers || {})
    }, e => { setErr(e) })
  }, [id])
  useEffect(() => {
    if (!d) return
    const tick = () => {
      const s = Math.max(0, Math.floor((Date.parse(d.deadline) - (Date.now() + offset.current)) / 1000))
      setLeft(s)
      if (s === 0) finish(true)
    }
    tick()
    const iv = setInterval(tick, 1000)
    const sv = setInterval(flush, 5000)
    return () => { clearInterval(iv); clearInterval(sv) }
  }, [d])
  const flush = async () => {
    const pending = dirty.current
    if (!Object.keys(pending).length) return
    dirty.current = {}
    try { await put(`/api/portal/tasks/${id}/answers`, { answers: pending }) } catch (e) {
      if (e instanceof ApiError && e.status === 409) { toast(e.message); onDone() } else dirty.current = { ...pending, ...dirty.current }
    }
  }
  const finished = useRef(false)
  const finish = async (auto = false) => {
    if (finished.current) return
    finished.current = true
    try {
      const r = await post(`/api/portal/tasks/${id}/submit`, auto ? undefined : { answers: { ...ans } })
      toast(auto ? `Vaxt bitdi – təhvil verildi: ${r.correct}/${r.total}` : `Təhvil verildi: ${r.correct}/${r.total} → ${r.grade}`)
    } catch (e) { if (!(e instanceof ApiError && e.status === 409)) toast('Xəta: ' + (e as Error).message) }
    onDone()
  }
  const debounce = useRef<number>(0)
  const set = (idx: number, v: any) => {
    setAns(a => ({ ...a, [idx]: v }))
    dirty.current[String(idx)] = v
    clearTimeout(debounce.current)
    debounce.current = window.setTimeout(flush, 800)          // son cavablar vaxt bitməzdən əvvəl serverə çatsın
  }
  if (err) return <><ErrorBox error={err} /><button className="btn" onClick={onDone}>‹ Geri</button></>
  if (!d) return <Loading />
  const q = d.questions[i]
  const mm = String(Math.floor(left / 60)).padStart(2, '0'), ss = String(left % 60).padStart(2, '0')
  return (
    <>
      <div className="row" style={{ marginBottom: 12, position: 'sticky', top: 0, background: 'var(--bg)', padding: '8px 0', zIndex: 5 }}>
        <b className="grow">{d.title}</b><span className="small muted">{t('Qalan vaxt')}</span><span className={'timer' + (left < 60 ? ' low' : '')}>{mm}:{ss}</span>
      </div>
      <div className="row" style={{ marginBottom: 12, gap: 4 }}>
        {d.questions.map((x: any, k: number) => (
          <button key={k} className="chip" style={{ minWidth: 38, padding: 0 }} aria-pressed={k === i} onClick={() => setI(k)}
            title={ans[x.index] != null && ans[x.index] !== '' ? 'cavablanıb' : 'cavabsız'}>{k + 1}{ans[x.index] != null && ans[x.index] !== '' ? '•' : ''}</button>))}
      </div>
      <section className="panel">
        <p className="small muted">Sual {i + 1} / {d.questions.length}</p>
        <MathText as="p" style={{ fontSize: 17, whiteSpace: 'pre-wrap' }} text={ml(q.text)} />
        {q.image && <img className="q-img" src={q.image} alt="" />}
        {q.kind === 'mcq' ? (
          <div className="stack">{q.options.map((o: any, k: number) => (
            <div key={k} className="q-opt" role="radio" tabIndex={0} aria-checked={ans[q.index] === k} onClick={() => set(q.index, k)} onKeyDown={e => { if (e.key === ' ' || e.key === 'Enter') set(q.index, k) }}>
              <b>{'ABCDE'[k]})</b><MathText text={ml(o)} /></div>))}</div>
        ) : (
          <input className="sel w100" style={{ fontSize: 16 }} placeholder="Cavabınızı yazın" value={ans[q.index] ?? ''} onChange={e => set(q.index, e.target.value)} />
        )}
        <div className="row" style={{ marginTop: 16 }}>
          <button className="btn" disabled={i === 0} onClick={() => setI(i - 1)}>‹ Əvvəlki</button>
          {i < d.questions.length - 1 ? <button className="btn primary" onClick={() => { flush(); setI(i + 1) }}>Növbəti ›</button> : null}
          <AsyncBtn className="btn primary right" onClick={() => finish(false)}>{t('Təhvil ver')}</AsyncBtn>
        </div>
      </section>
    </>
  )
}

function Review({ id, onClose }: { id: number; onClose: () => void }) {
  const [d, err] = useLoad<any>(() => get(`/api/portal/tasks/${id}/review`), [id])
  return (
    <Drawer title={d ? `${d.title} · ${d.correct}/${d.total}` : 'Cavablar'} onClose={onClose}>
      <ErrorBox error={err} />
      {d?.questions.map((q: any, k: number) => (
        <section key={k} className="panel" style={{ marginBottom: 10, borderColor: q.ok ? 'var(--ok)' : 'var(--bad)' }}>
          <p><b>{k + 1}.</b> <MathText text={ml(q.text)} /></p>
          {q.image && <img className="q-img" src={q.image} alt="" />}
          {q.kind === 'mcq' ? q.options.map((o: any, j: number) => (
            <div key={j} className="small" style={{ color: j === q.correct ? 'var(--ok)' : j === q.given ? 'var(--bad)' : undefined, fontWeight: j === q.correct ? 600 : 400 }}>{'ABCDE'[j]}) <MathText text={ml(o)} />{j === q.given ? ' ← sizin cavab' : ''}</div>))
            : <p className="small">Sizin cavab: <b>{q.given || '—'}</b> · Düzgün: <b style={{ color: 'var(--ok)' }}>{String(q.answer).split('|')[0]}</b></p>}
          {q.explanation && <p className="small muted" style={{ whiteSpace: 'pre-wrap' }}>İzah: <MathText text={ml(q.explanation)} /></p>}
        </section>))}
    </Drawer>
  )
}
