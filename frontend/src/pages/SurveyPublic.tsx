// Açıq sorğu linki (/s/{token}) – girişsiz, tətbiqin menyusu olmadan; WhatsApp və QR ilə paylaşılır.
import { useEffect, useState } from 'react'
import { ApiError, get, post } from '../api'
import { SurveyForm, type SvPublic } from './SurveyForm'

export default function SurveyPublic({ token }: { token: string }) {
  const [sv, setSv] = useState<SvPublic | null>(null)
  const [err, setErr] = useState('')
  useEffect(() => {
    document.title = 'Şagird sorğusu'
    // qısa link: hər şagird öz variantını alır; səhifə yenilənəndə eyni suallar qalsın (qaralama itməsin)
    const vk = `mk-sv-var-${token}`
    let v: string | null = null
    try { v = localStorage.getItem(vk) } catch { /* noop */ }
    get<SvPublic>(`/api/public/surveys/${token}`, { v }).then(x => {
      if (x.variant != null) { try { localStorage.setItem(vk, String(x.variant)) } catch { /* noop */ } }
      setSv(x)
    }, e => setErr(e instanceof ApiError ? e.message : 'Sorğu yüklənmədi'))
  }, [token])
  return (
    <div className="sv-wrap">
      <div className="row" style={{ gap: 8, margin: '4px 0 12px' }}>
        <span className="logo" style={{ width: 32, height: 32, fontSize: 15 }}>M</span><b>Müəllim köməkçisi</b><span className="muted small">· şagird sorğusu</span>
      </div>
      {sv ? <SurveyForm sv={sv} onSubmit={(answers, device) => post(`/api/public/surveys/${token}/responses`, { answers, device, variant: sv.variant ?? null })} />
        : <div className="sv-card"><p className={err ? 'err' : 'muted'} role={err ? 'alert' : undefined}>{err || 'Yüklənir…'}</p></div>}
    </div>
  )
}
