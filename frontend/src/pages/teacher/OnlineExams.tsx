// Sınaq imtahanları (onlayn): planla əlaqəsiz, bir neçə sinfə eyni anda. Nəticə – «Sınaq jurnalı» (bal, faiz, sinifdə və
// ümumi yer), siniflərin reytinqi, sual analizi, açıq sualın əl ilə yoxlanması, kumulyativ reytinq. Formativ jurnala düşmür.
import { StudentPicker } from './common'
import { useEffect, useMemo, useState } from 'react'
import { del as apiDel, get, post, put } from '../../api'
import { MathText } from '../../MathText'
import { ConfirmName, Drawer, ErrorBox, Field, fmt, Loading, Pill, Seg, Stat, toast, Top, useLoad } from '../../ui'
import { esc, head, printDoc, table } from '../../print'
import { BankPicker, iso, localParts, OwnQuestion, toCustom, type Q } from './TaskEditor'
import { TaskActions } from './Tasks'
import { PeriodBar, usePeriod } from '../../periods'

type Target = { ta_id: number; class_name: string; subject: string; grade: number | null; teacher: string; mine: boolean; students: number }
type Exam = { id: number; title: string; subject: string; grade: number | null; classes: string[]; opens_at: string | null; closes_at: string | null
  questions: number; mine: boolean; wrote: number; avg_pct: number | null; state: 'gözlənilir' | 'açıqdır' | 'bitib' }
type Row = { student_id: number | null; full_name: string | null; class_name: string; task_id: number; status: 'yazıb' | 'yazmayıb' | 'yazır'
  correct: number | null; wrong: number | null; blank: number | null; points: number | null; pct: number | null; grade: number | null
  place_all: number | null; place_class: number | null; retake: boolean }
type Res = { batch: { id: number; title: string; subject: string; grade: number | null; penalty: number; questions: number }
  summary: { students: number; wrote: number; avg_pct: number | null; max_pct: number | null; min_pct: number | null }
  classes: { task_id: number; ta_id: number; own: boolean; class_name: string; students: number; wrote: number; avg_pct: number | null; max_pct: number | null; place: number | null; state: string; opens_at: string; closes_at: string }[]
  rows: Row[]; questions: { index: number; text: any; kind: string; correct: number; of: number; pct: number | null }[]; access: 'full' | 'own' }

const ml = (x: any) => (x ? (typeof x === 'string' ? x : x.az || x.ru || x.en || '') : '')
const dt = (s: string | null) => (s ? new Date(s).toLocaleString('az-AZ', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—')
const stateTone = (s: string) => (s === 'açıqdır' ? 'ok' : s === 'bitib' ? 'info' : undefined)
const PENALTY: [string, string][] = [['0', 'cərimə yoxdur'], ['4', '4 səhv 1 düzü aparır'], ['3', '3 səhv 1 düzü aparır']]

export default function OnlineExams() {
  const [view, setView] = useState<'list' | 'rating'>('list')
  const [list, err, loading, reload] = useLoad<Exam[]>(() => get('/api/exams-online'), [])
  const [creating, setCreating] = useState(false)
  const [open, setOpen] = useState<number | null>(null)
  const f = usePeriod('exams', 'date')
  const all = list || []
  const shown = all.filter(x => !x.opens_at || f.has(x.opens_at)).sort(f.sort === 'topic'
    ? (a, b) => a.title.localeCompare(b.title, 'az', { numeric: true }) || Date.parse(b.opens_at || '') - Date.parse(a.opens_at || '')
    : (a, b) => Date.parse(b.opens_at || '') - Date.parse(a.opens_at || ''))
  return (
    <>
      <Top title="Sınaq imtahanları" sub="Onlayn sınaq bir neçə sinfə eyni anda · sınaq jurnalı · sinif və ümumi reytinq (formativ qiymətə təsir etmir)"
        actions={<button className="btn primary" onClick={() => setCreating(true)}>+ Yeni sınaq</button>} />
      <div className="toolbar"><Seg value={view} onChange={setView} options={[['list', 'Sınaqlar'], ['rating', 'Reytinq']]} /></div>
      <ErrorBox error={err} />
      {view === 'rating' ? <Rating /> : loading && !list ? <Loading /> : (
        <>{all.length > 0 && <PeriodBar f={f} count={shown.length} total={all.length} topicLabel="Ad üzrə" />}
        <div className="jlist">
          {list?.length === 0 && <div className="empty">Hələ sınaq yoxdur – «+ Yeni sınaq» ilə test bazasından sınaq seçin.</div>}
          {all.length > 0 && shown.length === 0 && <div className="empty">Bu dövrdə sınaq yoxdur – «‹ ›» ilə başqa dövrə keçin və ya «Hamısı»nı seçin.</div>}
          {shown.map(x => (
            <div key={x.id} className="jrow cols click" onClick={() => setOpen(x.id)} style={{ ['--cols' as any]: 'minmax(0,1fr)', ['--mcols' as any]: '1fr', gap: 6 }}>
              <div className="row"><b className="grow">{x.title}</b><Pill tone={stateTone(x.state)}>{x.state}</Pill>{x.mine && <Pill tone="acc">mənim</Pill>}</div>
              <span className="small muted">{x.subject}{x.grade ? ` · ${x.grade}-cu sinif` : ''} · {x.classes.join(', ')} · {dt(x.opens_at)} – {dt(x.closes_at)} · {x.questions} sual · {x.wrote} yazıb{x.avg_pct != null ? ` · orta ${fmt(x.avg_pct)}%` : ''}</span>
            </div>))}
        </div></>)}
      {creating && <NewExam onClose={() => setCreating(false)} onDone={() => { setCreating(false); reload() }} />}
      {open && <Results id={open} onClose={() => setOpen(null)} onChange={reload} />}
    </>
  )
}

// ---------------------------------------------------------------- yeni sınaq
type TRow = { on: boolean; d1: string; t1: string; d2: string; t2: string; ids?: number[] | null }   // ids: null – bütün sinif

function NewExam({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [targets, setTargets] = useState<Target[] | null>(null)
  const [subject, setSubject] = useState('')
  const [common, setCommon] = useState(() => { const t = localParts(new Date().toISOString())[0]; return { d1: t, t1: '10:00', d2: t, t2: '12:00' } })
  const [rows, setRows] = useState<Record<number, TRow>>({})
  const [f, setF] = useState({ title: '', duration: 60, penalty: '0', shuffle: true, show: 'after_close' })
  const [qs, setQs] = useState<Q[]>([])
  const [err, setErr] = useState<unknown>()
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    get<Target[]>('/api/exams-online/targets').then(t => { setTargets(t); setSubject(t[0]?.subject || '') }, setErr)
  }, [])
  const subjects = useMemo(() => [...new Set((targets || []).map(t => t.subject))], [targets])
  const shown = (targets || []).filter(t => t.subject === subject)
  const row = (id: number): TRow => rows[id] || { on: false, ...common }
  const set = (id: number, p: Partial<TRow>) => setRows(r => ({ ...r, [id]: { ...row(id), ...p } }))
  const chosen = shown.filter(t => row(t.ta_id).on)
  const has = (k: string) => qs.some(q => q.key === k)
  const add = (list: Q[]) => setQs(cur => [...cur, ...list.filter(q => !cur.some(c => c.key === q.key))])
  const remove = (k: string) => setQs(cur => cur.filter(q => q.key !== k))
  const toAll = () => setRows(r => Object.fromEntries(Object.entries(r).map(([k, v]) => [k, { ...v, ...common }])))
  const minutes = (r: TRow) => (Date.parse(iso(r.d2, r.t2)) - Date.parse(iso(r.d1, r.t1))) / 60000

  const problem = !f.title.trim() ? 'Sınağın adını yazın' : !qs.length ? 'Ən azı 1 sual seçin' : !chosen.length ? 'Ən azı bir sinif seçin'
    : chosen.some(t => minutes(row(t.ta_id)) <= 0) ? 'Bitmə vaxtı başlamadan sonra olmalıdır'
    : chosen.some(t => minutes(row(t.ta_id)) < f.duration) ? 'Həll müddəti açıq qalma aralığından uzundur'
    : chosen.some(t => row(t.ta_id).ids?.length === 0) ? '«Kimə» bölməsində ən azı bir şagird seçin' : ''
  const submit = async () => {
    if (problem) { setErr(new Error(problem)); return }
    setBusy(true)
    try {
      const r = await post<{ tasks: number }>('/api/exams-online', {
        title: f.title.trim(), duration_min: f.duration, penalty: Number(f.penalty), shuffle: f.shuffle, show_answers: f.show,
        bank_ids: [], custom: qs.map(toCustom),
        targets: chosen.map(t => { const x = row(t.ta_id); return { ta_id: t.ta_id, opens_at: iso(x.d1, x.t1), closes_at: iso(x.d2, x.t2), student_ids: x.ids ?? null } }),
      })
      toast(`Sınaq ${r.tasks} sinfə göndərildi`)
      onDone()
    } catch (e) { setErr(e) } finally { setBusy(false) }
  }
  return (
    <Drawer title="Yeni sınaq imtahanı" onClose={onClose}
      footer={<><span className="small muted grow">{qs.length} sual · {chosen.length} sinif</span><button className="btn" onClick={onClose}>Ləğv et</button>
        <button className="btn primary" disabled={busy} onClick={submit}>Göndər</button></>}>
      {!targets ? (err ? <ErrorBox error={err} /> : <Loading />) : (
        <div className="stack">
          <div className="fg">
            <Field label="Ad" full><input value={f.title} maxLength={200} placeholder="məs. Buraxılış sınağı №1" onChange={e => setF({ ...f, title: e.target.value })} /></Field>
            <Field label="Həll müddəti (dəq)"><input type="number" min={1} max={300} value={f.duration} onChange={e => setF({ ...f, duration: Number(e.target.value) })} /></Field>
            <Field label="Bal hesabı"><select value={f.penalty} onChange={e => setF({ ...f, penalty: e.target.value })}>{PENALTY.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field>
            <Field label="Düzgün cavablar görünsün" full><select value={f.show} onChange={e => setF({ ...f, show: e.target.value })}>
              <option value="after_close">sınaq bağlandıqdan sonra</option><option value="after_submit">təhvil verdikdən dərhal sonra</option><option value="never">heç vaxt</option></select></Field>
            <label className="check full"><input type="checkbox" checked={f.shuffle} onChange={e => setF({ ...f, shuffle: e.target.checked })} /> Sualların sırası hər şagirdə fərqli (köçürmənin qarşısını alır)</label>
          </div>
          <fieldset><legend>Siniflər və vaxt</legend>
            {subjects.length > 1 && <div className="row" style={{ marginBottom: 8 }}><span className="small">Fənn</span>
              <select className="sel" value={subject} onChange={e => { setSubject(e.target.value); setRows({}) }}>{subjects.map(s => <option key={s}>{s}</option>)}</select></div>}
            <div className="row" style={{ gap: 6, marginBottom: 8 }}>
              <span className="small">Hamısı üçün: başlama</span>
              <input type="date" className="sel" value={common.d1} onChange={e => setCommon({ ...common, d1: e.target.value, d2: e.target.value > common.d2 ? e.target.value : common.d2 })} />
              <input type="time" className="sel" value={common.t1} onChange={e => setCommon({ ...common, t1: e.target.value })} />
              <span className="small">bitmə</span>
              <input type="date" className="sel" value={common.d2} onChange={e => setCommon({ ...common, d2: e.target.value })} />
              <input type="time" className="sel" value={common.t2} onChange={e => setCommon({ ...common, t2: e.target.value })} />
              <button type="button" className="btn sm" onClick={toAll}>Seçilənlərə tətbiq et</button>
            </div>
            <p className="small muted" style={{ margin: '0 0 8px' }}>Tövsiyə: sınaq üçün bir gün, 2–3 saatlıq pəncərə – uzun aralıqda cavablar paylaşılır və reytinq ədalətsiz olur.</p>
            <div className="jlist">
              {shown.map(t => {
                const r = row(t.ta_id)
                return (
                  <div key={t.ta_id} className="jrow cols" style={{ ['--cols' as any]: 'minmax(0,1fr)', ['--mcols' as any]: '1fr', gap: 6 }}>
                    <label className="check" style={{ minHeight: 32 }}>
                      <input type="checkbox" checked={r.on} onChange={e => set(t.ta_id, { on: e.target.checked })} />
                      <b>{t.class_name}</b><span className="small muted">{t.students} şagird{t.grade ? ` · ${t.grade}-cu sinif` : ''}{!t.mine ? ` · ${t.teacher}` : ''}</span>
                    </label>
                    {r.on && <div className="row" style={{ gap: 6 }}>
                      <input type="date" className="sel" value={r.d1} onChange={e => set(t.ta_id, { d1: e.target.value })} />
                      <input type="time" className="sel" value={r.t1} onChange={e => set(t.ta_id, { t1: e.target.value })} />
                      <span className="small">–</span>
                      <input type="date" className="sel" value={r.d2} onChange={e => set(t.ta_id, { d2: e.target.value })} />
                      <input type="time" className="sel" value={r.t2} onChange={e => set(t.ta_id, { t2: e.target.value })} />
                    </div>}
                    {r.on && <StudentPicker ta={t.ta_id} legend={`Kimə – ${t.class_name}`} onChange={ids => set(t.ta_id, { ids })} />}
                  </div>)
              })}
              {!shown.length && <div className="empty">Dərsiniz yoxdur.</div>}
            </div>
          </fieldset>
          <BankPicker has={has} add={add} remove={remove} disabled={false} first={false}
            legend="Test bazasından – sınaqlar, yekun testlər və mövzu bölmələri" onTitle={t => !f.title && setF(x => ({ ...x, title: t }))} />
          <fieldset><legend>Seçilmiş suallar ({qs.length})</legend>
            {qs.length === 0 ? <p className="small muted">Yuxarıdan sınağı seçib «Hamısını əlavə et» basın (orijinal sınaq formatı).</p> : (
              <div className="jlist" style={{ maxHeight: 260, overflow: 'auto' }}>
                {qs.map((q, i) => (
                  <div key={q.key} className="jrow cols" style={{ ['--cols' as any]: '28px minmax(0,1fr) auto', ['--mcols' as any]: '28px minmax(0,1fr)' }}>
                    <span className="num muted">{i + 1}.</span><span className="small clamp2"><MathText text={q.text} /></span>
                    <button className="btn sm ghost" onClick={() => remove(q.key)} aria-label="Sil">✕</button>
                  </div>))}
              </div>)}
            <OwnQuestion onAdd={q => add([q])} />
          </fieldset>
          {problem && <p className="small" style={{ color: 'var(--warn)', margin: 0 }}>{problem}</p>}
          <ErrorBox error={err} />
        </div>)}
    </Drawer>
  )
}

// ---------------------------------------------------------------- sınaq jurnalı
function Results({ id, onClose, onChange }: { id: number; onClose: () => void; onChange: () => void }) {
  const [d, err, , reload] = useLoad<Res>(() => get(`/api/exams-online/${id}`), [id])
  const [tab, setTab] = useState<'rows' | 'classes' | 'questions'>('rows')
  const [cls, setCls] = useState('')
  const [att, setAtt] = useState<Row | null>(null)
  const [delAsk, setDelAsk] = useState(false)
  const rows = d ? d.rows.filter(r => !cls || r.class_name === cls) : []
  const name = (r: Row) => r.full_name || `şagird (${r.class_name})`
  const print = () => {
    if (!d) return
    const body = head(d.batch.title, `${d.batch.subject} · ${d.batch.questions} sual · yazıb ${d.summary.wrote}/${d.summary.students} · orta ${fmt(d.summary.avg_pct)}%`) +
      '<h3>Siniflərin reytinqi</h3>' + table(['Yer', 'Sinif', 'Yazıb', 'Orta %', 'Ən yüksək %'], d.classes.map(c => [c.place, c.class_name, `${c.wrote}/${c.students}`, fmt(c.avg_pct), fmt(c.max_pct)]), [2, 3, 4]) +
      `<h3>Sınaq jurnalı${cls ? ' – ' + esc(cls) : ''}</h3>` + table(['Ümumi yer', 'Sinifdə', 'Şagird', 'Sinif', 'Düz', 'Səhv', 'Boş', 'Bal', '%'],
        rows.map(r => [r.place_all, r.place_class, name(r), r.class_name, r.correct, r.wrong, r.blank, r.points, r.status === 'yazıb' ? fmt(r.pct) : r.status]), [4, 5, 6, 7, 8])
    printDoc({ title: `${d.batch.title} – sınaq jurnalı`, body })
  }
  return (
    <Drawer title={d ? d.batch.title : 'Sınaq jurnalı'} onClose={onClose}
      footer={d && <><button className="btn" onClick={print}>Çap et</button><span className="grow" />
        <button className="btn ghost" onClick={() => setDelAsk(true)}>{d.access === 'full' ? 'Sil' : 'Sinfimdən sil'}</button></>}>
      <ErrorBox error={err} />
      {d && delAsk && <><p className="small muted">Sınaq {d.access === 'full' ? 'bütün siniflərdən' : 'sinfinizdən'} birdəfəlik silinir – nəticələr və şagird cəhdləri də (geri qaytarmaq olmur).</p>
        <ConfirmName name={d.batch.title} action="Birdəfəlik sil" onCancel={() => setDelAsk(false)}
          onConfirm={async () => { await apiDel(`/api/exams-online/${id}`); toast('Sınaq sistemdən silindi'); onChange(); onClose() }} /></>}
      {!d ? <Loading /> : (
        <div className="stack">
          <div className="kpis">
            <Stat value={`${d.summary.wrote}/${d.summary.students}`} label="yazıb" /><Stat value={fmt(d.summary.avg_pct) + '%'} label="orta" />
            <Stat value={fmt(d.summary.max_pct) + '%'} label="ən yüksək" /><Stat value={d.batch.penalty ? `${d.batch.penalty} səhv = −1` : 'yox'} label="cərimə" />
          </div>
          {d.classes.some(c => c.own) && (
            <section className="panel"><h2>Testi idarə et <small>öz siniflərim</small></h2>
              <div className="jlist">{d.classes.filter(c => c.own).map(c => (
                <div key={c.task_id} className="jrow cols" style={{ ['--cols' as any]: 'minmax(0,1fr)', ['--mcols' as any]: '1fr', gap: 6 }}>
                  <div className="row"><b className="grow">{c.class_name}</b><Pill tone={stateTone(c.state)}>{c.state}</Pill></div>
                  <TaskActions ta={c.ta_id} id={c.task_id} cls={c.class_name} onChange={() => { reload(); onChange() }} />
                </div>))}</div>
            </section>)}
          {d.access === 'own' && <p className="small muted" style={{ margin: 0 }}>Başqa müəllimlərin siniflərindəki şagirdlərin adı göstərilmir – yalnız yer və bal.</p>}
          <div className="row">
            <Seg value={tab} onChange={setTab} options={[['rows', 'Jurnal'], ['classes', 'Siniflər'], ['questions', 'Suallar']]} />
            {tab === 'rows' && <select className="sel" value={cls} onChange={e => setCls(e.target.value)}><option value="">Bütün siniflər</option>{d.classes.map(c => <option key={c.task_id}>{c.class_name}</option>)}</select>}
          </div>
          {tab === 'rows' && (
            <div className="tbl-wrap"><table>
              <thead><tr><th className="r">Yer</th><th className="r">Sinifdə</th><th>Şagird</th><th className="r">Düz</th><th className="r">Səhv</th><th className="r">Boş</th><th className="r">Bal</th><th className="r">%</th></tr></thead>
              <tbody>{rows.map((r, i) => (
                <tr key={i} className={r.student_id && r.status === 'yazıb' ? 'click' : ''} onClick={() => r.student_id && r.status === 'yazıb' && setAtt(r)}>
                  <td className="r num"><b>{r.place_all ?? '—'}</b></td><td className="r num">{r.place_class ?? '—'}</td>
                  <td>{r.full_name ? <b>{r.full_name}</b> : <span className="muted">{name(r)}</span>}<span className="sub">{r.class_name}{r.retake ? ' · təkrar cəhd' : ''}</span></td>
                  {r.status === 'yazıb' ? <>
                    <td className="r num">{r.correct}</td><td className="r num">{r.wrong}</td><td className="r num">{r.blank}</td>
                    <td className="r num">{fmt(r.points, r.points != null && r.points % 1 ? 2 : 0)}</td><td className="r num"><b>{fmt(r.pct)}</b></td></>
                    : <td colSpan={5}><Pill tone={r.status === 'yazır' ? 'ok' : undefined}>{r.status}</Pill></td>}
                </tr>))}</tbody>
            </table></div>)}
          {tab === 'classes' && (
            <div className="tbl-wrap"><table>
              <thead><tr><th className="r">Yer</th><th>Sinif</th><th>Vaxt</th><th className="r">Yazıb</th><th className="r">Orta %</th><th className="r">Ən yüksək</th></tr></thead>
              <tbody>{d.classes.map(c => (
                <tr key={c.task_id}><td className="r num"><b>{c.place ?? '—'}</b></td><td><b>{c.class_name}</b> <Pill tone={stateTone(c.state)}>{c.state}</Pill></td>
                  <td className="small">{dt(c.opens_at)} – {dt(c.closes_at)}</td><td className="r num">{c.wrote}/{c.students}</td>
                  <td className="r num"><b>{fmt(c.avg_pct)}</b></td><td className="r num">{fmt(c.max_pct)}</td></tr>))}</tbody>
            </table></div>)}
          {tab === 'questions' && (
            <div className="jlist">
              {d.questions.map(q => (
                <div key={q.index} className="jrow cols" style={{ ['--cols' as any]: '28px minmax(0,1fr) 120px', ['--mcols' as any]: '28px minmax(0,1fr)' }}>
                  <span className="num muted">{q.index + 1}.</span><span className="small clamp2"><MathText text={ml(q.text)} /></span>
                  <span className="small">{q.pct == null ? '—' : <><div className="bar" style={{ height: 8 }}><i style={{ width: q.pct + '%', background: `var(--${q.pct >= 70 ? 'ok' : q.pct >= 40 ? 'warn' : 'bad'})` }} /></div>{fmt(q.pct)}% ({q.correct}/{q.of})</>}</span>
                </div>))}
            </div>)}
        </div>)}
      {att && <Attempt batch={id} r={att} onClose={() => setAtt(null)} onDone={() => { reload(); onChange() }} />}
    </Drawer>
  )
}

function Attempt({ batch, r, onClose, onDone }: { batch: number; r: Row; onClose: () => void; onDone: () => void }) {
  const url = `/api/exams-online/${batch}/attempt/${r.task_id}/${r.student_id}`
  const [d, err, , reload] = useLoad<{ items: any[] }>(() => get(url), [url])
  const L = 'ABCDE'
  const mark = async (index: number, ok: boolean | null) => { await put(url, { index, ok }); reload(); onDone() }
  return (
    <Drawer title={`${r.full_name} – cavablar`} onClose={onClose}>
      <ErrorBox error={err} />
      {!d ? <Loading /> : (
        <div className="jlist">
          {d.items.map(q => (
            <div key={q.index} className="jrow cols" style={{ ['--cols' as any]: 'minmax(0,1fr)', ['--mcols' as any]: '1fr', gap: 4 }}>
              <div className="row"><b>{q.index + 1}.</b><span className="grow small clamp2"><MathText text={ml(q.text)} /></span>
                <Pill tone={q.ok ? 'ok' : 'bad'}>{q.ok ? 'düz' : 'səhv'}</Pill>{q.manual != null && <Pill tone="acc">əl ilə</Pill>}</div>
              <span className="small">Cavabı: <b>{q.given == null || q.given === '' ? '—' : q.kind === 'mcq' ? L[q.given] : String(q.given)}</b> · düzgün: {q.kind === 'mcq' ? L[q.correct] : String(q.answer || '').split('|').join(' / ')}</span>
              {q.kind === 'open' && <div className="row" style={{ gap: 6 }}>
                <button className="btn sm" onClick={() => mark(q.index, true)}>Düz say</button>
                <button className="btn sm" onClick={() => mark(q.index, false)}>Səhv say</button>
                {q.manual != null && <button className="btn sm ghost" onClick={() => mark(q.index, null)}>Avtomatik yoxlamaya qaytar</button>}
              </div>}
            </div>))}
        </div>)}
    </Drawer>
  )
}

// ---------------------------------------------------------------- kumulyativ reytinq
function Rating() {
  const [subject, setSubject] = useState('')
  const [d, err, loading] = useLoad<{ batches: { id: number; title: string; avg_pct: number | null }[]; rows: any[]; total: number; improved: any[] }>(
    () => get('/api/exams-online/rating', subject ? { subject } : {}), [subject])
  const print = () => d && printDoc({ title: 'Sınaq reytinqi', body: head('Sınaq imtahanları – kumulyativ reytinq', `${d.batches.length} sınaq · ${d.total} şagird`) +
    table(['Ümumi yer', 'Sinifdə', 'Şagird', 'Sinif', 'Sınaq', 'Orta %', 'Son %', 'Dinamika'],
      d.rows.map(r => [r.place_all, r.place_class, r.full_name, r.class_name, r.count, fmt(r.avg_pct), fmt(r.last_pct), r.delta == null ? '—' : (r.delta > 0 ? '+' : '') + fmt(r.delta)]), [4, 5, 6, 7]) })
  return (
    <>
      <div className="toolbar">
        <input className="sel" placeholder="Fənn (boş – hamısı)" value={subject} onChange={e => setSubject(e.target.value)} />
        {d && d.rows.length > 0 && <button className="btn sm right" onClick={print}>Çap et</button>}
      </div>
      <ErrorBox error={err} />
      {loading && !d ? <Loading /> : d && (d.rows.length === 0 ? <div className="empty">Hələ nəticə yoxdur.</div> : (
        <div className="grid g2">
          <section className="panel" style={{ gridColumn: '1 / -1' }}>
            <h2>Kumulyativ reytinq <small>{d.batches.length} sınaq · ümumi yer {d.total} şagird arasında</small></h2>
            <div className="tbl-wrap"><table>
              <thead><tr><th className="r">Yer</th><th className="r">Sinifdə</th><th>Şagird</th><th className="r">Sınaq</th><th className="r">Orta %</th><th className="r">Son %</th><th className="r">Dinamika</th></tr></thead>
              <tbody>{d.rows.map(r => (
                <tr key={r.student_id}><td className="r num"><b>{r.place_all ?? '—'}</b></td><td className="r num">{r.place_class ?? '—'}</td>
                  <td><b>{r.full_name}</b><span className="sub">{r.class_name}</span></td><td className="r num">{r.count}</td>
                  <td className="r num"><b>{fmt(r.avg_pct)}</b></td><td className="r num">{fmt(r.last_pct)}</td>
                  <td className="r num">{r.delta == null ? '—' : <Pill tone={r.delta > 0 ? 'ok' : r.delta < 0 ? 'bad' : undefined}>{r.delta > 0 ? '+' : ''}{fmt(r.delta)}</Pill>}</td></tr>))}</tbody>
            </table></div>
          </section>
          {d.improved.length > 0 && <section className="panel"><h2>Ən çox irəliləyənlər</h2>
            {d.improved.map(r => <div key={r.student_id} className="row small"><b className="grow">{r.full_name}</b><span className="muted">{r.class_name}</span><Pill tone="ok">+{fmt(r.delta)}</Pill></div>)}</section>}
          <section className="panel"><h2>Sınaqlar üzrə orta</h2>
            {d.batches.map(b => <div key={b.id} className="row small"><span className="grow">{b.title}</span><b>{fmt(b.avg_pct)}%</b></div>)}</section>
        </div>))}
    </>
  )
}
