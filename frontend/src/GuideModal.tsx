// Şagirdin giriş videosu: girişdən sonra bir dəfə pəncərə (test icra ekranı istisna), «görüldü» serverdə (users.guide_seen_version).
// «Sonra bax» yalnız bu sessiyanı gizlədir (sessionStorage); 3 dəfədən sonra avtomatik pəncərə çıxmır – «🎬 Necə istifadə etməli» düyməsi qalır.
import { useContext, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { post } from './api'
import { useAuth } from './auth'
import { I18nCtx, LANGS, useT } from './i18n'
import { guideSubLangs, guideVideoSrc } from './guideData'
import { Drawer } from './ui'

const OPEN_EVT = 'mk-guide-open'
const LATER_KEY = 'mk-guide-later'          // sessionStorage: bu sessiyada «Sonra bax»
const LATER_N_KEY = 'mk-guide-later-n'      // localStorage: neçə dəfə «Sonra bax» basılıb
const MAX_LATER = 3

const ss = { get: (k: string) => { try { return sessionStorage.getItem(k) } catch { return null } },
  set: (k: string, v: string) => { try { sessionStorage.setItem(k, v) } catch { /* yaddaş əlçatmazdır */ } } }
const ls = { get: (k: string) => { try { return localStorage.getItem(k) } catch { return null } },
  set: (k: string, v: string) => { try { localStorage.setItem(k, v) } catch { /* yaddaş əlçatmazdır */ } } }

/** Video: telefon – 08-telefon, kompüter – 02-ana-sehife (yol və alt yazı dili – guideData). */
function videoId(): string {
  const narrow = typeof window !== 'undefined' && window.matchMedia('(max-width: 599px)').matches
  return narrow ? '08-telefon' : '02-ana-sehife'
}

function GuideDialog({ due, onClose }: { due: boolean; onClose: () => void }) {
  const t = useT()
  const lang = useContext(I18nCtx)
  const { refresh } = useAuth()
  const nav = useNavigate()
  const ref = useRef<HTMLVideoElement>(null)
  const [vid] = useState(videoId)
  const base = `/guide/student/${vid}`
  const [playing, setPlaying] = useState(false)
  const [noVideo, setNoVideo] = useState(false)
  const markSeen = async () => {
    if (!due) return
    try { await post('/api/portal/guide-seen'); await refresh() } catch { /* növbəti girişdə yenə çıxar */ }
  }
  const close = () => { void markSeen(); onClose() }
  const later = () => {
    ss.set(LATER_KEY, '1')
    ls.set(LATER_N_KEY, String((Number(ls.get(LATER_N_KEY)) || 0) + 1))
    onClose()
  }
  const all = async () => { await markSeen(); onClose(); nav('/guide') }
  const play = () => { setPlaying(true); ref.current?.play().catch(() => { /* istifadəçi özü başladar */ }) }
  return (
    <Drawer title={t('Tətbiqdən necə istifadə etməli')} onClose={close}
      footer={<div className="row" style={{ flexWrap: 'wrap', gap: 8 }}>
        <button type="button" className="btn primary" onClick={close}>{t('Bağla')}</button>
        <button type="button" className="btn" onClick={all}>{t('Bütün videolar')}</button>
        {due && <button type="button" className="btn ghost" onClick={later}>{t('Sonra bax')}</button>}
      </div>}>
      <p className="muted">{t('Bu qısa videoya bax – hər şey aydın olacaq.')}</p>
      {noVideo ? <p className="muted">{t('Video açılmadı.')}</p> : (
        <div style={{ position: 'relative' }}>
          <video ref={ref} controls={playing} preload="metadata" playsInline src={guideVideoSrc('student', vid, lang)}
            style={{ width: '100%', maxHeight: '60vh', background: '#000', borderRadius: 8 }}
            onError={() => setNoVideo(true)} onPlay={() => setPlaying(true)} onEnded={() => { void markSeen() }}>
            {LANGS.filter(([k]) => guideSubLangs(lang).includes(k)).map(([k, n]) => <track key={k} kind="subtitles" src={`${base}.${k}.vtt`} srcLang={k} label={n} default={k === lang && lang !== 'az'} />)}
          </video>
          {!playing && (
            <button type="button" aria-label={t('Videonu oynat')} onClick={play}
              style={{ position: 'absolute', inset: 0, margin: 'auto', width: 72, height: 72, borderRadius: '50%', border: 0,
                background: 'rgba(0,0,0,.65)', color: '#fff', fontSize: 32, cursor: 'pointer' }}>▶</button>)}
        </div>)}
    </Drawer>)
}

/** Şagird üçün: avtomatik pəncərə (guide_due) + «🎬 Necə istifadə etməli» düyməsi eyni pəncərəni açır. */
export function GuideGate() {
  const { me } = useAuth()
  const { pathname } = useLocation()
  const [open, setOpen] = useState<null | 'auto' | 'manual'>(null)
  const [solving, setSolving] = useState(false)
  const [shown, setShown] = useState(false)       // bu yüklənmədə avtomatik pəncərə bir dəfə
  const student = me?.role === 'student'
  const due = !!me?.guide_due
  useEffect(() => {
    const h = () => setOpen('manual')
    window.addEventListener(OPEN_EVT, h)
    return () => window.removeEventListener(OPEN_EVT, h)
  }, [])
  useEffect(() => {          // test icra ekranında (Tasks → Solver) pəncərə göstərilmir
    const id = window.setInterval(() => setSolving(!!document.body.dataset.solving), 800)
    return () => window.clearInterval(id)
  }, [])
  useEffect(() => {
    if (student && due && !open && !shown && !pathname.startsWith('/t/') && !ss.get(LATER_KEY) && (Number(ls.get(LATER_N_KEY)) || 0) < MAX_LATER
      && !document.body.dataset.solving) setOpen('auto')
    if (open) setShown(true)
  }, [student, due, open, shown, pathname])
  if (!student || !open || (solving && open === 'auto')) return null
  return <GuideDialog due={due} onClose={() => setOpen(null)} />
}

export function GuideButton() {
  const t = useT()
  return <button type="button" className="btn sm" style={{ marginBottom: 16 }}
    onClick={() => window.dispatchEvent(new Event(OPEN_EVT))}>{t('🎬 Necə istifadə etməli')}</button>
}
