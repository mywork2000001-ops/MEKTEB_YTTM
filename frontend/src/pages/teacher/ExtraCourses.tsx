// Əlavə məşğələ (əyani və onlayn): kurs → öz perspektiv planı (məşğələlər), davamiyyət, məşğələ testi, statistika.
// Dərs cədvəlindən və gündəlik plandan ayrıdır: jurnala qiymət yazmır, işçi planı sürüşdürmür. Şagird planı görür.
import { useState } from 'react'
import { del as apiDel, get, post, put } from '../../api'
import { AsyncBtn, Drawer, ErrorBox, Field, fmt, fmtDate, Loading, Pill, Seg, Stat, toast, Top, useLoad } from '../../ui'
import { head, printDoc, table } from '../../print'
import { useMyLessons } from './common'
import { BankPicker, iso, localParts, OwnQuestion, toCustom, type Q } from './TaskEditor'

type Sess = { id: number; date: string; weekday: string; start: string; end: string; format: 'əyani' | 'onlayn'; room: string | null; link: string | null
  topics: { plan_lesson_id: number | null; seq: number | null; text: string }[]; goals: string | null; resources: string | null; homework: string | null
  status: 'planned' | 'held' | 'cancelled'; note: string | null; recording_url: string | null; batch_id: number | null; present: number; joined: number; students: number | null }
type Course = { id: number; title: string; subject: string; format: string; classes: string[]; audience: { ta_ids: number[]; levels: string[] | null; student_ids: number[] | null }
  schedule: { weekday: number; start: string; end: string; room?: string | null; link?: string | null }[]; starts_on: string; ends_on: string; goal: string | null
  students: number; sessions: number; held: number; cancelled: number; next: Sess | null; session_list?: Sess[]; members?: { student_id: number; full_name: string; class_name: string }[]; warnings?: string[] }

const DAYS = ['Bazar ertəsi', 'Çərşənbə axşamı', 'Çərşənbə', 'Cümə axşamı', 'Cümə', 'Şənbə', 'Bazar']
const ST: Record<string, [string, any]> = { planned: ['planlaşdırılıb', undefined], held: ['keçirildi', 'ok'], cancelled: ['ləğv edildi', 'bad'] }

export default function ExtraCourses() {
  const [view, setView] = useState<'active' | 'archived'>('active')
  const [list, err, loading, reload] = useLoad<Course[]>(() => get('/api/extra', view === 'archived' ? { archived: true } : {}), [view])
  const [creating, setCreating] = useState(false)
  const [open, setOpen] = useState<number | null>(null)
  return (
    <>
      <Top title="Əlavə məşğələ" sub="Əyani və onlayn məşğələ kursu – öz perspektiv planı, davamiyyət, statistika (jurnala qiymət yazmır)"
        actions={<button className="btn primary" onClick={() => setCreating(true)}>+ Yeni kurs</button>} />
      <div className="toolbar"><Seg value={view} onChange={setView} options={[['active', 'Kurslar'], ['archived', 'Arxiv']]} /></div>
      <ErrorBox error={err} />
      {loading && !list ? <Loading /> : (
        <div className="grid g2">
          {list?.length === 0 && <div className="empty">{view === 'archived' ? 'Arxiv boşdur.' : 'Hələ kurs yoxdur. Məs.: «IX – buraxılışa hazırlıq, şənbə 10:00, 12 həftə» və ya «Zəif qrup – təkrar».'}</div>}
          {list?.map(c => (
            <section key={c.id} className="panel click" onClick={() => setOpen(c.id)}>
              <h2>{c.title} <small>{c.format}</small></h2>
              <p className="small muted" style={{ margin: '0 0 6px' }}>{c.subject} · {c.classes.join(', ')}{c.audience.levels ? ` · ${c.audience.levels.join(', ')} qrup` : ''} · {c.students} şagird</p>
              <p className="small" style={{ margin: '0 0 6px' }}>{c.schedule.map(s => `${DAYS[s.weekday].slice(0, 3)}. ${s.start}–${s.end}`).join(', ')} · {fmtDate(c.starts_on)} – {fmtDate(c.ends_on)}</p>
              <div className="row">
                <Pill tone="ok">keçirildi {c.held}/{c.sessions - c.cancelled}</Pill>
                {c.next && <Pill tone="info">növbəti: {fmtDate(c.next.date)} {c.next.start}{c.next.topics.length ? ` · ${c.next.topics[0].text}` : ''}</Pill>}
              </div>
            </section>))}
        </div>)}
      {creating && <NewCourse onClose={() => setCreating(false)} onDone={id => { setCreating(false); reload(); setOpen(id) }} />}
      {open && <CourseView id={open} archived={view === 'archived'} onClose={() => { setOpen(null); reload() }} />}
    </>
  )
}

// ---------------------------------------------------------------- yeni kurs
function NewCourse({ onClose, onDone }: { onClose: () => void; onDone: (id: number) => void }) {
  const [lessons] = useMyLessons()
  const [f, setF] = useState(() => {
    const t = localParts(new Date().toISOString())[0]
    const end = new Date(); end.setDate(end.getDate() + 84)
    return { title: '', format: 'əyani', goal: '', starts_on: t, ends_on: localParts(end.toISOString())[0], audience: 'all' as 'all' | 'levels', levels: ['Zəif'] as string[] }
  })
  const [tas, setTas] = useState<number[]>([])
  const [slots, setSlots] = useState([{ weekday: 5, start: '10:00', end: '11:00', room: '', link: '' }])
  const [err, setErr] = useState<unknown>()
  const subject = lessons?.find(l => l.id === tas[0])?.subject
  const avail = (lessons || []).filter(l => !subject || l.subject === subject)
  const setSlot = (i: number, p: any) => setSlots(s => s.map((x, j) => (j === i ? { ...x, ...p } : x)))
  const submit = async () => {
    try {
      const r = await post<Course>('/api/extra', {
        title: f.title.trim(), format: f.format, goal: f.goal || null, ta_ids: tas, starts_on: f.starts_on, ends_on: f.ends_on,
        levels: f.audience === 'levels' ? f.levels : null,
        schedule: slots.map(s => ({ weekday: s.weekday, start: s.start, end: s.end, room: s.room || null, link: s.link || null })),
      })
      toast(`Kurs yaradıldı – ${r.sessions} məşğələ planlaşdırıldı`)
      if (r.warnings?.length) toast('Diqqət: məktəb cədvəli ilə toqquşma var – kursda baxın')
      onDone(r.id)
    } catch (e) { setErr(e) }
  }
  return (
    <Drawer title="Yeni əlavə məşğələ kursu" onClose={onClose}
      footer={<><span className="grow" /><button className="btn" onClick={onClose}>Ləğv et</button>
        <button className="btn primary" disabled={!f.title.trim() || !tas.length || !slots.length} onClick={submit}>Yarat və planı qur</button></>}>
      <div className="stack">
        <div className="fg">
          <Field label="Ad" full><input value={f.title} maxLength={200} placeholder="məs. IX – buraxılışa hazırlıq" onChange={e => setF({ ...f, title: e.target.value })} /></Field>
          <Field label="Format"><select value={f.format} onChange={e => setF({ ...f, format: e.target.value })}>
            <option value="əyani">əyani (məktəbdə)</option><option value="onlayn">onlayn</option><option value="qarışıq">qarışıq</option></select></Field>
          <Field label="Başlama"><input type="date" value={f.starts_on} onChange={e => setF({ ...f, starts_on: e.target.value })} /></Field>
          <Field label="Bitmə"><input type="date" value={f.ends_on} onChange={e => setF({ ...f, ends_on: e.target.value })} /></Field>
          <Field label="Məqsəd" full><textarea value={f.goal} placeholder="məs. kəsrlər və faiz mövzularında boşluqları bağlamaq" onChange={e => setF({ ...f, goal: e.target.value })} /></Field>
        </div>
        <fieldset><legend>Kimə</legend>
          {avail.map(l => <label key={l.id} className="check"><input type="checkbox" checked={tas.includes(l.id)}
            onChange={e => setTas(s => e.target.checked ? [...s, l.id] : s.filter(x => x !== l.id))} /> {l.class_name} <span className="small muted">· {l.subject}</span></label>)}
          <div className="row" style={{ marginTop: 8 }}>
            <Seg value={f.audience} onChange={v => setF({ ...f, audience: v })} options={[['all', 'Bütün şagirdlər'], ['levels', 'Səviyyə qrupu']]} />
            {f.audience === 'levels' && ['Zəif', 'Orta', 'Güclü'].map(k => <label key={k} className="check"><input type="checkbox" checked={f.levels.includes(k)}
              onChange={e => setF({ ...f, levels: e.target.checked ? [...f.levels, k] : f.levels.filter(x => x !== k) })} /> {k}</label>)}
          </div>
          {f.audience === 'levels' && <p className="small muted">Səviyyə qrupları Jurnal → «Səviyyə qrupları»nda təyin olunur. Şagird öz səviyyəsini görmür – yalnız kursu görür.</p>}
        </fieldset>
        <fieldset><legend>Həftəlik cədvəl</legend>
          {slots.map((s, i) => (
            <div key={i} className="row" style={{ gap: 6, marginBottom: 6 }}>
              <select className="sel" value={s.weekday} onChange={e => setSlot(i, { weekday: Number(e.target.value) })}>{DAYS.map((d, j) => <option key={j} value={j}>{d}</option>)}</select>
              <input type="time" className="sel" value={s.start} onChange={e => setSlot(i, { start: e.target.value })} />
              <input type="time" className="sel" value={s.end} onChange={e => setSlot(i, { end: e.target.value })} />
              {f.format !== 'onlayn' && <input className="sel" placeholder="otaq" value={s.room} onChange={e => setSlot(i, { room: e.target.value })} style={{ width: 90 }} />}
              {f.format !== 'əyani' && <input className="sel grow" placeholder="https://meet… (onlayn)" value={s.link} onChange={e => setSlot(i, { link: e.target.value })} />}
              <button className="btn sm ghost" onClick={() => setSlots(x => x.filter((_, j) => j !== i))} aria-label="Sil">✕</button>
            </div>))}
          <button className="btn sm" onClick={() => setSlots(x => [...x, { weekday: 2, start: '15:00', end: '16:00', room: '', link: '' }])}>+ gün</button>
          <p className="small muted">Tarixlər bu cədvəldən avtomatik qurulur, tətil və bayram günləri çıxılır. Qarışıq formatda keçidi olan gün onlayn sayılır.</p>
        </fieldset>
        <ErrorBox error={err} />
      </div>
    </Drawer>
  )
}

// ---------------------------------------------------------------- kurs: Plan | Davamiyyət | Statistika
function CourseView({ id, archived, onClose }: { id: number; archived: boolean; onClose: () => void }) {
  const [c, err, , reload] = useLoad<Course>(() => get(`/api/extra/${id}`), [id])
  const [tab, setTab] = useState<'plan' | 'att' | 'stats'>('plan')
  const [edit, setEdit] = useState<Sess | 'new' | null>(null)
  const [held, setHeld] = useState<Sess | null>(null)
  const [test, setTest] = useState<Sess | null>(null)
  const [bulk, setBulk] = useState(false)
  const print = () => c && printDoc({ title: `${c.title} – məşğələ planı`, body: head(`${c.title} – əlavə məşğələ planı`, `${c.subject} · ${c.classes.join(', ')} · ${fmtDate(c.starts_on)}–${fmtDate(c.ends_on)}`) +
    table(['№', 'Tarix', 'Vaxt', 'Format', 'Mövzu', 'Ev tapşırığı', 'Status'], (c.session_list || []).map((s, i) => [i + 1, `${fmtDate(s.date)} ${s.weekday}`, `${s.start}–${s.end}`,
      s.format === 'onlayn' ? 'onlayn' : `əyani${s.room ? ' · ' + s.room : ''}`, s.topics.map(t => t.text).join('; '), s.homework || '', ST[s.status][0]])) })
  return (
    <Drawer title={c ? c.title : 'Kurs'} onClose={onClose}
      footer={c && <><button className="btn" onClick={print}>Planı çap et</button><span className="grow" />
        {archived ? <AsyncBtn className="btn" ok="Geri qaytarıldı" onClick={async () => { await post(`/api/extra/${id}/restore`); onClose() }}>Geri qaytar</AsyncBtn>
          : <AsyncBtn className="btn" ok="Arxivə köçürüldü" onClick={async () => { await post(`/api/extra/${id}/archive`); onClose() }}>Arxivə</AsyncBtn>}</>}>
      <ErrorBox error={err} />
      {!c ? <Loading /> : (
        <div className="stack">
          <p className="small muted" style={{ margin: 0 }}>{c.subject} · {c.classes.join(', ')}{c.audience.levels ? ` · ${c.audience.levels.join(', ')} qrup` : ''} · {c.students} şagird · {c.format}{c.goal ? ` · ${c.goal}` : ''}</p>
          {(c.warnings || []).length > 0 && <div className="banner" style={{ background: 'var(--warn-soft)', color: 'var(--warn)' }}>
            Məktəb cədvəli ilə toqquşma: {c.warnings!.join('; ')}</div>}
          <Seg value={tab} onChange={setTab} options={[['plan', 'Plan'], ['att', 'Şagirdlər'], ['stats', 'Statistika']]} />
          {tab === 'plan' && <>
            <div className="row"><button className="btn sm" onClick={() => setBulk(true)}>Mövzuları paylaşdır</button>
              <button className="btn sm" onClick={() => setEdit('new')}>+ Əlavə məşğələ</button></div>
            <div className="jlist">
              {(c.session_list || []).map((s, i) => (
                <div key={s.id} className="jrow cols" style={{ ['--cols' as any]: 'minmax(0,1fr)', ['--mcols' as any]: '1fr', gap: 4, opacity: s.status === 'cancelled' ? 0.6 : 1 }}>
                  <div className="row"><b>№{i + 1} · {fmtDate(s.date)} {s.weekday} {s.start}–{s.end}</b>
                    <Pill tone={s.format === 'onlayn' ? 'info' : undefined}>{s.format}{s.room ? ` · ${s.room}` : ''}</Pill>
                    <Pill tone={ST[s.status][1]}>{ST[s.status][0]}{s.status === 'held' ? ` · ${s.present}/${s.students}` : ''}</Pill>
                    {s.joined > 0 && s.status === 'planned' && <Pill tone="ok">qoşulub: {s.joined}</Pill>}
                    {s.batch_id && <Pill tone="acc">test</Pill>}</div>
                  <span className="small">{s.topics.length ? s.topics.map(t => (t.seq ? `№${t.seq} ` : '') + t.text).join(' · ') : <span className="muted">mövzu təyin edilməyib</span>}</span>
                  {(s.homework || s.note) && <span className="small muted">{s.homework ? `Ev tapşırığı: ${s.homework}` : ''}{s.note ? ` · ${s.note}` : ''}</span>}
                  {!archived && <div className="row" style={{ gap: 6 }}>
                    <button className="btn sm" onClick={() => setEdit(s)}>Redaktə</button>
                    {s.status !== 'cancelled' && <button className="btn sm" onClick={() => setHeld(s)}>{s.status === 'held' ? 'Davamiyyət' : 'Keçirildi'}</button>}
                    {!s.batch_id && s.status !== 'cancelled' && <button className="btn sm ghost" onClick={() => setTest(s)}>+ Test</button>}
                  </div>}
                </div>))}
            </div></>}
          {tab === 'att' && <div className="jlist">{(c.members || []).map(m => <div key={m.student_id} className="row small" style={{ padding: '6px 12px' }}><b className="grow">{m.full_name}</b><span className="muted">{m.class_name}</span></div>)}</div>}
          {tab === 'stats' && <Stats id={id} />}
        </div>)}
      {edit && c && <SessionEdit course={c} s={edit === 'new' ? null : edit} onClose={() => setEdit(null)} onDone={() => { setEdit(null); reload() }} />}
      {held && <Held course={id} s={held} onClose={() => setHeld(null)} onDone={() => { setHeld(null); reload() }} />}
      {test && <SessionTest course={id} s={test} onClose={() => setTest(null)} onDone={() => { setTest(null); reload() }} />}
      {bulk && <BulkTopics course={id} onClose={() => setBulk(false)} onDone={() => { setBulk(false); reload() }} />}
    </Drawer>
  )
}

function SessionEdit({ course, s, onClose, onDone }: { course: Course; s: Sess | null; onClose: () => void; onDone: () => void }) {
  const [sug] = useLoad<{ suggested: any[]; plan: any[] }>(() => get(`/api/extra/${course.id}/suggest-topics`), [course.id])
  const [f, setF] = useState(() => ({
    date: s?.date || localParts(new Date().toISOString())[0], start: s?.start || '10:00', end: s?.end || '11:00',
    format: s?.format || (course.format === 'onlayn' ? 'onlayn' : 'əyani'), room: s?.room || '', link: s?.link || '',
    goals: s?.goals || '', resources: s?.resources || '', homework: s?.homework || '', status: s?.status || 'planned',
    note: s?.note || '', recording_url: s?.recording_url || '',
  }))
  const [topics, setTopics] = useState<{ plan_lesson_id: number | null; text: string }[]>(s?.topics.map(t => ({ plan_lesson_id: t.plan_lesson_id, text: t.plan_lesson_id ? '' : t.text })) || [])
  const [free, setFree] = useState('')
  const [err, setErr] = useState<unknown>()
  const label = (t: { plan_lesson_id: number | null; text: string }) => {
    const p = sug?.plan.find(x => x.id === t.plan_lesson_id)
    return p ? `№${p.seq} ${p.topic}` : t.text
  }
  const save = async () => {
    const body = { ...f, room: f.room || null, link: f.link || null, recording_url: f.recording_url || null, note: f.note || null,
      topics: topics.map(t => ({ plan_lesson_id: t.plan_lesson_id, text: t.text || null })) }
    try {
      if (s) await put(`/api/extra/${course.id}/sessions/${s.id}`, body)
      else await post(`/api/extra/${course.id}/sessions`, body)
      toast('Məşğələ yadda saxlanıldı'); onDone()
    } catch (e) { setErr(e) }
  }
  return (
    <Drawer title={s ? `Məşğələ – ${fmtDate(s.date)}` : 'Əlavə məşğələ'} onClose={onClose}
      footer={<>{s && s.status !== 'held' && <AsyncBtn className="btn ghost" ok="Silindi" onClick={async () => { await apiDel(`/api/extra/${course.id}/sessions/${s.id}`); onDone() }}>Sil</AsyncBtn>}
        <span className="grow" /><button className="btn" onClick={onClose}>Ləğv et</button><button className="btn primary" onClick={save}>Yadda saxla</button></>}>
      <div className="stack">
        <div className="fg">
          <Field label="Tarix"><input type="date" value={f.date} onChange={e => setF({ ...f, date: e.target.value })} /></Field>
          <Field label="Format"><select value={f.format} onChange={e => setF({ ...f, format: e.target.value as any })}><option value="əyani">əyani</option><option value="onlayn">onlayn</option></select></Field>
          <Field label="Başlama"><input type="time" value={f.start} onChange={e => setF({ ...f, start: e.target.value })} /></Field>
          <Field label="Bitmə"><input type="time" value={f.end} onChange={e => setF({ ...f, end: e.target.value })} /></Field>
          {f.format === 'əyani' ? <Field label="Otaq"><input value={f.room} onChange={e => setF({ ...f, room: e.target.value })} /></Field>
            : <Field label="Keçid (https://)" full><input value={f.link} placeholder="https://meet.google.com/…" onChange={e => setF({ ...f, link: e.target.value })} /></Field>}
        </div>
        <fieldset><legend>Mövzular</legend>
          {topics.map((t, i) => <div key={i} className="row small"><span className="grow">{label(t)}</span><button className="btn sm ghost" onClick={() => setTopics(x => x.filter((_, j) => j !== i))} aria-label="Sil">✕</button></div>)}
          <select className="sel" value="" onChange={e => { const v = Number(e.target.value); if (v) setTopics(x => [...x, { plan_lesson_id: v, text: '' }]) }}>
            <option value="">+ Perspektiv plandan mövzu</option>
            {sug?.suggested.length ? <optgroup label="Təklif (təkrar / zəif nəticə)">{sug.suggested.map(x => <option key={'s' + x.plan_lesson_id} value={x.plan_lesson_id}>№{x.seq} {x.topic} – {x.reason}</option>)}</optgroup> : null}
            <optgroup label="Plan">{sug?.plan.map(x => <option key={x.id} value={x.id}>№{x.seq} {x.topic}</option>)}</optgroup>
          </select>
          <div className="row" style={{ marginTop: 6 }}><input className="sel grow" placeholder="və ya sərbəst mövzu (məs. sınaq səhvlərinin təhlili)" value={free} onChange={e => setFree(e.target.value)} />
            <button className="btn sm" disabled={!free.trim()} onClick={() => { setTopics(x => [...x, { plan_lesson_id: null, text: free.trim() }]); setFree('') }}>Əlavə et</button></div>
        </fieldset>
        <div className="fg">
          <Field label="Məqsəd" full><textarea value={f.goals} onChange={e => setF({ ...f, goals: e.target.value })} /></Field>
          <Field label="Material / keçidlər" full><textarea value={f.resources} onChange={e => setF({ ...f, resources: e.target.value })} /></Field>
          <Field label="Ev tapşırığı" full><input value={f.homework} onChange={e => setF({ ...f, homework: e.target.value })} /></Field>
          <Field label="Status"><select value={f.status} onChange={e => setF({ ...f, status: e.target.value as any })}>
            <option value="planned">planlaşdırılıb</option><option value="cancelled">ləğv edildi</option>{s?.status === 'held' && <option value="held">keçirildi</option>}</select></Field>
          <Field label={f.status === 'cancelled' ? 'Ləğv səbəbi' : 'Qeyd'}><input value={f.note} maxLength={300} onChange={e => setF({ ...f, note: e.target.value })} /></Field>
          {s?.status === 'held' && f.format === 'onlayn' && <Field label="Yazı keçidi (istəyə görə)" full><input value={f.recording_url} onChange={e => setF({ ...f, recording_url: e.target.value })} /></Field>}
        </div>
        <ErrorBox error={err} />
      </div>
    </Drawer>
  )
}

function Held({ course, s, onClose, onDone }: { course: number; s: Sess; onClose: () => void; onDone: () => void }) {
  const [rows, err] = useLoad<any[]>(() => get(`/api/extra/${course}/sessions/${s.id}/attendance`), [course, s.id])
  const [st, setSt] = useState<Record<number, string>>({})
  const val = (r: any) => st[r.student_id] ?? r.status ?? (r.joined_at || s.format === 'əyani' ? 'var' : 'yox')
  return (
    <Drawer title={`Davamiyyət – ${fmtDate(s.date)} ${s.start}`} onClose={onClose}
      footer={<><span className="grow" /><button className="btn" onClick={onClose}>Ləğv et</button>
        <AsyncBtn className="btn primary" ok="Keçirildi kimi qeyd olundu" onClick={async () => {
          await post(`/api/extra/${course}/sessions/${s.id}/held`, { attendance: Object.fromEntries((rows || []).map(r => [r.student_id, val(r)])) }); onDone()
        }}>Yadda saxla</AsyncBtn></>}>
      <ErrorBox error={err} />
      {s.format === 'onlayn' && <p className="small muted">Onlayn «Qoşul» basanlar avtomatik «var» təklif olunur – yoxlayıb təsdiqləyin.</p>}
      {!rows ? <Loading /> : rows.map(r => (
        <div key={r.student_id} className="row" style={{ borderTop: '1px solid var(--line)', padding: '6px 0' }}>
          <span className="grow small"><b>{r.full_name}</b>{r.joined_at ? <span className="muted"> · qoşulub {new Date(r.joined_at).toLocaleTimeString('az-AZ', { hour: '2-digit', minute: '2-digit' })}</span> : null}</span>
          <Seg value={val(r)} onChange={v => setSt(x => ({ ...x, [r.student_id]: v }))} options={[['var', 'var'], ['gecikdi', 'gecikdi'], ['yox', 'yox'], ['üzrlü', 'üzrlü']]} />
        </div>))}
    </Drawer>
  )
}

function SessionTest({ course, s, onClose, onDone }: { course: number; s: Sess; onClose: () => void; onDone: () => void }) {
  const [qs, setQs] = useState<Q[]>([])
  const [f, setF] = useState({ title: `Məşğələ testi – ${fmtDate(s.date)}`, d1: s.date, t1: s.start, d2: s.date, t2: '22:00', duration: 15 })
  const [err, setErr] = useState<unknown>()
  const has = (k: string) => qs.some(q => q.key === k)
  const add = (list: Q[]) => setQs(cur => [...cur, ...list.filter(q => !cur.some(c => c.key === q.key))])
  const remove = (k: string) => setQs(cur => cur.filter(q => q.key !== k))
  return (
    <Drawer title="Məşğələ testi" onClose={onClose}
      footer={<><span className="small muted grow">{qs.length} sual</span><button className="btn" onClick={onClose}>Ləğv et</button>
        <button className="btn primary" disabled={!qs.length} onClick={async () => {
          try {
            await post(`/api/extra/${course}/sessions/${s.id}/test`, { title: f.title, duration_min: f.duration, opens_at: iso(f.d1, f.t1), closes_at: iso(f.d2, f.t2), bank_ids: [], custom: qs.map(toCustom) })
            toast('Test kursun şagirdlərinə göndərildi'); onDone()
          } catch (e) { setErr(e) }
        }}>Göndər</button></>}>
      <div className="stack">
        <p className="small muted" style={{ margin: 0 }}>5–8 sual məşğələnin effektini ölçür. Yalnız kursun şagirdləri görür; nəticə jurnala yazılmır – statistikaya düşür.</p>
        <div className="fg">
          <Field label="Ad" full><input value={f.title} onChange={e => setF({ ...f, title: e.target.value })} /></Field>
          <Field label="Açılır"><input type="time" value={f.t1} onChange={e => setF({ ...f, t1: e.target.value })} /></Field>
          <Field label="Bağlanır (tarix)"><input type="date" value={f.d2} onChange={e => setF({ ...f, d2: e.target.value })} /></Field>
          <Field label="Bağlanır (saat)"><input type="time" value={f.t2} onChange={e => setF({ ...f, t2: e.target.value })} /></Field>
          <Field label="Müddət (dəq)"><input type="number" min={1} max={300} value={f.duration} onChange={e => setF({ ...f, duration: Number(e.target.value) })} /></Field>
        </div>
        <BankPicker has={has} add={add} remove={remove} onTitle={() => {}} disabled={false} first={false} kinds={['movzu', 'diaqnostik']} />
        <p className="small">Seçilib: {qs.length} sual</p>
        <OwnQuestion onAdd={q => add([q])} />
        <ErrorBox error={err} />
      </div>
    </Drawer>
  )
}

function BulkTopics({ course, onClose, onDone }: { course: number; onClose: () => void; onDone: () => void }) {
  const [sug] = useLoad<{ suggested: any[]; plan: any[] }>(() => get(`/api/extra/${course}/suggest-topics`), [course])
  const [sel, setSel] = useState<number[]>([])
  const [per, setPer] = useState(1)
  return (
    <Drawer title="Mövzuları məşğələlərə paylaşdır" onClose={onClose}
      footer={<><span className="small muted grow">{sel.length} mövzu</span><button className="btn" onClick={onClose}>Ləğv et</button>
        <AsyncBtn className="btn primary" disabled={!sel.length} onClick={async () => {
          const r = await post<any>(`/api/extra/${course}/topics/bulk`, { plan_lesson_ids: sel, per_session: per })
          toast(`${r.sessions} məşğələyə paylaşdırıldı${r.left ? ` · ${r.left} mövzu yer tapmadı` : ''}`); onDone()
        }}>Paylaşdır</AsyncBtn></>}>
      <p className="small muted">Seçilən mövzular mövzusu olmayan növbəti planlaşdırılmış məşğələlərə ardıcıl düşür.</p>
      <Field label="Bir məşğələyə"><select value={per} onChange={e => setPer(Number(e.target.value))}>{[1, 2, 3].map(n => <option key={n} value={n}>{n} mövzu</option>)}</select></Field>
      {sug?.suggested.length ? <><h3 className="small">Təklif olunan (təkrar / zəif nəticə)</h3>
        {sug.suggested.map(x => <label key={'s' + x.plan_lesson_id} className="check"><input type="checkbox" checked={sel.includes(x.plan_lesson_id)}
          onChange={e => setSel(s => e.target.checked ? [...s, x.plan_lesson_id] : s.filter(v => v !== x.plan_lesson_id))} /> №{x.seq} {x.topic} <span className="small muted">· {x.reason}</span></label>)}</> : null}
      <h3 className="small">Perspektiv plan</h3>
      <div style={{ maxHeight: 360, overflow: 'auto' }}>{sug?.plan.map(x => <label key={x.id} className="check"><input type="checkbox" checked={sel.includes(x.id)}
        onChange={e => setSel(s => e.target.checked ? [...s, x.id] : s.filter(v => v !== x.id))} /> №{x.seq} {x.topic}</label>)}</div>
    </Drawer>
  )
}

function Stats({ id }: { id: number }) {
  const [d, err] = useLoad<any>(() => get(`/api/extra/${id}/stats`), [id])
  if (!d) return err ? <ErrorBox error={err} /> : <Loading />
  const s = d.summary, cmp = d.compare
  const print = () => printDoc({ title: 'Əlavə məşğələ – hesabat', body: head('Əlavə məşğələ – hesabat', `keçirildi ${s.held} məşğələ · ${fmt(s.hours)} saat · orta iştirak ${fmt(s.attendance_pct)}%`) +
    table(['Şagird', 'Sinif', 'İştirak', '%', 'Məşğələ testi %', 'Kursdan əvvəl %', 'Sonra %', 'Dinamika'], d.students.map((x: any) => [x.full_name, x.class_name, `${x.present}/${x.held}`, fmt(x.attendance_pct), fmt(x.extra_test_avg), fmt(x.before_pct), fmt(x.after_pct), x.delta == null ? '—' : fmt(x.delta)]), [2, 3, 4, 5, 6, 7]) })
  return (
    <div className="stack">
      <div className="kpis">
        <Stat value={`${s.held}/${s.sessions - s.cancelled}`} label="keçirildi" /><Stat value={fmt(s.hours)} label="saat" />
        <Stat value={fmt(s.attendance_pct) + '%'} label="orta iştirak" /><Stat value={fmt(s.extra_test_avg) + '%'} label="məşğələ testi" />
      </div>
      {s.at_risk > 0 && <div className="banner" style={{ background: 'var(--warn-soft)', color: 'var(--warn)' }}>{s.at_risk} şagird ardıcıl 2 məşğələni buraxıb – valideynlə əlaqə saxlayın.</div>}
      <section className="panel"><h2>Effekt <small>kurs başlayandan sonra mövzu testləri və sınaqlar</small></h2>
        <div className="row"><Pill tone="ok">iştirakçılar ({cmp.participants}): {fmt(cmp.participants_pct)}%</Pill><Pill>digərləri ({cmp.others}): {fmt(cmp.others_pct)}%</Pill>
          {cmp.participants_pct != null && cmp.others_pct != null && <b>fərq {cmp.participants_pct - cmp.others_pct > 0 ? '+' : ''}{fmt(cmp.participants_pct - cmp.others_pct)}</b>}</div>
        <p className="small muted">İştirakçı – məşğələlərin ən azı yarısında olan şagird. Format üzrə iştirak: əyani {fmt(d.by_format['əyani'].attendance_pct)}%, onlayn {fmt(d.by_format.onlayn.attendance_pct)}%.</p></section>
      <div className="tbl-wrap"><table>
        <thead><tr><th>Şagird</th><th className="r">İştirak</th><th className="r">Test %</th><th className="r">Əvvəl</th><th className="r">Sonra</th><th className="r">±</th></tr></thead>
        <tbody>{d.students.map((x: any) => (
          <tr key={x.student_id}><td><b>{x.full_name}</b>{x.risk && <Pill tone="bad">2 buraxma</Pill>}<span className="sub">{x.class_name}</span></td>
            <td className="r num">{x.present}/{x.held}{x.attendance_pct != null ? ` (${fmt(x.attendance_pct, 0)}%)` : ''}</td><td className="r num">{fmt(x.extra_test_avg)}</td>
            <td className="r num">{fmt(x.before_pct)}</td><td className="r num">{fmt(x.after_pct)}</td>
            <td className="r num">{x.delta == null ? '—' : <Pill tone={x.delta > 0 ? 'ok' : x.delta < 0 ? 'bad' : undefined}>{x.delta > 0 ? '+' : ''}{fmt(x.delta)}</Pill>}</td></tr>))}</tbody>
      </table></div>
      <button className="btn sm" onClick={print}>Hesabatı çap et (tədris hissəsi üçün)</button>
    </div>
  )
}
