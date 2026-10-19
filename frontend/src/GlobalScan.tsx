// Daimi «📷 Skan» düyməsi (docs/yazili-sinaq-ve-skan-duymesi-promtu.md §C): müəllim interfeysinin hər səhifəsində.
// Kamera (ardıcıl skan – scanCamera.tsx, any rejimi) və ya fayl yükləmə (şəkillər / PDF); imtahanı və şagirdi QR özü göstərir.
// QR oxunmayanda – imtahan və şagirdi siyahıdan seçmək (son 7 günün imtahanları yuxarıda). Nişan: çap olunub, nəticəsi olmayan imtahan sayı.
import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { api, get } from './api'
import { useAuth } from './auth'
import { useT } from './i18n'
import ScanCamera from './scanCamera'
import { Drawer } from './ui'

type Found = { student_id: number; scan_id: number; full_name: string | null; exam: string; list: string }
type Up = { found: Found[]; already: { student_id: number; full_name: string | null; exam: string; points: number | null }[]
  problems: { file?: string; kind?: string; error: string; full_name?: string | null }[]; unmatched: number }
type Opt = { ta_id: number; exam_id: number; label: string; class_name: string; date: string; recent: boolean; students: { id: number; full_name: string }[] }
type Row = { id: number; status: string; points: number | null; flagged: number[]; error: string | null }

export default function GlobalScan() {
  const t = useT()
  const { me } = useAuth()
  const loc = useLocation()
  const [mode, setMode] = useState<null | 'menu' | 'camera'>(null)
  const [badge, setBadge] = useState(0)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [up, setUp] = useState<Up | null>(null)
  const [loose, setLoose] = useState<File[]>([])             // QR oxunmayan fayllar – əl ilə seçim
  const [manual, setManual] = useState<Blob | File | null>(null)
  const [pts, setPts] = useState<Record<number, Row>>({})
  const staff = !!me && me.role !== 'student'
  const input = useRef<HTMLInputElement>(null)

  const refresh = () => { get<{ waiting: number }>('/api/scans/any/summary').then(d => setBadge(d.waiting), () => {}) }
  useEffect(() => { if (staff && mode === null) refresh() }, [staff, loc.pathname, mode])   // eslint-disable-line react-hooks/exhaustive-deps

  // yüklənmiş kartların balı: oxunana qədər hər 3 saniyədən bir (təxminən 3 dəqiqə)
  useEffect(() => {
    if (!up?.found.length) return
    let n = 0, stop = false, timer = 0
    const lists = [...new Set(up.found.map(f => f.list))]
    const step = async () => {
      n++
      try {
        const ds = await Promise.all(lists.map(u => api<{ scans: Row[] }>(u)))
        const map: Record<number, Row> = {}
        ds.forEach(d => d.scans.forEach(s => { map[s.id] = s }))
        if (stop) return
        setPts(map)
        if (up.found.every(f => map[f.scan_id]?.status !== 'pending') || n >= 60) return
      } catch { /* növbəti cəhd */ }
      timer = window.setTimeout(step, 3000)
    }
    timer = window.setTimeout(step, 2000)
    return () => { stop = true; clearTimeout(timer) }
  }, [up])

  if (!staff) return null

  const send = async (files: File[]) => {
    if (!files.length) return
    setBusy(true); setErr(null); setUp(null); setLoose([])
    try {
      const form = new FormData()
      files.forEach(f => form.append('files', f, f.name))
      const r = await api<Up>('/api/scans/any', { method: 'POST', form })
      setUp(r)
      if (r.unmatched) setLoose(files.filter(f => !f.type.includes('pdf')))
    } catch (x) { setErr((x as Error).message) } finally { setBusy(false); refresh() }
  }

  const show = (f: { full_name: string | null; exam: string }) => `${f.full_name || '—'} · ${f.exam}`

  return (
    <>
      <button className="scan-fab" onClick={() => { setUp(null); setErr(null); setLoose([]); setMode('menu') }} aria-label={t('Skan')}>
        <span>📷 {t('Skan')}</span>
        {badge > 0 && <b className="scan-badge" title={t('Çap olunub, nəticəsi olmayan imtahan: {n}', { n: badge })}>{badge}</b>}
      </button>

      {mode === 'menu' && (
        <Drawer title={t('Cavab kartlarını skan et')} onClose={() => setMode(null)}>
          <div style={{ display: 'grid', gap: 10 }}>
            <p className="muted" style={{ margin: 0 }}>{t('Kartın QR-ı imtahanı və şagirdi özü tapır – sinif və imtahan seçmək lazım deyil.')}</p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button className="btn primary" onClick={() => setMode('camera')}>📷 {t('Şəkil çək')}</button>
              <button className="btn" disabled={busy} onClick={() => input.current?.click()}>{t('Fayl yüklə')}</button>
              <input ref={input} type="file" hidden multiple accept="image/*,application/pdf"
                onChange={e => { const fs = [...(e.target.files || [])]; e.target.value = ''; send(fs) }} />
            </div>
            {busy && <div>⏳ {t('Göndərilir…')}</div>}
            {err && <div className="err" role="alert">{err}</div>}
            {up && (
              <div style={{ display: 'grid', gap: 4 }}>
                {up.found.map(f => {
                  const r = pts[f.scan_id]
                  return (
                    <div key={f.scan_id}>
                      <b>{show(f)}</b> — {r?.status === 'graded' ? <>{t('{n} bal', { n: r.points ?? 0 })}{r.flagged.length > 0 && <span style={{ color: 'var(--warn)' }}> · ⚠ {t('yoxlayın: {n}', { n: r.flagged.length })}</span>}</>
                        : r?.status === 'error' ? <span style={{ color: 'var(--bad)' }}>{r.error}</span> : t('bal hesablanır…')}
                    </div>)
                })}
                {up.already.map((a, i) => (
                  <div key={i} className="muted">{show(a)} — {t('{name} artıq skan olunub', { name: a.full_name || '—' })}{a.points != null ? ` (${t('{n} bal', { n: a.points })})` : ''}</div>))}
                {up.problems.filter(p => p.kind !== 'no_qr').map((p, i) => (
                  <div key={i} style={{ color: 'var(--bad)' }}>{p.full_name ? p.full_name + ': ' : ''}{p.error}</div>))}
                {up.unmatched > 0 && <div style={{ color: 'var(--warn)' }}>{t('QR oxunmadı: {n} fayl – şagirdi və imtahanı özünüz seçin', { n: up.unmatched })}</div>}
                {loose.map((f, i) => (
                  <div key={i}><button className="btn sm" onClick={() => setManual(f)}>{t('Şagird və imtahanı seçin')}: {f.name}</button></div>))}
              </div>)}
          </div>
        </Drawer>)}

      {mode === 'camera' && (
        <ScanCamera url="/api/scans/any" any onSent={refresh} onClose={() => { setMode(null); refresh() }}
          onNoQr={b => { setMode('menu'); setManual(b) }} />)}

      {manual && <ManualPick file={manual} onClose={() => setManual(null)}
        onDone={r => { setManual(null); setMode('menu'); setUp(r); setLoose(l => l.filter(x => x !== manual)); refresh() }} />}
    </>
  )
}

/** QR oxunmayan şəkil üçün: imtahan (son 7 gün yuxarıda) və şagird seçilir. */
function ManualPick({ file, onClose, onDone }: { file: Blob | File; onClose: () => void; onDone: (r: Up) => void }) {
  const t = useT()
  const [opts, setOpts] = useState<Opt[]>([])
  const [ex, setEx] = useState<number | ''>('')
  const [st, setSt] = useState<number | ''>('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { get<Opt[]>('/api/scans/any/options').then(setOpts, x => setErr((x as Error).message)) }, [])
  const cur = opts.find(o => o.exam_id === ex)
  const go = async () => {
    if (!ex || !st) return
    setBusy(true); setErr(null)
    try {
      const form = new FormData()
      form.append('exam_id', String(ex)); form.append('student_id', String(st)); form.append('file', file, (file as File).name || 'kart.jpg')
      onDone(await api<Up>('/api/scans/any/manual', { method: 'POST', form }))
    } catch (x) { setErr((x as Error).message); setBusy(false) }
  }
  const opt = (o: Opt) => <option key={o.exam_id} value={o.exam_id}>{o.label} · {o.class_name} · {o.date.split('-').reverse().join('.')}</option>
  return (
    <Drawer title={t('Şagird və imtahanı seçin')} onClose={onClose}
      footer={<button className="btn primary" disabled={!ex || !st || busy} onClick={go}>{busy ? '…' : t('Qəbul et')}</button>}>
      <div style={{ display: 'grid', gap: 10 }}>
        <label>{t('İmtahan')}
          <select value={ex} onChange={e => { setEx(e.target.value ? +e.target.value : ''); setSt('') }}>
            <option value="">—</option>
            <optgroup label={t('Son 7 gün')}>{opts.filter(o => o.recent).map(opt)}</optgroup>
            <optgroup label={t('Əvvəlki')}>{opts.filter(o => !o.recent).map(opt)}</optgroup>
          </select></label>
        <label>{t('Şagird')}
          <select value={st} disabled={!cur} onChange={e => setSt(e.target.value ? +e.target.value : '')}>
            <option value="">—</option>
            {cur?.students.map(s => <option key={s.id} value={s.id}>{s.full_name}</option>)}
          </select></label>
        {err && <div className="err" role="alert">{err}</div>}
      </div>
    </Drawer>)
}
