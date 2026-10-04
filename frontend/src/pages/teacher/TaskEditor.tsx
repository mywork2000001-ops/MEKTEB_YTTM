// Onlayn tapşırıq redaktoru: yaratma və redaktə. Viktorina bazasından bir neçə mənbə və bir neçə bölmə (alt mövzu),
// seçilmiş sualların redaktəsi (mətn, variantlar, düzgün cavab, izah), öz sualım, vaxt, kimə.
import { useEffect, useMemo, useState } from 'react'
import { get, patch, post } from '../../api'
import { MathText } from '../../MathText'
import { Drawer, ErrorBox, Field, Pill, toast } from '../../ui'
import { TargetPicker } from './common'

type ML = string | { az?: string; ru?: string; en?: string } | null | undefined
const ml = (x: ML) => (x ? (typeof x === 'string' ? x : x.az || x.ru || x.en || '') : '')

export type Q = {
  key: string; kind: 'mcq' | 'open'; text: string; options: string[]; correct: number; answer: string; explanation: string
  image: string | null; bank_id: number | null; source: string | null; lesson: string | null; raw: any | null
}
export const fromSnapshot = (s: any, key: string): Q => ({
  key, kind: s.kind, text: ml(s.text), options: (s.options || []).map((o: ML) => ml(o)), correct: s.correct ?? 0,
  answer: s.answer || '', explanation: ml(s.explanation), image: s.image || null, bank_id: s.bank_id ?? null,
  source: s.source ?? null, lesson: s.lesson ?? null, raw: s,
})
const fromBank = (q: any, source: string, lesson: string): Q => fromSnapshot({
  bank_id: q.id, source, lesson, kind: q.kind, text: q.text, options: q.options, correct: q.correct, answer: q.answer,
  image: q.image, explanation: q.explanation }, 'b' + q.id)
export const toCustom = (q: Q) => ({
  kind: q.kind, text: q.text, options: q.kind === 'mcq' ? q.options : null, correct: q.kind === 'mcq' ? q.correct : null,
  answer: q.kind === 'open' ? q.answer : null, explanation: q.explanation || null, image: q.image, bank_id: q.bank_id,
  source: q.source, lesson: q.lesson, raw: q.raw,
})
export const iso = (d: string, t: string) => new Date(`${d}T${t}:00`).toISOString()
const pad = (n: number) => String(n).padStart(2, '0')
export const localParts = (s: string) => { const d = new Date(s); return [`${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`, `${pad(d.getHours())}:${pad(d.getMinutes())}`] }

export default function TaskEditor({ ta, taskId, fromBank: bankFirst = false, onClose, onDone }:
  { ta: number; taskId?: number; fromBank?: boolean; onClose: () => void; onDone: () => void }) {
  const today = new Date().toISOString().slice(0, 10)
  const [f, setF] = useState({ title: `Test – ${today.split('-').reverse().join('.')}`, date: today, from: '15:00', to: '16:00', duration: 40, show: 'after_close', shuffle: true })
  const [qs, setQs] = useState<Q[]>([])
  const [targets, setTargets] = useState<number[] | null | undefined>(taskId ? undefined : null)
  const [started, setStarted] = useState(0)
  const [aud, setAud] = useState<number[] | null | undefined>(taskId ? undefined : null)   // yüklənmiş auditoriya (redaktə)
  const [editing, setEditing] = useState<string | null>(null)
  const [err, setErr] = useState<unknown>()
  const locked = started > 0

  useEffect(() => {
    if (!taskId) return
    get(`/api/tasks/${ta}/${taskId}/full`).then(t => {
      const [d1, t1] = localParts(t.opens_at), [, t2] = localParts(t.closes_at)
      setF({ title: t.title, date: d1, from: t1, to: t2, duration: t.duration_min, show: t.show_answers, shuffle: t.shuffle })
      setQs(t.questions_full.map((s: any, i: number) => fromSnapshot(s, 'e' + i)))
      setStarted(t.started)
      setAud(t.student_ids ?? null)
    }, setErr)
  }, [ta, taskId])

  const has = (k: string) => qs.some(q => q.key === k)
  const add = (list: Q[]) => setQs(cur => [...cur, ...list.filter(q => !cur.some(c => c.key === q.key))])
  const remove = (k: string) => setQs(cur => cur.filter(q => q.key !== k))

  const problem = !f.title.trim() ? 'Tapşırığın adını yazın' : !qs.length ? 'Ən azı 1 sual seçin'
    : f.to <= f.from ? 'Bağlanma saatı açılma saatından sonra olmalıdır' : targets && !targets.length ? '«Kimə» bölməsində şagird seçin'
    : qs.length > 100 ? 'Bir tapşırıqda ən çoxu 100 sual' : ''
  const submit = async () => {
    if (problem) { setErr(new Error(problem)); return }
    const meta = { title: f.title.trim(), opens_at: iso(f.date, f.from), closes_at: iso(f.date, f.to), duration_min: f.duration, shuffle: f.shuffle, show_answers: f.show }
    try {
      if (taskId) {
        const body: any = { ...meta }
        if (!locked) body.questions = qs.map(toCustom)
        if (targets === null) body.all_students = true
        else if (targets) body.student_ids = targets
        await patch(`/api/tasks/${ta}/${taskId}`, body)
        toast('Tapşırıq yeniləndi')
      } else {
        await post(`/api/tasks/${ta}`, { ...meta, bank_ids: [], custom: qs.map(toCustom), student_ids: targets ?? null })
        toast('Sınaq yaradıldı – «Sınaq imtahanları»nda da görünür')
      }
      onDone()
    } catch (e) { setErr(e) }
  }

  const bank = <BankPicker has={has} add={add} remove={remove} onTitle={t => !taskId && setF(x => ({ ...x, title: t }))} disabled={locked} first={bankFirst} />
  return (
    <Drawer title={taskId ? 'Tapşırığı redaktə et' : bankFirst ? 'Viktorinadan test əlavə et' : 'Yeni tapşırıq'} onClose={onClose}
      footer={<><span className="small muted grow">{qs.length} sual</span><button className="btn" onClick={onClose}>Ləğv et</button><button className="btn primary" onClick={submit}>{taskId ? 'Yadda saxla' : 'Yarat'}</button></>}>
      <div className="stack">
        {locked && <div className="banner">Şagirdlər artıq başlayıb ({started}) – suallar dəyişdirilə bilməz; ad, vaxt və «kimə» dəyişə bilər.</div>}
        {bankFirst && !taskId && bank}
        <div className="fg">
          <Field label="Ad" full><input value={f.title} onChange={e => setF({ ...f, title: e.target.value })} placeholder="məs. Kvadrat tənliklər – test" /></Field>
          <Field label="Tarix"><input type="date" value={f.date} onChange={e => setF({ ...f, date: e.target.value })} /></Field>
          <Field label="Həll müddəti (dəq)"><input type="number" min={1} max={300} value={f.duration} onChange={e => setF({ ...f, duration: Number(e.target.value) })} /></Field>
          <Field label="Açılır"><input type="time" value={f.from} onChange={e => setF({ ...f, from: e.target.value })} /></Field>
          <Field label="Bağlanır"><input type="time" value={f.to} onChange={e => setF({ ...f, to: e.target.value })} /></Field>
          <Field label="Düzgün cavablar görünsün" full><select value={f.show} onChange={e => setF({ ...f, show: e.target.value })}>
            <option value="after_close">tapşırıq bağlandıqdan sonra</option><option value="after_submit">təhvil verdikdən dərhal sonra</option><option value="never">heç vaxt</option></select></Field>
          <label className="check full"><input type="checkbox" checked={f.shuffle} onChange={e => setF({ ...f, shuffle: e.target.checked })} /> Sualların sırası hər şagirdə fərqli</label>
        </div>
        {aud !== undefined && <TargetPicker ta={ta} value={aud} onChange={setTargets} />}
        {taskId && aud !== undefined && started > 0 && <p className="small muted" style={{ margin: 0 }}>Testə başlamış şagirdi auditoriyadan çıxarmaq olmaz – əlavə etmək olar.</p>}
        {!(bankFirst && !taskId) && bank}
        <fieldset><legend>Seçilmiş suallar ({qs.length})</legend>
          {qs.length === 0 ? <p className="small muted">Hələ sual yoxdur – yuxarıdan seçin və ya öz sualınızı yazın.</p> : (
            <div className="jlist">
              {qs.map((q, i) => editing === q.key && !locked ? (
                <QEdit key={q.key} q={q} onCancel={() => setEditing(null)} onSave={nq => { setQs(qs.map(x => x.key === q.key ? nq : x)); setEditing(null) }} />
              ) : (
                <div key={q.key} className="jrow cols" style={{ ['--cols' as any]: '28px minmax(0,1fr) auto', ['--mcols' as any]: '28px minmax(0,1fr)' }}>
                  <span className="num muted">{i + 1}.</span>
                  <span className="small"><span className="clamp2"><MathText text={q.text} /></span>
                    <span className="muted">{q.raw ? `${q.source || ''}${q.lesson ? ' · ' + q.lesson : ''}` : 'redaktə olunub / öz sualım'}{q.image ? ' · 🖼' : ''}</span></span>
                  {!locked && <span className="row" style={{ flexWrap: 'nowrap' }}>
                    <button className="btn sm" onClick={() => setEditing(q.key)}>Redaktə</button>
                    <button className="btn sm ghost" onClick={() => remove(q.key)} aria-label="Sil">✕</button></span>}
                </div>))}
            </div>)}
          {!locked && <OwnQuestion onAdd={q => add([q])} />}
        </fieldset>
        {problem && <p className="small" style={{ color: 'var(--warn)', margin: 0 }}>{problem}</p>}
        <ErrorBox error={err} />
      </div>
    </Drawer>
  )
}

// ---------------------------------------------------------------- viktorina: bir neçə mənbə və bölmə
/** kinds – yalnız bu növ fayllar (mövzu testi: movzu, diaqnostik; sınaq: sinaq, yekun); boş – hamısı. */
export function BankPicker({ has, add, remove, onTitle, disabled, first, kinds, legend }: { has: (k: string) => boolean; add: (q: Q[]) => void; remove: (k: string) => void; onTitle: (t: string) => void; disabled: boolean; first: boolean; kinds?: string[]; legend?: string }) {
  const [sources, setSources] = useState<any[]>([])
  const [srcSel, setSrcSel] = useState<string[]>([])
  const [lessons, setLessons] = useState<Record<string, any[]>>({})
  const [lesSel, setLesSel] = useState<{ id: number; src: string; label: string }[]>([])
  const [qByFile, setQByFile] = useState<Record<number, any[]>>({})
  const [filter, setFilter] = useState('')
  const [n, setN] = useState(10)
  const kindKey = kinds?.join(',') || ''
  useEffect(() => {
    get<any[]>('/api/bank/sources').then(x => setSources(x.filter(s => s.enabled && s.active &&
      (!kindKey || kindKey.split(',').some(k => (s.kinds || {})[k])))))
  }, [kindKey])
  useEffect(() => { srcSel.forEach(k => { if (!lessons[k]) get<any[]>('/api/bank/lessons', { source: k }).then(l => setLessons(x => ({ ...x, [k]: l }))) }) }, [srcSel])
  useEffect(() => { lesSel.forEach(l => { if (!qByFile[l.id]) get('/api/bank/questions', { file_id: l.id, limit: 200 }).then(r => setQByFile(x => ({ ...x, [l.id]: r.items }))) }) }, [lesSel])
  const label = (k: string) => (sources.find(s => s.key === k)?.label || k)
  const toggleSrc = (k: string) => setSrcSel(s => s.includes(k) ? s.filter(x => x !== k) : [...s, k])
  const toggleLes = (l: any, src: string) => setLesSel(s => {
    const next = s.some(x => x.id === l.id) ? s.filter(x => x.id !== l.id) : [...s, { id: l.id, src, label: l.label }]
    if (next.length === 1) onTitle(`${next[0].label} · ${label(next[0].src).split('·').pop()!.trim()}`.slice(0, 200))
    else if (next.length > 1) onTitle(`Test: ${next.length} bölmə`)
    return next
  })
  const groups = lesSel.map(l => ({ l, items: (qByFile[l.id] || []).map(q => fromBank(q, l.src, l.label)) }))
  const pool = groups.flatMap(g => g.items)
  const random = () => add([...pool.filter(q => !has(q.key))].sort(() => Math.random() - 0.5).slice(0, n))
  const list = (k: string) => (lessons[k] || []).filter(l => (!kinds || kinds.includes(l.kind || 'movzu')) &&
    (!filter || l.label.toLowerCase().includes(filter.toLowerCase())))
  return (
    <fieldset disabled={disabled}><legend>{legend || (first ? '1. Viktorinadan: mənbələr və bölmələr' : 'Test bazasından (viktorina – avtomatik yenilənir)')}</legend>
      <div className="stack">
        <div className="row" style={{ gap: 6 }}>
          {sources.map(s => <button key={s.key} type="button" className="chip" aria-pressed={srcSel.includes(s.key)} onClick={() => toggleSrc(s.key)}>{s.label} <span className="muted">({s.questions})</span></button>)}
        </div>
        {srcSel.length > 0 && (
          <>
            <input className="sel" placeholder="Bölmə / alt mövzu axtar" value={filter} onChange={e => setFilter(e.target.value)} />
            <div className="jlist" style={{ maxHeight: 220, overflow: 'auto' }}>
              {srcSel.map(k => (
                <div key={k}>
                  <div className="small" style={{ padding: '6px 12px', background: 'var(--surface-2)', fontWeight: 600 }}>{label(k)}</div>
                  {list(k).map(l => (
                    <label key={l.id} className="check" style={{ padding: '0 12px', minHeight: 36 }}>
                      <input type="checkbox" checked={lesSel.some(x => x.id === l.id)} onChange={() => toggleLes(l, k)} />
                      <span className="small">{l.label} <span className="muted">({l.questions}{l.grades?.length ? ` · ${l.grades.join(', ')}-cu sinif` : ''})</span></span></label>))}
                  {!lessons[k] && <p className="small muted" style={{ padding: '0 12px' }}>Yüklənir…</p>}
                </div>))}
            </div>
          </>)}
        {lesSel.length > 0 && (
          <>
            <div className="row">
              <span className="small">{lesSel.length} bölmə · {pool.length} sual</span>
              <button type="button" className="btn sm primary" onClick={() => add(pool)}>Hamısını əlavə et</button>
              <span className="small">Təsadüfi</span>
              <select className="grade-sel" value={n} onChange={e => setN(Number(e.target.value))}>{[5, 10, 15, 20, 25, 30, 40].map(x => <option key={x}>{x}</option>)}</select>
              <button type="button" className="btn sm" onClick={random}>seç</button>
            </div>
            <div className="jlist" style={{ maxHeight: 340, overflow: 'auto' }}>
              {groups.map(({ l, items }) => (
                <div key={l.id}>
                  <div className="row small" style={{ padding: '6px 12px', background: 'var(--surface-2)' }}>
                    <b className="grow">{l.label}</b>
                    <button type="button" className="btn sm ghost" onClick={() => add(items)}>hamısı ({items.length})</button>
                  </div>
                  {items.map(q => (
                    <label key={q.key} className="jrow cols" style={{ ['--cols' as any]: '24px minmax(0,1fr) auto', ['--mcols' as any]: '1fr', cursor: 'pointer' }}>
                      <input type="checkbox" checked={has(q.key)} onChange={() => (has(q.key) ? remove(q.key) : add([q]))} />
                      <span className="small clamp2"><MathText text={q.text} />{q.image ? ' 🖼' : ''}</span>
                      <Pill>{q.kind === 'mcq' ? 'variantlı' : 'açıq'}</Pill>
                    </label>))}
                  {!qByFile[l.id] && <p className="small muted" style={{ padding: '0 12px' }}>Yüklənir…</p>}
                </div>))}
            </div>
          </>)}
      </div>
    </fieldset>
  )
}

// ---------------------------------------------------------------- sual redaktəsi
function QEdit({ q, onSave, onCancel }: { q: Q; onSave: (q: Q) => void; onCancel: () => void }) {
  const [x, setX] = useState<Q>({ ...q, options: q.options.length ? [...q.options] : ['', '', '', ''] })
  const valid = x.text.trim() && (x.kind === 'mcq' ? x.options.filter(o => o.trim()).length >= 2 && (x.options[x.correct] || '').trim() : x.answer.trim())
  const save = () => {
    const kept = x.options.map((o, i) => [o.trim(), i] as const).filter(([o]) => o)
    onSave({ ...x, options: kept.map(([o]) => o), correct: Math.max(0, kept.findIndex(([, i]) => i === x.correct)), raw: null })
  }
  const preview = useMemo(() => x.text, [x.text])
  return (
    <div className="jrow cols" style={{ ['--cols' as any]: '1fr', ['--mcols' as any]: '1fr', gap: 8, background: 'var(--surface-2)' }}>
      <div className="row"><b className="grow">Sualı redaktə et</b>
        <select className="grade-sel" value={x.kind} onChange={e => setX({ ...x, kind: e.target.value as Q['kind'] })}><option value="mcq">variantlı</option><option value="open">açıq cavab</option></select></div>
      <textarea className="sel" style={{ minHeight: 70, padding: 10 }} value={x.text} onChange={e => setX({ ...x, text: e.target.value })} />
      {preview && /[$\\]/.test(preview) && <div className="small">Önbaxış: <MathText text={preview} /></div>}
      {x.image && <img className="q-img" src={x.image} alt="" style={{ maxHeight: 160 }} />}
      {x.kind === 'mcq' ? x.options.map((o, i) => (
        <label key={i} className="row" style={{ flexWrap: 'nowrap' }}>
          <input type="radio" checked={x.correct === i} onChange={() => setX({ ...x, correct: i })} aria-label={'Düzgün: ' + 'ABCDE'[i]} />
          <b>{'ABCDE'[i]})</b><input className="sel grow" value={o} onChange={e => { const y = [...x.options]; y[i] = e.target.value; setX({ ...x, options: y }) }} />
        </label>)) : <Field label="Düzgün cavab" hint="bir neçə qəbul edilən cavab «|» ilə: 2,5|5/2"><input value={x.answer} onChange={e => setX({ ...x, answer: e.target.value })} /></Field>}
      {x.kind === 'mcq' && x.options.length < 5 && <button type="button" className="btn sm ghost" onClick={() => setX({ ...x, options: [...x.options, ''] })}>+ variant</button>}
      <Field label="İzah (istəyə görə)"><textarea value={x.explanation} onChange={e => setX({ ...x, explanation: e.target.value })} /></Field>
      <div className="row"><button type="button" className="btn primary sm" disabled={!valid} onClick={save}>Yadda saxla</button><button type="button" className="btn sm" onClick={onCancel}>Ləğv et</button></div>
    </div>
  )
}

export function OwnQuestion({ onAdd }: { onAdd: (q: Q) => void }) {
  const [open, setOpen] = useState(false)
  if (!open) return <button type="button" className="btn sm" style={{ marginTop: 8 }} onClick={() => setOpen(true)}>+ Öz sualım</button>
  const blank: Q = { key: 'c' + Date.now(), kind: 'mcq', text: '', options: ['', '', '', ''], correct: 0, answer: '', explanation: '', image: null, bank_id: null, source: 'müəllim', lesson: null, raw: null }
  return <QEdit q={blank} onCancel={() => setOpen(false)} onSave={q => { onAdd({ ...q, key: 'c' + Date.now() }); setOpen(false) }} />
}
