// Şagird: vaxtlı tapşırıqlar. Taymer serverin vaxtına görə; cavablar avtomatik saxlanılır; vaxt bitəndə avtomatik təhvil.
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ApiError, get, post, put } from '../../api'
import { useT } from '../../i18n'
import { AsyncBtn, Drawer, ErrorBox, gradeTone, Loading, Pill, Seg, toast, Top, useLoad } from '../../ui'
import { MathText } from '../../MathText'
import { PeriodBar, usePeriod } from '../../periods'

const ml = (x: any) => (x ? (typeof x === 'string' ? x : x.az || x.ru || x.en || '') : '')
// Test rejimi: tam ekran (çıxanda xəbərdarlıq) və mətnin seçilməsi / kopyalanması / uzun basma menyusu bağlıdır.
// Qeyd: telefonun sistem funksiyalarını (ekran şəkli, Circle to Search) veb səhifə söndürə bilmir; iPhone-da tam ekran yoxdur.
const fsOk = () => !!document.fullscreenEnabled
const enterFs = () => (fsOk() && !document.fullscreenElement
  ? document.documentElement.requestFullscreen({ navigationUI: 'hide' }).then(() => true, () => false) : Promise.resolve(!!document.fullscreenElement))
const exitFs = () => { if (document.fullscreenElement) document.exitFullscreen().catch(() => {}) }
const block = (e: { preventDefault: () => void }) => e.preventDefault()
const isField = (t: EventTarget | null) => t instanceof HTMLInputElement || t instanceof HTMLTextAreaElement

const hm = (s: string) => new Date(s).toLocaleString('az-AZ', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })

export default function Tasks() {
  const t = useT()
  const { id: linkId } = useParams()
  const nav = useNavigate()
  const [list, err, loading, reload] = useLoad<any[]>(() => get('/api/portal/tasks'), [])
  const [solving, setSolving] = useState<number | null>(null)
  // test linki (/t/:id): açıqdırsa birbaşa başlanır
  useEffect(() => {
    if (!linkId || !list) return
    const x = list.find(q => q.id === Number(linkId))
    if (!x) toast('Bu test sizin üçün deyil və ya silinib')
    else if (x.status === 'açıq' || x.status === 'həll edilir') setSolving(x.id)
    else toast(x.status === 'gözlənilir' ? `Test hələ açılmayıb: ${new Date(x.opens_at).toLocaleString('az-AZ')}` : `Test: ${x.status}`)
    nav('/tasks', { replace: true })
  }, [linkId, list])
  const [review, setReview] = useState<number | null>(null)
  const [tab, setTab] = useState<'movzu' | 'sinaq'>('movzu')
  const f = usePeriod('st-tasks', 'date')
  // mövzu testləri – perspektiv plandan; qalanı (plandan kənar) – sınaqlar
  const mine = (list || []).filter(x => (x.kind === 'movzu') === (tab === 'movzu'))
  const shown = mine.filter(x => f.has(x.opens_at)).sort(f.sort === 'topic'
    ? (a, b) => a.subject.localeCompare(b.subject, 'az') || (tab === 'movzu' ? (a.topic_seq ?? 1e9) - (b.topic_seq ?? 1e9) : a.title.localeCompare(b.title, 'az', { numeric: true }))
    : (a, b) => Date.parse(b.opens_at) - Date.parse(a.opens_at))
  const open = (x: any) => x.status === 'açıq' || x.status === 'həll edilir'
  const count = (k: 'movzu' | 'sinaq') => (list || []).filter(x => (x.kind === 'movzu') === (k === 'movzu') && open(x)).length
  if (solving) return <Solver id={solving} onDone={() => { setSolving(null); reload() }} />
  return (
    <>
      <Top title={t('Tapşırıqlar')} sub="Vaxtlı testlər – açılma və bağlanma vaxtına diqqət edin" />
      <ErrorBox error={err} />
      <div className="toolbar"><Seg label="Bölmə" value={tab} onChange={setTab}
        options={[['movzu', `Mövzu testləri${count('movzu') ? ` · ${count('movzu')} açıq` : ''}`], ['sinaq', `Sınaqlar${count('sinaq') ? ` · ${count('sinaq')} açıq` : ''}`]]} /></div>
      {tab === 'sinaq' && <p className="small muted" style={{ marginTop: 0 }}>Sınaqda yeriniz və balınız test bağlanandan sonra «Nəticələrim»dədir.</p>}
      {loading && !list ? <Loading /> : (<>
        {mine.length > 0 && <PeriodBar f={f} count={shown.length} total={mine.length} topicLabel={tab === 'movzu' ? 'Mövzu üzrə' : 'Ad üzrə'} />}
        <div className="jlist">
          {list && mine.length === 0 && <div className="empty">{tab === 'movzu' ? 'Mövzu testi yoxdur.' : 'Sınaq yoxdur.'}</div>}
          {mine.length > 0 && shown.length === 0 && <div className="empty">Bu dövrdə test yoxdur – «‹ ›» ilə başqa dövrə keçin və ya «Hamısı»nı seçin.</div>}
          {shown.map(x => (
            <div key={x.id} className="jrow">
              <span><b>{x.title}</b><span className="sub small muted"><br />{x.subject}{x.topic_seq ? ` · mövzu №${x.topic_seq}` : ''} · {x.teacher} · {hm(x.opens_at)} – {hm(x.closes_at).slice(-5)} · {x.duration_min} dəq · {x.questions} sual</span></span>
              <span className="row">{x.result ? <Pill tone={gradeTone(x.result.grade)}>{x.result.correct}/{x.result.total} → {x.result.grade}</Pill> : <Pill tone={x.status === 'açıq' || x.status === 'həll edilir' ? 'ok' : x.status === 'buraxılıb' ? 'bad' : undefined}>{x.status}</Pill>}</span>
              <span>{(x.status === 'açıq' || x.status === 'həll edilir') && <button className="btn primary sm" onClick={() => { enterFs(); setSolving(x.id) }}>{x.status === 'açıq' ? t('Başla') : 'Davam et'}</button>}
                {x.can_review && <button className="btn sm" onClick={() => setReview(x.id)}>Cavablara bax</button>}</span>
            </div>))}
        </div></>)}
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
  const [full, setFull] = useState(() => !!document.fullscreenElement)
  const [fsFailed, setFsFailed] = useState(false)
  const [exits, setExits] = useState(0)
  useEffect(() => {
    const ch = () => { const f = !!document.fullscreenElement; setFull(f); if (!f) setExits(n => n + 1) }
    document.addEventListener('fullscreenchange', ch)
    // seçmə, kopyalama, kəsmə, yapışdırma, sürükləmə, uzun basma menyusu və Ctrl+C/A/X/V/P/S – test boyunca bağlıdır
    const sel = (e: Event) => { if (!isField(e.target)) e.preventDefault() }
    const keys = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && 'cxavps'.includes(e.key.toLowerCase())) e.preventDefault() }
    const evs: [string, EventListener][] = [['copy', block], ['cut', block], ['paste', block], ['contextmenu', block], ['dragstart', block],
      ['selectstart', sel], ['keydown', keys as EventListener]]
    evs.forEach(([n, f]) => document.addEventListener(n, f))
    document.body.classList.add('exam-guard')
    return () => {
      document.removeEventListener('fullscreenchange', ch)
      evs.forEach(([n, f]) => document.removeEventListener(n, f))
      document.body.classList.remove('exam-guard')
      exitFs()
    }
  }, [])
  const backToFs = async () => { if (!(await enterFs())) setFsFailed(true) }
  const offset = useRef(0)
  const dirty = useRef<Record<string, any>>({})
  const ansRef = useRef<Record<string, any>>({})
  useEffect(() => { ansRef.current = ans }, [ans])
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
    // tətbiqdən çıxanda / ekran bağlananda son cavablar dərhal göndərilsin
    const hide = () => { if (document.visibilityState === 'hidden') flush() }
    document.addEventListener('visibilitychange', hide)
    window.addEventListener('pagehide', flush)
    return () => { clearInterval(iv); clearInterval(sv); document.removeEventListener('visibilitychange', hide); window.removeEventListener('pagehide', flush); flush() }
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
    dirty.current = {}                                   // hamısı təhvildə gedir – sonra ayrıca saxlama olmasın
    try {
      // vaxt bitəndə də son cavablar göndərilir (server 10 san. gecikməni qəbul edir)
      const r = await post(`/api/portal/tasks/${id}/submit`, { answers: { ...ansRef.current } })
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
      {fsOk() && !full && !fsFailed && (
        <div className="fs-guard" role="alertdialog" aria-modal="true" aria-labelledby="fs-guard-t">
          <div className="panel" style={{ maxWidth: 420 }}>
            <h2 id="fs-guard-t">{exits ? '⚠ Tam ekrandan çıxdınız' : 'Test tam ekranda yazılır'}</h2>
            <p>{exits ? 'Testə qayıtmaq üçün tam ekrana keçin. Vaxt dayanmır – qalan vaxt: ' : 'Başlamaq üçün tam ekrana keçin. Qalan vaxt: '}<b>{mm}:{ss}</b></p>
            {exits > 0 && <p className="small muted">Tam ekrandan çıxma: {exits} dəfə.</p>}
            <button className="btn primary w100" onClick={backToFs}>Tam ekrana keç</button>
          </div>
        </div>)}
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
        {q.image && <img className="q-img" src={q.image} alt="" draggable={false} />}
        {q.kind === 'mcq' ? (
          <div className="stack">{q.options.map((o: any, k: number) => (
            <div key={k} className="q-opt" role="radio" tabIndex={0} aria-checked={ans[q.index] === k} onClick={() => set(q.index, k)} onKeyDown={e => { if (e.key === ' ' || e.key === 'Enter') set(q.index, k) }}>
              <b>{'ABCDE'[k]})</b><MathText text={ml(o)} /></div>))}</div>
        ) : (
          <input className="sel w100" style={{ fontSize: 16 }} placeholder="Cavabınızı yazın" value={ans[q.index] ?? ''} onChange={e => set(q.index, e.target.value)} />
        )}
        <div className="row exam-nav" style={{ marginTop: 16 }}>
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
