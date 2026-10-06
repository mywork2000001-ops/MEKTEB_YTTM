// Sınaq seriyası: seçilmiş sınaqlar növbə ilə dövrə görə (gün / həftə / ay) siniflərə özü gedir; bankda yeni sınaq
// görünəndə növbəyə düşür (docs/sinaq-seriyasi-promtu.md).
import { useEffect, useState } from 'react'
import { del as apiDel, get, patch, post } from '../../api'
import { Drawer, ErrorBox, Field, Loading, Pill, Seg, toast, useLoad } from '../../ui'

type Target = { ta_id: number; class_name: string; subject: string; grade: number | null; mine: boolean; students: number }
type BFile = { id: number; label: string; questions: number; kind: string; grades: number[]; source: string }
type Series = {
  id: number; title: string; subject: string; period: 'day' | 'week' | 'month'; every: number; weekday: number | null
  month_day: number | null; open_time: string; window_hours: number; duration_min: number; auto_new: boolean; active: boolean
  next_at: string; queue: { id: number; label: string | null }[]; done: { file_id: number; batch_id: number; at: string }[]
  preview: { at: string; weekday: string; file_id: number | null; label: string | null }[]; targets: { ta_id: number }[]; sources: string[]
}
const WD = ['Bazar ertəsi', 'Çərşənbə axşamı', 'Çərşənbə', 'Cümə axşamı', 'Cümə', 'Şənbə', 'Bazar']
const SOURCES: [string, string][] = [['sinaqlar', 'Sınaqlar (illər üzrə)'], ['p012', 'P012 · Riyaziyyat 11 Buraxılış'], ['p009', 'P009 · Riyaziyyat 11 DİM'], ['p004', 'P004 · TAİM']]
const when = (s: string) => new Date(s).toLocaleString('az-AZ', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
const rule = (s: Series) => s.period === 'day' ? `hər ${s.every > 1 ? s.every + ' ' : ''}gün` : s.period === 'week'
  ? `hər ${s.every > 1 ? s.every + ' ' : ''}həftə, ${WD[s.weekday ?? 0]}` : `hər ${s.every > 1 ? s.every + ' ' : ''}ay, ${s.month_day}-i`

export default function ExamSeriesPanel() {
  const [list, err, loading, reload] = useLoad<Series[]>(() => get('/api/exam-series'), [])
  const [creating, setCreating] = useState(false)
  const act = async (fn: () => Promise<unknown>, msg: string) => { try { await fn(); toast(msg); reload() } catch (e: any) { toast(e?.message || 'Xəta') } }
  return (
    <>
      <div className="row" style={{ marginBottom: 12 }}>
        <p className="small muted grow" style={{ margin: 0 }}>Bir dəfə qurun: seçdiyiniz sınaqlar növbə ilə (hər gün / həftə / ay) siniflərə özü gedir.
          «Yeni sınaqları avtomatik əlavə et» açıqdırsa, viktorina-ya əlavə etdiyiniz yeni sınaqlar da növbəyə düşür.</p>
        <button className="btn primary" onClick={() => setCreating(true)}>+ Yeni seriya</button>
      </div>
      <ErrorBox error={err} />
      {loading && !list ? <Loading /> : (
        <div className="jlist">
          {list?.length === 0 && <div className="empty">Seriya yoxdur – «+ Yeni seriya» ilə sınaqları seçib dövrü təyin edin.</div>}
          {list?.map(s => (
            <div key={s.id} className="jrow cols" style={{ ['--cols' as any]: 'minmax(0,1fr)', ['--mcols' as any]: '1fr', gap: 6 }}>
              <div className="row"><b className="grow">{s.title}</b>
                <Pill tone={s.active ? 'ok' : undefined}>{s.active ? 'işləyir' : 'dayandırılıb'}</Pill>
                {s.auto_new && <Pill tone="info">yeni sınaqlar avtomatik</Pill>}</div>
              <span className="small muted">{s.subject} · {rule(s)}, {s.open_time} · {s.window_hours} saat açıq · {s.duration_min} dəq ·
                növbədə {s.queue.length} · göndərilib {s.done.length}</span>
              {s.active && <div className="small">{s.preview.slice(0, 4).map((p, i) => (
                <div key={i}>{p.weekday} {when(p.at)} – {p.label ? <b>{p.label}</b> : <span className="muted">növbə boşdur – yeni sınaq gözlənilir</span>}</div>))}</div>}
              <div className="row" style={{ gap: 6 }}>
                <button className="btn sm" onClick={() => act(() => patch(`/api/exam-series/${s.id}`, { active: !s.active }), s.active ? 'Dayandırıldı' : 'Davam edir')}>{s.active ? 'Dayandır' : 'Davam et'}</button>
                <button className="btn sm" onClick={() => act(() => patch(`/api/exam-series/${s.id}`, { auto_new: !s.auto_new }), 'Saxlandı')}>{s.auto_new ? 'Yeniləri avtomatik əlavə etmə' : 'Yeniləri avtomatik əlavə et'}</button>
                <button className="btn sm ghost" onClick={() => act(() => apiDel(`/api/exam-series/${s.id}`), 'Seriya silindi (göndərilmiş sınaqlar qalır)')}>Sil</button>
              </div>
              {s.queue.length > 0 && <details><summary className="small">Növbə ({s.queue.length})</summary>
                {s.queue.map((q, i) => (
                  <div key={q.id} className="row small" style={{ gap: 6 }}><span className="grow">{i + 1}. {q.label}</span>
                    <button className="btn sm ghost" disabled={i === 0} onClick={() => { const x = s.queue.map(y => y.id); [x[i - 1], x[i]] = [x[i], x[i - 1]]; act(() => patch(`/api/exam-series/${s.id}`, { queue: x }), 'Sıra dəyişdi') }}>↑</button>
                    <button className="btn sm ghost" onClick={() => act(() => patch(`/api/exam-series/${s.id}`, { queue: s.queue.map(y => y.id).filter(y => y !== q.id) }), 'Növbədən çıxarıldı')}>✕</button>
                  </div>))}
              </details>}
            </div>))}
        </div>)}
      {creating && <NewSeries onClose={() => setCreating(false)} onDone={() => { setCreating(false); reload() }} />}
    </>
  )
}

function NewSeries({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const today = new Date().toISOString().slice(0, 10)
  const [targets, , tl] = useLoad<Target[]>(() => get('/api/exams-online/targets'), [])
  const [f, setF] = useState({ title: 'Həftəlik sınaqlar', sources: ['sinaqlar'], grade: '' as string, period: 'week' as 'day' | 'week' | 'month',
    every: 1, weekday: 5, month_day: 1, start: today, open_time: '15:00', window_hours: 48, duration_min: 60, penalty: 0,
    show_answers: 'after_close', auto_new: true })
  const [tas, setTas] = useState<number[]>([])
  const [files, setFiles] = useState<BFile[] | null>(null)
  const [queue, setQueue] = useState<number[]>([])
  const [err, setErr] = useState<unknown>()
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    setFiles(null)
    get<BFile[]>('/api/exam-series/files', { sources: f.sources.join(','), ...(f.grade ? { grade: f.grade } : {}) }).then(setFiles, setErr)
  }, [f.sources.join(','), f.grade])
  const subj = targets?.find(t => tas.includes(t.ta_id))?.subject
  const toggle = (id: number) => setQueue(q => q.includes(id) ? q.filter(x => x !== id) : [...q, id])
  const submit = async () => {
    setBusy(true)
    try {
      await post('/api/exam-series', { ...f, grade: f.grade ? Number(f.grade) : null, targets: tas.map(ta_id => ({ ta_id })), queue,
        weekday: f.period === 'week' ? f.weekday : null, month_day: f.period === 'month' ? f.month_day : null })
      toast('Seriya yaradıldı'); onDone()
    } catch (e) { setErr(e) } finally { setBusy(false) }
  }
  return (
    <Drawer title="Yeni sınaq seriyası" onClose={onClose}
      footer={<><span className="small muted grow">{queue.length} sınaq növbədə · {tas.length} sinif</span><button className="btn" onClick={onClose}>Ləğv et</button>
        <button className="btn primary" disabled={busy || !tas.length || (!queue.length && !f.auto_new)} onClick={submit}>Yarat</button></>}>
      <div className="stack">
        <div className="fg">
          <Field label="Ad" full><input value={f.title} maxLength={200} onChange={e => setF({ ...f, title: e.target.value })} /></Field>
          <Field label="Dövr" full><Seg value={f.period} onChange={v => setF({ ...f, period: v })} options={[['day', 'Hər gün'], ['week', 'Hər həftə'], ['month', 'Hər ay']]} /></Field>
          <Field label="Hər neçə dövrdən bir"><input type="number" min={1} max={12} value={f.every} onChange={e => setF({ ...f, every: Number(e.target.value) || 1 })} /></Field>
          {f.period === 'week' && <Field label="Həftənin günü"><select value={f.weekday} onChange={e => setF({ ...f, weekday: Number(e.target.value) })}>{WD.map((w, i) => <option key={i} value={i}>{w}</option>)}</select></Field>}
          {f.period === 'month' && <Field label="Ayın günü"><input type="number" min={1} max={31} value={f.month_day} onChange={e => setF({ ...f, month_day: Number(e.target.value) || 1 })} /></Field>}
          <Field label="Başlama tarixi"><input type="date" value={f.start} onChange={e => setF({ ...f, start: e.target.value })} /></Field>
          <Field label="Açılma saatı"><input type="time" value={f.open_time} onChange={e => setF({ ...f, open_time: e.target.value })} /></Field>
          <Field label="Açıq qalır (saat)"><input type="number" min={1} max={744} value={f.window_hours} onChange={e => setF({ ...f, window_hours: Number(e.target.value) || 48 })} /></Field>
          <Field label="Həll müddəti (dəq)"><input type="number" min={1} max={300} value={f.duration_min} onChange={e => setF({ ...f, duration_min: Number(e.target.value) || 60 })} /></Field>
          <Field label="Cərimə"><select value={f.penalty} onChange={e => setF({ ...f, penalty: Number(e.target.value) })}><option value={0}>yoxdur</option><option value={3}>3 səhv 1 düzü aparır</option><option value={4}>4 səhv 1 düzü aparır</option></select></Field>
          <Field label="Düzgün cavablar"><select value={f.show_answers} onChange={e => setF({ ...f, show_answers: e.target.value })}><option value="after_close">bağlandıqdan sonra</option><option value="after_submit">təhvildən dərhal sonra</option><option value="never">göstərilməsin</option></select></Field>
        </div>
        <fieldset><legend>Siniflər {subj ? `(${subj})` : ''}</legend>
          {tl && !targets ? <Loading /> : targets?.filter(t => t.mine).map(t => (
            <label key={t.ta_id} className="check"><input type="checkbox" checked={tas.includes(t.ta_id)} disabled={!!subj && t.subject !== subj}
              onChange={e => setTas(x => e.target.checked ? [...x, t.ta_id] : x.filter(y => y !== t.ta_id))} /> {t.class_name} <span className="small muted">· {t.subject} · {t.students} şagird</span></label>))}
        </fieldset>
        <fieldset><legend>Sınaqlar (seçilmə sırası = göndərilmə sırası)</legend>
          <div className="row" style={{ gap: 6, marginBottom: 6 }}>
            {SOURCES.map(([k, l]) => <button key={k} type="button" className="chip" aria-pressed={f.sources.includes(k)}
              onClick={() => setF({ ...f, sources: f.sources.includes(k) ? f.sources.filter(x => x !== k) : [...f.sources, k] })}>{l}</button>)}
            <select className="sel" value={f.grade} onChange={e => setF({ ...f, grade: e.target.value })}><option value="">bütün siniflər</option>
              {[5, 6, 7, 8, 9, 10, 11].map(g => <option key={g} value={g}>{g}-cu sinif</option>)}</select>
          </div>
          <label className="check"><input type="checkbox" checked={f.auto_new} onChange={e => setF({ ...f, auto_new: e.target.checked })} /> Yeni sınaqları avtomatik əlavə et (viktorina-ya əlavə olunanlar)</label>
          {!files ? <Loading /> : files.length === 0 ? <p className="small muted">Bu mənbələrdə sınaq yoxdur.</p> : <>
            <button type="button" className="btn sm ghost" onClick={() => setQueue(queue.length === files.length ? [] : files.map(x => x.id))}>{queue.length === files.length ? 'Heç biri' : 'Hamısını seç'}</button>
            <div style={{ maxHeight: 320, overflowY: 'auto' }}>{files.map(x => {
              const n = queue.indexOf(x.id)
              return <label key={x.id} className="check small"><input type="checkbox" checked={n >= 0} onChange={() => toggle(x.id)} />
                {n >= 0 && <b>{n + 1}.</b>} {x.label} <span className="muted">({x.questions} sual)</span></label>
            })}</div></>}
        </fieldset>
        <ErrorBox error={err} />
      </div>
    </Drawer>
  )
}
