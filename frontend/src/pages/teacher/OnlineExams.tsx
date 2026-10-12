// Sınaq imtahanları (onlayn): planla əlaqəsiz, bir neçə sinfə eyni anda. Nəticə – «Sınaq jurnalı» (bal, faiz, sinifdə və
// ümumi yer), siniflərin reytinqi, sual analizi, açıq sualın əl ilə yoxlanması, kumulyativ reytinq. Formativ jurnala düşmür.
import { StudentPicker } from './common'
import { useEffect, useMemo, useState } from 'react'
import { ApiError, del as apiDel, get, patch, post, put } from '../../api'
import { MathText } from '../../MathText'
import { Chips, ConfirmName, Drawer, ErrorBox, Field, fmt, Loading, Pill, Seg, Stat, toast, Top, useLoad } from '../../ui'
import { Link } from 'react-router-dom'
import { esc, head, printDoc, table } from '../../print'
import TaskEditor, { BankPicker, iso, localParts, OwnQuestion, toCustom, type Given, type Q } from './TaskEditor'
import { ResendToStudents, TaskActions } from './Tasks'
import { PeriodBar, usePeriod } from '../../periods'
import ExamSeriesPanel from './ExamSeries'
import { azDT } from '../../ui'
import { PointsSummary, previewPoints, QPoints } from '../../scoring'

// sınaq mənbələri (viktorina): Sınaqlar qovluğu, P012, P009; TAİM (P004) – müəllim imtahanı, göstərilmir
const EXAM_SOURCES = ['sinaqlar', 'p012', 'p009']

type Target = { ta_id: number; class_name: string; subject: string; grade: number | null; teacher: string; mine: boolean; students: number }
type Exam = { id: number; title: string; subject: string; grade: number | null; classes: string[]; ta_ids?: number[]; opens_at: string | null; closes_at: string | null
  questions: number; mine: boolean; wrote: number; avg_pct: number | null; state: 'gözlənilir' | 'açıqdır' | 'bitib' }
type Row = { student_id: number | null; full_name: string | null; class_name: string; task_id: number; status: 'yazıb' | 'yazmayıb' | 'yazır' | 'gözlənilir'
  correct: number | null; wrong: number | null; blank: number | null; points: number | null; pct: number | null; grade: number | null
  place_all: number | null; place_class: number | null; retake: boolean; late?: boolean }
type Res = { batch: { id: number; title: string; subject: string; grade: number | null; penalty: number; questions: number }
  summary: { students: number; wrote: number; avg_pct: number | null; max_pct: number | null; min_pct: number | null }
  classes: { task_id: number; ta_id: number; own: boolean; class_name: string; students: number; wrote: number; avg_pct: number | null; max_pct: number | null; place: number | null; state: string; opens_at: string; closes_at: string }[]
  rows: Row[]; questions: { index: number; text: any; kind: string; correct: number; of: number; pct: number | null }[]; access: 'full' | 'own' }

const ml = (x: any) => (x ? (typeof x === 'string' ? x : x.az || x.ru || x.en || '') : '')
const dt = (s: string | null) => (s ? azDT(new Date(s), { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—')
const stateTone = (s: string) => (s === 'açıqdır' ? 'ok' : s === 'bitib' ? 'info' : undefined)
const PENALTY: [string, string][] = [['0', 'cərimə yoxdur'], ['4', '4 səhv 1 düzü aparır'], ['3', '3 səhv 1 düzü aparır']]

/** embedded – «Testlər və sınaqlar» mərkəzində: sinif və görünüş (sınaqlar / seriyalar) yuxarıdakı açılan siyahılardan. */
export default function OnlineExams({ embedded, ta, view: viewProp }: { embedded?: boolean; ta?: number | null; view?: 'list' | 'series' } = {}) {
  const [viewOwn, setView] = useState<'list' | 'series'>('list')
  const view = embedded ? viewProp ?? 'list' : viewOwn
  const [st, setSt] = useState<'all' | Exam['state']>('all')
  const [list, err, loading, reload] = useLoad<Exam[]>(() => get('/api/exams-online'), [])
  const [creating, setCreating] = useState(false)
  const [open, setOpen] = useState<number | null>(null)
  const [exp, setExp] = useState<number | null>(null)          // şagird siyahısı açıq olan sınaq
  const [editing, setEditing] = useState<Exam | null>(null)
  const f = usePeriod('exams', 'date')
  const all = (list || []).filter(x => !ta || (x.ta_ids || []).includes(ta))     // sinif filtri – həmin sinfə verilən sınaqlar
  // eyni adlı sınaq ikinci dəfə (və ya «(təkrar)») – «təkrar» nişanı
  const base = (t: string) => t.replace(/\s*\(təkrar\)\s*$/i, '').trim().toLocaleLowerCase('az')
  const firstId = new Map<string, number>()
  for (const x of [...all].sort((a, b) => a.id - b.id)) if (!firstId.has(base(x.title))) firstId.set(base(x.title), x.id)
  const isRepeat = (x: Exam) => firstId.get(base(x.title)) !== x.id || /\(təkrar\)\s*$/i.test(x.title)
  const inPeriod = all.filter(x => !x.opens_at || f.has(x.opens_at))
  const n = (k: Exam['state']) => inPeriod.filter(x => x.state === k).length
  const ORD = { 'açıqdır': 0, 'gözlənilir': 1, 'bitib': 2 }
  // açıq sınaqlar həmişə yuxarıda
  const shown = inPeriod.filter(x => st === 'all' || x.state === st).sort((a, b) => ORD[a.state] - ORD[b.state] || (f.sort === 'topic'
    ? a.title.localeCompare(b.title, 'az', { numeric: true }) || Date.parse(b.opens_at || '') - Date.parse(a.opens_at || '')
    : Date.parse(b.opens_at || '') - Date.parse(a.opens_at || '')))
  return (
    <>
      {embedded ? <div className="hub-head"><span className="small muted grow">{view === 'series' ? 'Seçilmiş sınaqlar dövrə görə (gün / həftə / ay) siniflərə özü gedir.' : 'Plandan kənar sınaqlar – bir neçə sinfə eyni anda; sınaq jurnalı. Formativ qiymətə təsir etmir.'}</span>
        {view === 'list' && <button className="btn primary" onClick={() => setCreating(true)}>+ Yeni sınaq</button>}</div>
        : <Top title="Sınaq imtahanları" sub="Plandan kənar sınaqlar və avtomatik seriyalar – yaratmaq, sınaq jurnalı. Formativ qiymətə təsir etmir; reytinq və analitika – «Test nəticələri»."
          actions={<><Link className="btn" to="/tests?s=netice&v=rating&kind=sinaq">Reytinq →</Link><button className="btn primary" onClick={() => setCreating(true)}>+ Yeni sınaq</button></>} />}
      <div className="toolbar">{!embedded && <Seg value={view} onChange={setView} options={[['list', 'Sınaqlar'], ['series', 'Avtomatik seriyalar']]} />}
        {view === 'list' && all.length > 0 && <Chips label="Vəziyyət" value={st} onChange={setSt} options={[['all', 'Hamısı', inPeriod.length],
          ['açıqdır', '● Açıq', n('açıqdır')], ['gözlənilir', 'Gözlənilir', n('gözlənilir')], ['bitib', 'Bitib', n('bitib')]]} />}</div>
      <ErrorBox error={err} />
      {view === 'series' ? <ExamSeriesPanel /> : loading && !list ? <Loading /> : (
        <>{all.length > 0 && <PeriodBar f={f} count={shown.length} total={all.length} topicLabel="Ad üzrə" />}
        <div className="jlist">
          {list && all.length === 0 && <div className="empty">{ta ? 'Bu sinfə hələ sınaq verilməyib' : 'Hələ sınaq yoxdur'} – «+ Yeni sınaq» ilə test bazasından sınaq seçin.</div>}
          {all.length > 0 && shown.length === 0 && <div className="empty">Bu seçimdə sınaq yoxdur – vəziyyəti və ya dövrü dəyişin.</div>}
          {shown.map(x => <ExamRow key={x.id} x={x} repeat={isRepeat(x)} expanded={exp === x.id} onToggle={() => setExp(e => (e === x.id ? null : x.id))}
            onJournal={() => setOpen(x.id)} onEdit={() => setEditing(x)} onChange={reload} />)}
        </div></>)}
      {creating && <NewExam onClose={() => setCreating(false)} onDone={() => { setCreating(false); reload() }} />}
      {open && <Results id={open} onClose={() => setOpen(null)} onChange={reload} />}
      {editing && <EditExam x={editing} onClose={() => setEditing(null)} onChange={reload} />}
    </>
  )
}

// ---------------------------------------------------------------- siyahı sətri (docs/test-sinaq-siyahi-promtu.md)
/** Sınaq adı + həmişə görünən «Şagirdlər · Redaktə · Sil»; sətrə klik – sinif-sinif şagird adları sətrin altında açılır. */
function ExamRow({ x, repeat, expanded, onToggle, onJournal, onEdit, onChange }: { x: Exam; repeat: boolean; expanded: boolean; onToggle: () => void
  onJournal: () => void; onEdit: () => void; onChange: () => void }) {
  const [delAsk, setDelAsk] = useState(false)
  const stop = (fn: () => void) => (e: { stopPropagation: () => void }) => { e.stopPropagation(); fn() }
  return (
    <div className="jrow cols" style={{ ['--cols' as any]: 'minmax(0,1fr)', ['--mcols' as any]: '1fr', gap: 6 }}>
      <div className="click stack" style={{ gap: 4 }} onClick={onToggle} role="button" aria-expanded={expanded}>
        <div className="row"><b className="grow">{expanded ? '▾' : '▸'} {x.title}</b><Pill tone={stateTone(x.state)}>{x.state}</Pill>{repeat && <Pill tone="warn">təkrar</Pill>}{x.mine && <Pill tone="acc">mənim</Pill>}</div>
        <span className="small muted">{x.subject}{x.grade ? ` · ${x.grade}-cu sinif` : ''} · {x.classes.join(', ')} · {dt(x.opens_at)} – {dt(x.closes_at)} · {x.questions} sual · {x.wrote} yazıb{x.avg_pct != null ? ` · orta ${fmt(x.avg_pct)}%` : ''}</span>
      </div>
      <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
        <button className={'btn sm' + (expanded ? ' primary' : '')} onClick={stop(onToggle)}>👥 Şagirdlər</button>
        <button className="btn sm" onClick={stop(onEdit)}>✏ Redaktə</button>
        <button className="btn sm ghost" onClick={stop(() => setDelAsk(true))}>🗑 {x.mine ? 'Sil' : 'Sinfimdən sil'}</button>
        <button className="btn sm ghost" onClick={stop(onJournal)}>Ətraflı jurnal →</button>
      </div>
      {delAsk && <ConfirmName name={x.title} action="Birdəfəlik sil" onCancel={() => setDelAsk(false)}
        onConfirm={async () => { await apiDel(`/api/exams-online/${x.id}`); toast(x.mine ? 'Sınaq bütün siniflərdən silindi' : 'Sınaq sinfinizdən silindi'); setDelAsk(false); onChange() }} />}
      {delAsk && <span className="small muted">Nəticələr və şagird cəhdləri də silinir – geri qaytarmaq olmur.</span>}
      {expanded && <ExamStudents id={x.id} />}
    </div>
  )
}

const STATUS_TONE: Record<Row['status'], 'ok' | 'bad' | 'info' | undefined> = { 'yazıb': 'ok', 'yazmayıb': 'bad', 'yazır': 'info', 'gözlənilir': undefined }

/** Sınağı alan siniflərin şagirdləri (əlifba ilə) və vəziyyəti; başqa müəllimin sinfində adlar gizlidir (access: own). */
function ExamStudents({ id }: { id: number }) {
  const [d, err, , reload] = useLoad<Res>(() => get(`/api/exams-online/${id}`), [id])
  const [rs, setRs] = useState<{ ta: number; task: number; ids: number[] } | null>(null)
  if (err) return <ErrorBox error={err} />
  if (!d) return <Loading />
  return (
    <div className="subrows">
      {d.classes.map(c => {
        const rows = d.rows.filter(r => r.task_id === c.task_id || (r.class_name === c.class_name && !d.classes.some(k => k.task_id === r.task_id)))
          .sort((a, b) => (a.full_name || '').localeCompare(b.full_name || '', 'az'))
        const hidden = rows.length > 0 && rows.every(r => !r.full_name)
        return (
          <div key={c.task_id} className="subrow" style={{ alignItems: 'stretch' }}>
            <div className="row" style={{ flexWrap: 'wrap', gap: 6 }}><b>{c.class_name}</b><Pill tone={stateTone(c.state)}>{c.state}</Pill>
              <span className="small muted grow">{c.wrote}/{c.students} yazıb{c.avg_pct != null ? ` · orta ${fmt(c.avg_pct)}%` : ''}</span></div>
            {hidden ? <span className="small muted">Başqa müəllimin sinfi – şagird adları göstərilmir.</span>
              : rows.length === 0 ? <span className="small muted">Bu sinifdə şagird yoxdur.</span>
              : <ol className="small" style={{ margin: '4px 0 0', paddingLeft: 22, columns: '2 260px', columnGap: 24 }}>
                {rows.map((r, i) => (
                  <li key={(r.student_id ?? 'x') + '-' + i} style={{ breakInside: 'avoid', marginBottom: 2 }}>
                    {r.full_name || 'şagird'} <Pill tone={STATUS_TONE[r.status]}>{r.status === 'yazıb' ? `${fmt(r.pct)}%` : r.status}</Pill>
                    {r.retake && <span className="muted"> · təkrar</span>}
                    {c.own && r.student_id && <button className="btn sm ghost" style={{ padding: '0 6px', minHeight: 24, marginLeft: 4 }}
                      title="Bu şagirdə sınağı yenidən göndər (yeni vaxtla)" onClick={() => setRs({ ta: c.ta_id, task: r.task_id, ids: [r.student_id!] })}>↻ Yenidən göndər</button>}</li>))}
              </ol>}
          </div>)
      })}
      {rs && <ResendToStudents ta={rs.ta} taskId={rs.task} ids={rs.ids} onClose={() => setRs(null)} onDone={() => { setRs(null); reload() }} />}
    </div>
  )
}

/** Redaktə: sınağın adı (bütün siniflərdə birdən; yalnız yaradan / admin) + hər öz sinfi üçün vaxt və suallar (tapşırıq redaktoru). */
function EditExam({ x, onClose, onChange }: { x: Exam; onClose: () => void; onChange: () => void }) {
  const [d, err] = useLoad<Res>(() => get(`/api/exams-online/${x.id}`), [x.id])
  const [title, setTitle] = useState(x.title)
  const [saveErr, setSaveErr] = useState<unknown>()
  const [task, setTask] = useState<{ ta: number; id: number } | null>(null)
  const full = d?.access === 'full'
  const save = async () => {
    try { await patch(`/api/exams-online/${x.id}`, { title }); toast('Sınağın adı dəyişdi'); onChange(); onClose() } catch (e) { setSaveErr(e) }
  }
  return (
    <Drawer title={`Redaktə – ${x.title}`} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Bağla</button>{full && <button className="btn primary" disabled={!title.trim() || title.trim() === x.title} onClick={save}>Adı saxla</button>}</>}>
      <ErrorBox error={err} />
      {!d ? <Loading /> : (
        <div className="stack">
          <Field label="Sınağın adı" full hint={full ? 'bütün siniflərdə birdən dəyişir' : 'adı yalnız sınağı yaradan müəllim və ya admin dəyişə bilər'}>
            <input value={title} maxLength={200} disabled={!full} onChange={e => setTitle(e.target.value)} /></Field>
          <ErrorBox error={saveErr} />
          <fieldset><legend>Vaxt və suallar – sinif üzrə</legend>
            <div className="jlist">
              {d.classes.filter(c => c.own).map(c => (
                <div key={c.task_id} className="jrow" style={{ gridTemplateColumns: 'minmax(0,1fr) auto' }}>
                  <span><b>{c.class_name}</b> <span className="small muted">{dt(c.opens_at)} – {dt(c.closes_at)}</span></span>
                  <button className="btn sm" onClick={() => setTask({ ta: c.ta_id, id: c.task_id })}>Vaxt və suallar →</button>
                </div>))}
              {!d.classes.some(c => c.own) && <div className="empty">Bu sınaqda sizin sinfiniz yoxdur.</div>}
            </div>
          </fieldset>
        </div>)}
      {task && <TaskEditor ta={task.ta} taskId={task.id} fromBank={false} onClose={() => setTask(null)} onDone={() => { setTask(null); onChange() }} />}
    </Drawer>
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
  const [given, setGiven] = useState<Record<string, Given>>({})
  const [ask, setAsk] = useState<{ message: string; repeat: boolean; grade: boolean } | null>(null)
  const [confirm, setConfirm] = useState(false)
  useEffect(() => {
    get<Target[]>('/api/exams-online/targets').then(t => { setTargets(t); setSubject(t[0]?.subject || '') }, setErr)
  }, [])
  const subjects = useMemo(() => [...new Set((targets || []).map(t => t.subject))], [targets])
  const shown = (targets || []).filter(t => t.subject === subject)
  const row = (id: number): TRow => rows[id] || { on: false, ...common }
  const set = (id: number, p: Partial<TRow>) => setRows(r => ({ ...r, [id]: { ...row(id), ...p } }))
  const chosen = shown.filter(t => row(t.ta_id).on)
  const chosenKey = chosen.map(t => t.ta_id).join(',')
  const grades = [...new Set(chosen.map(t => t.grade).filter((g): g is number => !!g))]
  useEffect(() => {
    setAsk(null); setConfirm(false)
    if (!chosenKey) { setGiven({}); return }
    get<Record<string, Given>>('/api/exams-online/given', { ta_ids: chosenKey }).then(setGiven, () => setGiven({}))
  }, [chosenKey])
  useEffect(() => { setAsk(null); setConfirm(false) }, [qs.length])
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
        allow_repeat: confirm && !!ask?.repeat, allow_other_grade: confirm && !!ask?.grade,
        targets: chosen.map(t => { const x = row(t.ta_id); return { ta_id: t.ta_id, opens_at: iso(x.d1, x.t1), closes_at: iso(x.d2, x.t2), student_ids: x.ids ?? null } }),
      })
      toast(`Sınaq ${r.tasks} sinfə göndərildi`)
      onDone()
    } catch (e) {
      const d = e instanceof ApiError && e.status === 409 ? (e.data as any)?.detail : null
      if (d && typeof d === 'object') {
        // təkrar və ya başqa sinfin sınağı – müəllimin açıq təsdiqi lazımdır; ikisi də ola bilər, hər biri ayrıca soruşulur
        setAsk(a => ({ message: d.message, repeat: !!(a?.repeat || d.repeat?.length || d.same_title?.length), grade: !!(a?.grade || d.grade?.length) }))
        setConfirm(false); setErr(undefined)
      } else setErr(e)
    } finally { setBusy(false) }
  }
  return (
    <Drawer title="Yeni sınaq imtahanı" onClose={onClose}
      footer={<><span className="small muted grow">{qs.length} sual · {chosen.length} sinif</span><button className="btn" onClick={onClose}>Ləğv et</button>
        <button className="btn primary" disabled={busy} onClick={submit}>Göndər</button></>}>
      {!targets ? (err ? <ErrorBox error={err} /> : <Loading />) : (
        <div className="stack">
          <div className="fg">
            <Field label="Ad" full><input value={f.title} maxLength={200} placeholder="məs. Buraxılış sınağı №1" onChange={e => setF({ ...f, title: e.target.value })} /></Field>
            <Field label="Həll müddəti (dəq)" hint="ən azı 45"><input type="number" min={45} max={300} value={f.duration} onChange={e => setF({ ...f, duration: Number(e.target.value) })} /></Field>
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
          <BankPicker has={has} add={add} remove={remove} disabled={false} first={false} main={EXAM_SOURCES} exclude={['p004']} tall given={given} grades={grades}
            legend="Test bazasından – sınaqlar, yekun testlər və mövzu bölmələri" onTitle={t => !f.title && setF(x => ({ ...x, title: t }))} />
          <fieldset><legend>Seçilmiş suallar ({qs.length})</legend>
            {qs.length === 0 ? <p className="small muted">Yuxarıdan sınağı seçib «Hamısını əlavə et» basın (orijinal sınaq formatı).</p> : (
              <div className="jlist" style={{ maxHeight: 320, overflow: 'auto' }}>
                <PointsSummary qs={qs} />
                {qs.map((q, i) => (
                  <div key={q.key} className="jrow cols" style={{ ['--cols' as any]: '28px minmax(0,1fr) auto', ['--mcols' as any]: '28px minmax(0,1fr)' }}>
                    <span className="num muted">{i + 1}.</span><span className="small clamp2"><MathText text={q.text} /></span>
                    <span className="row" style={{ flexWrap: 'nowrap' }}>
                      <QPoints q={q} pts={previewPoints(qs)[i]} onLevel={l => setQs(cur => cur.map(x => (x.key === q.key ? { ...x, difficulty: l } : x)))} />
                      <button className="btn sm ghost" onClick={() => remove(q.key)} aria-label="Sil">✕</button></span>
                  </div>))}
              </div>)}
            <OwnQuestion onAdd={q => add([q])} />
          </fieldset>
          {problem && <p className="small" style={{ color: 'var(--warn)', margin: 0 }}>{problem}</p>}
          {ask && <div className="stack" style={{ gap: 6, padding: 10, border: '1px solid var(--warn)', borderRadius: 8 }}>
            <span className="small">⚠ {ask.message}</span>
            <label className="check small"><input type="checkbox" checked={confirm} onChange={e => setConfirm(e.target.checked)} />
              {ask.repeat && ask.grade ? 'Bilərəkdən təkrar və başqa sinfin sınağını göndərirəm' : ask.repeat ? 'Bilərəkdən təkrar göndərirəm (adına «təkrar» yazılacaq)' : 'Bilərəkdən başqa sinfin sınağını göndərirəm'}</label>
          </div>}
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
  const [rs, setRs] = useState<{ ta: number; task: number; ids: number[] } | null>(null)
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
          {d.access === 'own' && <p className="small muted" style={{ margin: 0 }}>Başqa müəllimlərin siniflərindəki şagirdlərin adı göstərilmir – yalnız yer və bal.</p>}
          <div className="row">
            <Seg value={tab} onChange={setTab} options={[['rows', 'Jurnal'], ['classes', d.classes.some(c => c.own) ? 'Siniflər və idarə' : 'Siniflər'], ['questions', 'Suallar']]} />
            {tab === 'rows' && <select className="sel" value={cls} onChange={e => setCls(e.target.value)}><option value="">Bütün siniflər</option>{d.classes.map(c => <option key={c.task_id}>{c.class_name}</option>)}</select>}
          </div>
          {tab === 'rows' && (
            <div className="tbl-wrap"><table>
              <thead><tr><th className="r">Yer</th><th className="r">Sinifdə</th><th>Şagird</th><th className="r">Düz</th><th className="r">Səhv</th><th className="r">Boş</th><th className="r">Bal</th><th className="r">%</th></tr></thead>
              <tbody>{rows.map((r, i) => (
                <tr key={i} className={r.student_id && r.status === 'yazıb' ? 'click' : ''} onClick={() => r.student_id && r.status === 'yazıb' && setAtt(r)}>
                  <td className="r num"><b>{r.place_all ?? '—'}</b></td><td className="r num">{r.place_class ?? '—'}</td>
                  <td>{r.full_name ? <b>{r.full_name}</b> : <span className="muted">{name(r)}</span>}<span className="sub">{r.class_name}{r.retake ? ' · təkrar cəhd' : ''}{r.late ? ' · sonradan yazıb' : ''}</span>
                    {r.student_id && (() => { const c = d.classes.find(k => k.task_id === r.task_id) || d.classes.find(k => k.class_name === r.class_name)
                      return c?.own ? <button className="btn sm ghost" style={{ padding: '0 6px', minHeight: 24 }} title="Bu şagirdə sınağı yenidən göndər"
                        onClick={e => { e.stopPropagation(); setRs({ ta: c.ta_id, task: c.task_id, ids: [r.student_id!] }) }}>↻ Yenidən göndər</button> : null })()}</td>
                  {r.status === 'yazıb' ? <>
                    <td className="r num">{r.correct}</td><td className="r num">{r.wrong}</td><td className="r num">{r.blank}</td>
                    <td className="r num">{fmt(r.points, r.points != null && r.points % 1 ? 2 : 0)}</td><td className="r num"><b>{fmt(r.pct)}</b></td></>
                    : <td colSpan={5}><Pill tone={r.status === 'yazır' ? 'ok' : r.status === 'yazmayıb' ? 'bad' : undefined}>{r.status}</Pill></td>}
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
          {tab === 'classes' && d.classes.some(c => c.own) && (
            <section className="panel"><h2>Sinfin testini idarə et <small>canlı izlə, link, yenidən göndər, kağız variant, redaktə</small></h2>
              <div className="jlist">{d.classes.filter(c => c.own).map(c => (
                <div key={c.task_id} className="jrow cols" style={{ ['--cols' as any]: 'minmax(0,1fr)', ['--mcols' as any]: '1fr', gap: 6 }}>
                  <div className="row"><b className="grow">{c.class_name}</b><Pill tone={stateTone(c.state)}>{c.state}</Pill></div>
                  <TaskActions ta={c.ta_id} id={c.task_id} cls={c.class_name} onChange={() => { reload(); onChange() }} />
                </div>))}</div>
            </section>)}
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
      {rs && <ResendToStudents ta={rs.ta} taskId={rs.task} ids={rs.ids} onClose={() => setRs(null)} onDone={() => { setRs(null); reload(); onChange() }} />}
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
