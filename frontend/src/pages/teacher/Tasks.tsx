// Onlayn tapşırıqlar (müəllim): yaratma / viktorinadan test / redaktə / link kimi göndərmə / silmə / canlı izləmə.
import { useEffect, useState } from 'react'
import { useT, ml, tt } from '../../i18n'
import { del as apiDel, get, post } from '../../api'
import { MathText } from '../../MathText'
import { AsyncBtn, Chips, ConfirmName, Drawer, ErrorBox, Field, fmt, fmtDate, gradeTone, isoDate, Loading, More, Pill, toast, Top, useLoad, hourN } from '../../ui'
import { type MyLesson, type Preset, StudentPicker, useMyLessons, usePick } from './common'
import { PeriodBar, usePeriod } from '../../periods'
import { Link } from 'react-router-dom'
import TaskEditor from './TaskEditor'
import { esc, head, mathHtml, printDoc, table } from '../../print'
import { azDT } from '../../ui'

type Task = { id: number; title: string; created_at?: string | null; opens_at: string; closes_at: string; duration_min: number; questions: number; submitted: number; avg_pct: number | null; student_ids: number[] | null
  kind?: string | null; topic?: { seq: number; topic: string } | null; journal_auto?: boolean; journal_done_at?: string | null
  ta_id?: number; class_name?: string | null; batch_id?: number | null; group_key?: string; group_sends?: number; group_main_id?: number }
const dt = (s: string) => azDT(new Date(s), { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
const hm = (s: string) => azDT(new Date(s), { hour: '2-digit', minute: '2-digit' })
export const taskLink = (id: number) => `${location.origin}/t/${id}`

type St = 'all' | 'open' | 'soon' | 'closed'
const stateOf = (t: { opens_at: string; closes_at: string }, now = Date.now()): Exclude<St, 'all'> =>
  now < Date.parse(t.opens_at) ? 'soon' : now < Date.parse(t.closes_at) ? 'open' : 'closed'
const ST_ORDER: Record<Exclude<St, 'all'>, number> = { open: 0, soon: 1, closed: 2 }

/** embedded – «Testlər və sınaqlar» mərkəzinin içində: sinif yuxarıdakı açılan siyahıdan gəlir, başlıq təkrarlanmır. */
export default function Tasks({ embedded, ta: taProp }: { embedded?: boolean; ta?: number | null } = {}) {
  const t = useT()
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
  // eyni testin yenidən göndərişləri (alt-qruplara) – əsas testin altında açılan sətir (yalnız görünüş; əməliyyatlar hər göndəriş üçün ayrıdır)
  const kidsMap = new Map<number, Task[]>()
  const kidIds = new Set<number>()
  const byGk = new Map<string, Task[]>()
  for (const t of shown) if (t.group_key) byGk.set(t.group_key, [...(byGk.get(t.group_key) || []), t])
  for (const arr of byGk.values()) {
    if (arr.length < 2) continue
    const main = arr.find(x => x.id === x.group_main_id) || arr[0]
    const kids = arr.filter(x => x !== main)
    kidsMap.set(main.id, kids)
    kids.forEach(k => kidIds.add(k.id))
  }
  const kidsOf = (t: Task) => kidsMap.get(t.id) || []
  const sendsPill = (t: Task) => (t.group_sends ?? 1) > 1 ? <Pill>{tt('{n} göndəriş', { n: t.group_sends })}</Pill> : null
  const kidRows = (t: Task) => kidsOf(t).length === 0 ? null : (
    <div className="subrows">{kidsOf(t).map(k => (
      <div key={k.id} className="subrow">
        <div className="row" style={{ flexWrap: 'wrap', gap: 6 }}>
          <span className="small muted grow">{tt('↳ yenidən göndəriş: {who}, {date}', {
            who: k.student_ids ? tt('{length} şagird', { length: k.student_ids.length }) : tt('bütün sinif'),
            date: azDT(new Date(k.opens_at), { day: '2-digit', month: '2-digit' }) })} · <b>{k.submitted}</b> {tt('təhvil')}</span>
          {statePill(stateOf(k, now))}
        </div>
        {actions(k, stateOf(k, now))}
      </div>))}</div>)
  const groups: { key: string; items: Task[] }[] = []
  for (const t of shown.filter(x => !kidIds.has(x.id))) {
    const key = t.batch_id ? `b${t.batch_id}` : `t${t.id}`
    const g = groups.find(x => x.key === key)
    if (g) g.items.push(t)
    else groups.push({ key, items: [t] })
  }
  const statePill = (s: Exclude<St, 'all'>) => s === 'soon' ? <Pill>{t('gözlənilir')}</Pill> : s === 'open' ? <Pill tone="ok">{t('● açıqdır')}</Pill> : <Pill tone="info">{t('bağlanıb')}</Pill>
  const when = (t: Task) => `${dt(t.opens_at)} – ${t.opens_at.slice(0, 10) === t.closes_at.slice(0, 10) ? hm(t.closes_at) : dt(t.closes_at)}`
  const actions = (t: Task, s: Exclude<St, 'all'>) => (<>
    {archived ? (
      <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
        <AsyncBtn className="btn sm primary" ok="Test geri qaytarıldı" onClick={async () => { await post(`/api/tasks/${t.ta_id}/${t.id}/restore`); reload() }}>{tt('Geri qaytar')}</AsyncBtn>
        <button className="btn sm" onClick={() => setWatch(t)}>{tt('Nəticələr')}</button>
        <button className="btn sm ghost" onClick={() => setDel(t)}>{tt('Birdəfəlik sil')}</button>
      </div>
    ) : (
      <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
        <button className={'btn sm' + (exp === t.id ? ' primary' : '')} onClick={() => setExp(e => (e === t.id ? null : t.id))}>{tt('👥 Şagirdlər')}</button>
        <button className="btn sm" onClick={() => setEdit(t)}>{tt('✏ Redaktə')}</button>
        <button className="btn sm ghost" onClick={() => setDel(t)}>{tt('🗑 Sil')}</button>
        <button className={'btn sm' + (s === 'open' ? ' primary' : '')} onClick={() => setWatch(t)}>{s === 'open' ? tt('Canlı izlə') : 'Nəticələr'}</button>
        <More>
          <button onClick={() => setShare(t)}>{tt('Link göndər')}</button>
          <button onClick={() => setResend(t)}>{tt('Yenidən göndər')}</button>
          <button onClick={() => paper(t.ta_id!, t.id, t.class_name || '')}>{tt('Kağız variant (çap)')}</button>
        </More>
      </div>)}
    {exp === t.id && <TaskStudents ta={t.ta_id!} id={t.id} />}
    {del?.id === t.id && <ConfirmName name={t.title} action={archived ? tt('Birdəfəlik sil') : 'Sil'} onCancel={() => setDel(null)}
      onConfirm={async () => {
        if (archived) { await apiDel(`/api/tasks/${t.ta_id}/${t.id}`); toast(tt('Test sistemdən birdəfəlik silindi')) }
        else { await post(`/api/tasks/${t.ta_id}/${t.id}/archive`); toast(tt('Test silindi – «Silinənlər»dən geri qaytarmaq və ya birdəfəlik silmək olar')) }
        setDel(null); reload() }} />}
  </>)
  return (
    <>
      {(() => {
        const sub = archived ? 'Silinmiş mövzu testləri – geri qaytarmaq və ya birdəfəlik silmək olar' : t('Perspektiv planın mövzu testləri – təyin etmək, izləmək, idarə etmək.')
        const act = archived ? <button className="btn" onClick={() => setArchived(false)}>{t('‹ Mövzu testləri')}</button>
          : <Link className="btn primary" to="/plan" title={t('Perspektiv planda mövzunun yanındakı «🧪 Test» düyməsi')}>{t('+ Mövzu testi təyin et')}</Link>
        return embedded ? <div className="hub-head"><span className="small muted grow">{sub}</span>{act}</div>
          : <Top title={archived ? t('Silinmiş mövzu testləri') : 'Onlayn tapşırıqlar'} sub={sub} actions={act} />
      })()}
      <ErrorBox error={err0 || err} />
      {!embedded && <div className="toolbar">
        <select className="sel" aria-label={t('Sinif / qrup')} style={{ width: 'auto', maxWidth: 280 }} value={ta ?? ''} onChange={e => setTa(e.target.value ? Number(e.target.value) : null)}>
          <option value="">{t('Bütün siniflərim')}</option>
          {(lessons || []).map(l => <option key={l.id} value={l.id}>{l.class_name}{l.subject !== 'Riyaziyyat' ? ` · ${l.subject}` : ''}</option>)}
        </select></div>}
      {loading && !list ? <Loading /> : (<>
        {inClass.length > 0 && <PeriodBar f={f} count={shown.length} total={inClass.length} topicLabel="Sinif və mövzu üzrə" lead={!archived ? <Chips label={t('Vəziyyət')} value={st} onChange={setSt} options={[['all', 'Hamısı', inPeriod.length], ['open', '● Açıq', count('open')], ['soon', 'Gözlənilir', count('soon')], ['closed', t('Bağlanıb'), count('closed')]]} /> : undefined} />}
        <div className="jlist">
          {list && inClass.length === 0 && <div className="empty">{archived ? t('Silinmiş mövzu testi yoxdur.')
            : <>{t('Hələ mövzu testi yoxdur.')} <Link to="/plan">{t('Perspektiv plan')}</Link>{t('da mövzunun yanındakı «🧪 Test» ilə təyin edin.')}</>}</div>}
          {inClass.length > 0 && shown.length === 0 && <div className="empty">{t('Bu seçimdə test yoxdur – vəziyyəti və ya dövrü dəyişin.')}</div>}
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
                  {!one && <Pill>{g.items.length} {t('sinif')}</Pill>}
                  {one && head.journal_auto && <Pill tone={head.journal_done_at ? 'ok' : undefined}>{head.journal_done_at ? t('jurnala yazılıb') : t('jurnala yazılacaq')}</Pill>}
                  {one && sendsPill(head)}
                  {statePill(s)}
                </div>
                {one ? <><span className="small muted">{when(head)} · {head.duration_min} {t('dəq ·')} {head.questions} {t('sual ·')} {head.student_ids ? t('{length} şagird', { length: head.student_ids.length }) : 'bütün sinif'} · <b>{head.submitted}</b> {t('təhvil')}{head.avg_pct != null ? <> {t('· orta')} <b>{fmt(head.avg_pct)}%</b></> : ''}</span>
                  {actions(head, stateOf(head, now))}{kidRows(head)}</>
                  : <><span className="small muted">{head.duration_min} {t('dəq ·')} {head.questions} {t('sual ·')} <b>{sub}</b> {t('təhvil')}{avg != null ? <> {t('· orta')} <b>{fmt(avg)}%</b></> : ''}</span>
                    <div className="subrows">{g.items.map(t => (
                      <div key={t.id} className="subrow">
                        <div className="row" style={{ flexWrap: 'wrap', gap: 6 }}>
                          <Pill tone="info">{t.class_name}</Pill>{sendsPill(t)}{statePill(stateOf(t, now))}
                          <span className="small muted grow">{when(t)} · <b>{t.submitted}</b> {tt('təhvil')}{t.avg_pct != null ? <> {tt('· orta')} <b>{fmt(t.avg_pct)}%</b></> : ''}{t.journal_auto ? (t.journal_done_at ? (' · ' + tt('jurnala yazılıb')) : (' · ' + tt('jurnala yazılacaq'))) : ''}</span>
                        </div>
                        {actions(t, stateOf(t, now))}{kidRows(t)}
                      </div>))}</div></>}
              </div>)
          })}
        </div>
        {!archived && <p className="small" style={{ marginTop: 12 }}><button className="btn sm ghost" onClick={() => setArchived(true)}>{t('🗑 Silinənlər')}</button></p>}
      </>)}
      {edit && <TaskEditor ta={edit.ta_id!} taskId={edit.id} fromBank={false} onClose={() => setEdit(null)} onDone={() => { setEdit(null); reload() }} />}
      {watch && <Watch ta={watch.ta_id!} id={watch.id} onClose={() => { setWatch(null); reload() }} />}
      {share && <Share task={share} cls={share.class_name || ''} onClose={() => setShare(null)} />}
      {resend && <Resend ta={resend.ta_id!} task={resend} lessons={lessons || []} onClose={() => setResend(null)}
        onDone={(t, sameClass) => {
          setResend(null)
          if (t.kind === 'sinaq') toast(tt('Hədəf sinfin planında bu mövzu yoxdur – test sınaq kimi «Sınaq imtahanları»na düşdü'))
          if (sameClass) reload()
          setShare({ ...t, class_name: lessons?.find(l => l.id === t.ta_id)?.class_name ?? resend.class_name }) }} />}
    </>
  )
}

const TASK_TONE: Record<string, 'ok' | 'info' | undefined> = { 'təhvil verib': 'ok', 'həll edir': 'info', 'başlamayıb': undefined }

/** Testi alan şagirdlər (əlifba ilə) və vəziyyəti – siyahıda sətrin altında (docs/test-sinaq-siyahi-promtu.md §1). */
function TaskStudents({ ta, id }: { ta: number; id: number }) {
  const t = useT()
  const [d, err] = useLoad<any>(() => get(`/api/tasks/${ta}/${id}`), [ta, id])
  if (err) return <ErrorBox error={err} />
  if (!d) return <Loading />
  const rows = [...d.rows].sort((a: any, b: any) => a.full_name.localeCompare(b.full_name, 'az'))
  return (
    <div className="subrows"><div className="subrow" style={{ alignItems: 'stretch' }}>
      <span className="small muted">{d.summary['təhvil verib']}/{rows.length} {t('təhvil verib ·')} {d.summary['həll edir']} {t('həll edir ·')} {d.summary['başlamayıb']} {t('başlamayıb')}</span>
      {rows.length === 0 ? <span className="small muted">{t('Şagird yoxdur.')}</span>
        : <ol className="small" style={{ margin: '4px 0 0', paddingLeft: 22, columns: '2 260px', columnGap: 24 }}>
          {rows.map((r: any) => (
            <li key={r.student_id} style={{ breakInside: 'avoid', marginBottom: 2 }}>{r.full_name}{' '}
              <Pill tone={r.status === 'təhvil verib' ? (r.pct >= 70 ? 'ok' : r.pct >= 40 ? 'warn' : 'bad') : TASK_TONE[r.status]}>
                {r.status === 'təhvil verib' ? `${fmt(r.pct, r.grade ? 0 : 1)}%${r.grade ? ` → ${r.grade}` : ''}` : t(r.status)}</Pill></li>))}
        </ol>}
    </div></div>
  )
}

/** Bir testin idarəsi (sınaq jurnalında hər sinif üçün): canlı izlə, link; nadir əməllər «⋯» menyusunda. */
export function TaskActions({ ta, id, cls, onChange }: { ta: number; id: number; cls: string; onChange: () => void }) {
  const t = useT()
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
        <button className="btn sm" onClick={() => setMode('watch')}>{t('Canlı izlə')}</button>
        <button className="btn sm" onClick={() => open('share')}>{t('Link göndər')}</button>
        <More>
          <button onClick={() => open('resend')}>{t('Yenidən göndər')}</button>
          <button onClick={() => paper(ta, id, cls)}>{t('Kağız variant (çap)')}</button>
          <button onClick={() => setMode('edit')}>{t('Redaktə')}</button>
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
/** Bir (və ya bir neçə) konkret şagirdə yenidən göndər — sınaq jurnalından / şagird siyahısından (eyni sınaq paketinə düşür). */
export function ResendToStudents({ ta, taskId, ids, onClose, onDone }: { ta: number; taskId: number; ids: number[]; onClose: () => void; onDone: () => void }) {
  const t = useT()
  const [lessons] = useMyLessons()
  const [task, err] = useLoad<Task>(() => get(`/api/tasks/${ta}/${taskId}/full`), [ta, taskId])
  if (err) return <Drawer title={t('Yenidən göndər')} onClose={onClose}><ErrorBox error={err} /></Drawer>
  if (!task) return null
  return <Resend ta={ta} task={task} lessons={lessons || []} onlyIds={ids} onClose={onClose}
    onDone={() => { toast(ids.length === 1 ? t('Sınaq şagirdə yenidən göndərildi') : t('Sınaq {length} şagirdə yenidən göndərildi', { length: ids.length })); onDone() }} />
}

function Resend({ ta, task, lessons, preset, onlyIds, onClose, onDone }: { ta: number; task: Task; lessons: MyLesson[]; preset?: 'absent'; onlyIds?: number[]; onClose: () => void; onDone: (t: Task, sameClass: boolean) => void }) {
  const t = useT()
  // həmin sinfə: «Yazmayanlar» və «50%-dən aşağı» – bu testin nəticələrindən (docs/sagird-secimi-promtu.md §6)
  const [res] = useLoad<any>(() => get(`/api/tasks/${ta}/${task.id}`), [ta, task.id])
  const presets: Preset[] = res ? [
    { key: 'absent', label: 'Yazmayanlar', ids: res.rows.filter((r: any) => r.status !== 'təhvil verib').map((r: any) => r.student_id) },
    { key: 'low', label: t('50%-dən aşağı'), ids: res.rows.filter((r: any) => r.pct != null && r.pct < 50).map((r: any) => r.student_id) },
  ] : []
  const [ids, setIds] = useState<number[] | null>(onlyIds ?? null)
  useEffect(() => { if (res && preset === 'absent' && !onlyIds) setIds(presets[0].ids) }, [res])
  const start = new Date(); start.setMinutes(Math.ceil(start.getMinutes() / 5) * 5 + 5, 0, 0)
  const end = new Date(start.getTime() + Math.max(Math.max(task.duration_min, 45) + 10, 60) * 60000)
  const [f, setF] = useState({ target: ta, opens: localInput(start), closes: localInput(end), duration: Math.max(task.duration_min, 45), title: task.title })
  const [err, setErr] = useState<unknown>()
  const save = async () => {
    try {
      const t = await post<Task>(`/api/tasks/${ta}/${task.id}/copy`, { target_ta_id: f.target, opens_at: new Date(f.opens).toISOString(),
        closes_at: new Date(f.closes).toISOString(), duration_min: f.duration, title: f.title, student_ids: ids })
      toast(tt('Test yenidən göndərildi')); onDone(t, f.target === ta)
    } catch (e) { setErr(e) }
  }
  return (
    <Drawer title={t('Testi yenidən göndər')} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>{t('Ləğv et')}</button><AsyncBtn className="btn primary" disabled={ids?.length === 0} onClick={save}>{t('Göndər')}</AsyncBtn></>}>
      <div className="stack">
        <p className="small muted">{t('Eyni')} {task.questions} {t('sualla yeni test yaradılır. Köhnə testin nəticələri yerində qalır; şagirdlər yenisini təzədən həll edir.')}</p>
        <div className="fg">
          <Field label={t('Sinif / qrup')} full><select value={f.target} onChange={e => setF({ ...f, target: Number(e.target.value) })}>
            {lessons.map(l => <option key={l.id} value={l.id}>{l.class_name}{l.subject !== 'Riyaziyyat' ? ` · ${l.subject}` : ''}{l.id === ta ? (' ' + t('(həmin sinif)')) : ''}</option>)}</select></Field>
          <Field label={t('Ad')} full><input value={f.title} maxLength={200} onChange={e => setF({ ...f, title: e.target.value })} /></Field>
          <Field label={t('Açılır')}><input type="datetime-local" value={f.opens} onChange={e => setF({ ...f, opens: e.target.value })} /></Field>
          <Field label={t('Bağlanır')}><input type="datetime-local" value={f.closes} onChange={e => setF({ ...f, closes: e.target.value })} /></Field>
          <Field label={t('Həll müddəti (dəq)')} hint="ən azı 45"><input type="number" min={45} max={300} value={f.duration} onChange={e => setF({ ...f, duration: Number(e.target.value) })} /></Field>
        </div>
        {(f.target !== ta || res) && <StudentPicker key={`${f.target}-${!!res}`} ta={f.target} presets={f.target === ta ? presets : []}
          value={f.target === ta && onlyIds ? onlyIds : f.target === ta && preset === 'absent' && res ? presets[0].ids : null}
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
  const t = useT()
  const url = taskLink(task.id)
  const text = `${cls} – onlayn test «${task.title}»: ${dt(task.opens_at)}–${hm(task.closes_at)}, ${task.duration_min} dəq. Keçid: ${url}`
  return (
    <Drawer title={t('Testi link kimi göndər')} onClose={onClose}>
      <div className="stack">
        <p className="small muted">{t('Şagird linki açır → giriş kodu və PIN ilə daxil olur (və ya qeydiyyat linki ilə qeydiyyatdan keçir) → birbaşa bu testə düşür. Test yalnız bu sinfin/qrupun (seçilmiş) şagirdlərinə açılır.')}</p>
        <input className="sel w100" readOnly value={url} onFocus={e => e.target.select()} />
        <div className="row">
          <button className="btn primary" onClick={async () => { try { await navigator.clipboard.writeText(url); toast(t('Link kopyalandı')) } catch { toast('Linki seçib kopyalayın') } }}>{t('Linki kopyala')}</button>
          <button className="btn" onClick={async () => { try { await navigator.clipboard.writeText(text); toast(t('Mətn kopyalandı')) } catch { toast(t('Kopyalanmadı')) } }}>{t('Mətnlə kopyala')}</button>
          <a className="btn" target="_blank" rel="noreferrer" href={'https://wa.me/?text=' + encodeURIComponent(text)}>{t('WhatsApp')}</a>
          {'share' in navigator && <button className="btn" onClick={() => (navigator as any).share({ title: task.title, text, url }).catch(() => {})}>{t('Paylaş…')}</button>}
        </div>
      </div>
    </Drawer>
  )
}

/** Təhvil verilmiş nəticələr formativ «test» qiyməti kimi seçilən dərsə (defolt – testin açıldığı gün). */
function ToJournal({ ta, id, opens }: { ta: number; id: number; opens: string }) {
  const t = useT()
  const [date, setDate] = useState(() => isoDate(new Date(opens)))
  const [day] = useLoad<any>(() => get(`/api/journal/${ta}/day`, { date }), [ta, date])
  const [period, setPeriod] = useState<number | ''>('')
  const [res, setRes] = useState<any>(null)
  useEffect(() => { setPeriod(day?.lessons?.[0]?.period ?? '') }, [day])
  const lessons = (day?.lessons || []) as any[]
  return (
    <section className="panel"><h2>{t('Jurnala köçür')} <small>{t('formativ «test» qiyməti')}</small></h2>
      <div className="row">
        <input type="date" className="sel" value={date} max={isoDate(new Date())} onChange={e => { setDate(e.target.value); setRes(null) }} aria-label={t('Dərs günü')} />
        <select className="sel" value={period} onChange={e => setPeriod(e.target.value === '' ? '' : Number(e.target.value))} aria-label={t('Dərs saatı')}>
          {lessons.length === 0 && <option value="">{t('bu gün dərs yoxdur')}</option>}
          {lessons.map(l => <option key={l.period} value={l.period} disabled={['KSQ', 'BSQ'].includes(l.plan?.assessment_type)}>
            {hourN(l.period)} · {(l.entry?.topic || l.plan?.topic || '').slice(0, 40)}{['KSQ', 'BSQ'].includes(l.plan?.assessment_type) ? (' ' + t('({assessment_type} – olmaz)', { assessment_type: l.plan.assessment_type })) : ''}</option>)}
        </select>
        <AsyncBtn className="btn primary" disabled={period === ''} onClick={async () => setRes(await post(`/api/tasks/${ta}/${id}/to-journal`, { date, period }))}>{t('Köçür')}</AsyncBtn>
      </div>
      {res && <p className="small" style={{ margin: '8px 0 0' }}>{fmtDate(res.date)}, {hourN(res.period)}: <b>{res.copied}</b> {t('yeni,')} <b>{res.updated}</b> {t('yeniləndi')}
        {res.skipped.length > 0 && <> {t('· ötürüldü:')} {res.skipped.map((s: any) => `${s.full_name} (${s.reason})`).join(', ')}</>}</p>}
      <p className="small muted" style={{ margin: '6px 0 0' }}>{t('Qiymət: düzgün / sual → faiz → qiymət. Həmin dərsdə olmayan şagird ötürülür; təkrar köçürmə köhnəni yeniləyir.')}</p>
    </section>
  )
}

// ---------------------------------------------------------------- canlı izləmə və nəticələr
function Watch({ ta, id, onClose, onResendAbsent }: { ta: number; id: number; onClose: () => void; onResendAbsent?: () => void }) {
  const t = useT()
  const [d, err, , reload] = useLoad<any>(() => get(`/api/tasks/${ta}/${id}`), [ta, id])
  const [q, setQ] = useState('')
  const [st, setSt] = useState<'all' | 'başlamayıb' | 'həll edir' | 'təhvil verib'>('all')
  const [auto, setAuto] = useState(true)
  const live = !!d && Date.now() < Date.parse(d.task.closes_at)
  useEffect(() => { if (!auto || !live) return; const i = setInterval(reload, 5000); return () => clearInterval(i) }, [auto, live, reload])
  const skew = d ? Date.parse(d.server_time) - Date.now() : 0
  const left = (s: string | null) => { if (!s) return ''; const m = Math.max(0, Math.round((Date.parse(s) - (Date.now() + skew)) / 60000)); return t('{m} dəq qalıb', { m }) }
  const rows = (d?.rows || []).filter((r: any) => (st === 'all' || r.status === st) && (!q || r.full_name.toLowerCase().includes(q.toLowerCase())))
  const total = d?.task.questions || 0
  return (
    <Drawer title={d ? d.task.title : 'Nəticələr'} onClose={onClose}>
      <ErrorBox error={err} />
      {d && (
        <div className="stack">
          <div className="kpis">
            <div className="kpi"><b>{d.summary['başlamayıb']}</b><span>{t('başlamayıb')}</span></div>
            <div className="kpi"><b style={{ color: 'var(--info)' }}>{d.summary['həll edir']}</b><span>{t('həll edir')}</span></div>
            <div className="kpi"><b style={{ color: 'var(--ok)' }}>{d.summary['təhvil verib']}</b><span>{t('təhvil verib')}</span></div>
          </div>
          <div className="row">
            {live ? <label className="check small"><input type="checkbox" checked={auto} onChange={e => setAuto(e.target.checked)} /> {t('Canlı (hər 5 san.)')}</label> : <Pill tone="info">{t('bağlanıb')}</Pill>}
            <button className="btn sm" onClick={reload}>{t('Yenilə')}</button>
            <input className="sel grow" placeholder={t('Şagird axtar')} value={q} onChange={e => setQ(e.target.value)} />
            {!live && onResendAbsent && d.summary['başlamayıb'] + d.summary['həll edir'] > 0 &&
              <button className="btn sm" onClick={onResendAbsent}>{t('Yazmayanlara yenidən göndər (')}{d.summary['başlamayıb'] + d.summary['həll edir']})</button>}
          </div>
          <div className="row" style={{ gap: 6 }}>
            {(['all', 'həll edir', 'başlamayıb', 'təhvil verib'] as const).map(k => <button key={k} className="chip" aria-pressed={st === k} onClick={() => setSt(k)}>{k === 'all' ? t('Hamısı') : t(k)}</button>)}
          </div>
          <div className="jlist">{rows.map((r: any) => (
            <div className="jrow" key={r.student_id} style={{ gridTemplateColumns: 'minmax(0,1fr) auto' }}>
              <span><b>{r.full_name}</b><span className="sub small muted"> {r.portal_code}{r.auto_submitted ? (' · ' + t('vaxt bitdi')) : ''}</span>
                {r.solution_at && <> <a className="small" href={`/api/tasks/${ta}/${id}/solution/${r.student_id}`} target="_blank" rel="noreferrer" title={t('Şagirdin həll şəkilləri (PDF)')}>{t('📄 Həll')}</a></>}
                {r.status === 'həll edir' && <>
                  <div className="cmp" style={{ marginTop: 6 }}><i style={{ width: (total ? r.answered * 100 / total : 0) + '%' }} /></div>
                  <span className="small muted">{r.answered}/{total} {t('cavab ·')} {left(r.deadline)}</span></>}
              </span>
              <span className="row">{r.status === 'təhvil verib'
                ? <><span className="small">{r.correct}/{r.total}</span><Pill tone={r.grade ? gradeTone(r.grade) : r.pct >= 70 ? 'ok' : r.pct >= 40 ? 'warn' : 'bad'}>{fmt(r.pct, r.grade ? 0 : 1)}%{r.grade ? ` → ${r.grade}` : ''}</Pill></>
                : <Pill tone={r.status === 'həll edir' ? 'info' : undefined}>{r.status}</Pill>}
                {r.status !== 'başlamayıb' && <AsyncBtn className="btn sm" ok={tt('Şagird testi davam etdirə bilər')} title={tt('Cavablar saxlanır, qalan vaxt yenidən verilir (test bağlansa da)')}
                  onClick={async () => { await post(`/api/tasks/${ta}/${id}/attempts/${r.student_id}/resume`); reload() }}>▶ {tt('Davam etsin')}</AsyncBtn>}
                {live && r.status !== 'başlamayıb' && <AsyncBtn className="btn sm ghost" ok="Təkrar icazə verildi"
                  onClick={async () => { await apiDel(`/api/tasks/${ta}/${id}/attempts/${r.student_id}`); reload() }}>{t('Təkrar icazə')}</AsyncBtn>}</span>
            </div>))}
            {rows.length === 0 && <div className="empty">{t('Uyğun şagird yoxdur.')}</div>}
          </div>
          {d.task.kind === 'sinaq' ? <p className="small muted">{t('Sınaq imtahanı formativ jurnala köçürülmür – nəticə «Sınaq imtahanları» bölməsində (jurnal və reytinq).')}</p>
            : d.summary['təhvil verib'] > 0 && <ToJournal ta={ta} id={id} opens={d.task.opens_at} />}
          {d.questions.length > 0 && d.summary['təhvil verib'] > 0 && (
            <section className="panel"><h2>{t('Suallar üzrə')}</h2>
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
