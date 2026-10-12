// Bir şagird bir neçə sinifdə/qrupda və təkrar şagirdlərin birləşdirilməsi (docs/sagird-coxlu-sinif-ve-birlesme-promtu.md).
import { useState } from 'react'
import { del as apiDel, get, post } from '../../api'
import { AsyncBtn, ConfirmName, Drawer, ErrorBox, fmtDate, Loading, Pill, toast, useLoad } from '../../ui'

type C = { id: number; name: string; kind: string; parent_id: number | null; can_open: boolean }
type S = { id: number; full_name: string; portal_code: string; class_name: string }

/** Siniflər → sinif/qrup → «+ Başqa sinifdən»: mövcud şagird əlavə üzv kimi (əsas sinfi dəyişmir). */
export function AddExisting({ cls, have, onClose, onDone }: { cls: C; have: number[]; onClose: () => void; onDone: () => void }) {
  const [classes] = useLoad<C[]>(() => get('/api/classes'), [])
  // bölünmə qrupu – yalnız ana sinifdən; qalanı – başqa (bütöv) siniflərdən
  const src = (classes || []).filter(c => c.can_open && c.kind !== 'qrup' && c.id !== cls.id && (!cls.parent_id || c.id === cls.parent_id))
  const [from, setFrom] = useState<number | ''>('')
  const cur = from || src[0]?.id
  const [rows] = useLoad<S[]>(() => (cur ? get('/api/students', { class_id: cur }) : Promise.resolve([])), [cur])
  const free = (rows || []).filter(s => !have.includes(s.id))
  const [pick, setPick] = useState<number[]>([])
  const [err, setErr] = useState<unknown>()
  return (
    <Drawer title={`${cls.name} – başqa sinifdən şagird`} onClose={onClose}
      footer={<><span className="small muted grow">seçilib {pick.length}</span><button className="btn" onClick={onClose}>Bağla</button>
        <AsyncBtn className="btn primary" disabled={!pick.length} ok="Əlavə olundu" onClick={async () => {
          try { await post(`/api/classes/${cls.id}/members/add`, { student_ids: pick }); setPick([]); onDone() } catch (e) { setErr(e); throw e }
        }}>Əlavə et ({pick.length})</AsyncBtn></>}>
      <div className="stack">
        <p className="small muted" style={{ margin: 0 }}>Şagird öz əsas sinfində qalır və bu {cls.kind === 'qrup' ? 'qrupda' : 'sinifdə'} də olur
          (jurnal, testlər, sınaqlar). Məs.: fərdi hazırlıqda IX və XI sinif – bir şagird, iki sinif.</p>
        <label className="hub-pick"><span>Hansı sinifdən</span>
          <select value={cur ?? ''} onChange={e => { setFrom(Number(e.target.value)); setPick([]) }}>
            {src.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
        {!rows ? <Loading /> : free.length === 0 ? <p className="small muted">Bu sinifdən əlavə ediləsi şagird yoxdur.</p> : <>
          <button className="btn sm ghost" style={{ alignSelf: 'flex-start' }} onClick={() => setPick(pick.length === free.length ? [] : free.map(s => s.id))}>{pick.length === free.length ? 'Heç biri' : 'Hamısını seç'}</button>
          <div className="jlist" style={{ maxHeight: '50vh', overflow: 'auto' }}>{free.map(s => (
            <label key={s.id} className="check" style={{ padding: '0 12px', minHeight: 36 }}>
              <input type="checkbox" checked={pick.includes(s.id)} onChange={e => setPick(p => e.target.checked ? [...p, s.id] : p.filter(x => x !== s.id))} />
              {s.full_name} <span className="small muted mono">{s.portal_code}</span></label>))}</div></>}
        <ErrorBox error={err} />
      </div>
    </Drawer>
  )
}

/** Şagird kartı → «Siniflər və qruplar»: əsas sinif + əlavə siniflər və qruplar (qeyd qutusu ilə). */
export function ClassMemberships({ studentId }: { studentId: number }) {
  const [d, err, , reload] = useLoad<{ class: { id: number; name: string }; groups: { id: number; name: string; kind: string; member: boolean; can_edit: boolean }[] }>(
    () => get(`/api/classes/student/${studentId}/groups`), [studentId])
  const [busy, setBusy] = useState<number | null>(null)
  const toggle = async (g: { id: number; member: boolean }) => {
    setBusy(g.id)
    try {
      if (g.member) await apiDel(`/api/classes/${g.id}/members/${studentId}`)
      else await post(`/api/classes/${g.id}/members/add`, { student_ids: [studentId] })
      toast(g.member ? 'Çıxarıldı' : 'Əlavə olundu'); reload()
    } catch (e) { toast('Xəta: ' + (e as Error).message) } finally { setBusy(null) }
  }
  return (
    <section className="panel" style={{ marginTop: 12 }}>
      <h2>Siniflər və qruplar</h2>
      <ErrorBox error={err} />
      {!d ? <Loading /> : <>
        <p className="small" style={{ margin: '0 0 8px' }}>Əsas sinif: <b>{d.class.name}</b> <span className="muted">(ID bu sinfin kodu ilədir; dəyişmək – Tənzimləmələr)</span></p>
        {d.groups.length === 0 ? <p className="small muted" style={{ margin: 0 }}>Əlavə sinif və ya qrup yoxdur.</p>
          : d.groups.map(g => <label key={g.id} className="check"><input type="checkbox" checked={g.member} disabled={!g.can_edit || busy === g.id} onChange={() => toggle(g)} />
            {g.name} <span className="small muted">· {g.kind}</span></label>)}
      </>}
    </section>
  )
}

// ---------------------------------------------------------------- təkrar şagirdlər (admin)
type One = { id: number; full_name: string; class_name: string; portal_code: string; birth_date: string | null; marks: number; attempts: number; attendance: number }
type Pair = { level: string; a: One; b: One }

export function Duplicates({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [list, err, loading, reload] = useLoad<Pair[]>(() => get('/api/students/duplicates'), [])
  const [keep, setKeep] = useState<Record<string, number>>({})
  const [ask, setAsk] = useState<Pair | null>(null)
  const key = (p: Pair) => `${p.a.id}-${p.b.id}`
  const kept = (p: Pair) => (keep[key(p)] ?? p.a.id) === p.a.id ? [p.a, p.b] : [p.b, p.a]
  const card = (x: One, p: Pair) => (
    <label key={x.id} className="check" style={{ alignItems: 'flex-start', padding: 8, border: '1px solid var(--line)', borderRadius: 8, flex: '1 1 220px' }}>
      <input type="radio" name={key(p)} checked={kept(p)[0].id === x.id} onChange={() => setKeep(k => ({ ...k, [key(p)]: x.id }))} />
      <span><b>{x.full_name}</b><br /><span className="small">{x.class_name} · <span className="mono">{x.portal_code}</span>{x.birth_date ? ` · ${fmtDate(x.birth_date)}` : ''}</span><br />
        <span className="small muted">{x.marks} qiymət · {x.attempts} test · {x.attendance} davamiyyət</span></span></label>)
  return (
    <Drawer title="Təkrar şagirdlər" onClose={onClose}>
      <div className="stack">
        <p className="small muted" style={{ margin: 0 }}>Eyni uşaq iki dəfə yazılıbsa – birləşdirin. <b>Saxlanan</b> qeydin əsas sinfi və ID-si qalır; o biri qeydin
          qiymətləri, testləri, davamiyyəti ona keçir, sinfi isə əlavə sinif olur (məs. IX + XI). Silinən qeyd arxivə gedir, onun ID-si ilə giriş bağlanır.
          Geri qaytarılmır – adı yazmaqla təsdiq olunur.</p>
        <ErrorBox error={err} />
        {loading && !list ? <Loading /> : list?.length === 0 ? <div className="empty">Təkrar şagird tapılmadı.</div> : list?.map(p => {
          const [k, dr] = kept(p)
          return (
            <section key={key(p)} className="panel" style={{ padding: 12 }}>
              <div className="row" style={{ marginBottom: 8 }}><Pill tone={p.level === 'oxşar ad' ? undefined : 'warn'}>{p.level}</Pill>
                <span className="small muted grow">Saxlanacaq qeydi seçin (əsas sinif və ID)</span></div>
              <div className="row" style={{ gap: 8, alignItems: 'stretch' }}>{card(p.a, p)}{card(p.b, p)}</div>
              {ask && key(ask) === key(p) ? <ConfirmName name={k.full_name} action="Birləşdir" onCancel={() => setAsk(null)}
                onConfirm={async typed => {
                  const r = await post<{ moved: number; portal_code: string }>('/api/students/merge', { keep_id: k.id, drop_id: dr.id, confirm: typed })
                  toast(`Birləşdirildi: ${k.full_name} – ID ${r.portal_code}`); setAsk(null); reload(); onDone()
                }} /> : <button className="btn sm primary" style={{ marginTop: 8 }} onClick={() => setAsk(p)}>Birləşdir: {dr.class_name} → {k.class_name} ({k.portal_code})</button>}
            </section>)
        })}
      </div>
    </Drawer>
  )
}
