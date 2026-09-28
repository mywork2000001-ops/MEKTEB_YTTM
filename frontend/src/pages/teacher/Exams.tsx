import { useEffect, useState } from 'react'
import { get, post, put } from '../../api'
import { AsyncBtn, Drawer, ErrorBox, Field, fmt, fmtDate, gradeTone, Pill, toast, useLoad } from '../../ui'
import type { MyLesson } from './common'

type Exam = { id: number; kind: 'KSQ' | 'BSQ'; no: number; semester: number; date: string; max_points: number; items: { n: number; points: number; standard?: string }[] | null }
type Planned = { kind: 'KSQ' | 'BSQ'; no: number; semester: number; date: string; topic: string; created: boolean }

export default function Exams({ ta }: { ta: MyLesson }) {
  const [d, err, , reload] = useLoad<{ has_summative: boolean; exams: Exam[]; planned: Planned[] }>(() => get(`/api/exams/${ta.id}`), [ta.id])
  const [create, setCreate] = useState<Planned | null>(null)
  const [open, setOpen] = useState<number | null>(null)
  if (d && !d.has_summative) return <div className="empty">Bu qrupda KSQ/BSQ keçirilmir – bütöv sinifdə keçirilir.</div>
  const byKey = new Map((d?.exams || []).map(e => [`${e.kind}-${e.semester}-${e.no}`, e]))
  return (
    <>
      <ErrorBox error={err} />
      <p className="small muted">Bal → faiz → qiymət: 0–30% → 2, 31–60% → 3, 61–80% → 4, 81–100% → 5.</p>
      <div className="jlist">
        {(d?.planned || []).map(p => {
          const e = byKey.get(`${p.kind}-${p.semester}-${p.no}`)
          return (
            <div className="jrow" key={`${p.kind}${p.semester}${p.no}`}>
              <span><b>{p.kind}-{p.no}</b> <span className="muted small">({p.semester}-ci yarımil) · {fmtDate(p.date)}</span><span className="sub small muted"><br />{p.topic}</span></span>
              {e ? <Pill tone="ok">{e.max_points} bal{e.items ? ` · ${e.items.length} tapşırıq` : ''}</Pill> : <Pill>yaradılmayıb</Pill>}
              {e ? <button className="btn sm primary" onClick={() => setOpen(e.id)}>Nəticələr</button> : <button className="btn sm" onClick={() => setCreate(p)}>Hazırla</button>}
            </div>)
        })}
        {d && !d.planned.length && <div className="empty">Planda KSQ/BSQ yoxdur (plan yüklənməyib?).</div>}
      </div>
      {create && <CreateExam ta={ta} p={create} onClose={() => setCreate(null)} onDone={id => { setCreate(null); reload(); setOpen(id) }} />}
      {open && <Scores ta={ta} examId={open} onClose={() => { setOpen(null); reload() }} />}
    </>
  )
}

function CreateExam({ ta, p, onClose, onDone }: { ta: MyLesson; p: Planned; onClose: () => void; onDone: (id: number) => void }) {
  const [mode, setMode] = useState<'total' | 'items'>('items')
  const [max, setMax] = useState(20)
  const [n, setN] = useState(10)
  const [pts, setPts] = useState(2)
  const [date, setDate] = useState(p.date)
  const [err, setErr] = useState<unknown>()
  const submit = async () => {
    try {
      const body: any = { kind: p.kind, no: p.no, semester: p.semester, date, title: p.topic }
      if (mode === 'items') body.items = Array.from({ length: n }, (_, i) => ({ n: i + 1, points: pts }))
      else body.max_points = max
      const e = await post<Exam>(`/api/exams/${ta.id}`, body)
      toast(`${p.kind}-${p.no} hazırlandı`)
      onDone(e.id)
    } catch (x) { setErr(x) }
  }
  return (
    <Drawer title={`${p.kind}-${p.no} hazırla`} onClose={onClose} footer={<><button className="btn" onClick={onClose}>Ləğv et</button><button className="btn primary" onClick={submit}>Yadda saxla</button></>}>
      <div className="stack">
        <Field label="Tarix"><input type="date" value={date} onChange={e => setDate(e.target.value)} /></Field>
        <div className="seg"><button aria-pressed={mode === 'items'} onClick={() => setMode('items')}>Tapşırıq üzrə (✓/✗)</button><button aria-pressed={mode === 'total'} onClick={() => setMode('total')}>Yalnız ümumi bal</button></div>
        {mode === 'items' ? (
          <div className="fg">
            <Field label="Tapşırıq sayı"><select value={n} onChange={e => setN(Number(e.target.value))}>{Array.from({ length: 40 }, (_, i) => <option key={i + 1}>{i + 1}</option>)}</select></Field>
            <Field label="Hər tapşırığın balı"><select value={pts} onChange={e => setPts(Number(e.target.value))}>{[0.5, 1, 1.5, 2, 2.5, 3, 4, 5].map(v => <option key={v}>{v}</option>)}</select></Field>
            <p className="full small muted">Maksimal bal: <b>{n * pts}</b></p>
          </div>
        ) : <Field label="Maksimal bal"><input type="number" min={1} value={max} onChange={e => setMax(Number(e.target.value))} /></Field>}
        <ErrorBox error={err} />
      </div>
    </Drawer>
  )
}

function Scores({ ta, examId, onClose }: { ta: MyLesson; examId: number; onClose: () => void }) {
  const [d, err, , reload] = useLoad<any>(() => get(`/api/exams/${ta.id}/${examId}`), [ta.id, examId])
  const [rows, setRows] = useState<Record<number, { points: string; marks: number[] | null; absent: boolean }>>({})
  useEffect(() => {
    if (!d) return
    setRows(Object.fromEntries(d.rows.map((r: any) => [r.student_id, {
      points: r.points == null ? '' : String(r.points), absent: r.absent,
      marks: d.exam.items ? (r.item_marks || d.exam.items.map(() => 0)) : null }])))
  }, [d])
  const items = d?.exam.items as Exam['items']
  const save = async () => {
    const body = Object.entries(rows).map(([sid, r]) => r.absent ? { student_id: Number(sid), absent: true }
      : items ? { student_id: Number(sid), item_marks: r.marks } : { student_id: Number(sid), points: r.points === '' ? null : Number(r.points.replace(',', '.')) })
    await put(`/api/exams/${ta.id}/${examId}/scores`, body)
    reload()
  }
  return (
    <Drawer title={d ? `${d.exam.kind}-${d.exam.no} · ${fmtDate(d.exam.date)} · ${d.exam.max_points} bal` : 'Nəticələr'} onClose={onClose}
      footer={<AsyncBtn className="btn primary" onClick={save} ok="Nəticələr yadda saxlanıldı">Yadda saxla</AsyncBtn>}>
      <ErrorBox error={err} />
      {d && (
        <>
          <div className="kpis" style={{ marginBottom: 12 }}>
            <div className="kpi"><b>{d.summary.written}</b><span>yazıb</span></div>
            <div className="kpi"><b>{fmt(d.summary.avg_pct)}%</b><span>orta</span></div>
            <div className="kpi"><b>{[5, 4, 3, 2].map(g => d.summary.distribution[g]).join(' / ')}</b><span>5 / 4 / 3 / 2</span></div>
          </div>
          <div className="jlist">
            {d.rows.map((r: any) => {
              const v = rows[r.student_id]
              if (!v) return null
              const set = (x: Partial<typeof v>) => setRows({ ...rows, [r.student_id]: { ...v, ...x } })
              return (
                <div className="jrow" key={r.student_id} style={{ gridTemplateColumns: '1fr', gap: 6 }}>
                  <div className="row"><b className="grow">{r.full_name}</b>
                    {r.grade != null && <Pill tone={gradeTone(r.grade)}>{fmt(r.pct)}% → {r.grade}</Pill>}
                    <label className="check small"><input type="checkbox" checked={v.absent} onChange={e => set({ absent: e.target.checked })} /> yox idi</label>
                  </div>
                  {!v.absent && (items ? (
                    <div className="att-btns">
                      {items.map((it, i) => (
                        <button key={i} className={v.marks?.[i] ? 'var' : 'yox'} aria-pressed title={`${it.n}: ${it.points} bal`}
                          onClick={() => { const m = [...(v.marks || [])]; m[i] = m[i] ? 0 : 1; set({ marks: m }) }}>{it.n}{v.marks?.[i] ? '✓' : '✗'}</button>))}
                      <span className="small muted">{(v.marks || []).reduce((a, m, i) => a + m * items[i].points, 0)} bal</span>
                    </div>
                  ) : (
                    <input className="sel" inputMode="decimal" style={{ maxWidth: 140 }} placeholder={`0–${d.exam.max_points}`} value={v.points} onChange={e => set({ points: e.target.value })} aria-label="Bal" />
                  ))}
                </div>)
            })}
          </div>
          {d.items?.length > 0 && (
            <section className="panel" style={{ marginTop: 14 }}>
              <h2>Tapşırıq təhlili</h2>
              {d.items.map((it: any) => (
                <div key={it.n} className="row small" style={{ marginBottom: 4 }}>
                  <span style={{ width: 38 }}>№{it.n}</span>
                  <div className="cmp grow" style={{ marginTop: 0 }}><i style={{ width: (it.pct || 0) + '%', background: (it.pct ?? 0) < 50 ? 'var(--bad)' : 'var(--accent)' }} /></div>
                  <span className="num" style={{ width: 48, textAlign: 'right' }}>{fmt(it.pct, 0)}%</span>
                </div>))}
              {d.standards.length > 0 && <><h2 style={{ marginTop: 12 }}>Standartlar</h2>
                {d.standards.map((s: any) => <div key={s.standard} className="row small"><span className="grow">{s.standard}</span><b>{fmt(s.pct, 0)}%</b></div>)}</>}
            </section>)}
        </>
      )}
    </Drawer>
  )
}
