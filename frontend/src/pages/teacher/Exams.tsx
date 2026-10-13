import { useEffect, useState } from 'react'
import { api, del, get, patch, post, put } from '../../api'
import { AsyncBtn, ConfirmName, Drawer, ErrorBox, Field, fmt, fmtDate, gradeTone, Loading, Pill, toast, useLoad } from '../../ui'
import type { MyLesson } from './common'
import { head, printDoc, SIGN, table } from '../../print'
import { tt } from '../../i18n'
import { printKey, printSheets, type KsqPrint } from '../../ksqPrint'
import ScanCamera from '../../scanCamera'

type Exam = { id: number; kind: 'KSQ' | 'BSQ'; no: number; semester: number; date: string; max_points: number; items: { n: number; points: number; standard?: string }[] | null }
type Planned = { kind: 'KSQ' | 'BSQ'; no: number; semester: number; date: string; topic: string; created: boolean }

export default function Exams({ ta }: { ta: MyLesson }) {
  const [d, err, , reload] = useLoad<{ has_summative: boolean; exams: Exam[]; planned: Planned[] }>(() => get(`/api/exams/${ta.id}`), [ta.id])
  const [create, setCreate] = useState<Planned | null>(null)
  const [open, setOpen] = useState<number | null>(null)
  const [vars, setVars] = useState<Exam | null>(null)
  const [edit, setEdit] = useState<Exam | null>(null)
  const [delAsk, setDelAsk] = useState<Exam | null>(null)
  if (d && !d.has_summative) return <div className="empty">Bu qrupda KSQ/BSQ keçirilmir – bütöv sinifdə keçirilir.</div>
  const byKey = new Map((d?.exams || []).map(e => [`${e.kind}-${e.semester}-${e.no}`, e]))
  return (
    <>
      <ErrorBox error={err} />
      <p className="small muted">Bal → faiz → qiymət: 0–30% → 2, 31–60% → 3, 61–80% → 4, 81–100% → 5.</p>
      {/* arxiv: siniflər və tarix üzrə ZIP – Google Drive-da saxlamaq üçün; sonra kart şəkilləri serverdən silinə bilər */}
      {d && d.exams.length > 0 && <div className="row" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
        <a className="btn sm" href={`/api/exam-archive/zip?ta_id=${ta.id}`} title={tt('Siniflər və tarix üzrə qovluqlar: variantlar, açar, nəticələr, kart şəkilləri')}>📦 {tt('KSQ arxivi (ZIP)')}</a>
        <a className="btn sm ghost" href="/api/exam-archive/zip">📦 {tt('Bütün siniflərim')}</a>
        <AsyncBtn className="btn sm ghost" title={tt('Arxivi Google Drive-a yüklədikdən sonra: kart şəkilləri serverdən silinir (bal və jurnal qalır)')}
          onClick={async () => { if (!window.confirm(tt('Arxivi endirib Google Drive-a yüklədinizmi? Kart şəkilləri serverdən silinəcək.'))) return; const r = await post<{ removed: number }>(`/api/exam-archive/purge-images?ta_id=${ta.id}`); toast(tt('Silinən şəkil: {n}', { n: r.removed })) }}>🧹 {tt('Şəkilləri serverdən sil')}</AsyncBtn>
      </div>}
      <div className="jlist">
        {(d?.planned || []).map(p => {
          const e = byKey.get(`${p.kind}-${p.semester}-${p.no}`)
          return (
            <div className="jrow cols" key={`${p.kind}${p.semester}${p.no}`} style={{ ['--cols' as any]: 'minmax(0,1fr) auto auto', ['--mcols' as any]: 'minmax(0,1fr) auto' }}>
              <span><b>{p.kind}-{p.no}</b> <span className="muted small">({p.semester}-ci yarımil) · {fmtDate(p.date)}</span><span className="sub small muted"><br />{p.topic}</span></span>
              {e ? <Pill tone="ok">{e.max_points} bal{e.items ? ` · ${e.items.length} tapşırıq` : ''}</Pill> : <Pill>yaradılmayıb</Pill>}
              {e ? <span className="row" style={{ gap: 4, flexWrap: 'wrap' }}><button className="btn sm ghost" onClick={() => setEdit(e)} title={tt('Tarixi və başlığı dəyiş')}>✏</button>
                <button className="btn sm ghost" onClick={() => setDelAsk(e)} title={tt('Sil')}>🗑</button>
                <button className="btn sm" onClick={() => setVars(e)} title={tt('Hər şagirdə fərqli 30 sual · bir A4 + cavab kartı')}>🖨 {tt('Kağız variantlar')}</button>
                <button className="btn sm primary" onClick={() => setOpen(e.id)}>Nəticələr</button></span> : <button className="btn sm" onClick={() => setCreate(p)}>Hazırla</button>}
            </div>)
        })}
        {/* yaradılmış, amma planda olmayan imtahanlar da görünsün (plan dəyişib və ya plansız yaradılıb) */}
        {(d?.exams || []).filter(e => !(d?.planned || []).some(p => p.kind === e.kind && p.semester === e.semester && p.no === e.no)).map(e => (
          <div className="jrow cols" key={'x' + e.id} style={{ ['--cols' as any]: 'minmax(0,1fr) auto auto', ['--mcols' as any]: 'minmax(0,1fr) auto' }}>
            <span><b>{e.kind}-{e.no}</b> <span className="muted small">({e.semester}-ci yarımil) · {fmtDate(e.date)}</span><span className="sub small muted"><br />{tt('planda yoxdur')}</span></span>
            <Pill tone="ok">{e.max_points} bal{e.items ? ` · ${e.items.length} tapşırıq` : ''}</Pill>
            <span className="row" style={{ gap: 4, flexWrap: 'wrap' }}><button className="btn sm ghost" onClick={() => setEdit(e)} title={tt('Tarixi və başlığı dəyiş')}>✏</button>
              <button className="btn sm ghost" onClick={() => setDelAsk(e)} title={tt('Sil')}>🗑</button>
              <button className="btn sm" onClick={() => setVars(e)}>🖨 {tt('Kağız variantlar')}</button>
              <button className="btn sm primary" onClick={() => setOpen(e.id)}>Nəticələr</button></span>
          </div>))}
        {d && !d.planned.length && !d.exams.length && <div className="empty">Planda KSQ/BSQ yoxdur (plan yüklənməyib?).</div>}
      </div>
      {create && <CreateExam ta={ta} p={create} prev={(d?.planned || []).filter(x => x.semester === create.semester && x.date < create.date).map(x => x.date).sort().pop() || null} onClose={() => setCreate(null)} onDone={id => { setCreate(null); reload(); setOpen(id) }} />}
      {open && <Scores ta={ta} examId={open} onClose={() => { setOpen(null); reload() }} />}
      {vars && <Variants ta={ta} e={vars} onClose={() => { setVars(null); reload() }} />}
      {edit && <EditExam ta={ta} e={edit} onClose={() => setEdit(null)} onDone={() => { setEdit(null); reload() }} />}
      {delAsk && <ConfirmName name={`${delAsk.kind}-${delAsk.no}`} action={tt('Birdəfəlik sil (nəticələr, variantlar və skanlar da)')} onCancel={() => setDelAsk(null)}
        onConfirm={async () => { const r = await del<{ scores: number; variants: number; scans: number }>(`/api/exams/${ta.id}/${delAsk.id}`); toast(tt('Silindi: nəticə {a}, variant {b}, skan {c}', { a: r.scores, b: r.variants, c: r.scans })); setDelAsk(null); reload() }} />}
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
      footer={<>{d && <button className="btn" onClick={() => printDoc({ signers: [{ role: 'Fənn müəllimi' }, SIGN.deputy()], title: `${ta.class_name} – ${d.exam.kind}-${d.exam.no} nəticələri`, body: head(`${ta.class_name} – ${d.exam.kind}-${d.exam.no} (${d.exam.semester}-ci yarımil)`, `${fmtDate(d.exam.date)} · maksimal bal ${d.exam.max_points} · orta ${fmt(d.summary.avg_pct)}%`) + table(['№', 'Şagird', 'Bal', '%', 'Qiymət'], d.rows.map((r: any, i: number) => [i + 1, r.full_name + (r.taken_on ? ` (sonradan: ${fmtDate(r.taken_on)})` : ''), r.absent ? 'yox idi' : fmt(r.points), fmt(r.pct), r.grade ?? '—']), [2, 3, 4]) + (d.items?.length ? '<h2>Tapşırıq təhlili</h2>' + table(['Tapşırıq', 'Bal', 'Standart', 'Həll %'], d.items.map((it: any) => [it.n, it.points, it.standard || '', fmt(it.pct, 0)]), [1, 3]) : '') })}>Çap / PDF</button>}<AsyncBtn className="btn primary" onClick={save} ok="Nəticələr yadda saxlanıldı">Yadda saxla</AsyncBtn></>}>
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

type Sources = { source: string; projects?: { key: string; label: string; default: boolean; files: number }[]; plan: { seq: number; topic: string; files: { file_id: number; label: string; questions: number }[] }[]
  all: { file_id: number; label: string; questions: number }[] }
type VarRes = { exam: Exam; variants: { student_id: number; full_name: string | null; code: string }[]
  report: { open_pct: number; [k: string]: unknown } | null; stale?: boolean }
type Ready = { students: number; n: number; need: number; ok: boolean; max_n: number | null; share: number | null
  topics: { topic: string; files: number; mcq: number; open: number; templates: number }[]; selected: { mcq: number; open: number }
  shortage: { slot?: number; kind?: string; level?: string; missing: number }[] }

/** Addım kartı: nömrəli dairə + başlıq + vəziyyət; aktiv addım vurğulanır (docs/ksq-movzu-dizayn-promtu.md D). */
function Step({ no, title, state, active, children }: { no: number; title: string; state?: string; active?: boolean; children?: React.ReactNode }) {
  return (
    <section className={'kstep' + (active ? ' on' : '')}>
      <header><span className="kno">{no}</span><b>{title}</b>{state && <span className="kstate">{state}</span>}</header>
      {children && <div className="kbody">{children}</div>}
    </section>
  )
}

/** KSQ/BSQ kağız variantları: 1 Hazırlıq (yalnız keçilmiş mövzular) → 2 Variantlar → 3 Çap → 4 Skan. */
function Variants({ ta, e, onClose }: { ta: MyLesson; e: Exam; onClose: () => void }) {
  const [d, err, , reload] = useLoad<VarRes>(() => get(`/api/exams/${ta.id}/${e.id}/variants`), [e.id])
  const [fail, setFail] = useState<string | null>(null)
  const [n, setN] = useState(30)
  const [src, setSrc] = useState<Sources | null>(null)
  const [mode, setMode] = useState<'plan' | 'add' | 'only'>('plan')
  const [pickd, setPickd] = useState<number[]>([])
  const [projs, setProjs] = useState<string[]>([])           // seçilmiş test layihələri (boş – sinfin əsas layihəsi)
  const [ready, setReady] = useState<Ready | null>(null)
  const [checking, setChecking] = useState(false)
  const [openV, setOpenV] = useState<number | null>(null)
  const [sibs, setSibs] = useState<{ ta_id: number; class_name: string; exam_id: number | null; variants: boolean; locked: boolean }[]>([])
  const [also, setAlso] = useState<number[]>([])
  useEffect(() => { get<typeof sibs>(`/api/exams/${ta.id}/${e.id}/siblings`).then(setSibs, () => setSibs([])) }, [e.id])   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { get<Sources>(`/api/exams/${ta.id}/${e.id}/sources`, projs.length ? { sources: projs.join(',') } : undefined).then(setSrc, () => setSrc(null)) }, [e.id, projs.join(',')])   // eslint-disable-line react-hooks/exhaustive-deps
  const body = () => ({ n, file_ids: mode === 'plan' ? null : pickd, only_mine: mode === 'only', sources: projs.length ? projs : null })
  // hazırlıq: seçim dəyişəndə hovuz yenidən yoxlanır (kiçik gecikmə ilə)
  useEffect(() => {
    if (mode !== 'plan' && !pickd.length) { setReady(null); return }
    setChecking(true)
    const t = setTimeout(() => { post<Ready>(`/api/exams/${ta.id}/${e.id}/readiness`, body()).then(setReady, () => setReady(null)).finally(() => setChecking(false)) }, 350)
    return () => clearTimeout(t)
  }, [n, mode, pickd.join(','), projs.join(',')])   // eslint-disable-line react-hooks/exhaustive-deps
  const make = async () => {
    setFail(null)
    try {
      if (also.length) {                     // eyni proqramlı siniflər də – hər sinfin nəticəsi ayrıca
        const r = await post<{ ta_id: number; ok: boolean; error?: string }[]>(`/api/exams/${ta.id}/${e.id}/variants-multi`, { ...body(), ta_ids: [ta.id, ...also] })
        const name = (id: number) => id === ta.id ? ta.class_name : sibs.find(x => x.ta_id === id)?.class_name || id
        toast(r.map(x => `${name(x.ta_id)}: ${x.ok ? '✓' : '⚠ ' + (x.error || '')}`).join(' · '))
        if (r.some(x => !x.ok)) setFail(r.filter(x => !x.ok).map(x => `${name(x.ta_id)}: ${x.error}`).join(' · '))
      } else { await post(`/api/exams/${ta.id}/${e.id}/variants`, body()); toast(tt('Variantlar hazırdır')) }
      reload()
    } catch (x) { setFail((x as Error).message); throw x }
  }
  const load = () => get<KsqPrint>(`/api/exams/${ta.id}/${e.id}/variants/print`)
  const has = !!d?.variants.length
  const ok = !!ready?.ok
  return (
    <Drawer title={`${e.kind}-${e.no} · ${tt('Kağız variantlar')}`} onClose={onClose}>
      <ErrorBox error={err} />
      {d?.stale && <div className="kverdict warn" style={{ marginTop: 0 }}>⚠ {tt('Bu variantlar köhnə qaydalarla yaradılıb – mövzuya uyğun olmayan sual ola bilər. 1-ci addımda «Yenidən yarat» basın (nəticə yazılıbsa – sualları 2-ci addımda tək-tək əvəz edin).')}
        <div style={{ marginTop: 6 }}><AsyncBtn className="btn sm primary" onClick={async () => { const r = await post<{ fixed: number; failed: number; students: number }>(`/api/exams/${ta.id}/${e.id}/fix-offtopic`); toast(tt('Əvəz olundu: {n} sual ({s} şagird)', { n: r.fixed, s: r.students }) + (r.failed ? ' · ⚠ ' + r.failed : '') + ' · ' + tt('çap olunubsa – vərəqi yenidən çap edin')); reload() }}>🧹 {tt('Uyğunsuz sualları avtomatik düzəlt')}</AsyncBtn></div></div>}
      <div className="ksteps">
        <Step no={1} title={tt('Hazırlıq: mövzular və testlər')} active={!has} state={checking ? '…' : ready ? (ok ? '✓ ' + tt('hazırdır') : '⚠ ' + tt('sual çatmır')) : undefined}>
          <p className="small muted" style={{ margin: '0 0 8px' }}>{tt('Suallar yalnız bu imtahana qədər keçilmiş mövzulardan seçilir (perspektiv plan). Sinifdə hər şagirdin sualları fərqlidir.')}</p>
          <div className="lsel-bar">
            <label className="lsel"><span>{tt('Sual sayı')}</span>
              <select className="sel" value={n} onChange={x => setN(Number(x.target.value))}>{[10, 12, 15, 18, 20, 24, 25, 30].map(k => <option key={k} value={k}>{tt('{n} sual · 100 bal', { n: k })}</option>)}</select></label>
            <label className="lsel"><span>{tt('Testlər')}</span>
              <select className="sel" value={mode} onChange={x => setMode(x.target.value as typeof mode)}>
                <option value="plan">{tt('Perspektiv plandan (hər mövzunun öz testləri)')}</option>
                <option value="add">{tt('Plan + özüm əlavə edirəm')}</option>
                <option value="only">{tt('Yalnız özüm seçdiklərim')}</option></select></label>
          </div>
          {src?.projects && src.projects.length > 1 && <div style={{ marginTop: 8 }}>
            <span className="small" style={{ fontWeight: 600 }}>{tt('Test layihələri')}:</span>{' '}
            {src.projects.map(p => { const on = projs.length ? projs.includes(p.key) : p.default
              return <button key={p.key} className="chip" aria-pressed={on} title={tt('{n} fayl', { n: p.files })} style={{ margin: '2px 4px 2px 0' }}
                onClick={() => { const cur = projs.length ? projs : src.projects!.filter(x => x.default).map(x => x.key); const nx = on ? cur.filter(k => k !== p.key) : [...cur, p.key]; setProjs(nx.length ? nx : []) }}>{p.label}</button> })}
            <p className="small muted" style={{ margin: '2px 0 0' }}>{tt('Mövzuya uyğun testlər seçilmiş layihələrdən avtomatik götürülür; başqa layihəni qoşmaq üçün üzərinə toxunun.')}</p></div>}
          <p className="small muted" style={{ margin: '8px 0 0' }}>{tt('Suallar yalnız layihənin testlərindən (X–XI: P0010 Blok İmtahan), şablon yoxdur. Təkrarı sistem özü ən az səviyyədə seçir.')}</p>
          {mode !== 'plan' && src && <div className="kpick">
            {src.all.map(f => <label key={f.file_id} className="check small"><input type="checkbox" checked={pickd.includes(f.file_id)}
              onChange={x => setPickd(p => x.target.checked ? [...p, f.file_id] : p.filter(i => i !== f.file_id))} />{f.label} <span className="muted">({f.questions})</span></label>)}
            <p className="small muted" style={{ margin: '4px 0 0' }}>{tt('Seçildi: {n}', { n: pickd.length })}</p></div>}
          {ready && <>
            <div className="tbl-wrap" style={{ marginTop: 8 }}><table className="ktbl">
              <thead><tr><th>{tt('Mövzu')}</th><th className="r">{tt('Fayl')}</th><th className="r">{tt('Test')}</th><th className="r">{tt('Açıq')}</th></tr></thead>
              <tbody>{ready.topics.map((t, i) => <tr key={i} className={t.mcq + t.open === 0 ? (t.files ? 'shared' : 'bad') : ''}>
                <td title={t.topic}>{t.topic.length > 70 ? t.topic.slice(0, 68) + '…' : t.topic}{t.mcq + t.open === 0 && t.files > 0 && <span className="small muted"> · {tt('faylı qonşu mövzu ilə ortaqdır – sualları orada sayılır')}</span>}</td>
                <td className="r num">{t.files}</td><td className="r num">{t.mcq}</td><td className="r num">{t.open}</td></tr>)}
                {(ready.selected.mcq + ready.selected.open > 0) && <tr><td><i>{tt('Seçdiyim testlər')}</i></td><td /><td className="r num">{ready.selected.mcq}</td><td className="r num">{ready.selected.open}</td></tr>}</tbody></table></div>
            <p className={'small kverdict ' + (ok ? 'ok' : 'warn')}>{tt('{s} şagird × {n} sual = {need} sual lazımdır.', { s: ready.students, n: ready.n, need: ready.need })}{' '}
              {ok ? (ready.share && ready.share > 1 ? tt('Hər sual ən çox {k} şagirddə olacaq (bankda sual az olduğuna görə – ən az mümkün təkrar).', { k: ready.share }) : tt('Hər şagirdin sualları fərqlidir.')) : ready.max_n ? tt('Bu seçimlə ən çox {m} sual mümkündür.', { m: ready.max_n }) : tt('Bu seçimlə variant yaratmaq olmur.')}</p>
            {!ok && <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
              {ready.max_n && <button className="btn sm" onClick={() => setN([10, 12, 15, 18, 20, 24, 25, 30].filter(k => k <= ready.max_n!).pop() || 10)}>↓ {tt('Sual sayını azalt ({m})', { m: ready.max_n })}</button>}
              {mode === 'plan' && <button className="btn sm" onClick={() => setMode('add')}>＋ {tt('Test əlavə et')}</button>}
            </div>}
          </>}
          {sibs.length > 0 && <div className="kpick" style={{ maxHeight: 'none' }}>
            <b className="small">{tt('Eyni proqramlı siniflər – eyni ayarlarla birlikdə hazırla')}</b>
            {sibs.map(x => <label key={x.ta_id} className="check small"><input type="checkbox" disabled={x.locked} checked={also.includes(x.ta_id)}
              onChange={ev => setAlso(p => ev.target.checked ? [...p, x.ta_id] : p.filter(i => i !== x.ta_id))} />{x.class_name}
              <span className="muted"> · {x.locked ? tt('nəticə yazılıb – dəyişmir') : x.exam_id ? (x.variants ? tt('variantlar var – yenilənəcək') : tt('imtahan var')) : tt('imtahan yaradılacaq')}</span></label>)}
            <p className="small muted" style={{ margin: '4px 0 0' }}>{tt('Siniflər arasında suallar ən çox 20 % təkrarlanır.')}</p></div>}
          {fail && <div className="small" style={{ color: 'var(--bad)', marginTop: 6, whiteSpace: 'pre-wrap' }}>{fail}</div>}
          <div className="row" style={{ marginTop: 10, gap: 6 }}>
            <AsyncBtn className={'btn ' + (has ? 'ghost sm' : 'primary')} disabled={!ok} onClick={make}>{has ? '↻ ' + tt('Yenidən yarat') : tt('Variantları yarat')}</AsyncBtn></div>
        </Step>
        <Step no={2} title={tt('Variantlar')} active={has} state={has ? tt('{n} şagird', { n: d!.variants.length }) : undefined}>
          {has ? <>
            <p className="small muted" style={{ margin: '0 0 6px' }}>{tt('Şagirdə toxunun – sualları görün, əvəz edin, düzəldin və ya ləğv edin.')}</p>
            <div className="kvars2">{d!.variants.map(v => <button key={v.student_id} className={'chip' + (openV === v.student_id ? ' on' : '')} aria-pressed={openV === v.student_id}
              onClick={() => setOpenV(openV === v.student_id ? null : v.student_id)}>{v.full_name || '—'} <span className="muted">{v.code}</span></button>)}</div>
            {openV && <VariantView ta={ta.id} examId={e.id} sid={openV} name={d!.variants.find(v => v.student_id === openV)?.full_name || ''}
              annulled={new Set(((d!.exam.items || []) as any[]).filter(it => it.annulled).map(it => it.n))} onChange={reload} />}
          </>
            : <p className="small muted" style={{ margin: 0 }}>{tt('Əvvəl 1-ci addım.')}</p>}
        </Step>
        <Step no={3} title={tt('Çap')} active={has}>
          {has ? <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
            <AsyncBtn className="btn primary" onClick={async () => printSheets(await load())}>🖨 {tt('Vərəqləri çap et (A4)')}</AsyncBtn>
            <AsyncBtn className="btn" onClick={async () => printKey(await load())}>🔑 {tt('Müəllim açarı')}</AsyncBtn>
            <span className="small muted">{tt('İki üzlü çap edin: hər şagirdə bir vərəq + cavab kartı.')}</span></div>
            : <p className="small muted" style={{ margin: 0 }}>{tt('Variantlar hazır olanda.')}</p>}
        </Step>
        <Step no={4} title={tt('Skan və nəticə')} active={has}>
          {has ? <Scans ta={ta.id} examId={e.id} /> : <p className="small muted" style={{ margin: 0 }}>{tt('Yazıdan sonra kartları skan edin – bal jurnala özü yazılır.')}</p>}
        </Step>
      </div>
    </Drawer>
  )
}

type Scan = { id: number; student_id: number; full_name: string | null; code: string; status: 'pending' | 'graded' | 'error'; points: number | null
  flagged: number[]; reading: { slot: number; value: string | null; confidence: number | null }[] | null; marks: number[] | null; error: string | null; rescans: number; lost: number[]; n: number | null }
type ScanList = { scans: Scan[]; missing: string[]; claude: boolean; counts: { variants: number; scanned: number; graded: number; pending: number; flagged: number } }
const SCAN_TONE: Record<string, 'ok' | 'warn' | 'bad'> = { graded: 'ok', pending: 'warn', error: 'bad' }

/** Cavab kartlarının skanı: şəkil / PDF yüklə → QR ilə şagird → oxunuş → bal jurnala özü yazılır; şübhəli xana – sarı, müəllim düzəldir. */
function Scans({ ta, examId }: { ta: number; examId: number }) {
  const [d, err, , reload] = useLoad<ScanList>(() => get(`/api/exam-scans/${ta}/${examId}`), [examId])
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState<number | null>(null)
  const [cam, setCam] = useState(false)
  const [again, setAgain] = useState(false)         // yenidən skan: köhnə skanlar əvəz olunur (bir blank – bir dəfə qaydasından istisna)
  const upUrl = `/api/exam-scans/${ta}/${examId}/upload` + (again ? '?replace=true' : '')
  const send = async (files: FileList | null) => {
    if (!files?.length) return
    const form = new FormData()
    Array.from(files).forEach(f => form.append('files', f))
    setBusy(true)
    try {
      const r = await api<{ found: { full_name: string | null }[]; problems: { file: string; error: string; kind?: string; full_name?: string | null }[];
        already?: { full_name: string | null }[] }>(upUrl, { method: 'POST', form })
      const al = r.already || []
      toast(tt('Tapılan kart: {n}', { n: r.found.length })
        + (al.length ? ' · ' + tt('artıq skan olunub (təkrar göndərilmədi): {names}', { names: al.map(x => x.full_name || '—').join(', ') }) : '')
        + (r.problems.length ? ' · ' + r.problems.map(p => `${p.file}: ${p.kind === 'partial' ? (p.full_name ? p.full_name + ' – ' : '') + tt('Kart kadra tam düşməyib – bütün kartı çərçivəyə salıb yenidən çəkin') : p.error}`).join('; ') : ''))
      reload()
    } catch (x) { toast((x as Error).message) } finally { setBusy(false) }
  }
  const c = d?.counts
  // oxunuş gedir – siyahı özü yenilənir (Claude adətən 10–30 saniyəyə oxuyur)
  useEffect(() => { if (!c?.pending || !d?.claude) return; const id = setTimeout(reload, 8000); return () => clearTimeout(id) }, [d])
  return (
    <section>
      <p className="small muted" style={{ marginTop: 0 }}>{tt('Kartların şəklini çəkin və ya skan PDF yükləyin – bir şəkildə bir neçə kart ola bilər. Şagird QR koddan tanınır, bal və qiymət jurnala özü yazılır.')}</p>
      <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
        <button type="button" className="btn sm primary" onClick={() => setCam(true)} title={tt('Kamera açıq qalır, kartları bir-bir çəkin')}>📷 {tt('Ardıcıl skan')}</button>
        <label className="btn sm">📷 {tt('Kamera')}
          <input type="file" accept="image/*" capture="environment" hidden disabled={busy} onChange={e => { send(e.target.files); e.target.value = '' }} /></label>
        <label className="btn sm">🖼 {tt('Şəkil / PDF seç')}
          <input type="file" accept="image/*,application/pdf" multiple hidden disabled={busy} onChange={e => { send(e.target.files); e.target.value = '' }} /></label>
        {d && d.scans.length > 0 && <AsyncBtn className="btn sm ghost" onClick={async () => { await post(`/api/exam-scans/${ta}/${examId}/regrade`); reload() }}
          title={tt('Bütün kartlar mövcud açarla yenidən hesablanır')}>🔄 {tt('Yenilə')}</AsyncBtn>}
        {d && d.scans.length > 0 && d.claude && <AsyncBtn className="btn sm ghost" onClick={async () => { await post(`/api/exam-scans/${ta}/${examId}/reread`); reload() }}
          title={tt('Kartlar Claude-a təzədən göndərilir (əl düzəlişləri də silinir)')}>👁 {tt('Yenidən oxu')}</AsyncBtn>}
        {d && d.scans.length > 0 && <label className="small row" style={{ gap: 4 }} title={tt('Kartlar yenidən skan olunanda köhnə skan və oxunuş əvəz olunur')}>
          <input type="checkbox" checked={again} onChange={e => setAgain(e.target.checked)} />{tt('Yenidən skan (köhnəni əvəz et)')}</label>}
        {busy && <span className="small muted">{tt('Yüklənir…')}</span>}
      </div>
      {cam && <ScanCamera url={`/api/exam-scans/${ta}/${examId}/upload`} replaceAll={again} onClose={() => { setCam(false); reload() }} onSent={reload} />}
      <ErrorBox error={err} />
      {d && !d.claude && <p className="small" style={{ margin: '8px 0 0', color: 'var(--warn)' }}>{tt('Süni intellekt bağlantısı yoxdur: kartlar oxunmağı gözləyəcək. Tənzimləmələr → «Süni intellekt» → OpenRouter və ya Anthropic açarını daxil edin (OpenRouter-də şəkil oxuyan model: Claude, Gemini, GPT-4o).')}</p>}
      {c && <p className="small" style={{ margin: '8px 0 4px' }}>{tt('Skan: {a}/{b} · yoxlanılıb: {c} · oxunmağı gözləyir: {p}', { a: c.scanned, b: c.variants, c: c.graded, p: c.pending })}
        {c.flagged > 0 && <> · <b style={{ color: 'var(--warn)' }}>{tt('baxılmalı: {n}', { n: c.flagged })}</b></>}</p>}
      {d && d.missing.length > 0 && <p className="small muted" style={{ margin: '0 0 6px' }}>{tt('Kartı yoxdur')}: {d.missing.join(', ')}</p>}
      <div className="jlist">
        {d?.scans.map(s => (
          <div key={s.id} className="jrow" style={{ display: 'block' }}>
            <div className="row" style={{ gap: 6, flexWrap: 'wrap', cursor: 'pointer' }} onClick={() => setOpen(o => (o === s.id ? null : s.id))}>
              <b className="grow">{s.full_name || '—'} <span className="small muted">{s.code}</span></b>
              <Pill tone={SCAN_TONE[s.status]}>{s.status === 'graded' ? `${fmt(s.points)} ${tt('bal')}` : tt(s.status === 'pending' ? 'oxunmağı gözləyir' : 'xəta')}</Pill>
              {s.flagged.length > 0 && <Pill tone="warn">⚠ {s.flagged.length}</Pill>}
            </div>
            {s.error && <div className="small" style={{ color: 'var(--bad)' }}>{s.error}</div>}
            {open === s.id && <ScanDetail s={s} onChange={reload} />}
          </div>))}
      </div>
    </section>
  )
}

function ScanDetail({ s, onChange }: { s: Scan; onChange: () => void }) {
  const val = (slot: number) => s.reading?.find(r => r.slot === slot)?.value ?? ''
  const fix = async (slot: number, value: string) => {
    try { await put(`/api/exam-scans/${s.id}/slot`, { slot, value: value.trim() || null }); onChange() } catch (x) { toast((x as Error).message) }
  }
  // variantın öz sual sayı (10–30) – həmişə 30 deyil
  const n = s.n || Math.max(0, ...(s.reading || []).map(r => r.slot)) || 30
  const lost = new Set(s.lost || [])
  const toggleLost = async (slot: number) => {
    const next = new Set(lost); if (next.has(slot)) next.delete(slot); else next.add(slot)
    try { await put(`/api/exam-scans/${s.id}/lost`, { slots: [...next] }); onChange() } catch (x) { toast((x as Error).message) }
  }
  return (
    <div style={{ marginTop: 8 }}>
      <img src={`/api/exam-scans/image/${s.id}`} alt="" style={{ width: '100%', border: '1px solid var(--line)', borderRadius: 6 }} />
      {s.reading ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(92px,1fr))', gap: 4, marginTop: 6 }}>
          {Array.from({ length: n }, (_, i) => i + 1).map(slot => {
            const ok = s.marks?.[slot - 1] === 1, flag = s.flagged.includes(slot), gone = lost.has(slot)
            return (
              <label key={slot} className="small" style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '2px 4px', borderRadius: 6,
                background: gone ? '#e5e7eb' : flag ? '#fef3c7' : ok ? '#dcfce7' : '#fee2e2', color: '#111', opacity: gone ? .7 : 1 }}>
                <b style={{ minWidth: 18, textDecoration: gone ? 'line-through' : undefined }}>{slot}</b>
                <input defaultValue={val(slot)} maxLength={8} disabled={gone} style={{ width: '100%', minWidth: 0, padding: '2px 4px' }}
                  onBlur={e => { if (e.target.value !== val(slot)) fix(slot, e.target.value) }} />
                <button type="button" className="btn sm ghost" style={{ padding: '0 3px' }} onClick={() => toggleLost(slot)}
                  title={gone ? tt('Sayılsın (vərəqdə var idi)') : tt('Vərəqdə yox idi – sayılmasın')}>⊘</button></label>)
          })}
        </div>) : <p className="small muted">{tt('Kart hələ oxunmayıb.')}</p>}
      {lost.size > 0 && <p className="small muted" style={{ margin: '4px 0 0' }}>{tt('Vərəqdə görünməyən suallar sayılmır, bal qalanlar üzrə 100-ə hesablanır: {list}', { list: [...lost].sort((a, b) => a - b).join(', ') })}</p>}
    </div>
  )
}

/** KSQ/BSQ redaktəsi: tarix və başlıq (nəticə yazılıbsa da olar); bal və tapşırıq quruluşu toxunulmur. */
function EditExam({ ta, e, onClose, onDone }: { ta: MyLesson; e: Exam & { title?: string | null }; onClose: () => void; onDone: () => void }) {
  const [date, setDate] = useState(e.date)
  const [title, setTitle] = useState(e.title || '')
  const save = async () => {
    await patch(`/api/exams/${ta.id}/${e.id}`, { kind: e.kind, no: e.no, semester: e.semester, date, title: title.trim() || null,
      max_points: e.max_points, items: e.items })
    toast(tt('Yadda saxlanıldı')); onDone()
  }
  return (
    <Drawer title={`${e.kind}-${e.no} · ${tt('Redaktə')}`} onClose={onClose} footer={<AsyncBtn className="btn primary" onClick={save}>{tt('Yadda saxla')}</AsyncBtn>}>
      <div className="fg">
        <Field label={tt('Tarix')}><input type="date" value={date} onChange={x => setDate(x.target.value)} /></Field>
        <Field label={tt('Başlıq / qeyd')}><input value={title} maxLength={300} onChange={x => setTitle(x.target.value)} /></Field>
      </div>
      <p className="small muted">{tt('Bal və tapşırıqların quruluşu burada dəyişmir (kağız variantlarda sual sayı «Yenidən yarat» ilə).')}</p>
    </Drawer>
  )
}

type VQ = { slot: number; kind: 'mcq' | 'open'; level: string; points: number; text: any; options?: any[] | null; correct?: number | null
  answer?: string | null; topic?: string | null; topic_actual?: string | null; bank_id?: number | null; template?: string | null; replaced?: boolean; edited?: boolean }
const LET = 'ABCDE'
const az = (x: any) => (x && typeof x === 'object' ? x.az ?? Object.values(x)[0] : x) ?? ''

/** Variantın sualları: 🔄 əvəz et · ✏ redaktə · ⊘ slotu hamı üçün ləğv et · 🔄 bu slotu bütün şagirdlərdə əvəz et. */
function VariantView({ ta, examId, sid, name, annulled, onChange }: { ta: number; examId: number; sid: number; name: string; annulled: Set<number>; onChange: () => void }) {
  const [qs, setQs] = useState<VQ[] | null>(null)
  const [edit, setEdit] = useState<number | null>(null)
  const load = () => get<any>(`/api/exams/${ta}/${examId}/variants`).then(d => setQs(d.variants.find((v: any) => v.student_id === sid)?.questions || []))
  useEffect(() => { load() }, [sid])   // eslint-disable-line react-hooks/exhaustive-deps
  const act = async (fn: () => Promise<unknown>, ok: string) => { try { await fn(); toast(ok + ' · ' + tt('çap olunubsa – vərəqi yenidən çap edin')); await load(); onChange() } catch (x) { toast((x as Error).message) } }
  if (!qs) return <Loading />
  return (
    <div className="vview">
      <p className="small muted" style={{ margin: '4px 0 8px' }}>{name}: {tt('{n} sual', { n: qs.length })}</p>
      {qs.sort((a, b) => a.slot - b.slot).map(q => (
        <div key={q.slot} className={'vq' + (annulled.has(q.slot) ? ' off' : '')}>
          <div className="row" style={{ gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
            <span className="vno">{q.slot}</span>
            <span className="small muted grow">{q.topic_actual || q.topic || '—'} · {q.kind === 'mcq' ? tt('test') : tt('açıq')} · {q.level} · {String(q.points).replace('.', ',')} {tt('bal')}
              {q.replaced && ' · 🔄'}{q.edited && ' · ✏'}{annulled.has(q.slot) && <b style={{ color: 'var(--bad)' }}> · {tt('ləğv edilib')}</b>}</span>
            <AsyncBtn className="btn sm ghost" title={tt('Bu şagirddə başqa sualla əvəz et (eyni mövzu, növ və çətinlik)')}
              onClick={() => act(() => post(`/api/exams/${ta}/${examId}/variants/${sid}/${q.slot}/replace`, { hide_in_bank: false }), tt('Sual əvəz olundu'))}>🔄</AsyncBtn>
            <button className="btn sm ghost" title={tt('Redaktə et')} onClick={() => setEdit(edit === q.slot ? null : q.slot)}>✏</button>
            <AsyncBtn className="btn sm ghost" title={tt('Bu slotu BÜTÜN şagirdlərdə yeni sualla əvəz et')}
              onClick={() => act(() => post(`/api/exams/${ta}/${examId}/slots/${q.slot}/replace-all`, {}), tt('Slot bütün şagirdlərdə əvəz olundu'))}>🔄👥</AsyncBtn>
            <AsyncBtn className="btn sm ghost" title={annulled.has(q.slot) ? tt('Ləğvi geri qaytar') : tt('Səhv sual: bu slotu hamı üçün ləğv et (bal 100-ə miqyaslanır)')}
              onClick={() => act(() => post(`/api/exams/${ta}/${examId}/slots/${q.slot}/annul`, { annulled: !annulled.has(q.slot) }), annulled.has(q.slot) ? tt('Ləğv geri qaytarıldı') : tt('Slot ləğv edildi'))}>⊘</AsyncBtn>
          </div>
          <div className="vtext">{az(q.text)}</div>
          {q.kind === 'mcq' ? <div className="small">{(q.options || []).map((o, i) => <span key={i} style={{ marginRight: 10, fontWeight: i === q.correct ? 800 : 400 }}>{LET[i]}) {az(o)}{i === q.correct ? ' ✓' : ''}</span>)}</div>
            : <div className="small">{tt('Cavab')}: <b>{q.answer}</b></div>}
          {q.bank_id && <AsyncBtn className="btn sm ghost" title={tt('Bankdakı səhv sual: bir daha heç bir varianta düşməsin və bu şagirddə əvəz olunsun')}
            onClick={() => act(() => post(`/api/exams/${ta}/${examId}/variants/${sid}/${q.slot}/replace`, { hide_in_bank: true }), tt('Sual bankda gizlədildi və əvəz olundu'))}>🚫 {tt('Bankda gizlət')}</AsyncBtn>}
          {edit === q.slot && <QEdit q={q} onSave={body => act(() => put(`/api/exams/${ta}/${examId}/variants/${sid}/${q.slot}`, body), tt('Yadda saxlanıldı')).then(() => setEdit(null))} />}
        </div>))}
    </div>
  )
}

function QEdit({ q, onSave }: { q: VQ; onSave: (b: any) => Promise<void> }) {
  const [text, setText] = useState<string>(az(q.text))
  const [opts, setOpts] = useState<string[]>((q.options || []).map(az))
  const [cor, setCor] = useState<number>(q.correct ?? 0)
  const [ans, setAns] = useState<string>(q.answer || '')
  return (
    <div className="fg" style={{ marginTop: 6, padding: 8, border: '1px dashed var(--line)', borderRadius: 8 }}>
      <Field label={tt('Sualın mətni')}><textarea rows={3} value={text} onChange={x => setText(x.target.value)} /></Field>
      {q.kind === 'mcq' ? opts.map((o, i) => (
        <label key={i} className="row small" style={{ gap: 6 }}><input type="radio" checked={cor === i} onChange={() => setCor(i)} /> {LET[i]})
          <input className="grow" value={o} onChange={x => setOpts(p => p.map((v, k) => (k === i ? x.target.value : v)))} /></label>))
        : <Field label={tt('Düzgün cavab (kart xanaları: rəqəm, - , / ;)')}><input value={ans} maxLength={8} onChange={x => setAns(x.target.value)} /></Field>}
      <AsyncBtn className="btn sm primary" onClick={() => onSave(q.kind === 'mcq' ? { text, options: opts, correct: cor } : { text, answer: ans })}>{tt('Yadda saxla')}</AsyncBtn>
    </div>
  )
}
