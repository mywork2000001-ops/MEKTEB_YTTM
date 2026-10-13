// Köhnə versiya xəbərdarlığı (docs/skan-sayac-ve-donma-promtu.md §F): tətbiq açıq qalanda deploy olunmuş yeni versiya
// görünmür (SPA) – 13.10.2026 müəllimin telefonunda köhnə kamera işləyirdi. «/» yüklənir, assets/index-*.js cari ilə
// müqayisə olunur; fərqlidirsə – «Yeni versiya hazırdır – Yenilə».
import { useEffect, useState } from 'react'
import { tt } from './i18n'

const RE = /\/assets\/index-[\w-]+\.js/
const mine = () => (document.querySelector('script[type="module"][src*="/assets/index-"]') as HTMLScriptElement | null)?.getAttribute('src')?.match(RE)?.[0] || null

/** Serverdə daha yeni versiya varmı? (dev rejimində və ya xətada – false) */
export async function newVersion(): Promise<boolean> {
  const cur = mine()
  if (!cur) return false
  try {
    const html = await fetch('/', { cache: 'no-store', credentials: 'same-origin' }).then(r => (r.ok ? r.text() : ''))
    const live = html.match(RE)?.[0]
    return !!live && live !== cur
  } catch { return false }
}

export function UpdateBanner() {
  const [fresh, setFresh] = useState(false)
  useEffect(() => {
    let stop = false
    const check = () => { newVersion().then(v => { if (!stop && v) setFresh(true) }) }
    const vis = () => { if (document.visibilityState === 'visible') check() }
    check()
    const id = setInterval(check, 5 * 60 * 1000)
    document.addEventListener('visibilitychange', vis)
    return () => { stop = true; clearInterval(id); document.removeEventListener('visibilitychange', vis) }
  }, [])
  if (!fresh) return null
  return (
    <div role="status" style={{ position: 'fixed', left: 12, right: 12, bottom: 12, zIndex: 2000, display: 'flex', gap: 10, alignItems: 'center',
      justifyContent: 'space-between', background: 'var(--acc, #2563eb)', color: '#fff', padding: '10px 14px', borderRadius: 10, boxShadow: '0 4px 16px rgba(0,0,0,.25)' }}>
      <span>{tt('Yeni versiya hazırdır – yeniləyin')}</span>
      <button className="btn sm" onClick={() => location.reload()}>↻ {tt('Yenilə')}</button>
    </div>
  )
}
