// KSQ/BSQ telefon skan rejimi (docs/ksq-bsq-kagiz-promtu.md mərhələ 5): kamera açıq qalır, kartlar bir-bir çəkilir;
// bulanıq / qaranlıq / çox işıqlı şəkil göndərilmir («yenidən çək»), yaxşı şəkil fonda yüklənir – növbəti karta keçmək olar.
// Brauzer QR tanıyırsa (BarcodeDetector), kart kadra düzgün girəndə özü çəkir.
import { useEffect, useRef, useState } from 'react'
import { api } from './api'
import { tt } from './i18n'

type Quality = { ok: boolean; why?: string }

/** Kiçildilmiş boz şəkildə parlaqlıq və kəskinlik (Laplas dispersiyası). */
export function quality(c: HTMLCanvasElement): Quality {
  const w = 320, h = Math.round((c.height / c.width) * 320)
  const t = document.createElement('canvas'); t.width = w; t.height = h
  const x = t.getContext('2d')!
  x.drawImage(c, 0, 0, w, h)
  const d = x.getImageData(0, 0, w, h).data
  const g = new Float32Array(w * h)
  let sum = 0
  for (let i = 0; i < w * h; i++) { g[i] = 0.299 * d[i * 4] + 0.587 * d[i * 4 + 1] + 0.114 * d[i * 4 + 2]; sum += g[i] }
  const mean = sum / (w * h)
  let m = 0, m2 = 0, n = 0
  for (let y = 1; y < h - 1; y++) for (let k = 1; k < w - 1; k++) {
    const i = y * w + k, l = 4 * g[i] - g[i - 1] - g[i + 1] - g[i - w] - g[i + w]
    m += l; m2 += l * l; n++
  }
  const sharp = m2 / n - (m / n) ** 2
  if (mean < 70) return { ok: false, why: tt('Qaranlıqdır – işıqlı yerdə yenidən çəkin') }
  if (mean > 252 && sharp < 120) return { ok: false, why: tt('Çox işıqlıdır – parıltısız yenidən çəkin') }   // ağ vərəq parlaqdır – yalnız «yanmış» kadr
  if (sharp < 60) return { ok: false, why: tt('Bulanıqdır – telefonu sabit saxlayıb yenidən çəkin') }
  return { ok: true }
}

export default function ScanCamera({ url, onClose, onSent }: { url: string; onClose: () => void; onSent: () => void }) {
  const video = useRef<HTMLVideoElement>(null)
  const [msg, setMsg] = useState<{ text: string; bad?: boolean } | null>(null)
  const [sent, setSent] = useState(0)
  const [queue, setQueue] = useState(0)
  const [err, setErr] = useState<string | null>(null)
  const last = useRef(0)

  useEffect(() => {
    let stream: MediaStream | null = null, stop = false
    navigator.mediaDevices?.getUserMedia({ video: { facingMode: 'environment', width: { ideal: 2560 }, height: { ideal: 1440 } }, audio: false })
      .then(s => { stream = s; if (video.current) { video.current.srcObject = s; video.current.play().catch(() => {}) } })
      .catch(() => setErr(tt('Kamera açılmadı – brauzerə kamera icazəsi verin və ya «Şəkil / PDF seç» istifadə edin')))
    // QR görünəndə özü çəkir (yalnız BarcodeDetector olan brauzerlərdə; 3 saniyədə bir dəfədən çox yox)
    const BD = (window as any).BarcodeDetector
    const det = BD ? new BD({ formats: ['qr_code'] }) : null
    const tick = async () => {
      if (stop) return
      if (det && video.current?.readyState === 4 && Date.now() - last.current > 3000) {
        try { const r = await det.detect(video.current); if (r.some((x: any) => String(x.rawValue).startsWith('MK1|'))) shoot() } catch { /* noop */ }
      }
      setTimeout(tick, 500)
    }
    tick()
    return () => { stop = true; stream?.getTracks().forEach(t => t.stop()) }
  }, [])

  const shoot = () => {
    const v = video.current
    if (!v || !v.videoWidth) return
    last.current = Date.now()
    const c = document.createElement('canvas'); c.width = v.videoWidth; c.height = v.videoHeight
    c.getContext('2d')!.drawImage(v, 0, 0)
    const q = quality(c)
    if (!q.ok) { setMsg({ text: q.why!, bad: true }); return }
    setMsg({ text: tt('Göndərilir…') })
    c.toBlob(async b => {
      if (!b) return
      setQueue(n => n + 1)
      const form = new FormData(); form.append('files', b, `kart-${Date.now()}.jpg`)
      try {
        const r = await api<{ found: { full_name: string | null }[]; problems: { error: string }[] }>(url, { method: 'POST', form })
        if (r.found.length) { setSent(n => n + r.found.length); setMsg({ text: '✓ ' + r.found.map(f => f.full_name).join(', ') }); onSent() }
        else setMsg({ text: r.problems[0]?.error || tt('QR kod tapılmadı – yenidən çəkin'), bad: true })
      } catch (x) { setMsg({ text: (x as Error).message, bad: true }) } finally { setQueue(n => n - 1) }
    }, 'image/jpeg', 0.88)
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: '#000', zIndex: 1000, display: 'flex', flexDirection: 'column' }}>
      <div style={{ position: 'relative', flex: 1, minHeight: 0 }}>
        <video ref={video} playsInline muted style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
        <div style={{ position: 'absolute', inset: '12% 6%', border: '3px dashed rgba(255,255,255,.7)', borderRadius: 12, pointerEvents: 'none' }} />
        <div style={{ position: 'absolute', top: 8, left: 8, right: 8, color: '#fff', fontSize: 14, textShadow: '0 1px 3px #000' }}>
          {tt('Cavab kartını çərçivəyə salın – QR və dörd qara künc görünsün')}</div>
        {err && <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', padding: 24, textAlign: 'center' }}>{err}</div>}
      </div>
      <div style={{ background: '#111', color: '#fff', padding: '10px 12px calc(10px + env(safe-area-inset-bottom))', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {msg && <div style={{ fontSize: 14, color: msg.bad ? '#fca5a5' : '#86efac' }}>{msg.text}</div>}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 13 }} className="grow">{tt('Göndərildi: {n}', { n: sent })}{queue > 0 ? ` · ${tt('yüklənir: {n}', { n: queue })}` : ''}</span>
          <button className="btn" onClick={onClose}>{tt('Bitir')}</button>
          <button className="btn primary" style={{ minWidth: 96 }} onClick={shoot} disabled={!!err}>📷 {tt('Çək')}</button>
        </div>
      </div>
    </div>
  )
}
