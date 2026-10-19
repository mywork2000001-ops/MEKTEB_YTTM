// KSQ/BSQ telefon skan rejimi (docs/ksq-bsq-kagiz-promtu.md mərhələ 5): kamera açıq qalır, kartlar bir-bir çəkilir;
// bulanıq / qaranlıq / çox işıqlı şəkil göndərilmir («yenidən çək»).
// Brauzer QR tanıyırsa (BarcodeDetector), kart kadra düzgün girəndə özü çəkir.
// 13.10.2026 (docs/ksq-skan-tam-kart-promtu.md): bir blank – bir dəfə (qəbul edilmiş kart təkrar göndərilmir, yalnız
// «Yenidən skan et» ilə); kart kadra tam düşməyibsə – «yenidən çək».
// 13.10.2026 (docs/kart-skanlarini-silme-promtu.md): BİR ŞAGİRD – BİR NƏTİCƏ. Kart oxunub balı göstərilməyincə növbəti kart
// çəkilmir (avtomatik çəkiliş də dayanır); bal ekranda böyük görünür, müəllim «Növbəti şagird» basır. Oxunuş gecikərsə –
// «Keç (sonra oxunsun)»; bütün açarlar limitdədirsə – səbəb müəllimin dilində.
// 13.10.2026 (docs/skan-sayac-ve-donma-promtu.md): sayğac – fərqli şagird (əvəzetmə ayrıca); açıq «Bu kartı yenidən çək» –
// force (serverin 90 s qoruması olmadan); gözləmə 10 dəq + «↻ Yoxla»; köhnə versiya xəbərdarlığı.
import { useEffect, useRef, useState } from 'react'
import { api } from './api'
import { tt } from './i18n'
import { newVersion } from './version'

type Quality = { ok: boolean; why?: string }
type Found = { student_id: number; scan_id: number; full_name: string | null; list?: string; exam?: string }
type Res = { scan_id: number; name: string; exam?: string; points: number | null; right?: number; total?: number; check?: number; lost?: number; wait: boolean; queue?: number; late?: boolean; err?: string | null }
type Up = { found: Found[]; problems: { error: string; kind?: string; full_name?: string | null }[];
  already: { student_id: number; scan_id: number; points: number | null; full_name: string | null }[]; unmatched?: number }
type List = { scans: { id: number; status: string; points: number | null; marks: number[] | null; flagged: number[]; error: string | null; lost?: number[] }[]
  claude: boolean; ai_error?: string | null; counts: { pending: number; variants: number; scanned: number } }
// cari şagird: yüklənir → oxunur → nəticə (növbəti şagird yalnız bundan sonra)
type Cur = { phase: 'upload' } | { phase: 'read'; ids: number[]; since: number } | { phase: 'done'; ids: number[] }
const buzz = (p: number | number[]) => { try { navigator.vibrate?.(p) } catch { /* noop */ } }
const SKIP_AFTER = 30                                       // saniyə – bundan sonra «Keç (sonra oxunsun)» görünür

/** Süni intellekt xətasının kodu (ai:credit …) – müəllimin dilində bir dəfə (docs/ksq-skan-ekran-ve-onlayn-promtu.md). */
export const aiErrorText = (code: string) => ({
  'ai:credit': tt('OpenRouter balansı bitib – openrouter.ai-də kredit əlavə edin və ya açarın limitini artırın. Kartlar gözləyir, balans artanda özü oxunacaq.'),
  'ai:key': tt('Süni intellekt açarı qəbul olunmur – Tənzimləmələr → «Süni intellekt» bölməsində açarı yoxlayın.'),
  'ai:rate': tt('Bütün kart açarları limitdədir – limit bərpa olunanda kartlar özü oxunacaq. Daha çox açar əlavə edə bilərsiniz (5-ə qədər).'),
  'ai:limit': tt('Aylıq süni intellekt limiti dolub – kartlar gözləyir (admin limiti artıra bilər).'),
  'ai:busy': tt('Google serverləri hazırda məşğuldur (503) – oxunuş bir dəqiqədən sonra özü davam edəcək.'),
  'ai:model': tt('Süni intellekt modeli bu açar üçün əlçatan deyil – Tənzimləmələr → «Kart oxuyucusu»nda modeli «gemini-flash-latest» seçin.'),
} as Record<string, string>)[code] || code

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

/** `any` – ümumi «📷 Skan» (POST /api/scans/any): imtahanı QR özü göstərir, hər kartın nəticə siyahısı cavabdakı `list` ünvanındadır;
 *  QR oxunmayanda `onNoQr(şəkil)` – əl ilə şagird/imtahan seçimi. */
export default function ScanCamera({ url, onClose, onSent, replaceAll = false, any = false, onNoQr }:
  { url: string; onClose: () => void; onSent: () => void; replaceAll?: boolean; any?: boolean; onNoQr?: (b: Blob) => void }) {
  const video = useRef<HTMLVideoElement>(null)
  const [msg, setMsg] = useState<{ text: string; bad?: boolean } | null>(null)
  const got = useRef(new Set<number>())               // bu sessiyada qəbul edilmiş şagirdlər (sayğac – fərqli şagird)
  const [sent, setSent] = useState(0)
  const [replaced, setReplaced] = useState(0)
  const [pending, setPending] = useState(0)
  const [old, setOld] = useState(false)               // telefonda köhnə versiya – yeniləmək lazımdır
  const poke = useRef<(() => void) | null>(null)       // «↻ Yoxla» – nəticəni dərhal yoxla
  const [err, setErr] = useState<string | null>(null)
  const last = useRef(0)
  const accepted = useRef(new Set<string>())        // bu sessiyada qəbul edilmiş QR-lar – avtomatik çəkiliş təkrar göndərmir
  const [replace, setReplace] = useState<{ name: string } | null>(null)
  const replaceRef = useRef(false)
  const [results, setResults] = useState<Res[]>([])
  const [cur, setCurState] = useState<Cur | null>(null)
  const curRef = useRef<Cur | null>(null)             // avtomatik çəkiliş (setTimeout dövrü) cari vəziyyəti görsün
  const setCur = (c: Cur | null) => { curRef.current = c; setCurState(c) }
  const [left, setLeft] = useState<number | null>(null)   // skan olunmamış şagird sayı
  const [aiErr, setAiErr] = useState<string | null>(null)
  const [now, setNow] = useState(Date.now())
  const listUrl = url.replace(/\/upload$/, '')
  const lists = useRef(new Map<number, string>())      // ümumi rejim: skan → imtahanın siyahı ünvanı
  useEffect(() => { if (cur?.phase !== 'read') return; const id = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(id) }, [cur])
  useEffect(() => { if (!any) api<List>(listUrl).then(d => setLeft(Math.max(0, d.counts.variants - d.counts.scanned)), () => {}); newVersion().then(setOld) }, [])   // eslint-disable-line react-hooks/exhaustive-deps

  // oxunmuş kartların balı: hər 2 saniyədən bir (10 dəqiqəyədək) siyahı yoxlanılır; hamısı hazır olanda – nəticə ekranı
  const watch = (ids: number[]) => {
    let n = 0, timer = 0
    const step = async () => {
      n++
      clearTimeout(timer)
      try {
        const urls = [...new Set(ids.map(i => lists.current.get(i) || listUrl))]
        const ds = await Promise.all(urls.map(u => api<List>(u)))
        const d: List = { scans: ds.flatMap(x => x.scans), claude: ds.some(x => x.claude), ai_error: ds.find(x => x.ai_error)?.ai_error,
          counts: { ...ds[0].counts, pending: ds.reduce((a, x) => a + x.counts.pending, 0) } }
        if (!any) setLeft(Math.max(0, d.counts.variants - d.counts.scanned))
        setAiErr(d.ai_error || null)
        setPending(d.counts.pending)
        const final = n >= 300
        let open = false
        setResults(rs => rs.map(r => {
          if (!ids.includes(r.scan_id)) return r
          const s = d.scans.find(x => x.id === r.scan_id)
          if (s?.status === 'error') return { ...r, wait: false, err: s.error || tt('xəta') }
          if (!s || s.status !== 'graded') { open = true; return { ...r, wait: d.claude && !final, late: final, queue: d.counts.pending, err: s?.error && !s.error.startsWith('ai:') ? s.error : null } }
          return { ...r, wait: false, points: s.points, right: (s.marks || []).filter(Boolean).length, total: (s.marks || []).length - (s.lost || []).length, check: s.flagged.length, lost: (s.lost || []).length }
        }))
        const c = curRef.current
        const mine = c && c.phase !== 'upload' && c.ids.join() === ids.join()
        if (!open || !d.claude) {                                   // hazırdır (və ya açar yoxdur – oxunmayacaq)
          if (mine && c!.phase === 'read') { setCur({ phase: 'done', ids }); buzz([80, 60, 80]) }
          if (mine) poke.current = null
          return
        }
        if (!final) timer = window.setTimeout(step, 2000)
      } catch { if (n < 300) timer = window.setTimeout(step, 2000) }
    }
    poke.current = () => { n = Math.min(n, 299); step() }
    timer = window.setTimeout(step, 2000)
  }

  useEffect(() => {
    let stream: MediaStream | null = null, stop = false
    navigator.mediaDevices?.getUserMedia({ video: { facingMode: 'environment', width: { ideal: 2560 }, height: { ideal: 1440 } }, audio: false })
      .then(s => { stream = s; if (video.current) { video.current.srcObject = s; video.current.play().catch(() => {}) } })
      .catch(() => setErr(tt('Kamera açılmadı – brauzerə kamera icazəsi verin və ya «Şəkil / PDF seç» istifadə edin')))
    // QR görünəndə özü çəkir (yalnız BarcodeDetector olan brauzerlərdə; 3 saniyədə bir dəfədən çox yox; cari şagird bitməyibsə – yox)
    const BD = (window as any).BarcodeDetector
    const det = BD ? new BD({ formats: ['qr_code'] }) : null
    const tick = async () => {
      if (stop) return
      if (det && !curRef.current && video.current?.readyState === 4 && Date.now() - last.current > 3000) {
        try {
          const r = await det.detect(video.current)
          const mine = r.filter((x: any) => String(x.rawValue).startsWith('MK1|'))
          if (mine.length && (replaceRef.current || mine.some((x: any) => !accepted.current.has(String(x.rawValue))))) shoot(mine.map((x: any) => String(x.rawValue)))
          else if (mine.length) setMsg({ text: tt('Bu kart artıq qəbul edilib – növbəti karta keçin') })
        } catch { /* noop */ }
      }
      setTimeout(tick, 500)
    }
    tick()
    return () => { stop = true; stream?.getTracks().forEach(t => t.stop()) }
  }, [])

  const shoot = (seen: string[] = []) => {
    const v = video.current
    if (!v || !v.videoWidth || curRef.current) return          // bir şagird bitməmiş digəri çəkilmir
    last.current = Date.now()
    const c = document.createElement('canvas'); c.width = v.videoWidth; c.height = v.videoHeight
    c.getContext('2d')!.drawImage(v, 0, 0)
    const q = quality(c)
    if (!q.ok) { setMsg({ text: q.why!, bad: true }); buzz([60, 80, 60]); return }
    setMsg(null)
    setCur({ phase: 'upload' })
    c.toBlob(async b => {
      if (!b) { setCur(null); return }
      const form = new FormData(); form.append('files', b, `kart-${Date.now()}.jpg`)
      const explicit = replaceRef.current                  // «Bu kartı yenidən çək» / «Yenidən skan et» – açıq əvəz (force)
      const q = explicit ? '?replace=true&force=true' : replaceAll ? '?replace=true' : ''
      try {
        const r = await api<Up>(url + q, { method: 'POST', form })
        r.found.forEach(f => { if (f.list) lists.current.set(f.scan_id, f.list) })
        if (any && onNoQr && !r.found.length && !r.already?.length && r.unmatched) { setCur(null); onNoQr(b); return }   // QR yoxdur – əl ilə seçim
        const already = r.already || []
        if (r.found.length) {
          seen.forEach(x => accepted.current.add(x))
          replaceRef.current = false; setReplace(null)
          r.found.forEach(f => { if (got.current.has(f.student_id)) setReplaced(n => n + 1); else got.current.add(f.student_id) })
          setSent(got.current.size); buzz(60)
          const ids = r.found.map(f => f.scan_id)
          setResults(rs => [...r.found.map(f => ({ scan_id: f.scan_id, name: f.full_name || '—', exam: f.exam, points: null, wait: true })),
            ...rs.filter(x => !ids.includes(x.scan_id))].slice(0, 6))
          setCur({ phase: 'read', ids, since: Date.now() })
          watch(ids); onSent()
        } else if (already.length) {
          setCur(null)
          seen.forEach(x => accepted.current.add(x))
          const a = already[0]
          setMsg({ text: tt('{name} artıq skan olunub', { name: a.full_name || '—' }) + (a.points != null ? ` (${tt('{n} bal', { n: a.points })})` : '') })
          setReplace({ name: a.full_name || '—' })
        } else {
          setCur(null)
          const p = r.problems[0]
          buzz([60, 80, 60])
          setMsg({ text: p?.kind === 'partial' ? (p.full_name ? p.full_name + ': ' : '') + tt('Kart kadra tam düşməyib – bütün kartı çərçivəyə salıb yenidən çəkin')
            : p?.error || tt('QR kod tapılmadı – yenidən çəkin'), bad: true })
        }
      } catch (x) { setCur(null); setMsg({ text: (x as Error).message, bad: true }); buzz([60, 80, 60]) }
    }, 'image/jpeg', 0.88)
  }

  const curRes = cur && cur.phase !== 'upload' ? results.filter(r => cur.ids.includes(r.scan_id)) : []
  const secs = cur?.phase === 'read' ? Math.round((now - cur.since) / 1000) : 0
  const next = () => { setCur(null); setMsg(null); last.current = Date.now() }   // növbəti şagird – avtomatik çəkiliş 3 s sonra
  const big = (r: Res) => r.points != null
    ? <div key={r.scan_id} style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 18, fontWeight: 600 }}>{r.name}{r.exam ? ' · ' + r.exam : ''}</div>
        <div style={{ fontSize: 44, fontWeight: 800, color: '#86efac', lineHeight: 1.1 }}>{tt('{n} bal', { n: r.points })}</div>
        <div style={{ fontSize: 14 }}>{tt('Düz: {r}/{t}', { r: r.right ?? 0, t: r.total ?? 0 })}</div>
        {!!r.lost && <div style={{ fontSize: 14, color: '#cbd5e1' }}>⊘ {tt('{n} sual vərəqə düşməyib – sayılmır, bal qalanlar üzrə 100-ə', { n: r.lost })}</div>}
        {!!r.check && <div style={{ fontSize: 14, color: '#fde68a' }}>⚠ {tt('Sarı xana: {n} – siyahıda şəkilə baxıb yoxlayın', { n: r.check })}</div>}
      </div>
    : <div key={r.scan_id} style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 18, fontWeight: 600 }}>{r.name}{r.exam ? ' · ' + r.exam : ''}</div>
        <div style={{ fontSize: 15, color: r.err ? '#fca5a5' : '#fde68a' }}>{r.err || (r.late ? tt('bal hələ hazır deyil – oxunuş növbədədir, nəticə siyahıda görünəcək') : tt('Kart qəbul edildi, amma oxunmadı – nəticə siyahıda görünəcək'))}</div>
      </div>

  return (
    <div style={{ position: 'fixed', inset: 0, background: '#000', zIndex: 1000, display: 'flex', flexDirection: 'column' }}>
      <div style={{ position: 'relative', flex: 1, minHeight: 0 }}>
        <video ref={video} playsInline muted style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
        <div style={{ position: 'absolute', inset: '12% 6%', border: '3px dashed rgba(255,255,255,.7)', borderRadius: 12, pointerEvents: 'none' }} />
        <div style={{ position: 'absolute', top: 8, left: 8, right: 8, color: '#fff', fontSize: 14, textShadow: '0 1px 3px #000' }}>
          {tt('Cavab kartını çərçivəyə salın – QR və dörd qara künc görünsün')}</div>
        {err && <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', padding: 24, textAlign: 'center' }}>{err}</div>}
        {cur && <div role="status" aria-live="polite" style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,.82)', color: '#fff', display: 'flex',
          flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 14, padding: 24 }}>
          {cur.phase === 'upload' && <div style={{ fontSize: 18 }}>⏳ {tt('Göndərilir…')}</div>}
          {cur.phase === 'read' && <>
            <div style={{ fontSize: 18, fontWeight: 600, textAlign: 'center' }}>{curRes.map(r => r.name).join(', ')}</div>
            <div style={{ fontSize: 16 }}>⏳ {tt('Kart oxunur… {s} san.', { s: secs })}</div>
            <div style={{ fontSize: 13, opacity: .8, textAlign: 'center' }}>{tt('Nəticə gələnə qədər növbəti kartı çəkməyin')}</div>
            {aiErr && <div style={{ fontSize: 14, color: '#fde68a', textAlign: 'center', maxWidth: 520 }}>⚠ {aiErrorText(aiErr)}</div>}
            {!aiErr && secs >= 60 && <div style={{ fontSize: 14, color: '#fde68a', textAlign: 'center' }}>{tt('Oxunuş uzun çəkir – növbədə {n} kart', { n: pending })}</div>}
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center' }}>
              <button className="btn" onClick={() => poke.current?.()}>↻ {tt('Yoxla')}</button>
              {(secs >= SKIP_AFTER || aiErr) && <button className="btn" onClick={next}>{tt('Keç – sonra oxunsun')} ▶</button>}
            </div>
          </>}
          {cur.phase === 'done' && <>
            {curRes.map(big)}
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center' }}>
              <button className="btn" onClick={() => { replaceRef.current = true; setReplace({ name: curRes.map(r => r.name).join(', ') }); next() }}>↻ {tt('Bu kartı yenidən çək')}</button>
              <button className="btn primary" style={{ minWidth: 160, fontSize: 16 }} autoFocus onClick={next}>{tt('Növbəti şagird')} ▶</button>
            </div>
          </>}
        </div>}
      </div>
      <div style={{ background: '#111', color: '#fff', padding: '10px 12px calc(10px + env(safe-area-inset-bottom))', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {old && <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14, color: '#fde68a' }}>
          <span className="grow">⚠ {tt('Telefonda köhnə versiya açıqdır – səhifəni yeniləyin')}</span>
          <button className="btn sm" onClick={() => location.reload()}>↻ {tt('Yenilə')}</button></div>}
        {msg && <div style={{ fontSize: 14, color: msg.bad ? '#fca5a5' : '#86efac' }}>{msg.text}</div>}
        {replace && <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
          <span className="grow">{replaceRef.current ? tt('Növbəti çəkiliş {name} üçün köhnə skanı əvəz edəcək', { name: replace.name }) : tt('Səhv oxunubsa, yenidən skan edin')}</span>
          {!replaceRef.current && <button className="btn sm" onClick={() => { replaceRef.current = true; setReplace({ ...replace }) }}>{tt('Yenidən skan et')}</button>}
        </div>}
        {results.length > 0 && <div style={{ fontSize: 13, display: 'grid', gap: 2 }}>
          {results.map(r => <div key={r.scan_id}>
            <b>{r.name}</b>{r.exam ? ' · ' + r.exam : ''} — {r.points != null ? <>{tt('{n} bal', { n: r.points })} ({r.right}/{r.total}){r.check ? ` · ${tt('yoxlayın: {n}', { n: r.check })}` : ''}</>
              : r.err ? <span style={{ color: '#fca5a5' }}>{r.err}</span>
              : r.late ? tt('bal hələ hazır deyil – oxunuş növbədədir, nəticə siyahıda görünəcək')
              : r.wait ? tt('bal hesablanır…') + (r.queue && r.queue > 1 ? ' ' + tt('(növbədə {n} kart)', { n: r.queue }) : '')
              : tt('bal: süni intellekt açarı yoxdur – siyahıdan yoxlayın')}
          </div>)}
        </div>}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 13 }} className="grow">{tt('Qəbul edildi: {n} şagird', { n: sent })}{replaced ? ` · ${tt('əvəz edildi: {n}', { n: replaced })}` : ''}{left != null ? ` · ${tt('qalıb: {n} şagird', { n: left })}` : ''}</span>
          <button className="btn" onClick={onClose}>{tt('Bitir')}</button>
          <button className="btn primary" style={{ minWidth: 96 }} onClick={() => shoot()} disabled={!!err || !!cur}>📷 {tt('Çək')}</button>
        </div>
      </div>
    </div>
  )
}
