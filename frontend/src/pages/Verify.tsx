// Sertifikatın açıq yoxlanması (girişsiz): /v/:code – QR koddan açılır.
import { useEffect, useState } from 'react'
import { fmtDate } from '../ui'

type V = { code: string; title: string; kind: string; student: string; issued_at: string; valid: boolean; school: string | null
  teacher: string | null; subject: string | null; pct: number | null; place: number | null; of: number | null }

export default function Verify({ code }: { code: string }) {
  const [v, setV] = useState<V | null>(null)
  const [err, setErr] = useState('')
  useEffect(() => {
    fetch(`/api/verify/${encodeURIComponent(code)}`).then(async r => (r.ok ? setV(await r.json()) : setErr((await r.json().catch(() => ({}))).detail || 'Tapılmadı')),
      () => setErr('Şəbəkə xətası'))
  }, [code])
  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', padding: 16, background: 'var(--bg)' }}>
      <div className="panel" style={{ maxWidth: 460, width: '100%', textAlign: 'center' }}>
        <h2 style={{ marginTop: 0 }}>Sertifikatın yoxlanması</h2>
        {err ? <p style={{ color: 'var(--bad)' }}>✕ {err}</p> : !v ? <p className="muted">Yoxlanılır…</p> : (
          <>
            <div style={{ fontSize: 44 }}>{v.valid ? '✅' : '⛔'}</div>
            <p style={{ fontWeight: 800, color: v.valid ? 'var(--ok)' : 'var(--bad)', margin: '4px 0 12px' }}>{v.valid ? 'Sertifikat həqiqidir' : 'Sertifikat ləğv edilib'}</p>
            <p style={{ margin: '0 0 4px' }}><b>{v.student}</b></p>
            <p style={{ margin: '0 0 8px' }}>{v.title}</p>
            <p className="small muted" style={{ margin: 0 }}>
              {[v.subject, v.pct != null ? `${Math.round(v.pct)}%` : '', v.place ? `sinifdə ${v.place}-ci yer` : '', fmtDate(v.issued_at)].filter(Boolean).join(' · ')}
              <br />{[v.school, v.teacher].filter(Boolean).join(' · ')}<br />Kod: <b>{v.code}</b></p>
          </>)}
      </div>
    </div>
  )
}
