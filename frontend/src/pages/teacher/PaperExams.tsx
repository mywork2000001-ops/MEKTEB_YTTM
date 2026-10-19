// Yazılı (kağız) rejim: mövzu testi, sınaq və sərbəst yazılı iş (docs/yazili-sinaq-ve-skan-duymesi-promtu.md §A).
// Plan tələb olunmur; məktəb və fərdi məkanda eyni. Çap – variants/print (ümumi vərəqə), skan – daimi «📷 Skan» düyməsi.
import { useEffect, useState } from 'react'
import { del, get, patch, post } from '../../api'
import { AsyncBtn, Drawer, ErrorBox, Field, fmt, fmtDate, gradeTone, Loading, Pill, PickFirst, toast, useLoad } from '../../ui'
import { useT } from '../../i18n'
import { printBooklet, printKey, printSheets, type KsqPrint } from '../../ksqPrint'
import OwnNumbersReport, { type OwnReport } from '../../OwnNumbersReport'

type Paper = { id: number; kind: 'TEST' | 'SINAQ' | 'YI' | 'VIK'; no: number; title: string | null; date: string; to_journal: boolean
  online_task_id: number | null; variants: number; printed: boolean; scanned: number; graded: number; variant_mode: string | null }
type TaskRow = { id: number; title: string; kind: string | null; archived?: boolean }
type Res = { rows: { student_id: number; full_name: string; points: number | null; grade: number | null; paper_points: number | null
  online_points: number | null; differs: boolean }[] }
type Src = { key: string; label: string; enabled: boolean }
type BFile = { id: number; label: string; questions: number }
type VGroup = { source_key: string; source_label: string; no_grade: boolean; files: BFile[] }

const KIND_LABEL: Record<string, string> = { TEST: 'Mövzu testi', SINAQ: 'Sınaq', YI: 'Sərbəst yazılı iş', VIK: 'Viktorina' }

export default function PaperExams({ ta }: { ta: number | null }) {
  const t = useT()
  const [d, err, , reload] = useLoad<Paper[] | null>(() => (ta ? get<Paper[]>(`/api/paper-exams/${ta}`) : Promise.resolve(null)), [ta])
  const [create, setCreate] = useState(false)
  const [open, setOpen] = useState<number | null>(null)
  if (!ta) return <PickFirst text="Yazılı iş üçün sinif seçin" />
  return (
    <>
      <div className="card" style={{ marginBottom: 12 }}>
        <p className="muted" style={{ margin: 0 }}>{t('Hazır testi və ya sınağı kağızda keçirin (hamıya eyni vərəq) və ya bank fayllarından sərbəst yazılı iş düzəldin. Hər şagirdə QR-lı cavab vərəqi çap olunur, sonra istənilən səhifədən «📷 Skan» ilə oxunur.')}</p>
        <div style={{ marginTop: 10 }}><button className="btn primary" onClick={() => setCreate(true)}>+ {t('Yazılı iş yarat')}</button></div>
      </div>
      {err ? <ErrorBox error={err} /> : !d ? <Loading /> : d.length === 0 ? <div className="empty">{t('Hələ yazılı iş yoxdur')}</div> : (
        <div style={{ display: 'grid', gap: 10 }}>
          {d.map(p => (
            <section key={p.id} className="card">
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <b>{p.title || `${t(KIND_LABEL[p.kind])} ${p.no}`}</b>
                <Pill tone="info">{t(KIND_LABEL[p.kind])}</Pill>
                <span className="muted">{fmtDate(p.date)}</span>
                <span className="grow" />
                <span className="muted">{t('Skan: {a}/{b}', { a: p.graded, b: p.variants })}</span>
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8, alignItems: 'center' }}>
                <AsyncBtn className="btn sm primary" onClick={async () => { printSheets(await get<KsqPrint>(`/api/exams/${ta}/${p.id}/variants/print`)); reload() }}>🖨 {t('Vərəqləri çap et')}</AsyncBtn>
                <AsyncBtn className="btn sm" onClick={async () => printSheets(await get<KsqPrint>(`/api/exams/${ta}/${p.id}/variants/print`), { cardOnly: true })}>{t('Yalnız cavab vərəqləri')}</AsyncBtn>
                <AsyncBtn className="btn sm" onClick={async () => printBooklet(await get<KsqPrint>(`/api/exams/${ta}/${p.id}/variants/print`))}>{t('Sual kitabçası')}</AsyncBtn>
                {p.variant_mode !== 'different' && <AsyncBtn className="btn sm" onClick={async () => {
                  try { printSheets(await get<KsqPrint>(`/api/exams/${ta}/${p.id}/variants/print`, { blank: true }), { cardOnly: true }) } catch (x) { toast((x as Error).message) }
                }}>{t('Boş forma')}</AsyncBtn>}
                <AsyncBtn className="btn sm" onClick={async () => printKey(await get<KsqPrint>(`/api/exams/${ta}/${p.id}/variants/print`))}>{t('Açar')}</AsyncBtn>
                <button className="btn sm" onClick={() => window.dispatchEvent(new Event('mk-open-scan'))}>📷 {t('Skan')}</button>
                <button className="btn sm" onClick={() => setOpen(open === p.id ? null : p.id)}>{t('Nəticələr')}</button>
                <label style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: 13 }}>
                  <input type="checkbox" checked={p.to_journal} onChange={async e => { await patch(`/api/paper-exams/${ta}/${p.id}`, { to_journal: e.target.checked }); reload() }} />
                  {t('Jurnala yaz')}</label>
                <AsyncBtn className="btn sm danger" onClick={async () => {
                  if (!confirm(t('Yazılı iş silinsin?'))) return
                  try { await del(`/api/paper-exams/${ta}/${p.id}`); reload() } catch (x) {
                    if (confirm((x as Error).message + '\n' + t('Yenə də silinsin?'))) { await del(`/api/paper-exams/${ta}/${p.id}`, undefined, { force: true }); reload() }
                  }
                }}>{t('Sil')}</AsyncBtn>
              </div>
              {open === p.id && <Results ta={ta} id={p.id} />}
            </section>))}
        </div>)}
      {create && <Create ta={ta} onClose={() => setCreate(false)} onDone={() => { setCreate(false); reload() }} />}
    </>
  )
}

function Results({ ta, id }: { ta: number; id: number }) {
  const t = useT()
  const [d, err] = useLoad<Res>(() => get(`/api/paper-exams/${ta}/${id}/results`), [ta, id])
  if (err) return <ErrorBox error={err} />
  if (!d) return <Loading />
  return (
    <table className="tbl" style={{ marginTop: 10 }}>
      <thead><tr><th>{t('Şagird')}</th><th>{t('Kağız')}</th><th>{t('Onlayn')}</th><th>{t('Qiymət')}</th></tr></thead>
      <tbody>{d.rows.map(r => (
        <tr key={r.student_id}>
          <td>{r.full_name}</td>
          <td>{r.paper_points != null ? fmt(r.paper_points) : '—'}</td>
          <td>{r.online_points != null ? fmt(r.online_points) : '—'}{r.differs && <span title={t('Kağız və onlayn bal fərqlidir')}> ⚠</span>}</td>
          <td>{r.grade != null ? <Pill tone={gradeTone(r.grade)}>{r.grade}</Pill> : '—'}</td>
        </tr>))}</tbody>
    </table>
  )
}

function Create({ ta, onClose, onDone }: { ta: number; onClose: () => void; onDone: () => void }) {
  const t = useT()
  const [mode, setMode] = useState<'task' | 'free' | 'vik'>('task')
  const [grade, setGrade] = useState<number | ''>('')
  const [groups, setGroups] = useState<VGroup[] | null>(null)
  const [vq, setVq] = useState('')
  const [shut, setShut] = useState<Record<string, boolean>>({})
  const [tasks, setTasks] = useState<TaskRow[]>([])
  const [taskId, setTaskId] = useState<number | ''>('')
  const [sources, setSources] = useState<Src[]>([])
  const [src, setSrc] = useState('')
  const [files, setFiles] = useState<BFile[]>([])
  const [pick, setPick] = useState<number[]>([])
  const [n, setN] = useState(20)
  const [vm, setVm] = useState<'same' | 'different' | 'same_numbers'>('same')
  const [rep, setRep] = useState<OwnReport | null>(null)
  const [title, setTitle] = useState('')
  const [journal, setJournal] = useState(false)
  const [fail, setFail] = useState<string | null>(null)
  useEffect(() => { get<TaskRow[]>(`/api/tasks/${ta}`).then(setTasks, () => {}); get<Src[]>('/api/bank/sources').then(s => setSources(s.filter(x => x.enabled)), () => {}) }, [ta])
  useEffect(() => { if (src) get<BFile[]>('/api/bank/lessons', { source: src }).then(setFiles, () => setFiles([])); setPick([]) }, [src])
  useEffect(() => { get<{ grade: number | null }>(`/api/paper-exams/${ta}/grade`).then(r => setGrade(r.grade && r.grade >= 1 && r.grade <= 11 ? r.grade : ''), () => {}) }, [ta])
  useEffect(() => {
    if (mode !== 'vik') return
    setGroups(null); setPick([])
    get<VGroup[]>('/api/bank/viktorina-topics', grade === '' ? {} : { grade }).then(setGroups, () => setGroups([]))
  }, [mode, grade])
  const go = async () => {
    setFail(null)
    try {
      const body = mode === 'task' ? { task_id: taskId, title: title || null, to_journal: journal, variant_mode: vm === 'different' ? 'same' : vm }
        : { file_ids: pick, n, variant_mode: vm, title: title || null, to_journal: journal, ...(mode === 'vik' ? { viktorina: true } : {}) }
      const res = await post<{ own_numbers: OwnReport | null }>(`/api/paper-exams/${ta}`, body)
      toast(t('Yazılı iş hazırdır – vərəqləri çap edin'))
      if (res?.own_numbers) setRep(res.own_numbers)       // hesabatı göstər, müəllim «Bağla» ilə bağlayır
      else onDone()
    } catch (x) {
      const m = (x as any)?.detail?.message || (x as Error).message
      setFail(String(m))
    }
  }
  const ok = mode === 'task' ? taskId !== '' : pick.length > 0
  if (rep) return (
    <Drawer title="Yazılı iş yarat" onClose={onDone} footer={<button className="btn primary" onClick={onDone}>{t('Bağla')}</button>}>
      <OwnNumbersReport r={rep} />
    </Drawer>)
  return (
    <Drawer title="Yazılı iş yarat" onClose={onClose} footer={<AsyncBtn className="btn primary" disabled={!ok} onClick={go}>{t('Yarat')}</AsyncBtn>}>
      <div style={{ display: 'grid', gap: 12 }}>
        <div className="seg" role="group">
          <button aria-pressed={mode === 'task'} className="btn sm" onClick={() => setMode('task')}>{t('Hazır test / sınaq')}</button>
          <button aria-pressed={mode === 'free'} className="btn sm" onClick={() => setMode('free')}>{t('Sərbəst yazılı iş')}</button>
          <button aria-pressed={mode === 'vik'} className="btn sm" onClick={() => setMode('vik')}>{t('Viktorina')}</button>
        </div>
        {mode === 'task' ? (
          <>
          <Field label={t('Test və ya sınaq')}>
            <select value={taskId} onChange={e => setTaskId(e.target.value ? +e.target.value : '')}>
              <option value="">—</option>
              {tasks.map(x => <option key={x.id} value={x.id}>{x.title}{x.kind === 'sinaq' ? ' · ' + t('Sınaq') : ''}</option>)}
            </select></Field>
            <Field label={t('Variantlar')}>
              <select value={vm === 'different' ? 'same' : vm} onChange={e => setVm(e.target.value as 'same' | 'same_numbers')}>
                <option value="same">{t('Hamıya eyni suallar')}</option>
                <option value="same_numbers">{t('Hamıya eyni suallar, hər şagirdə öz rəqəmləri')}</option>
              </select></Field>
          </>
        ) : mode === 'vik' ? (
          <>
            <p className="muted" style={{ margin: 0 }}>{t('Seçdiyiniz mövzulardan təsadüfi suallar – bütün viktorina bazasından, bir neçə layihədən ola bilər.')}</p>
            <Field label={t('Sinif')}>
              <select value={grade} onChange={e => setGrade(e.target.value ? +e.target.value : '')}>
                <option value="">—</option>
                {Array.from({ length: 11 }, (_, i) => i + 1).map(g => <option key={g} value={g}>{g}</option>)}
              </select></Field>
            <input value={vq} onChange={e => setVq(e.target.value)} placeholder={t('Mövzu axtar')} />
            {groups === null ? <Loading /> : groups.length === 0 ? <div className="empty">{t('Bu sinif üçün mövzu tapılmadı')}</div> : (
              <div style={{ maxHeight: 300, overflow: 'auto', border: '1px solid var(--line)', borderRadius: 8, padding: 8, display: 'grid', gap: 6 }}>
                {groups.map(g => {
                  const gk = g.source_key + (g.no_grade ? ':ng' : '')
                  const fl = g.files.filter(f => f.label.toLowerCase().includes(vq.trim().toLowerCase()))
                  if (!fl.length) return null
                  const closed = !!shut[gk] && !vq.trim()
                  return (
                    <div key={gk}>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                        <button className="btn sm" onClick={() => setShut(s => ({ ...s, [gk]: !s[gk] }))}>{closed ? '▸' : '▾'}</button>
                        <b style={{ fontSize: 13 }}>{g.source_label}{g.no_grade ? ` (${t('sinfi göstərilməyib')})` : ''}</b>
                        <span className="muted">({fl.length})</span>
                        <span className="grow" />
                        <button className="btn sm" onClick={() => setPick(p => [...new Set([...p, ...fl.map(f => f.id)])])}>{t('Hamısını seç')}</button>
                        <button className="btn sm" onClick={() => setPick(p => p.filter(id => !fl.some(f => f.id === id)))}>{t('Heç birini')}</button>
                      </div>
                      {!closed && fl.map(f => (
                        <label key={f.id} style={{ display: 'flex', gap: 8, fontSize: 13, marginLeft: 12 }}>
                          <input type="checkbox" checked={pick.includes(f.id)} onChange={e => setPick(p => e.target.checked ? [...p, f.id] : p.filter(x => x !== f.id))} />
                          {f.label} <span className="muted">({f.questions})</span></label>))}
                    </div>)
                })}
              </div>)}
            <div className="muted">{t('Seçilib: {n}', { n: pick.length })}</div>
            <Field label={t('Sual sayı (5–30)')}>
              <input type="number" min={5} max={30} value={n} onChange={e => setN(Math.max(5, Math.min(30, +e.target.value || 5)))} /></Field>
            <Field label={t('Variantlar')}>
              <select value={vm} onChange={e => setVm(e.target.value as 'same' | 'different' | 'same_numbers')}>
                <option value="same">{t('Hamıya eyni suallar')}</option>
                <option value="different">{t('Hər şagirdə fərqli suallar')}</option>
                <option value="same_numbers">{t('Hamıya eyni suallar, hər şagirdə öz rəqəmləri')}</option>
              </select></Field>
          </>
        ) : (
          <>
            <Field label={t('Test layihəsi')}>
              <select value={src} onChange={e => setSrc(e.target.value)}>
                <option value="">—</option>
                {sources.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
              </select></Field>
            {files.length > 0 && (
              <div style={{ maxHeight: 220, overflow: 'auto', border: '1px solid var(--line)', borderRadius: 8, padding: 8 }}>
                {files.map(f => (
                  <label key={f.id} style={{ display: 'flex', gap: 8, fontSize: 13 }}>
                    <input type="checkbox" checked={pick.includes(f.id)} onChange={e => setPick(p => e.target.checked ? [...p, f.id] : p.filter(x => x !== f.id))} />
                    {f.label} <span className="muted">({f.questions})</span></label>))}
              </div>)}
            <Field label={t('Sual sayı (5–30)')}>
              <input type="number" min={5} max={30} value={n} onChange={e => setN(Math.max(5, Math.min(30, +e.target.value || 5)))} /></Field>
            <Field label={t('Variantlar')}>
              <select value={vm} onChange={e => setVm(e.target.value as 'same' | 'different' | 'same_numbers')}>
                <option value="same">{t('Hamıya eyni suallar')}</option>
                <option value="different">{t('Hər şagirdə fərqli suallar')}</option>
                <option value="same_numbers">{t('Hamıya eyni suallar, hər şagirdə öz rəqəmləri')}</option>
              </select></Field>
          </>)}
        <Field label={t('Ad (istəyə görə)')}><input value={title} onChange={e => setTitle(e.target.value)} maxLength={200} /></Field>
        <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input type="checkbox" checked={journal} onChange={e => setJournal(e.target.checked)} />
          {t('Nəticə jurnala da yazılsın')}</label>
        {fail && <div className="err" role="alert">{fail}</div>}
      </div>
    </Drawer>
  )
}
