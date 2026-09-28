import { useEffect, useState } from 'react'
import { get, post } from '../../api'
import { AsyncBtn, Drawer, ErrorBox, Field, fmt, gradeTone, PickFirst, Pill, toast, Top, useLoad } from '../../ui'
import { LessonSelect, useMyLessons, usePick } from './common'

type Task = { id: number; title: string; opens_at: string; closes_at: string; duration_min: number; questions: number; submitted: number; avg_pct: number | null }
const ml = (x: any) => (x ? x.az || x.ru || x.en || '' : '')
const dt = (s: string) => new Date(s).toLocaleString('az-AZ', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })

export default function Tasks() {
  const [lessons, err0] = useMyLessons()
  const [ta, setTa] = usePick('tasks')
  const [list, err, , reload] = useLoad<Task[] | null>(() => (ta ? get(`/api/tasks/${ta}`) : Promise.resolve(null)), [ta])
  const [creating, setCreating] = useState(false)
  const [open, setOpen] = useState<number | null>(null)
  return (
    <>
      <Top title="Onlayn tapşırıqlar" sub="Vaxtlı testlər: tarix + saat aralığı + həll müddəti; vaxt bitəndə avtomatik təhvil"
        actions={ta ? <button className="btn primary" onClick={() => setCreating(true)}>+ Yeni tapşırıq</button> : undefined} />
      <ErrorBox error={err0 || err} />
      <div className="toolbar"><LessonSelect lessons={lessons} value={ta} onChange={setTa} /></div>
      {!ta ? <PickFirst /> : (
        <div className="jlist">
          {list?.length === 0 && <div className="empty">Hələ tapşırıq yoxdur.</div>}
          {list?.map(t => {
            const now = Date.now(), o = Date.parse(t.opens_at), c = Date.parse(t.closes_at)
            return (
              <div className="jrow" key={t.id}>
                <span><b>{t.title}</b><span className="sub small muted"><br />{dt(t.opens_at)} – {dt(t.closes_at).slice(-5)} · {t.duration_min} dəq · {t.questions} sual</span></span>
                <span className="row">{now < o ? <Pill>gözlənilir</Pill> : now < c ? <Pill tone="ok">açıqdır</Pill> : <Pill tone="info">bağlanıb</Pill>}
                  <span className="small">{t.submitted} təhvil · orta {fmt(t.avg_pct)}%</span></span>
                <button className="btn sm" onClick={() => setOpen(t.id)}>Nəticələr</button>
              </div>)
          })}
        </div>
      )}
      {creating && ta && <CreateTask ta={ta} onClose={() => setCreating(false)} onDone={() => { setCreating(false); reload() }} />}
      {open && ta && <Results ta={ta} id={open} onClose={() => setOpen(null)} />}
    </>
  )
}

function CreateTask({ ta, onClose, onDone }: { ta: number; onClose: () => void; onDone: () => void }) {
  const today = new Date().toISOString().slice(0, 10)
  const [f, setF] = useState({ title: '', date: today, from: '15:00', to: '16:00', duration: 40, show: 'after_close', shuffle: true })
  const [sources] = useLoad<any[]>(() => get('/api/bank/sources'), [])
  const [src, setSrc] = useState('')
  const [lessons, setLessons] = useState<any[]>([])
  const [file, setFile] = useState<number | null>(null)
  const [qs, setQs] = useState<any[]>([])
  const [picked, setPicked] = useState<Map<number, any>>(new Map())
  const [n, setN] = useState(10)
  const [err, setErr] = useState<unknown>()
  useEffect(() => { setLessons([]); setFile(null); if (src) get(`/api/bank/lessons`, { source: src }).then(setLessons, setErr) }, [src])
  useEffect(() => { setQs([]); if (file) get('/api/bank/questions', { file_id: file, limit: 200 }).then(r => setQs(r.items), setErr) }, [file])
  const toggle = (q: any) => { const m = new Map(picked); m.has(q.id) ? m.delete(q.id) : m.set(q.id, q); setPicked(m) }
  const random = () => { const m = new Map(picked); [...qs].sort(() => Math.random() - 0.5).slice(0, n).forEach(q => m.set(q.id, q)); setPicked(m) }
  const submit = async () => {
    try {
      const iso = (t: string) => new Date(`${f.date}T${t}:00`).toISOString()
      await post(`/api/tasks/${ta}`, { title: f.title, opens_at: iso(f.from), closes_at: iso(f.to), duration_min: f.duration,
        bank_ids: [...picked.keys()], shuffle: f.shuffle, show_answers: f.show })
      toast('Tapşırıq yaradıldı')
      onDone()
    } catch (e) { setErr(e) }
  }
  return (
    <Drawer title="Yeni tapşırıq" onClose={onClose} footer={<><span className="small muted grow">{picked.size} sual seçilib</span><button className="btn" onClick={onClose}>Ləğv et</button><button className="btn primary" disabled={!f.title || !picked.size} onClick={submit}>Yarat</button></>}>
      <div className="stack">
        <div className="fg">
          <Field label="Ad" full><input value={f.title} onChange={e => setF({ ...f, title: e.target.value })} placeholder="məs. Kvadrat tənliklər – test" /></Field>
          <Field label="Tarix"><input type="date" value={f.date} onChange={e => setF({ ...f, date: e.target.value })} /></Field>
          <Field label="Həll müddəti (dəq)"><input type="number" min={1} max={300} value={f.duration} onChange={e => setF({ ...f, duration: Number(e.target.value) })} /></Field>
          <Field label="Açılır"><input type="time" value={f.from} onChange={e => setF({ ...f, from: e.target.value })} /></Field>
          <Field label="Bağlanır"><input type="time" value={f.to} onChange={e => setF({ ...f, to: e.target.value })} /></Field>
          <Field label="Düzgün cavablar görünsün" full><select value={f.show} onChange={e => setF({ ...f, show: e.target.value })}>
            <option value="after_close">tapşırıq bağlanandan sonra</option><option value="after_submit">təhvil verəndən dərhal sonra</option><option value="never">heç vaxt</option></select></Field>
          <label className="check full"><input type="checkbox" checked={f.shuffle} onChange={e => setF({ ...f, shuffle: e.target.checked })} /> Sualların sırası hər şagirdə fərqli</label>
        </div>
        <fieldset><legend>Test bazasından suallar (viktorina – avtomatik yenilənir)</legend>
          <div className="stack">
            <select className="sel" value={src} onChange={e => setSrc(e.target.value)}><option value="">— mənbə —</option>
              {(sources || []).filter(s => s.enabled && s.active).map(s => <option key={s.key} value={s.key}>{s.label} ({s.questions})</option>)}</select>
            {src && <select className="sel" value={file ?? ''} onChange={e => setFile(e.target.value ? Number(e.target.value) : null)}><option value="">— dərs / variant —</option>
              {lessons.map(l => <option key={l.id} value={l.id}>{l.label} ({l.questions})</option>)}</select>}
            {qs.length > 0 && <div className="row"><span className="small">Təsadüfi</span><select className="grade-sel" value={n} onChange={e => setN(Number(e.target.value))}>{[5, 10, 15, 20, 25, 30].map(x => <option key={x}>{x}</option>)}</select><button className="btn sm" onClick={random}>sual seç</button></div>}
            <div className="jlist" style={{ maxHeight: 360, overflow: 'auto' }}>
              {qs.map(q => (
                <label key={q.id} className="jrow" style={{ gridTemplateColumns: '24px minmax(0,1fr) auto', cursor: 'pointer' }}>
                  <input type="checkbox" checked={picked.has(q.id)} onChange={() => toggle(q)} />
                  <span className="small">{q.n}. {ml(q.text).slice(0, 180)}{q.image ? ' 🖼' : ''}</span>
                  <Pill>{q.kind === 'mcq' ? 'variantlı' : 'açıq'}</Pill>
                </label>))}
            </div>
          </div>
        </fieldset>
        <ErrorBox error={err} />
      </div>
    </Drawer>
  )
}

function Results({ ta, id, onClose }: { ta: number; id: number; onClose: () => void }) {
  const [d, err, , reload] = useLoad<any>(() => get(`/api/tasks/${ta}/${id}`), [ta, id])
  return (
    <Drawer title={d?.task.title || 'Nəticələr'} onClose={onClose} footer={<AsyncBtn onClick={async () => reload()}>Yenilə</AsyncBtn>}>
      <ErrorBox error={err} />
      {d && (
        <div className="stack">
          <div className="jlist">{d.rows.map((r: any) => (
            <div className="jrow" key={r.student_id} style={{ gridTemplateColumns: 'minmax(0,1fr) auto' }}>
              <span>{r.full_name}{r.auto_submitted && <span className="small muted"> · vaxt bitdi</span>}</span>
              <span className="row">{r.status === 'təhvil verib' ? <><span className="small">{r.correct}/{r.total}</span><Pill tone={gradeTone(r.grade)}>{fmt(r.pct, 0)}% → {r.grade}</Pill></> : <Pill>{r.status}</Pill>}</span>
            </div>))}</div>
          <section className="panel"><h2>Suallar üzrə</h2>
            {d.questions.map((q: any) => (
              <div key={q.index} className="row small" style={{ marginBottom: 6 }}>
                <span className="grow">{q.index + 1}. {ml(q.text).slice(0, 90)}</span>
                <div className="cmp" style={{ width: 120, marginTop: 0 }}><i style={{ width: (q.pct || 0) + '%', background: (q.pct ?? 100) < 50 ? 'var(--bad)' : 'var(--accent)' }} /></div>
                <b className="num" style={{ width: 44, textAlign: 'right' }}>{fmt(q.pct, 0)}%</b>
              </div>))}
          </section>
        </div>)}
    </Drawer>
  )
}
