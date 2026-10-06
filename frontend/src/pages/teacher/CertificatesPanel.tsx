// Müəllim: sinfin sertifikatları – avtomatik verilənlər, əl ilə vermək, ləğv, hədlər (docs/sertifikat-ve-motivasiya-promtu.md).
import { useState } from 'react'
import { get, post, put } from '../../api'
import { printCert, type Cert } from '../../certificate'
import { CertDrawer } from '../student/Achievements'
import { ErrorBox, Field, Pill, toast, useLoad } from '../../ui'
import { StudentPicker } from './common'

type Rules = { enabled: boolean; movzu: number; sinaq_pct: number; sinaq_top: number; seriya: number }
const KIND: Record<string, string> = { movzu: 'mövzu', sinaq: 'sınaq', seriya: 'seriya', manual: 'əl ilə' }

export default function CertificatesPanel({ ta }: { ta: number }) {
  const [d, err, , reload] = useLoad<{ rules: Rules; items: Cert[] }>(() => get('/api/certificates', { ta_id: ta }), [ta])
  const [open, setOpen] = useState<Cert | null>(null)
  const [give, setGive] = useState(false)
  const [rulesOpen, setRulesOpen] = useState(false)
  if (!d) return <ErrorBox error={err} />
  return (
    <section className="panel" style={{ marginTop: 12 }}>
      <h2>Sertifikatlar<small>{d.items.filter(c => !c.revoked).length}</small></h2>
      <p className="small muted" style={{ marginTop: 0 }}>Avtomatik: mövzu testi ≥ {d.rules.movzu}%, sınaq ≥ {d.rules.sinaq_pct}% və ya sinifdə ilk {d.rules.sinaq_top} yer,
        sınaq seriyasında ≥ {d.rules.seriya}% iştirak.{!d.rules.enabled && <b style={{ color: 'var(--warn)' }}> Avtomatik vermə söndürülüb.</b>} Şagird sertifikatı öz tətbiqində dərhal görür.</p>
      <div className="row" style={{ gap: 6, marginBottom: 8 }}>
        <button className="btn sm primary" onClick={() => setGive(x => !x)}>+ Sertifikat ver</button>
        <button className="btn sm" onClick={() => setRulesOpen(x => !x)}>Hədlər</button>
      </div>
      {give && <Give ta={ta} onDone={() => { setGive(false); reload() }} />}
      {rulesOpen && <RulesForm ta={ta} r={d.rules} onDone={() => { setRulesOpen(false); reload() }} />}
      <div className="jlist">
        {d.items.length === 0 && <div className="empty">Hələ sertifikat yoxdur.</div>}
        {d.items.map(c => (
          <div key={c.id} className="jrow" style={{ gridTemplateColumns: 'minmax(0,1fr) auto', opacity: c.revoked ? 0.5 : 1 }}>
            <span><b>{c.student}</b> <span className="small muted">· {c.title} · {new Date(c.issued_at).toLocaleDateString('az-AZ')}</span>
              {' '}<Pill tone={c.revoked ? 'bad' : 'info'}>{c.revoked ? 'ləğv edilib' : KIND[c.kind] || c.kind}</Pill></span>
            <span className="row" style={{ gap: 4 }}>
              <button className="btn sm" onClick={() => setOpen(c)}>Bax</button>
              <button className="btn sm ghost" onClick={() => printCert(c)}>Çap</button>
              {!c.revoked && <button className="btn sm ghost" onClick={() => post(`/api/certificates/${c.id}/revoke`).then(() => { toast('Ləğv edildi'); reload() }, e => toast(e.message))}>Ləğv et</button>}
            </span>
          </div>))}
      </div>
      {open && <CertDrawer c={open} onClose={() => setOpen(null)} />}
    </section>
  )
}

function Give({ ta, onDone }: { ta: number; onDone: () => void }) {
  const [ids, setIds] = useState<number[] | null>(null)
  const [title, setTitle] = useState('')
  const [note, setNote] = useState('')
  const send = async () => {
    if (ids && !ids.length) { toast('Şagird seçin'); return }                    // null – bütün sinif
    try { const r = await post<{ created: number }>('/api/certificates', { ta_id: ta, student_ids: ids, title: title.trim(), note: note.trim() || null }); toast(`${r.created} sertifikat verildi`); onDone() }
    catch (e: any) { toast(e?.message || 'Xəta') }
  }
  return (
    <div className="stack" style={{ border: '1px solid var(--line)', borderRadius: 10, padding: 10, marginBottom: 10 }}>
      <Field label="Nəyə görə (sertifikatda)" full><input value={title} maxLength={300} placeholder="məs. Riyaziyyat olimpiadasında iştiraka görə" onChange={e => setTitle(e.target.value)} /></Field>
      <Field label="Qeyd (istəyə görə)" full><input value={note} maxLength={300} onChange={e => setNote(e.target.value)} /></Field>
      <StudentPicker ta={ta} legend="Kimə" onChange={setIds} />
      <button className="btn primary sm" disabled={title.trim().length < 3} onClick={send}>Ver</button>
    </div>
  )
}

function RulesForm({ ta, r, onDone }: { ta: number; r: Rules; onDone: () => void }) {
  const [f, setF] = useState(r)
  const num = (k: keyof Rules, label: string, min: number, max: number) => (
    <Field label={label}><input type="number" min={min} max={max} value={f[k] as number} onChange={e => setF({ ...f, [k]: Number(e.target.value) })} /></Field>)
  return (
    <div className="fg" style={{ border: '1px solid var(--line)', borderRadius: 10, padding: 10, marginBottom: 10 }}>
      <label className="check full"><input type="checkbox" checked={f.enabled} onChange={e => setF({ ...f, enabled: e.target.checked })} /> Sertifikatlar avtomatik verilsin</label>
      {num('movzu', 'Mövzu testi, %', 50, 100)}{num('sinaq_pct', 'Sınaq, %', 50, 100)}{num('sinaq_top', 'Sınaqda ilk neçə yer', 0, 10)}{num('seriya', 'Seriyada iştirak, %', 50, 100)}
      <button className="btn primary sm" onClick={() => put(`/api/certificates/rules/${ta}`, f).then(() => { toast('Saxlandı'); onDone() }, e => toast(e.message))}>Saxla</button>
    </div>
  )
}
