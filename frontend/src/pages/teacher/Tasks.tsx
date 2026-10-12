// Onlayn tapşırıqlar (müəllim): yaratma / viktorinadan test / redaktə / link kimi göndərmə / silmə / canlı izləmə.
import { useEffect, useState } from 'react'
import { del as apiDel, get, post } from '../../api'
import { MathText } from '../../MathText'
import { AsyncBtn, Chips, ConfirmName, Drawer, ErrorBox, Field, fmt, fmtDate, gradeTone, isoDate, Loading, More, Pill, toast, Top, useLoad, ord } from '../../ui'
import { type MyLesson, type Preset, StudentPicker, useMyLessons, usePick } from './common'
import { PeriodBar, usePeriod } from '../../periods'
import { Link } from 'react-router-dom'
import TaskEditor from './TaskEditor'
import { esc, head, mathHtml, printDoc, table } from '../../print'
import { azDT } from '../../ui'

type Task = { id: number; title: string; created_at?: string | null; opens_at: string; closes_at: string; duration_min: number; questions: number; submitted: number; avg_pct: number | null; student_ids: number[] | null
  kind?: string | null; topic?: { seq: number; topic: string } | null; journal_auto?: boolean; journal_done_at?: string | null
  ta_id?: number; class_name?: string | null; batch_id?: number | null }
const ml = (x: any) => (x ? (typeof x === 'string' ? x : x.az || x.ru || x.en || '') : '')
const dt = (s: string) => azDT(new Date(s), { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
const hm = (s: string) => azDT(new Date(s), { hour: '2-digit', minute: '2-digit' })
export const taskLink = (id: number) => `${location.origin}/t/${id}`

type St = 'all' | 'open' | 'soon' | 'closed'
const stateOf = (t: { opens_at: string; closes_at: string }, now = Date.now()): Exclude<St, 'all'> =>
  now < Date.parse(t.opens_at) ? 'soon' : now < Date.parse(t.closes_at) ? 'open' : 'closed'
const ST_ORDER: Record<Exclude<St, 'all'>, number> = { open: 0, soon: 1, closed: 2 }

/** embedded – «Testlər və sınaqlar» mərkəzinin içində: sinif yuxarıdakı açılan siyahıdan gəlir, başlıq təkrarlanmır. */
export default function Tasks({ embedded, ta: taProp }: { embedded?: boolean; ta?: number | null } = {}) {
  const [lessons, err0] = useMyLessons()
  const [taOwn, setTa] = usePick('tasks-all')             // boş – bütün siniflərim (sinif seçmədən hər şey görünür)
  const ta = embedded ? taProp ?? null : taOwn
  const [archived, setArchived] = useState(false)
  const [list, err, loading, reload] = useLoad<Task[]>(() => get('/api/tasks/mine', archived ? { archived: true } : {}), [archived])
  const [st, setSt] = useState<St>('all')
  const [resend, setResend] = useState<Task | null>(null)
  const [edit, setEdit] = useState<Task | null>(null)
  const [watch, setWatch] = useState<Task | null>(null)
  const [share, setShare] = useState<Task | null>(null)
  const [del, setDel] = useState<Task | null>(null)
  const [exp, setExp] = useState<number | null>(null)          // şagird siyahısı açıq olan test
  const f = usePeriod('tasks', 'date')
  const now = Date.now()
  const inClass = (list || []).filter(t => !ta || t.ta_id === ta)
  const inPeriod = inClass.filter(t => f.has(t.opens_at))
  const count = (k: Exclude<St, 'all'>) => inPeriod.filter(t => stateOf(t, now) === k).length
  // açıq testlər yuxarıda, sonra gözlənilənlər, sonra bağlananlar (seçilmiş sıralama ilə)
  const shown = inPeriod.filter(t => st === 'all' || stateOf(t, now) === st).sort((a, b) =>
    ST_ORDER[stateOf(a, now)] - ST_ORDER[stateOf(b, now)] || (f.sort === 'topic'
      ? (a.class_name || '').localeCompare(b.class_name || '', 'az') || (a.topic?.seq ?? 1e9) - (b.topic?.seq ?? 1e9)
      : Date.parse(b.opens_at) - Date.parse(a.opens_at)))
  const many = !ta                                       // «Bütün siniflərim» – hər testdə sinif nişanı
  // eyni test (bir paket) bir neçə sinfə verilibsə – bir kart, içində siniflər (səliqə: 3 sinif = 3 sətir yox)
  const groups: { key: string; items: Task[] }[] = []
  for (const t of shown) {
    const key = t.batch_id ? `b${t.batch_id}` : `t${t.id}`
    const g = groups.find(x => x.key === key)
    if (g) g.items.push(t)
    else groups.push({ key, items: [t] })
  }
  const statePill = (s: Exclude<St, 'all'>) => s === 'soon' ? <Pill>gözlənilir</Pill> : s === 'open' ? <Pill tone="ok">● açıqdır</Pill> : <Pill tone="info">bağlanıb</Pill>
  const when = (t: Task) => `${dt(t.opens_at)} – ${t.opens_at.slice(0, 10) === t.closes_at.slice(0, 10) ? hm(t.closes_at) : dt(t.closes_at)}`
  const actions = (t: Task, s: Exclude<St, 'all'>) => (<>
    {archived ? (
      <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
        <AsyncBtn className="btn sm primary" ok="Test geri qaytarıldı" onClick={async () => { await post(`/api/tasks/${t.ta_id}/${t.id}/restore`); reload() }}>Geri qaytar</AsyncBtn>
        <button className="btn sm" onClick={() => setWatch(t)}>Nəticələr</button>
        <button className="btn sm ghost" onClick={() => setDel(t)}>Birdəfəlik sil</button>
      </div>
    ) : (
      <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
        <button className={'btn sm' + (exp === t.id ? ' primary' : '')} onClick={() => setExp(e => (e === t.id ? null : t.id))}>👥 Şagirdlər</button>
        <button className="btn sm" onClick={() => setEdit(t)}>✏ Redaktə</button>
        <button className="btn sm ghost" onClick={() => setDel(t)}>🗑 Sil</button>
        <button className={'btn sm' + (s === 'open' ? ' primary' : '')} onClick={() => setWatch(t)}>{s === 'open' ? 'Canlı izlə' : 'Nəticələr'}</button>
        <More>
          <button onClick={() => setShare(t)}>Link göndər</button>
          <button onClick={() => setResend(t)}>Yenidən göndər</button>
          <button onClick={() => paper(t.ta_id!, t.id, t.class_name || '')}>Kağız variant (çap)</button>
        </More>
      </div>)}
    {exp === t.id && <TaskStudents ta={t.ta_id!} id={t.id} />}
    {del?.id === t.id && <ConfirmName name={t.title} action={archived ? 'Birdəfəlik sil' : 'Sil'} onCancel={() => setDel(null)}
      onConfirm={async () => {
        if (archived) { await apiDel(`/api/tasks/${t.ta_id}/${t.id}`); toast('Test sistemdən birdəfəlik silindi') }
        else { await post(`/api/tasks/${t.ta_id}/${t.id}/archive`); toast('Test silindi – «Silinənlər»dən geri qaytarmaq və ya birdəfəlik silmək olar') }
        setDel(null); reload() }} />}
  </>)
  return (
    <>
      {(() => {
        const sub = archived ? 'Silinmiş mövzu testləri – geri qaytarmaq və ya birdəfəlik silmək olar' : 'Perspektiv planın mövzu testləri – təyin etmək, izləmək, idarə etmək.'
        const act = archived ? <button className="btn" onClick={() => setArchived(false)}>‹ Mövzu testləri</button>
          : <Link className="btn primary" to="/plan" title="Perspektiv planda mövzunun yanındakı «🧪 Test» düyməsi">+ Mövzu testi təyin et</Link>
        return embedded ? <div className="hub-head"><span className="small muted grow">{sub}</span>{act}</div>
          : <Top title={archived ? 'Silinmiş mövzu testləri' : 'Onlayn tapşırıqlar'} sub={sub} actions={act} />
      })()}
      <ErrorBox error={err0 || err} />
      <div className="toolbar">
        {!embedded && <select className="sel" aria-label="Sinif / qrup" style={{ width: 'auto', maxWidth: 280 }} value={ta ?? ''} onChange={e => setTa(e.target.value ? Number(e.target.value) : null)}>
          <option value="">Bütün siniflərim</option>
          {(lessons || []).map(l => <option key={l.id} value={l.id}>{l.class_name}{l.subject !== 'Riyaziyyat' ? ` · ${l.subject}` : ''}</option>)}
        </select>}
        {!archived && <Chips label="Vəziyyət" value={st} onChange={setSt} options={[['all', 'Hamısı', inPeriod.length], ['open', '● Açıq', count('open')],
          ['soon', 'Gözlənilir', count('soon')], ['closed', 'Bağlanıb', count('closed')]]} />}
      </div>
      {loading && !list ? <Loading /> : (<>
        {inClass.length > 0 && <PeriodBar f={f} count={shown.length} total={inClass.length} topicLabel="Sinif və mövzu üzrə" />}
        <div className="jlist">
          {list && inClass.length === 0 && <div className="empty">{archived ? 'Silinmiş mövzu testi yoxdur.'
            : <>Hələ mövzu testi yoxdur. <Link to="/plan">Perspektiv plan</Link>da mövzunun yanındakı «🧪 Test» ilə təyin edin.</>}</div>}
          {inClass.length > 0 && shown.length === 0 && <div className="empty">Bu seçimdə test yoxdur – vəziyyəti və ya dövrü dəyişin.</div>}
          {groups.map(g => {
            const head = g.items[0]
            const sts = g.items.map(t => stateOf(t, now))
            const s = sts.includes('open') ? 'open' : sts.includes('soon') ? 'soon' : 'closed'
            const sub = g.items.reduce((n, t) => n + t.submitted, 0)
            const avg = sub ? g.items.reduce((n, t) => n + (t.avg_pct ?? 0) * t.submitted, 0) / sub : null
            const one = g.items.length === 1
            return (
              <div className="jrow cols" key={g.key} style={{ ['--cols' as any]: 'minmax(0,1fr)', ['--mcols' as any]: '1fr', gap: 8 }}>
                <div className="row" style={{ flexWrap: 'wrap' }}>
                  {one && many && <Pill tone="info">{head.class_name}</Pill>}
                  <Pill tone="acc">{head.topic ? `№${head.topic.seq}` : 'planda yoxdur'}</Pill>
                  <b className="grow">{head.title}</b>
                  {!one && <Pill>{g.items.length} sinif</Pill>}
                  {one && head.journal_auto && <Pill tone={head.journal_done_at ? 'ok' : undefined}>{head.journal_done_at ? 'jurnala yazılıb' : 'jurnala yazılacaq'}</Pill>}
                  {statePill(s)}
                </div>
                {one ? <><span className="small muted">{when(head)} · {head.duration_min} dəq · {head.questions} sual · {head.student_ids ? `${head.student_ids.length} şagird` : 'bütün sinif'} · <b>{head.submitted}</b> təhvil{head.avg_pct != null ? <> · orta <b>{fmt(head.avg_pct)}%</b></> : ''}</span>
                  {actions(head, stateOf(head, now))}</>
                  : <><span className="small muted">{head.duration_min} dəq · {head.questions} sual · <b>{sub}</b> təhvil{avg != null ? <> · orta <b>{fmt(avg)}%</b></> : ''}</span>
                    <div className="subrows">{g.items.map(t => (
                      <div key={t.id} className="subrow">
                        <div className="row" style={{ flexWrap: 'wrap', gap: 6 }}>
                          <Pill tone="info">{t.class_name}</Pill>{statePill(stateOf(t, now))}
                          <span className="small muted grow">{when(t)} · <b>{t.submitted}</b> təhvil{t.avg_pct != null ? <> · orta <b>{fmt(t.avg_pct)}%</b></> : ''}{t.journal_auto ? (t.journal_done_at ? ' · jurnala yazılıb' : ' · jurnala yazılacaq') : ''}</span>
                        </div>
                        {actions(t, stateOf(t, now))}
                      </div>))}</div></>}
              </div>)
          })}
        </div>
        {!archived && <p className="small" style={{ marginTop: 12 }}><button className="btn sm ghost" onClick={() => setArchived(true)}>🗑 Silinənlər</button></p>}
      </>)}
      {edit && <TaskEditor ta={edit.ta_id!} taskId={edit.id} fromBank={false} onClose={() => setEdit(null)} onDone={() => { setEdit(null); reload() }} />}
      {watch && <Watch ta={watch.ta_id!} id={watch.id} onClose={() => { setWatch(null); reload() }} />}
      {share && <Share task={share} cls={share.class_name || ''} onClose={() => setShare(null)} />}
      {resend && <Resend ta={resend.ta_id!} task={resend} lessons={lessons || []} onClose={() => setResend(null)}
        onDone={(t, sameClass) => {
          setResend(null)
          if (t.kind === 'sinaq') toast('Hədəf sinfin planında bu mövzu yoxdur – test sınaq kimi «Sınaq imtahanları»na düşdü')
          if (sameClass) reload()
          setShare({ ...t, class_name: lessons?.find(l => l.id === t.ta_id)?.class_name ?? resend.class_name }) }} />}
    </>
  )
}

const TASK_TONE: Record<string, 'ok' | 'info' | undefined> = { 'təhvil verib': 'ok', 'həll edir': 'info', 'başlamayıb': undefined }

/** Testi alan şagirdlər (əlifba ilə) və vəziyyəti – siyahıda sətrin altında (docs/test-sinaq-siyahi-promtu.md §1). */
function TaskStudents({ ta, id }: { ta: number; id: number }) {
  const [d, err] = useLoad<any>(() => get(`/api/tasks/${ta}/${id}`), [ta, id])
  if (err) return <ErrorBox error={err} />
  if (!d) return <Loading />
  const rows = [...d.rows].sort((a: any, b: any) => a.full_name.localeCompare(b.full_name, 'az'))
  return (
    <div className="subrows"><div className="subrow" style={{ alignItems: 'stretch' }}>
      <span className="small muted">{d.summary['təhvil verib']}/{rows.length} təhvil verib · {d.summary['həll edir']} həll edir · {d.summary['başlamayıb']} başlamayıb</span>
      {rows.length === 0 ? <span className="small muted">Şagird yoxdur.</span>
        : <ol className="small" style={{ margin: '4px 0 0', paddingLeft: 22, columns: '2 260px', columnGap: 24 }}>
          {rows.map((r: any) => (
            <li key={r.student_id} style={{ breakInside: 'avoid', marginBottom: 2 }}>{r.full_name}{' '}
              <Pill tone={r.status === 'təhvil verib' ? (r.pct >= 70 ? 'ok' : r.pct >= 40 ? 'warn' : 'bad') : TASK_TONE[r.status]}>
                {r.status === 'təhvil verib' ? `${fmt(r.pct, r.grade ? 0 : 1)}%${r.grade ? ` → ${r.grade}` : ''}` : r.status}</Pill></li>))}
        </ol>}
    </div></div>
  )
}

/** Bir testin idarəsi (sınaq jurnalında hər sinif üçün): canlı izlə, link; nadir əməllər «⋯» menyusunda. */
export function TaskActions({ ta, id, cls, onChange }: { ta: number; id: number; cls: string; onChange: () => void }) {
  const [lessons] = useMyLessons()
  const [mode, setMode] = useState<null | 'watch' | 'share' | 'resend' | 'edit'>(null)
  const [task, setTask] = useState<Task | null>(null)
  const [preset, setPreset] = useState<'absent' | undefined>()
  const open = async (m: 'share' | 'resend', p?: 'absent') => {
    try { setTask(await get<Task>(`/api/tasks/${ta}/${id}/full`)); setPreset(p); setMode(m) } catch (e) { toast('Xəta: ' + (e as Error).message) }
  }
  return (
    <>
      <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
        <button className="btn sm" onClick={() => setMode('watch')}>Canlı izlə</button>
        <button className="btn sm" onClick={() => open('share')}>Link göndər</button>
        <More>
          <button onClick={() => open('resend')}>Yenidən göndər</button>
          <button onClick={() => paper(ta, id, cls)}>Kağız variant (çap)</button>
          <button onClick={() => setMode('edit')}>Redaktə</button>
        </More>
      </div>
      {mode === 'watch' && <Watch ta={ta} id={id} onClose={() => { setMode(null); onChange() }} onResendAbsent={() => open('resend', 'absent')} />}
      {mode === 'share' && task && <Share task={task} cls={cls} onClose={() => setMode(null)} />}
      {mode === 'resend' && task && <Resend ta={ta} task={task} lessons={lessons || []} preset={preset} onClose={() => setMode(null)}
        onDone={t => { setTask(t); setMode('share'); onChange() }} />}
      {mode === 'edit' && <TaskEditor ta={ta} taskId={id} fromBank={false} onClose={() => setMode(null)} onDone={() => { setMode(null); onChange() }} />}
    </>
  )
}

const localInput = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16)

/** Yenidən göndər: eyni suallarla surət – yeni vaxt, həmin və ya başqa sinif/qrup. Köhnə nəticələr yerində qalır. */
function Resend({ ta, task, lessons, preset, onClose, onDone }: { ta: number; task: Task; lessons: MyLesson[]; preset?: 'absent'; onClose: () => void; onDone: (t: Task, sameClass: boolean) => void }) {
  // həmin sinfə: «Yazmayanlar» və «50%-dən aşağı» – bu testin nəticələrindən (docs/sagird-secimi-promtu.md §6)
  const [res] = useLoad<any>(() => get(`/api/tasks/${ta}/${task.id}`), [ta, task.id])
  const presets: Preset[] = res ? [
    { key: 'absent', label: 'Yazmayanlar', ids: res.rows.filter((r: any) => r.status !== 'təhvil verib').map((r: any) => r.student_id) },
    { key: 'low', label: '50%-dən aşağı', ids: res.rows.filter((r: any) => r.pct != null && r.pct < 50).map((r: any) => r.student_id) },
  ] : []
  const [ids, setIds] = useState<number[] | null>(null)
  useEffect(() => { if (res && preset === 'absent') setIds(presets[0].ids) }, [res])
  const start = new Date(); start.setMinutes(Math.ceil(start.getMinutes() / 5) * 5 + 5, 0, 0)
  const end = new Date(start.getTime() + Math.max(Math.max(task.duration_min, 45) + 10, 60) * 60000)
  const [f, setF] = useState({ target: ta, opens: localInput(start), closes: localInput(end), duration: Math.max(task.duration_min, 45), title: task.title })
  const [err, setErr] = useState<unknown>()
  const save = async () => {
    try {
      const t = await post<Task>(`/api/tasks/${ta}/${task.id}/copy`, { target_ta_id: f.target, opens_at: new Date(f.opens).toISOString(),
        closes_at: new Date(f.closes).toISOString(), duration_min: f.duration, title: f.title, student_ids: ids })
      toast('Test yenidən göndərildi'); onDone(t, f.target === ta)
    } catch (e) { setErr(e) }
  }
  return (
    <Drawer title="Testi yenidən göndər" onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Ləğv et</button><AsyncBtn className="btn primary" disabled={ids?.length === 0} onClick={save}>Göndər</AsyncBtn></>}>
      <div className="stack">
        <p className="small muted">Eyni {task.questions} sualla yeni test yaradılır. Köhnə testin nəticələri yerində qalır; şagirdlər yenisini təzədən həll edir.</p>
        <div className="fg">
          <Field label="Sinif / qrup" full><select value={f.target} onChange={e => setF({ ...f, target: Number(e.target.value) })}>
            {lessons.map(l => <option key={l.id} value={l.id}>{l.class_name}{l.subject !== 'Riyaziyyat' ? ` · ${l.subject}` : ''}{l.id === ta ? ' (həmin sinif)' : ''}</option>)}</select></Field>
          <Field label="Ad" full><input value={f.title} maxLength={200} onChange={e => setF({ ...f, title: e.target.value })} /></Field>
          <Field label="Açılır"><input type="datetime-local" value={f.opens} onChange={e => setF({ ...f, opens: e.target.value })} /></Field>
          <Field label="Bağlanır"><input type="datetime-local" value={f.closes} onChange={e => setF({ ...f, closes: e.target.value })} /></Field>
          <Field label="Həll müddəti (dəq)" hint="ən azı 45"><input type="number" min={45} max={300} value={f.duration} onChange={e => setF({ ...f, duration: Number(e.target.value) })} /></Field>
        </div>
        {(f.target !== ta || res) && <StudentPicker key={`${f.target}-${!!res}`} ta={f.target} presets={f.target === ta ? presets : []}
          value={f.target === ta && preset === 'absent' && res ? presets[0].ids : null}
          initialPreset={f.target === ta && preset === 'absent' ? 'absent' : undefined} onChange={setIds} />}
        <ErrorBox error={err} />
      </div>
    </Drawer>
  )
}

async function paper(ta: number, id: number, cls: string) {
  const t = await get(`/api/tasks/${ta}/${id}/full`)
  const L = 'ABCDE'
  const qs = t.questions_full.map((q: any, i: number) => `<div class="q"><b>${i + 1}.</b> ${mathHtml(ml(q.text))}${q.image ? `<img src="${esc(q.image)}">` : ''}
    ${q.kind === 'mcq' ? `<div class="opts">${(q.options || []).map((o: any, j: number) => `${L[j]}) ${mathHtml(ml(o))}`).join('<br>')}</div>` : '<div class="opts">Cavab: ______________________</div>'}</div>`).join('')
  const key = table(['Sual', 'Düzgün cavab'], t.questions_full.map((q: any, i: number) => [i + 1, q.kind === 'mcq' ? L[q.correct] : String(q.answer || '').split('|')[0]]))
  printDoc({ title: `${t.title} – kağız variant`, body: head(t.title, `${cls} · ${t.questions} sual · ${t.duration_min} dəqiqə`) +
    '<p>Ad, soyad: ______________________________ &nbsp; Tarix: ____________</p>' + qs +
    '<div class="pb"></div>' + head(`${t.title} – cavab açarı (müəllim üçün)`) + key })
}

function Share({ task, cls, onClose }: { task: Task; cls: string; onClose: () => void }) {
  const url = taskLink(task.id)
  const text = `${cls} – onlayn test «${task.title}»: ${dt(task.opens_at)}–${hm(task.closes_at)}, ${task.duration_min} dəq. Keçid: ${url}`
  return (
    <Drawer title="Testi link kimi göndər" onClose={onClose}>
      <div className="stack">
        <p className="small muted">Şagird linki açır → giriş kodu və PIN ilə daxil olur (və ya qeydiyyat linki ilə qeydiyyatdan keçir) → birbaşa bu testə düşür. Test yalnız bu sinfin/qrupun (seçilmiş) şagirdlərinə açılır.</p>
        <input className="sel w100" readOnly value={url} onFocus={e => e.target.select()} />
        <div className="row">
          <button className="btn primary" onClick={async () => { try { await navigator.clipboard.writeText(url); toast('Link kopyalandı') } catch { toast('Linki seçib kopyalayın') } }}>Linki kopyala</button>
          <button className="btn" onClick={async () => { try { await navigator.clipboard.writeText(text); toast('Mətn kopyalandı') } catch { toast('Kopyalanmadı') } }}>Mətnlə kopyala</button>
          <a className="btn" target="_blank" rel="noreferrer" href={'https://wa.me/?text=' + encodeURIComponent(text)}>WhatsApp</a>
          {'share' in navigator && <button className="btn" onClick={() => (navigator as any).share({ title: task.title, text, url }).catch(() => {})}>Paylaş…</button>}
        </div>
      </div>
    </Drawer>
  )
}

/** Təhvil verilmiş nəticələr formativ «test» qiyməti kimi seçilən dərsə (defolt – testin açıldığı gün). */
function ToJournal({ ta, id, opens }: { ta: number; id: number; opens: string }) {
  const [date, setDate] = useState(() => isoDate(new Date(opens)))
  const [day] = useLoad<any>(() => get(`/api/journal/${ta}/day`, { date }), [ta, date])
  const [period, setPeriod] = useState<number | ''>('')
  const [res, setRes] = useState<any>(null)
  useEffect(() => { setPeriod(day?.lessons?.[0]?.period ?? '') }, [day])
  const lessons = (day?.lessons || []) as any[]
  return (
    <section className="panel"><h2>Jurnala köçür <small>formativ «test» qiyməti</small></h2>
      <div className="row">
        <input type="date" className="sel" value={date} max={isoDate(new Date())} onChange={e => { setDate(e.target.value); setRes(null) }} aria-label="Dərs günü" />
        <select className="sel" value={period} onChange={e => setPeriod(e.target.value === '' ? '' : Number(e.target.value))} aria-label="Dərs saatı">
          {lessons.length === 0 && <option value="">bu gün dərs yoxdur</option>}
          {lessons.map(l => <option key={l.period} value={l.period} disabled={['KSQ', 'BSQ'].includes(l.plan?.assessment_type)}>
            {ord(l.period)} saat · {(l.entry?.topic || l.plan?.topic || '').slice(0, 40)}{['KSQ', 'BSQ'].includes(l.plan?.assessment_type) ? ` (${l.plan.assessment_type} – olmaz)` : ''}</option>)}
        </select>
        <AsyncBtn className="btn primary" disabled={period === ''} onClick={async () => setRes(await post(`/api/tasks/${ta}/${id}/to-journal`, { date, period }))}>Köçür</AsyncBtn>
      </div>
      {res && <p className="small" style={{ margin: '8px 0 0' }}>{fmtDate(res.date)}, {ord(res.period)} saat: <b>{res.copied}</b> yeni, <b>{res.updated}</b> yeniləndi
        {res.skipped.length > 0 && <> · ötürüldü: {res.skipped.map((s: any) => `${s.full_name} (${s.reason})`).join(', ')}</>}</p>}
      <p className="small muted" style={{ margin: '6px 0 0' }}>Qiymət: düzgün / sual → faiz → qiymət. Həmin dərsdə olmayan şagird ötürülür; təkrar köçürmə köhnəni yeniləyir.</p>
    </section>
  )
}

// ---------------------------------------------------------------- canlı izləmə və nəticələr
function Watch({ ta, id, onClose, onResendAbsent }: { ta: number; id: number; onClose: () => void; onResendAbsent?: () => void }) {
  const [d, err, , reload] = useLoad<any>(() => get(`/api/tasks/${ta}/${id}`), [ta, id])
  const [q, setQ] = useState('')
  const [st, setSt] = useState<'all' | 'başlamayıb' | 'həll edir' | 'təhvil verib'>('all')
  const [auto, setAuto] = useState(true)
  const live = !!d && Date.now() < Date.parse(d.task.closes_at)
  useEffect(() => { if (!auto || !live) return; const i = setInterval(reload, 5000); return () => clearInterval(i) }, [auto, live, reload])
  const skew = d ? Date.parse(d.server_time) - Date.now() : 0
  const left = (s: string | null) => { if (!s) return ''; const m = Math.max(0, Math.round((Date.parse(s) - (Date.now() + skew)) / 60000)); return `${m} dəq qalıb` }
  const rows = (d?.rows || []).filter((r: any) => (st === 'all' || r.status === st) && (!q || r.full_name.toLowerCase().includes(q.toLowerCase())))
  const total = d?.task.questions || 0
  return (
    <Drawer title={d ? d.task.title : 'Nəticələr'} onClose={onClose}>
      <ErrorBox error={err} />
      {d && (
        <div className="stack">
          <div className="kpis">
            <div className="kpi"><b>{d.summary['başlamayıb']}</b><span>başlamayıb</span></div>
            <div className="kpi"><b style={{ color: 'var(--info)' }}>{d.summary['həll edir']}</b><span>həll edir</span></div>
            <div className="kpi"><b style={{ color: 'var(--ok)' }}>{d.summary['təhvil verib']}</b><span>təhvil verib</span></div>
          </div>
          <div className="row">
            {live ? <label className="check small"><input type="checkbox" checked={auto} onChange={e => setAuto(e.target.checked)} /> Canlı (hər 5 san.)</label> : <Pill tone="info">bağlanıb</Pill>}
            <button className="btn sm" onClick={reload}>Yenilə</button>
            <input className="sel grow" placeholder="Şagird axtar" value={q} onChange={e => setQ(e.target.value)} />
            {!live && onResendAbsent && d.summary['başlamayıb'] + d.summary['həll edir'] > 0 &&
              <button className="btn sm" onClick={onResendAbsent}>Yazmayanlara yenidən göndər ({d.summary['başlamayıb'] + d.summary['həll edir']})</button>}
          </div>
          <div className="row" style={{ gap: 6 }}>
            {(['all', 'həll edir', 'başlamayıb', 'təhvil verib'] as const).map(k => <button key={k} className="chip" aria-pressed={st === k} onClick={() => setSt(k)}>{k === 'all' ? 'Hamısı' : k}</button>)}
          </div>
          <div className="jlist">{rows.map((r: any) => (
            <div className="jrow" key={r.student_id} style={{ gridTemplateColumns: 'minmax(0,1fr) auto' }}>
              <span><b>{r.full_name}</b><span className="sub small muted"> {r.portal_code}{r.auto_submitted ? ' · vaxt bitdi' : ''}</span>
                {r.solution_at && <> <a className="small" href={`/api/tasks/${ta}/${id}/solution/${r.student_id}`} target="_blank" rel="noreferrer" title="Şagirdin həll şəkilləri (PDF)">📄 Həll</a></>}
                {r.status === 'həll edir' && <>
                  <div className="cmp" style={{ marginTop: 6 }}><i style={{ width: (total ? r.answered * 100 / total : 0) + '%' }} /></div>
                  <span className="small muted">{r.answered}/{total} cavab · {left(r.deadline)}</span></>}
              </span>
              <span className="row">{r.status === 'təhvil verib'
                ? <><span className="small">{r.correct}/{r.total}</span><Pill tone={r.grade ? gradeTone(r.grade) : r.pct >= 70 ? 'ok' : r.pct >= 40 ? 'warn' : 'bad'}>{fmt(r.pct, r.grade ? 0 : 1)}%{r.grade ? ` → ${r.grade}` : ''}</Pill></>
                : <Pill tone={r.status === 'həll edir' ? 'info' : undefined}>{r.status}</Pill>}
                {live && r.status !== 'başlamayıb' && <AsyncBtn className="btn sm ghost" ok="Təkrar icazə verildi"
                  onClick={async () => { await apiDel(`/api/tasks/${ta}/${id}/attempts/${r.student_id}`); reload() }}>Təkrar icazə</AsyncBtn>}</span>
            </div>))}
            {rows.length === 0 && <div className="empty">Uyğun şagird yoxdur.</div>}
          </div>
          {d.task.kind === 'sinaq' ? <p className="small muted">Sınaq imtahanı formativ jurnala köçürülmür – nəticə «Sınaq imtahanları» bölməsində (jurnal və reytinq).</p>
            : d.summary['təhvil verib'] > 0 && <ToJournal ta={ta} id={id} opens={d.task.opens_at} />}
          {d.questions.length > 0 && d.summary['təhvil verib'] > 0 && (
            <section className="panel"><h2>Suallar üzrə</h2>
              {d.questions.map((x: any) => (
                <div key={x.index} className="row small" style={{ marginBottom: 6, flexWrap: 'nowrap' }}>
                  <span className="grow clamp2">{x.index + 1}. <MathText text={ml(x.text)} /></span>
                  <div className="cmp" style={{ width: 100, marginTop: 0, flex: 'none' }}><i style={{ width: (x.pct || 0) + '%', background: (x.pct ?? 100) < 50 ? 'var(--bad)' : 'var(--accent)' }} /></div>
                  <b className="num" style={{ width: 44, textAlign: 'right' }}>{fmt(x.pct, 0)}%</b>
                </div>))}
            </section>)}
        </div>)}
    </Drawer>
  )
}
