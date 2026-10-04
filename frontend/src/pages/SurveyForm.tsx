// Şagird sorğusu – cavab forması (açıq link /s/{token} və şagirdin tətbiqi üçün ortaq).
// Anonimlik mətni → bölmələr (bir ekranda bir bölmə) → «Göndər» → «Təşəkkür edirik!». Qaralama brauzerdə saxlanır.
import { useEffect, useMemo, useState } from 'react'
import { ApiError } from '../api'

export type SvQuestion = { id: number; key: string | null; section: string; kind: 'likert5' | 'scale10' | 'single' | 'multi' | 'text'
  text: string; options: { min?: number; max?: number; choices?: string[] } | null; required: boolean }
export type SvPublic = { id: number; title: string; description: string | null; teacher: string; label: string | null
  repeat: 'once' | 'weekly'; period: string; period_label: string | null; sections: { key: string; title: string }[]
  likert: string[]; questions: SvQuestion[]; done?: boolean; mode?: 'full' | 'short'; variant?: number | null
  classes?: { id: number; name: string }[] | null }
type Val = number | string | number[] | undefined

const store = {
  get(k: string) { try { return localStorage.getItem(k) } catch { return null } },
  set(k: string, v: string | null) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v) } catch { /* noop */ } },
}

/** Brauzerin bir dəfə yaradılan təsadüfi nişanı (təkrar göndərməyə qarşı; serverdə yalnız heşi saxlanır). */
export function deviceToken(): string {
  let t = store.get('mk-sv-device')
  if (!t) {
    const a = new Uint8Array(16); crypto.getRandomValues(a)
    t = Array.from(a, b => b.toString(16).padStart(2, '0')).join('')
    store.set('mk-sv-device', t)
  }
  return t
}

export function SurveyForm({ sv, onSubmit, onDone }: { sv: SvPublic; onSubmit: (answers: Record<string, Val>, device: string, classId: number | null) => Promise<unknown>; onDone?: () => void }) {
  const draftKey = `mk-sv-draft-${sv.id}-${sv.period}`
  const [ans, setAns] = useState<Record<string, Val>>(() => { try { return JSON.parse(store.get(draftKey) || '{}') } catch { return {} } })
  // qısa sorğu (≤ 10 sual) – bir ekranda, ayrıca giriş ekranı olmadan: şagird üçün yorucu olmasın
  const compact = sv.questions.length <= 10
  const sections = useMemo(() => compact ? [{ key: '*', title: '' }] : sv.sections.filter(s => sv.questions.some(q => q.section === s.key)), [sv, compact])
  const [step, setStep] = useState(compact ? 0 : -1)       // -1 – giriş (anonimlik mətni)
  const minutes = Math.max(1, Math.round(sv.questions.length * 12 / 60))
  const [miss, setMiss] = useState<Set<number>>(new Set())
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(!!sv.done)
  // ümumi link (WhatsApp qrupu): şagird sinfini seçir – müəllim nəticəni sinif üzrə görsün; seçim yadda qalır
  const needClass = !!sv.classes?.length
  const clsKey = `mk-sv-class-${sv.id}`
  const [cls, setCls] = useState<number | null>(() => { const v = Number(store.get(clsKey)); return sv.classes?.some(c => c.id === v) ? v : null })
  const [clsMiss, setClsMiss] = useState(false)
  const pickClass = (v: number) => { setCls(v); setClsMiss(false); store.set(clsKey, String(v)) }
  const classOk = () => { if (needClass && !cls) { setClsMiss(true); setErr('Sinifinizi seçin'); return false } return true }
  useEffect(() => { store.set(draftKey, Object.keys(ans).length ? JSON.stringify(ans) : null) }, [ans, draftKey])
  useEffect(() => { window.scrollTo({ top: 0 }) }, [step])

  const set = (q: SvQuestion, v: Val) => { setAns(a => ({ ...a, [q.id]: v })); setMiss(m => { const n = new Set(m); n.delete(q.id); return n }) }
  const empty = (v: Val) => v == null || v === '' || (Array.isArray(v) && v.length === 0)
  const check = (qs: SvQuestion[]) => {
    const m = new Set(qs.filter(q => q.required && empty(ans[q.id])).map(q => q.id))
    setMiss(m)
    if (m.size) { setErr('Qırmızı ilə göstərilən suallara cavab verin'); return false }
    setErr(''); return true
  }
  const cur = sections[step]
  const qs = cur ? sv.questions.filter(q => compact || q.section === cur.key) : []
  const send = async () => {
    if (!classOk()) return
    if (!check(sv.questions)) { if (!compact) setStep(sections.findIndex(s => sv.questions.some(q => q.section === s.key && q.required && empty(ans[q.id])))); return }
    setBusy(true); setErr('')
    try {
      await onSubmit(Object.fromEntries(Object.entries(ans).filter(([, v]) => !empty(v))), deviceToken(), needClass ? cls : null)
      store.set(draftKey, null); setDone(true); onDone?.()
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) { store.set(draftKey, null); setDone(true) }
      setErr(e instanceof ApiError ? e.message : 'Göndərilmədi – internet bağlantısını yoxlayın')
    } finally { setBusy(false) }
  }

  if (done) return (
    <div className="sv-card" style={{ textAlign: 'center' }}>
      <div style={{ fontSize: 44 }} aria-hidden>🙏</div>
      <h1>Təşəkkür edirik!</h1>
      <p className="muted">Cavabınız anonim qəbul edildi.{sv.repeat === 'weekly' ? ' Növbəti həftə sorğu yenidən açılacaq.' : ''}</p>
      {err && <p className="small muted">{err}</p>}
    </div>
  )
  const pct = compact ? Math.round((sv.questions.filter(q => !empty(ans[q.id])).length * 100) / sv.questions.length)
    : step < 0 ? 0 : Math.round(((step + 1) * 100) / sections.length)
  return (
    <div className="sv-card">
      <h1>{sv.title}</h1>
      <p className="muted small" style={{ margin: 0 }}>Müəllim: <b>{sv.teacher}</b>{sv.label ? ` · ${sv.label}` : ''}{sv.period_label ? ` · həftə: ${sv.period_label}` : ''}</p>
      <div className="sv-prog" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}><i style={{ width: pct + '%' }} /></div>
      {step < 0 ? (
        <>
          {sv.description && <p style={{ whiteSpace: 'pre-wrap' }}>{sv.description}</p>}
          <div className="banner" style={{ background: 'var(--accent-soft)', color: 'var(--ink)', borderRadius: 10 }}>
            <span>🔒 <b>Sorğu anonimdir.</b> Adınız soruşulmur və müəllim kimin nə yazdığını görə bilməz.
              Səmimi cavablarınız dərslərin daha yaxşı olmasına kömək edəcək.</span></div>
          {needClass && <ClassPick classes={sv.classes!} value={cls} miss={clsMiss} onChange={pickClass} />}
          {err && <p className="err" role="alert">{err}</p>}
          <p className="small muted">{sv.questions.length} sual · təxminən {minutes} dəqiqə · {sections.length} bölmə{sv.repeat === 'weekly' ? ' · hər həftə bir dəfə' : ''}</p>
          <button className="btn primary" style={{ width: '100%' }} onClick={() => { if (classOk()) { setErr(''); setStep(0) } }}>Başla</button>
        </>
      ) : (
        <>
          {compact ? <p className="small muted" style={{ margin: '0 0 4px' }}>🔒 Anonim · {sv.questions.length} sual · ~{minutes} dəq. Müəllim kimin nə yazdığını görmür.</p>
            : <h2 style={{ margin: '0 0 4px', fontSize: 17 }}>{step + 1}. {cur.title} <small className="muted" style={{ fontWeight: 400 }}>{step + 1} / {sections.length}</small></h2>}
          {compact && needClass && <ClassPick classes={sv.classes!} value={cls} miss={clsMiss} onChange={pickClass} />}
          {qs.map(q => <Question key={q.id} q={q} likert={sv.likert} v={ans[q.id]} miss={miss.has(q.id)} onChange={v => set(q, v)} />)}
          {err && <p className="err" role="alert">{err}</p>}
          <div className="sv-nav">
            {!compact ? <button className="btn" onClick={() => { setErr(''); setStep(step - 1) }}>Geri</button> : <span />}
            {step < sections.length - 1
              ? <button className="btn primary" onClick={() => check(qs) && setStep(step + 1)}>İrəli</button>
              : <button className="btn primary" disabled={busy} onClick={send}>{busy ? 'Göndərilir…' : 'Göndər'}</button>}
          </div>
        </>
      )}
    </div>
  )
}

/** Ümumi linkdə sinif seçimi (anonimlik pozulmur: sinif üzrə nəticə yalnız ≥ 5 cavabda görünür). */
function ClassPick({ classes, value, miss, onChange }: { classes: { id: number; name: string }[]; value: number | null; miss: boolean; onChange: (v: number) => void }) {
  return (
    <div className={'sv-q' + (miss ? ' miss' : '')} role="group" aria-label="Sinifiniz">
      <p>Sinifiniz / qrupunuz</p>
      <div className="sv-opts" style={{ gridTemplateColumns: 'repeat(auto-fill,minmax(110px,1fr))' }}>
        {classes.map(c => <button key={c.id} type="button" className="sv-opt" style={{ justifyContent: 'center' }} aria-pressed={value === c.id} onClick={() => onChange(c.id)}>{c.name}</button>)}
      </div>
      <div className="small muted" style={{ marginTop: 4 }}>Müəllim nəticəni yalnız sinif üzrə ümumi şəkildə görür (ən azı 5 cavab olduqda) – adınız yoxdur.</div>
    </div>
  )
}

function Question({ q, likert, v, miss, onChange }: { q: SvQuestion; likert: string[]; v: Val; miss: boolean; onChange: (v: Val) => void }) {
  const label = q.text + (q.required ? '' : ' (istəyə görə)')
  return (
    <div className={'sv-q' + (miss ? ' miss' : '')} role="group" aria-label={q.text}>
      <p>{label}</p>
      {q.kind === 'likert5' && (
        <div className="sv-likert">{likert.map((l, i) => (
          <button key={i} type="button" aria-pressed={v === i + 1} aria-label={l} title={l} onClick={() => onChange(i + 1)}><b>{i + 1}</b><span>{l}</span></button>))}</div>)}
      {q.kind === 'scale10' && (() => { const lo = q.options?.min ?? 0, hi = q.options?.max ?? 10
        return <>
          <div className="sv-scale" style={{ gridTemplateColumns: `repeat(${Math.min(hi - lo + 1, 11)},minmax(0,1fr))` }}>
            {Array.from({ length: hi - lo + 1 }, (_, i) => lo + i).map(n => <button key={n} type="button" aria-pressed={v === n} onClick={() => onChange(n)}>{n}</button>)}</div>
          <div className="sv-scale-ends"><span>{lo} – çox pis</span><span>{hi} – əla</span></div></> })()}
      {q.kind === 'single' && (
        <div className="sv-opts">{(q.options?.choices || []).map((c, i) => (
          <button key={i} type="button" className="sv-opt" aria-pressed={v === i} onClick={() => onChange(v === i ? undefined : i)}>{c}</button>))}</div>)}
      {q.kind === 'multi' && (
        <div className="sv-opts">{(q.options?.choices || []).map((c, i) => { const arr = Array.isArray(v) ? v : []; const on = arr.includes(i)
          return <button key={i} type="button" className="sv-opt" aria-pressed={on} onClick={() => onChange(on ? arr.filter(x => x !== i) : [...arr, i])}>{on ? '☑' : '☐'} {c}</button> })}</div>)}
      {q.kind === 'text' && (
        <><textarea value={typeof v === 'string' ? v : ''} maxLength={1000} onChange={e => onChange(e.target.value)} aria-label={q.text} placeholder="Fikrinizi yazın…" />
          <div className="small muted" style={{ textAlign: 'right' }}>{typeof v === 'string' ? v.length : 0} / 1000</div></>)}
    </div>
  )
}
