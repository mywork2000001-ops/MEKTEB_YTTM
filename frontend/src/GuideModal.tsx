// Xoş gəldin pəncərəsi (şagird və müəllim): girişdən sonra bir dəfə ortada böyük pəncərə + tanıtım videosu (00-tanitim).
// «Gördü» serverdə (users.guide_seen_version, POST /api/auth/guide-seen): video sona çatanda və ya «Bir daha göstərmə» basanda.
// «Sonra bax» yalnız bu sessiyanı gizlədir (sessionStorage); 3 dəfədən sonra avtomatik pəncərə çıxmır – «🎬 Necə istifadə etməli» düyməsi qalır.
// Test icra ekranında (data-solving) və /t/ yolunda avtomatik pəncərə göstərilmir.
import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { useLocation, useNavigate } from 'react-router-dom'
import { post } from './api'
import { useAuth } from './auth'
import { GuidePlayer } from './GuidePlayer'
import { useT } from './i18n'

const OPEN_EVT = 'mk-guide-open'
const LATER_KEY = 'mk-guide-later'          // sessionStorage: bu sessiyada «Sonra bax»
const LATER_N_KEY = 'mk-guide-later-n'      // localStorage: neçə dəfə «Sonra bax» basılıb
const MAX_LATER = 3

const ss = { get: (k: string) => { try { return sessionStorage.getItem(k) } catch { return null } },
  set: (k: string, v: string) => { try { sessionStorage.setItem(k, v) } catch { /* yaddaş əlçatmazdır */ } } }
const ls = { get: (k: string) => { try { return localStorage.getItem(k) } catch { return null } },
  set: (k: string, v: string) => { try { localStorage.setItem(k, v) } catch { /* yaddaş əlçatmazdır */ } } }

function GuideDialog({ due, role, onClose }: { due: boolean; role: 'student' | 'teacher'; onClose: () => void }) {
  const t = useT()
  const { refresh } = useAuth()
  const nav = useNavigate()
  const markSeen = async () => {
    if (!due) return
    try { await post('/api/auth/guide-seen'); await refresh() } catch { /* növbəti girişdə yenə çıxar */ }
  }
  const later = () => {
    if (due) {
      ss.set(LATER_KEY, '1')
      ls.set(LATER_N_KEY, String((Number(ls.get(LATER_N_KEY)) || 0) + 1))
    }
    onClose()
  }
  const never = () => { void markSeen(); onClose() }
  const all = async () => { await markSeen(); onClose(); nav('/guide') }
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') later() }
    document.addEventListener('keydown', k)
    document.body.style.overflow = 'hidden'
    return () => { document.removeEventListener('keydown', k); document.body.style.overflow = '' }
  })
  const teacher = role === 'teacher'
  return createPortal(
    <div className="gw-scrim" onMouseDown={e => { if (e.target === e.currentTarget) later() }}>
      <section className="gw" role="dialog" aria-modal="true" aria-label={t('Tətbiqdən necə istifadə etməli')}>
        <header className="gw-head">
          <div>
            <h2>{teacher ? t('Xoş gəlmisiniz!') : t('Xoş gəldin!')}</h2>
            <p>{teacher ? t('Qısa tanıtım videosu – planlaşdırma, testlər və jurnal bir yerdə.') : t('Qısa tanıtım videosu – bir dəqiqəyə hər şey aydın olacaq.')}</p>
          </div>
          <button type="button" className="gw-x" onClick={later} aria-label={t('Sonra bax')}>✕</button>
        </header>
        <div className="gw-body">
          <GuidePlayer role={role} id="00-tanitim" onEnded={() => { void markSeen() }} />
        </div>
        <footer className="gw-foot">
          <button type="button" className="btn" onClick={later}>{t('Sonra bax')}</button>
          {due && <button type="button" className="btn ghost" onClick={never}>{t('Bir daha göstərmə')}</button>}
          <button type="button" className="btn primary" onClick={all}>{t('Bütün videolar')}</button>
        </footer>
      </section>
    </div>, document.body)
}

/** Şagird və müəllim üçün: avtomatik pəncərə (guide_due) + «🎬 Necə istifadə etməli» düyməsi eyni pəncərəni açır. */
export function GuideGate() {
  const { me } = useAuth()
  const { pathname } = useLocation()
  const [open, setOpen] = useState<null | 'auto' | 'manual'>(null)
  const [solving, setSolving] = useState(false)
  const [shown, setShown] = useState(false)       // bu yüklənmədə avtomatik pəncərə bir dəfə
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
    if (me && due && !open && !shown && !pathname.startsWith('/t/') && !ss.get(LATER_KEY) && (Number(ls.get(LATER_N_KEY)) || 0) < MAX_LATER
      && !document.body.dataset.solving) setOpen('auto')
    if (open) setShown(true)
  }, [me, due, open, shown, pathname])
  if (!me || !open || (solving && open === 'auto')) return null
  return <GuideDialog due={due} role={me.role === 'student' ? 'student' : 'teacher'} onClose={() => setOpen(null)} />
}

export function GuideButton() {
  const t = useT()
  return <button type="button" className="btn sm" style={{ marginBottom: 16 }}
    onClick={() => window.dispatchEvent(new Event(OPEN_EVT))}>{t('🎬 Necə istifadə etməli')}</button>
}
