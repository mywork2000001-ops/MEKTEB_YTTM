// Mövzu testi: perspektiv planın mövzusuna onlayn test – eyni mövzunu keçən digər siniflərə də eyni anda.
// Hər sinfin öz başlama/bitmə vaxtı (default – mövzunun həmin sinifdəki dərsindən sonra → ertəsi gün 22:00);
// test bağlananda nəticə formativ jurnala, mövzunun dərsinə yazılır.
import { useEffect, useState } from 'react'
import { get, post } from '../../api'
import { MathText } from '../../MathText'
import { Drawer, ErrorBox, Field, fmtDate, Loading, Pill, toast } from '../../ui'
import { sectionText } from './Plan'
import { BankPicker, fromSnapshot, iso, localParts, OwnQuestion, toCustom, type Q } from './TaskEditor'
import { StudentPicker } from './common'

type Peer = {
  ta_id: number; class_name: string; kind: string; current: boolean; students: number
  plan_lesson: { id: number; seq: number; topic: string } | null; already_has_test: boolean
  working_date: string | null; period: number | null; opens_at: string | null; closes_at: string | null
  lessons?: { id: number; seq: number; topic: string }[]
}
type Peers = { topic: { id: number; seq: number; topic: string; section: string | null; assessment_type: string }; subject: string; grade: number | null; classes: Peer[] }
type Row = { on: boolean; pl: number | null; d1: string; t1: string; d2: string; t2: string; ids: number[] | null }   // ids: null – bütün sinif
type Lv = 'Zəif' | 'Orta' | 'Güclü'
const LV: Lv[] = ['Zəif', 'Orta', 'Güclü']
type Toplu = { mode: 'chapter' | 'exam' | 'diag' | 'mock'; in_bank: boolean; url?: string; chapter?: string; has_ev?: boolean
  title?: string; questions: any[]; missing: number[]; absent?: string[] }
type P0010 = { eligible: boolean; matches: { file_id: number; label: string; count: number }[]; file?: { file_id: number; label: string }
  title?: string; questions: any[] }
type Prev = { task_id: number; title: string; class_name: string; opens_at: string; questions: any[]; count: number; avg_pct: number | null }

const nextDay = (d: string) => { const x = new Date(d + 'T00:00'); x.setDate(x.getDate() + 1); return localParts(x.toISOString())[0] }

function defaults(p: Peer): Row {
  const today = localParts(new Date().toISOString())[0]
  const [d1, t1] = p.opens_at ? localParts(p.opens_at) : [today, '15:00']
  const [d2, t2] = p.closes_at ? localParts(p.closes_at) : [nextDay(d1), '22:00']
  return { on: p.current || (!!p.plan_lesson && !p.already_has_test), pl: p.plan_lesson?.id ?? null, d1, t1, d2, t2, ids: null }
}

export default function TopicTest({ ta, pl, onClose, onDone }: { ta: number; pl: number; onClose: () => void; onDone: () => void }) {
  const [d, setD] = useState<Peers | null>(null)
  const [rows, setRows] = useState<Record<number, Row>>({})
  const [plain, setPlain] = useState<Q[]>([])
  const [variants, setVariants] = useState(false)
  const [vk, setVk] = useState<Lv>('Orta')
  const [vqs, setVqs] = useState<Record<Lv, Q[]>>({ 'Zəif': [], 'Orta': [], 'Güclü': [] })
  const [prev, setPrev] = useState<Prev[] | null>(null)
  const [toplu, setToplu] = useState<Toplu | null>(null)
  const [tn, setTn] = useState(15)
  const [tbusy, setTbusy] = useState(false)
  const [p10, setP10] = useState<P0010 | null>(null)
  const qs = variants ? vqs[vk] : plain
  const setQs = (fn: (cur: Q[]) => Q[]) => (variants ? setVqs(v => ({ ...v, [vk]: fn(v[vk]) })) : setPlain(fn))
  const [f, setF] = useState({ title: '', duration: 20, show: 'after_close', shuffle: true, journal: true })
  const [err, setErr] = useState<unknown>()
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    get<Peers>(`/api/plan/${ta}/topics/${pl}/peers`).then(p => {
      setD(p)
      setRows(Object.fromEntries(p.classes.map(c => [c.ta_id, defaults(c)])))
      setF(x => ({ ...x, title: `№${p.topic.seq} ${p.topic.topic} – mövzu testi`.slice(0, 200) }))
      // X–XI: mövzuya ən uyğun P0010 faylının sualları özü əlavə olunur (docs/x-xi-p0010-testleri-promtu.md)
      get<P0010>(`/api/plan/${ta}/topics/${pl}/p0010`).then(r => {
        setP10(r)
        if (r.eligible && r.questions.length) {
          setPlain(cur => cur.length ? cur : r.questions.map(q => fromSnapshot(q, 'b' + q.bank_id)))
          if (r.title) setF(x => ({ ...x, title: r.title! }))
        }
      }, () => setP10(null))
    }, setErr)
    get<Prev[]>(`/api/plan/${ta}/topics/${pl}/previous`).then(setPrev, () => setPrev([]))
    get<Toplu>(`/api/programs/toplu/questions?lesson_id=${pl}`).then(setToplu, () => setToplu(null))   // «Test toplusu» dərsi deyilsə – 400
  }, [ta, pl])
  const takePrev = (p: Prev) => { setQs(cur => [...cur, ...p.questions.map((q, i) => fromSnapshot(q, `p${p.task_id}-${i}`)).filter(q => !cur.some(c => c.key === q.key))]); toast(`${p.count} sual götürüldü`) }

  // «Test toplusu» dərsi: S/E/M aralığı, ev tapşırığı, fəsil testi və ya sınaq – P007 bankından (docs/ix-dim-toplu-perspektiv-promtu.md §4)
  const takeToplu = async (scope: 'lesson' | 'ev' | 'chapter') => {
    setTbusy(true)
    try {
      const r = await get<Toplu>(`/api/programs/toplu/questions?lesson_id=${pl}&scope=${scope}&n=${tn}`)
      if (!r.questions.length) { toast('Bu aralıqda bazada sual yoxdur'); return }
      add(r.questions.map(q => fromSnapshot(q, 'b' + q.bank_id)))
      if (r.title) setF(x => ({ ...x, title: r.title!.slice(0, 200) }))
      toast(`${r.questions.length} sual götürüldü${r.missing.length ? ` · bazada yoxdur: ${r.missing.length}` : ''}`)
    } catch (e) { setErr(e) } finally { setTbusy(false) }
  }

  const takeP10 = async (fileId: number) => {
    setTbusy(true)
    try {
      const r = await get<P0010>(`/api/plan/${ta}/topics/${pl}/p0010?file_id=${fileId}&n=${tn}`)
      add(r.questions.map(q => fromSnapshot(q, 'b' + q.bank_id)))
      toast(`${r.questions.length} sual götürüldü`)
    } catch (e) { setErr(e) } finally { setTbusy(false) }
  }

  const has = (k: string) => qs.some(q => q.key === k)
  const add = (list: Q[]) => setQs(cur => [...cur, ...list.filter(q => !cur.some(c => c.key === q.key))])
  const remove = (k: string) => setQs(cur => cur.filter(q => q.key !== k))
  const set = (id: number, patch: Partial<Row>) => setRows(r => ({ ...r, [id]: { ...r[id], ...patch } }))
  const chosen = d ? d.classes.filter(c => rows[c.ta_id]?.on) : []
  const sameTime = () => {
    const cur = d?.classes.find(c => c.current)
    if (!cur) return
    const r = rows[cur.ta_id]
    setRows(x => Object.fromEntries(Object.entries(x).map(([k, v]) => [k, { ...v, d1: r.d1, t1: r.t1, d2: r.d2, t2: r.t2 }])))
  }

  const noQs = variants ? !vqs['Orta'].length || LV.some(k => vqs[k].length > 100) : !plain.length
  const problem = !f.title.trim() ? 'Testin adını yazın' : noQs ? (variants ? '«Orta» variantına ən azı 1 sual seçin (səviyyəsi olmayanlar onu alır)' : 'Ən azı 1 sual seçin') : !chosen.length ? 'Ən azı bir sinif seçin'
    : chosen.some(c => !rows[c.ta_id].pl) ? 'Mövzusu tapılmayan sinifdə mövzunu seçin'
    : chosen.some(c => rows[c.ta_id].ids?.length === 0) ? '«Kimə» bölməsində ən azı bir şagird seçin'
    : chosen.some(c => { const r = rows[c.ta_id]; return iso(r.d2, r.t2) <= iso(r.d1, r.t1) }) ? 'Bitmə vaxtı başlamadan sonra olmalıdır'
    : !variants && plain.length > 100 ? 'Bir testdə ən çoxu 100 sual' : ''

  const submit = async () => {
    if (problem) { setErr(new Error(problem)); return }
    setBusy(true)
    try {
      const r = await post<{ tasks: any[] }>(`/api/plan/${ta}/topics/${pl}/test`, {
        title: f.title.trim(), duration_min: f.duration, shuffle: f.shuffle, show_answers: f.show, journal_auto: f.journal,
        bank_ids: [], custom: variants ? [] : plain.map(toCustom),
        variants: variants ? Object.fromEntries(LV.filter(k => vqs[k].length).map(k => [k, { bank_ids: [], custom: vqs[k].map(toCustom) }])) : null,
        targets: chosen.map(c => { const x = rows[c.ta_id]; return { ta_id: c.ta_id, plan_lesson_id: x.pl, opens_at: iso(x.d1, x.t1), closes_at: iso(x.d2, x.t2), student_ids: x.ids } }),
      })
      toast(r.tasks.length > 1 ? `Test ${r.tasks.length} sinfə göndərildi` : 'Test göndərildi')
      onDone()
    } catch (e) { setErr(e) } finally { setBusy(false) }
  }

  return (
    <Drawer title="Mövzuya onlayn test" onClose={onClose}
      footer={<><span className="small muted grow">{variants ? LV.map(k => `${k} ${vqs[k].length}`).join(' · ') : `${plain.length} sual`} · {chosen.length} sinif</span><button className="btn" onClick={onClose}>Ləğv et</button>
        <button className="btn primary" disabled={busy} onClick={submit}>Göndər</button></>}>
      {!d ? (err ? <ErrorBox error={err} /> : <Loading />) : (
        <div className="stack">
          <div className="banner"><div>
            <b>№{d.topic.seq} {d.topic.topic}</b>{d.topic.section ? <span className="muted"> · {sectionText(d.topic.section)}</span> : null}
            <div className="small" style={{ marginTop: 4 }}>{f.journal ? 'Test bağlananda nəticə (bal və qiymət) formativ jurnala – bu mövzunun dərsinə yazılır. Testi yazmayana qiymət yazılmır.' : 'Nəticə jurnala avtomatik yazılmayacaq.'}</div>
          </div></div>
          <div className="fg">
            <Field label="Ad" full><input value={f.title} maxLength={200} onChange={e => setF({ ...f, title: e.target.value })} /></Field>
            <Field label="Həll müddəti (dəq)"><input type="number" min={1} max={300} value={f.duration} onChange={e => setF({ ...f, duration: Number(e.target.value) })} /></Field>
            <Field label="Düzgün cavablar görünsün"><select value={f.show} onChange={e => setF({ ...f, show: e.target.value })}>
              <option value="after_close">test bağlandıqdan sonra</option><option value="after_submit">təhvil verdikdən dərhal sonra</option><option value="never">heç vaxt</option></select></Field>
            <label className="check full"><input type="checkbox" checked={f.shuffle} onChange={e => setF({ ...f, shuffle: e.target.checked })} /> Sualların sırası hər şagirdə fərqli</label>
            <label className="check full"><input type="checkbox" checked={f.journal} onChange={e => setF({ ...f, journal: e.target.checked })} /> Bağlananda formativ jurnala yaz</label>
            <label className="check full"><input type="checkbox" checked={variants} onChange={e => setVariants(e.target.checked)} /> Səviyyəyə görə variant (Zəif / Orta / Güclü – hər qrupa öz sualları)</label>
          </div>
          {variants && <p className="small muted" style={{ margin: 0 }}>Hər şagird öz səviyyəsinin variantını alır (Jurnal → Səviyyə qrupları). Səviyyəsi təyin edilməyən və ya variantı boş qalan
            qrupun şagirdləri «Orta» variantını alır. Qiymət hər şagirdin öz variantının sual sayından hesablanır. Şagird səviyyə adını görmür.</p>}

          <fieldset><legend>Siniflər – eyni mövzu ({d.subject}{d.grade ? `, ${d.grade}-cu sinif səviyyəsi` : ''})</legend>
            <div className="jlist">
              {d.classes.map(c => {
                const r = rows[c.ta_id]
                if (!r) return null
                return (
                  <div key={c.ta_id} className="jrow cols" style={{ ['--cols' as any]: 'minmax(0,1fr)', ['--mcols' as any]: '1fr', gap: 6 }}>
                    <label className="check" style={{ minHeight: 32 }}>
                      <input type="checkbox" checked={r.on} disabled={c.current} onChange={e => set(c.ta_id, { on: e.target.checked })} />
                      <b>{c.class_name}</b><span className="small muted">{c.students} şagird</span>
                      {c.current && <Pill tone="acc">bu sinif</Pill>}
                      {c.already_has_test && <Pill tone="warn">bu mövzuya test artıq var</Pill>}
                    </label>
                    {c.plan_lesson ? (
                      <span className="small muted">№{c.plan_lesson.seq} {c.plan_lesson.topic}{c.working_date ? ` · dərs: ${fmtDate(c.working_date)}, ${c.period}-ci saat` : ' · işçi planda tarix yoxdur'}</span>
                    ) : r.on && (
                      <select className="sel" value={r.pl ?? ''} onChange={e => set(c.ta_id, { pl: Number(e.target.value) || null })}>
                        <option value="">Mövzu tapılmadı – bu sinfin planından seçin</option>
                        {c.lessons?.map(l => <option key={l.id} value={l.id}>№{l.seq} {l.topic}</option>)}
                      </select>)}
                    {r.on && (
                      <div className="row" style={{ gap: 6 }}>
                        <span className="small">Başlama</span>
                        <input type="date" className="sel" value={r.d1} onChange={e => set(c.ta_id, { d1: e.target.value })} />
                        <input type="time" className="sel" value={r.t1} onChange={e => set(c.ta_id, { t1: e.target.value })} />
                        <span className="small">Bitmə</span>
                        <input type="date" className="sel" value={r.d2} onChange={e => set(c.ta_id, { d2: e.target.value })} />
                        <input type="time" className="sel" value={r.t2} onChange={e => set(c.ta_id, { t2: e.target.value })} />
                      </div>)}
                    {r.on && <StudentPicker ta={c.ta_id} legend={`Kimə – ${c.class_name}`} onChange={ids => set(c.ta_id, { ids })} />}
                    {r.on && variants && r.ids && <span className="small muted">Seçilmiş şagirdlər öz səviyyəsinin variantını alır.</span>}
                  </div>)
              })}
            </div>
            {d.classes.length > 1 && <button type="button" className="btn sm ghost" style={{ marginTop: 8 }} onClick={sameTime}>Hamısına bu sinfin vaxtını qoy</button>}
            {d.classes.length === 1 && <p className="small muted">Eyni fənn və sinif səviyyəsində başqa sinfiniz yoxdur.</p>}
          </fieldset>

          {prev && prev.length > 0 && (
            <fieldset><legend>Bu mövzu üçün əvvəlki testləriniz ({prev.length})</legend>
              {prev.slice(0, 6).map(p => (
                <div key={p.task_id} className="row small" style={{ borderTop: '1px solid var(--line)', padding: '6px 0' }}>
                  <span className="grow"><b>{p.title}</b> <span className="muted">· {p.class_name} · {fmtDate(p.opens_at)} · {p.count} sual{p.avg_pct != null ? ` · orta ${p.avg_pct}%` : ''}</span></span>
                  <button type="button" className="btn sm" onClick={() => takePrev(p)}>Sualları götür</button>
                </div>))}
              <p className="small muted" style={{ margin: '6px 0 0' }}>Keçən illərin testləri də burada görünür – yeni ildə eyni mövzuya sualları bir kliklə götürün.</p>
            </fieldset>)}
          {toplu && (
            <fieldset><legend>Toplu tapşırıqlarından (P007){toplu.chapter ? ` – ${toplu.chapter}` : ''}</legend>
              {!toplu.in_bank ? (
                <p className="small muted" style={{ margin: 0 }}>Bu fəslin P007 testləri hələ test bazasında yoxdur (admin «Hamısını yenidən oxu» ilə yeniləyə bilər).{' '}
                  {toplu.url && <a href={toplu.url} target="_blank" rel="noreferrer">P007-də aç</a>}</p>
              ) : toplu.mode === 'chapter' ? (
                <div className="row" style={{ gap: 6 }}>
                  <button type="button" className="btn sm" disabled={tbusy} onClick={() => takeToplu('lesson')}>Dərsin tapşırıqları</button>
                  {toplu.has_ev && <button type="button" className="btn sm" disabled={tbusy} onClick={() => takeToplu('ev')}>Ev tapşırığı (onlayn yoxlama)</button>}
                  <button type="button" className="btn sm" disabled={tbusy} onClick={() => takeToplu('chapter')}>Fəsil testi:</button>
                  <input type="number" className="sel" style={{ width: 64 }} min={1} max={100} value={tn} onChange={e => setTn(Number(e.target.value) || 15)} />
                  <span className="small muted">təsadüfi sual (qapalı : açıq ≈ 2 : 1)</span>
                </div>
              ) : (
                <div className="row" style={{ gap: 6 }}>
                  <button type="button" className="btn sm" disabled={tbusy} onClick={() => takeToplu('lesson')}>
                    {toplu.mode === 'exam' ? '2025 imtahan tapşırıqlarını götür' : toplu.mode === 'diag' ? 'Diaqnostik test (hər fəsildən 1)' : 'Toplu sınağı (hər fəsildən 2)'}</button>
                  {toplu.mode !== 'exam' && <span className="small muted">Bu sinfə əvvəl verilmiş suallar təkrarlanmır.</span>}
                  {!!toplu.absent?.length && <span className="small muted">Bazada olmayan fəsillər: {toplu.absent.length}</span>}
                </div>)}
            </fieldset>)}
          {p10?.eligible && (
            <fieldset><legend>P0010 testləri (mövzuya uyğun)</legend>
              {!p10.matches.length ? <p className="small muted" style={{ margin: 0 }}>P0010 test bazasında bu mövzuya uyğun fayl tapılmadı – aşağıdan əl ilə seçin.</p> : (<>
                {p10.file && <p className="small" style={{ margin: '0 0 6px' }}>Avtomatik əlavə olundu: <b>{p10.file.label}</b> ({p10.questions.length} sual). Lazım olmayanları siyahıdan silin.</p>}
                <div className="row" style={{ gap: 6 }}>
                  {p10.matches.map(m => <button key={m.file_id} type="button" className="btn sm" disabled={tbusy} onClick={() => takeP10(m.file_id)}>{m.label} <span className="muted">({m.count})</span></button>)}
                </div>
                <div className="row" style={{ gap: 6, marginTop: 6 }}><span className="small muted">Bir fayldan ən çoxu</span>
                  <input type="number" className="sel" style={{ width: 64 }} min={1} max={100} value={tn} onChange={e => setTn(Number(e.target.value) || 15)} />
                  <span className="small muted">sual (çoxdursa təsadüfi, qapalı : açıq ≈ 2 : 1)</span></div>
              </>)}
            </fieldset>)}
          {variants && <div className="row"><span className="small">Variant:</span>
            {LV.map(k => <button key={k} type="button" className="chip" aria-pressed={vk === k} onClick={() => setVk(k)}>{k} <span className="muted">({vqs[k].length})</span></button>)}</div>}
          <BankPicker has={has} add={add} remove={remove} onTitle={() => {}} disabled={false} first={false} kinds={['movzu', 'diaqnostik']}
            legend="Test bazasından – mövzu testləri (sınaqlar ayrıca bölmədədir)" />
          <fieldset><legend>{variants ? `«${vk}» variantının sualları` : 'Seçilmiş suallar'} ({qs.length})</legend>
            {qs.length === 0 ? <p className="small muted">Yuxarıdan test bazasından seçin və ya öz sualınızı yazın.</p> : (
              <div className="jlist">
                {qs.map((q, i) => (
                  <div key={q.key} className="jrow cols" style={{ ['--cols' as any]: '28px minmax(0,1fr) auto', ['--mcols' as any]: '28px minmax(0,1fr)' }}>
                    <span className="num muted">{i + 1}.</span>
                    <span className="small"><span className="clamp2"><MathText text={q.text} /></span>
                      <span className="muted">{q.raw ? `${q.source || ''}${q.lesson ? ' · ' + q.lesson : ''}` : 'öz sualım'}</span></span>
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
