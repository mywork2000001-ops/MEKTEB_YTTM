import { useEffect, useState } from 'react'
import { get, post, put } from '../../api'
import { AsyncBtn, Drawer, ErrorBox, Field, fmt, fmtDate, gradeTone, Pill, toast, useLoad } from '../../ui'
import type { MyLesson } from './common'
import { head, printDoc, table } from '../../print'

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
            <div className="jrow cols" key={`${p.kind}${p.semester}${p.no}`} style={{ ['--cols' as any]: 'minmax(0,1fr) auto auto', ['--mcols' as any]: 'minmax(0,1fr) auto' }}>
              <span><b>{p.kind}-{p.no}</b> <span className="muted small">({p.semester}-ci yarımil) · {fmtDate(p.date)}</span><span className="sub small muted"><br />{p.topic}</span></span>
              {e ? <Pill tone="ok">{e.max_points} bal{e.items ? ` · ${e.items.length} tapşırıq` : ''}</Pill> : <Pill>yaradılmayıb</Pill>}
              {e ? <button className="btn sm primary" onClick={() => setOpen(e.id)}>Nəticələr</button> : <button className="btn sm" onClick={() => setCreate(p)}>Hazırla</button>}
            </div>)
        })}
        {d && !d.planned.length && <div className="empty">Planda KSQ/BSQ yoxdur (plan yüklənməyib?).</div>}
      </div>
      {create && <CreateExam ta={ta} p={create} prev={(d?.planned || []).filter(x => x.semester === create.semester && x.date < create.date).map(x => x.date).sort().pop() || null} onClose={() => setCreate(null)} onDone={id => { setCreate(null); reload(); setOpen(id) }} />}
      {open && <Scores ta={ta} examId={open} onClose={() => { setOpen(null); reload() }} />}
    </>
  )
}

function CreateExam({ ta, p, prev, onClose, onDone }: { ta: MyLesson; p: Planned; prev: string | null; onClose: () => void; onDone: (id: number) => void }) {
  const [mode, setMode] = useState<'total' | 'items'>('items')
  const [plan] = useLoad<any[]>(() => get(`/api/plan/${ta.id}/official`), [ta.id])
  // bu summativin əhatə etdiyi mövzuların standartları: əvvəlki KSQ/BSQ-dan bu günə qədər (eyni yarımil)
  const stds = [...new Set((plan || []).filter(l => l.semester === p.semester && l.official_date <= p.date && (!prev || l.official_date > prev))
    .flatMap(l => l.standards || []))].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
  const [itemStd, setItemStd] = useState<Record<number, string>>({})
  const [max, setMax] = useState(20)
  const [n, setN] = useState(10)
  const [pts, setPts] = useState(2)
  const [date, setDate] = useState(p.date)
  const [err, setErr] = useState<unknown>()
  const submit = async () => {
    try {
      const body: any = { kind: p.kind, no: p.no, semester: p.semester, date, title: p.topic }
      if (mode === 'items') body.items = Array.from({ length: n }, (_, i) => ({ n: i + 1, points: pts, standard: itemStd[i + 1] || null }))
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
            {stds.length > 0 && <fieldset className="full"><legend>Tapşırıq → məzmun standartı <span className="hint">(standart təhlili üçün)</span></legend>
              <div className="fg">{Array.from({ length: n }, (_, i) => (
                <Field key={i} label={`№${i + 1}`}><select value={itemStd[i + 1] || ''} onChange={e => setItemStd({ ...itemStd, [i + 1]: e.target.value })}>
                  <option value="">—</option>{stds.map(s => <option key={s}>{s}</option>)}</select></Field>))}</div>
              <p className="small muted" style={{ margin: 0 }}>Standartlar bu summativin əhatə etdiyi mövzulardan (perspektiv plan) götürülüb.</p>
            </fieldset>}
          </div>
        ) : <Field label="Maksimal bal"><input type="number" min={1} value={max} onChange={e => setMax(Number(e.target.value))} /></Field>}
        <ErrorBox error={err} />
      </div>
    </Drawer>
  )
}

function Scores({ ta, examId, onClose }: { ta: MyLesson; examId: number; onClose: () => void }) {
  const [d, err, , reload] = useLoad<any>(() => get(`/api/exams/${ta.id}/${examId}`), [ta.id, examId])
  const [rows, setRows] = useState<Record<number, { points: string; marks: number[] | null; absent: boolean; later: boolean; taken_on: string }>>({})
  useEffect(() => {
    if (!d) return
    setRows(Object.fromEntries(d.rows.map((r: any) => [r.student_id, {
      points: r.points == null ? '' : String(r.points), absent: r.absent,
      later: !!r.taken_on, taken_on: r.taken_on || '',
      marks: r.item_marks || null }])))                       // null = hələ daxil edilməyib (0 bal deyil!)
  }, [d])
  const items = d?.exam.items as Exam['items']
  const save = async () => {
    const body = Object.entries(rows).map(([sid, r]) => r.absent ? { student_id: Number(sid), absent: true }
      : { student_id: Number(sid), taken_on: r.later && r.taken_on && (items ? r.marks : r.points !== '') ? r.taken_on : null,
          ...(items ? { item_marks: r.marks } : { points: r.points === '' ? null : Number(r.points.replace(',', '.')) }) })
    await put(`/api/exams/${ta.id}/${examId}/scores`, body)
    reload()
  }
  return (
    <Drawer title={d ? `${d.exam.kind}-${d.exam.no} · ${fmtDate(d.exam.date)} · ${d.exam.max_points} bal` : 'Nəticələr'} onClose={onClose}
      footer={<>{d && <button className="btn" onClick={() => printDoc({ title: `${ta.class_name} – ${d.exam.kind}-${d.exam.no} nəticələri`, body: head(`${ta.class_name} – ${d.exam.kind}-${d.exam.no} (${d.exam.semester}-ci yarımil)`, `${fmtDate(d.exam.date)} · maksimal bal ${d.exam.max_points} · orta ${fmt(d.summary.avg_pct)}%`) + table(['№', 'Şagird', 'Bal', '%', 'Qiymət'], d.rows.map((r: any, i: number) => [i + 1, r.full_name + (r.taken_on ? ` (sonradan: ${fmtDate(r.taken_on)})` : ''), r.absent ? 'yox idi' : fmt(r.points), fmt(r.pct), r.grade ?? '—']), [2, 3, 4]) + (d.items?.length ? '<h2>Tapşırıq təhlili</h2>' + table(['Tapşırıq', 'Bal', 'Standart', 'Həll %'], d.items.map((it: any) => [it.n, it.points, it.standard || '', fmt(it.pct, 0)]), [1, 3]) : '') })}>Çap / PDF</button>}<AsyncBtn className="btn primary" onClick={save} ok="Nəticələr yadda saxlanıldı">Yadda saxla</AsyncBtn></>}>
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
                <div className="jrow cols" key={r.student_id} style={{ ['--cols' as any]: '1fr', ['--mcols' as any]: '1fr', gap: 6 }}>
                  <div className="row"><b className="grow">{r.full_name}</b>
                    {r.grade != null && <Pill tone={gradeTone(r.grade)}>{fmt(r.pct)}% → {r.grade}</Pill>}
                    {r.taken_on && <Pill tone="info">sonradan: {fmtDate(r.taken_on)}</Pill>}
                    <label className="check small"><input type="checkbox" checked={v.absent} onChange={e => set({ absent: e.target.checked, later: false })} /> yox idi</label>
                    {!v.absent && <label className="check small" title="Üzrlü səbəbdən imtahan günü olmayıb, sonradan yazıb"><input type="checkbox" checked={v.later} onChange={e => set({ later: e.target.checked })} /> sonradan yazdı</label>}
                    {!v.absent && v.later && <input type="date" className="sel" style={{ maxWidth: 160 }} min={d.exam.date} value={v.taken_on} onChange={e => set({ taken_on: e.target.value })} aria-label="Yazdığı tarix" />}
                  </div>
                  {!v.absent && (items ? (
                    <div className="att-btns">
                      {items.map((it, i) => (
                        <button key={i} className={v.marks ? (v.marks[i] ? 'var' : 'yox') : ''} aria-pressed={!!v.marks} title={`${it.n}: ${it.points} bal`}
                          onClick={() => { const m = [...(v.marks || items.map(() => 0))]; m[i] = m[i] ? 0 : 1; set({ marks: m }) }}>{it.n}{v.marks ? (v.marks[i] ? '✓' : '✗') : '·'}</button>))}
                      {v.marks ? <span className="small muted">{v.marks.reduce((a, m, i) => a + m * items[i].points, 0)} bal</span>
                        : <button className="btn sm ghost" onClick={() => set({ marks: items.map(() => 0) })}>daxil et</button>}
                      {v.marks && <button className="btn sm ghost" onClick={() => set({ marks: null })} title="Nəticəni sil (hələ yazmayıb)">təmizlə</button>}
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
                {d.standards.map((s: any) => <div key={s.standard} className="row small"><span className="grow">{s.standard}</span>{s.pct != null && s.pct < 50 && <Pill tone="bad">təkrar tövsiyə olunur</Pill>}<b>{fmt(s.pct, 0)}%</b></div>)}</>}
            </section>)}
        </>
      )}
    </Drawer>
  )
}
