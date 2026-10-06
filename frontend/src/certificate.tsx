// Sertifikat (EduCert dizaynı əsasında – hub _Shared_Core/certificate.js): A4 albom, rəng zolağı, künc bəzəkləri, ad,
// nailiyyət, faiz dairəsi, məktəb, müəllim, tarix, yoxlama kodu + QR. Eyni HTML həm tətbiqdə, həm çapda/PDF-də.
import { useEffect, useRef, useState } from 'react'
import QRCode from 'qrcode'
import { esc, printDoc } from './print'

export type Cert = {
  id: number; code: string; kind: string; title: string; issued_at: string; revoked?: boolean; new?: boolean; student: string | null
  details: { pct?: number; correct?: number; total?: number; place?: number; of?: number; subject?: string; class_name?: string
    teacher?: string; school?: string; note?: string; taken?: number }
}
const THEME: Record<string, [string, string, string]> = {
  movzu: ['#10b981', '#047857', 'Mövzu ustası'], sinaq: ['#8b5cf6', '#6d28d9', 'Sınaq imtahanı'],
  seriya: ['#3b82f6', '#1d4ed8', 'Sınaq seriyası'], manual: ['#f59e0b', '#b45309', 'Müəllimdən təşəkkür'],
}
export const verifyUrl = (code: string) => `${location.origin}/v/${code}`
const dmy = (s: string) => new Date(s).toLocaleDateString('az-AZ', { day: '2-digit', month: '2-digit', year: 'numeric' })

export async function qrData(code: string) {
  return QRCode.toDataURL(verifyUrl(code), { margin: 0, width: 220, color: { dark: '#0f172a', light: '#ffffff' } })
}

export function certHtml(c: Cert, qr: string): string {
  const [c1, c2, label] = THEME[c.kind] || THEME.manual
  const d = c.details || {}
  const what = c.title.replace(/^[^:]+:\s*/, '')
  const score = d.pct != null ? `<div style="display:flex;align-items:center;gap:22px;justify-content:center">
      <div style="width:92px;height:92px;border-radius:50%;background:linear-gradient(135deg,${c1},${c2});color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;box-shadow:0 4px 16px ${c1}55">
        <b style="font-size:26px;line-height:1">${Math.round(d.pct)}%</b><span style="font-size:9px;letter-spacing:.08em;opacity:.9">NƏTİCƏ</span></div>
      <div style="text-align:left"><div style="font-size:24px;font-weight:900;color:#0f172a">${d.correct ?? '—'} <span style="font-size:15px;color:#94a3b8;font-weight:500">/ ${d.total ?? '—'}</span></div>
        ${d.place ? `<div style="margin-top:4px;display:inline-block;padding:3px 10px;border-radius:999px;background:#fef3c7;color:#92400e;font-size:12px;font-weight:800">🏅 Sinifdə ${d.place}-ci yer${d.of ? ` (${d.of} şagird)` : ''}</div>` : ''}</div></div>`
    : d.taken ? `<div style="font-size:16px;font-weight:700;color:#334155">${d.taken} / ${d.of} sınaqda iştirak</div>`
      : d.note ? `<div style="font-size:15px;color:#334155;max-width:560px">${esc(d.note)}</div>` : ''
  return `<div style="font-family:Arial,Helvetica,sans-serif;width:100%;max-width:1060px;margin:0 auto;aspect-ratio:297/210;background:#fff;border-radius:14px;box-shadow:0 8px 40px rgba(0,0,0,.12);position:relative;overflow:hidden;color:#0f172a;box-sizing:border-box">
  <div style="height:9px;background:linear-gradient(90deg,${c1},${c2})"></div>
  ${['top:18px;left:18px;border-right:none;border-bottom:none;border-radius:10px 0 0 0', 'top:18px;right:18px;border-left:none;border-bottom:none;border-radius:0 10px 0 0',
    'bottom:18px;left:18px;border-right:none;border-top:none;border-radius:0 0 0 10px', 'bottom:18px;right:18px;border-left:none;border-top:none;border-radius:0 0 10px 0']
    .map(p => `<div style="position:absolute;width:110px;height:110px;border:3px solid ${c1}33;${p}"></div>`).join('')}
  <div style="padding:26px 54px 22px;display:flex;flex-direction:column;align-items:center;text-align:center;gap:12px;height:calc(100% - 14px);box-sizing:border-box">
    <div style="display:flex;justify-content:space-between;align-items:center;width:100%;gap:12px">
      <div style="font-size:12px;font-weight:700;color:#475569;text-align:left;max-width:60%">${esc(d.school || '')}</div>
      <div style="padding:6px 14px;border-radius:999px;background:linear-gradient(135deg,${c1},${c2});color:#fff;font-size:11px;font-weight:800;letter-spacing:.06em;text-transform:uppercase">${label}</div>
    </div>
    <div style="font-family:Georgia,'Times New Roman',serif;font-size:44px;font-weight:900;letter-spacing:.16em">SERTİFİKAT</div>
    <div style="width:64px;height:3px;border-radius:9px;background:linear-gradient(90deg,${c1},${c2});margin-top:-6px"></div>
    <div style="font-size:13px;color:#64748b">Bu sertifikat təqdim olunur</div>
    <div style="font-family:Georgia,'Times New Roman',serif;font-size:36px;font-weight:700;color:${c2};padding:2px 28px 6px;border-bottom:2px solid ${c1}44;min-width:320px">${esc(c.student || '—')}</div>
    <div><div style="font-size:11px;font-weight:800;letter-spacing:.1em;color:#94a3b8;text-transform:uppercase">${c.kind === 'manual' ? 'Təqdirəlayiq' : 'Uğurla tamamladı'}</div>
      <div style="font-size:19px;font-weight:700;color:#1e293b;max-width:640px;line-height:1.35;margin-top:4px">${esc(what)}</div>
      ${d.subject ? `<div style="font-size:12px;color:#64748b;margin-top:2px">${esc(d.subject)}${d.class_name ? ' · ' + esc(d.class_name) : ''}</div>` : ''}</div>
    ${score}
    <div style="margin-top:auto;width:100%;display:flex;align-items:flex-end;justify-content:space-between;border-top:1px solid #f1f5f9;padding-top:12px">
      <div style="text-align:center"><div style="width:170px;height:1px;background:#cbd5e1;margin-bottom:5px"></div>
        <div style="font-size:12px;font-weight:700;color:#334155">${esc(d.teacher || '')}</div><div style="font-size:10px;color:#94a3b8">Müəllim</div></div>
      <div style="display:flex;align-items:center;gap:10px"><img src="${qr}" alt="" style="width:74px;height:74px">
        <div style="text-align:left;font-size:10px;color:#64748b">Yoxlama kodu<br><b style="font-family:monospace;font-size:13px;color:#0f172a;letter-spacing:.06em">${c.code}</b><br>QR ilə yoxlayın</div></div>
      <div style="text-align:center"><div style="font-size:15px;font-weight:800">${dmy(c.issued_at)}</div><div style="font-size:10px;color:#94a3b8;letter-spacing:.07em">TARİX</div></div>
    </div>
  </div>
  ${c.revoked ? '<div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:72px;font-weight:900;color:#dc262655;transform:rotate(-18deg)">LƏĞV EDİLİB</div>' : ''}
</div>`
}

/** Tətbiqdə sertifikat: ekranın eninə sığır (A4 nisbəti), şrift kiçilir. */
export function CertView({ c }: { c: Cert }) {
  const [qr, setQr] = useState('')
  const box = useRef<HTMLDivElement>(null)
  const [k, setK] = useState(1)
  useEffect(() => { qrData(c.code).then(setQr, () => setQr('')) }, [c.code])
  useEffect(() => {
    const el = box.current
    if (!el) return
    const fit = () => setK(Math.min(1, el.clientWidth / 1060))
    fit()
    const ro = new ResizeObserver(fit)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return (
    <div ref={box} style={{ width: '100%', height: 750 * k, overflow: 'hidden' }}>
      <div style={{ width: 1060, transform: `scale(${k})`, transformOrigin: 'top left' }} dangerouslySetInnerHTML={{ __html: certHtml(c, qr) }} />
    </div>
  )
}

export async function printCert(c: Cert) {
  const qr = await qrData(c.code).catch(() => '')
  printDoc({ title: `Sertifikat – ${c.student || ''} – ${c.code}`, landscape: true,
    body: `<style>@page{size:A4 landscape;margin:8mm}body{margin:0}</style>${certHtml(c, qr).replace('box-shadow:0 8px 40px rgba(0,0,0,.12);', '')}` })
}

export function shareCert(c: Cert) {
  const text = `${c.student} – ${c.title}. Yoxlama: ${verifyUrl(c.code)}`
  if (navigator.share) navigator.share({ title: 'Sertifikat', text, url: verifyUrl(c.code) }).catch(() => {})
  else window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, '_blank', 'noopener')
}

/** Təbrik: CSS konfetti (hərəkət azaldılıbsa – göstərilmir). */
export function confetti() {
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return
  const colors = ['#10b981', '#8b5cf6', '#f59e0b', '#3b82f6', '#ef4444', '#ec4899']
  const host = document.createElement('div')
  host.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:9999;overflow:hidden'
  document.body.appendChild(host)
  for (let i = 0; i < 90; i++) {
    const p = document.createElement('i')
    const size = 6 + Math.random() * 6
    p.style.cssText = `position:absolute;top:-12px;left:${Math.random() * 100}%;width:${size}px;height:${size * 0.6}px;background:${colors[i % colors.length]};border-radius:2px`
    host.appendChild(p)
    p.animate([{ transform: 'translate(0,0) rotate(0)', opacity: 1 },
      { transform: `translate(${(Math.random() - 0.5) * 240}px, ${window.innerHeight + 40}px) rotate(${Math.random() * 720}deg)`, opacity: 0.9 }],
    { duration: 1800 + Math.random() * 1400, delay: Math.random() * 300, easing: 'cubic-bezier(.2,.6,.4,1)', fill: 'forwards' })
  }
  setTimeout(() => host.remove(), 3800)
}
