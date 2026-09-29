import { useEffect, useState, type ReactNode } from 'react'
import { flushOutbox, get, outbox } from './api'
import { toast } from './ui'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from './auth'
import { useT } from './i18n'
import { Drawer, Icon } from './ui'

export type NavItem = { to: string; icon: string; label: string; short?: string }

export const TEACHER_NAV: NavItem[] = [
  { to: '/', icon: 'home', label: 'Əsas səhifə', short: 'Əsas' },
  { to: '/classes', icon: 'classes', label: 'Siniflər və qruplar', short: 'Siniflər' },
  { to: '/journal', icon: 'journal', label: 'Jurnal' },
  { to: '/plan', icon: 'plan', label: 'Perspektiv plan', short: 'Plan' },
  { to: '/timetable', icon: 'topics', label: 'Həftəlik cədvəl', short: 'Cədvəl' },
  { to: '/tasks', icon: 'online', label: 'Onlayn tapşırıqlar', short: 'Tapşırıq' },
  { to: '/materials', icon: 'clip', label: 'Materiallar' },
  { to: '/reports', icon: 'reports', label: 'Analitika və hesabat', short: 'Hesabat' },
  { to: '/homeroom', icon: 'classes', label: 'Sinif rəhbəri', short: 'Rəhbər' },
  { to: '/chat', icon: 'feedback', label: 'Çat' },
  { to: '/settings', icon: 'settings', label: 'Tənzimləmələr', short: 'Tənzimləmə' },
]
const TEACHER_TABS = ['/', '/journal', '/chat', '/reports']

export const STUDENT_NAV: NavItem[] = [
  { to: '/', icon: 'today', label: 'Bu gün' },
  { to: '/lesson', icon: 'journal', label: 'Dərs' },
  { to: '/tasks', icon: 'online', label: 'Tapşırıqlar' },
  { to: '/materials', icon: 'clip', label: 'Materiallar' },
  { to: '/plan', icon: 'plan', label: 'Plan' },
  { to: '/results', icon: 'rating', label: 'Nəticələrim', short: 'Nəticə' },
  { to: '/analytics', icon: 'reports', label: 'Analitika' },
  { to: '/chat', icon: 'feedback', label: 'Çat' },
  { to: '/settings', icon: 'settings', label: 'Tənzimləmələr', short: 'Tənzimləmə' },
]
const STUDENT_TABS = ['/', '/lesson', '/tasks', '/results']

export function Layout({ children }: { children: ReactNode }) {
  const { me, logout } = useAuth()
  const t = useT()
  const nav = useNavigate()
  const loc = useLocation()
  const [more, setMore] = useState(false)
  const [online, setOnline] = useState(navigator.onLine)
  const [pending, setPending] = useState(outbox().length)
  useEffect(() => {
    const sync = async () => { const r = await flushOutbox(); if (r.sent) toast(`${r.sent} oflayn yazı göndərildi`); if (r.failed) toast(`${r.failed} yazı göndərilmədi (məlumat səhvdir)`) }
    const on = () => { setOnline(true); sync() }
    const off = () => setOnline(false)
    const upd = () => setPending(outbox().length)
    window.addEventListener('online', on); window.addEventListener('offline', off); window.addEventListener('mk-outbox', upd)
    sync()
    return () => { window.removeEventListener('online', on); window.removeEventListener('offline', off); window.removeEventListener('mk-outbox', upd) }
  }, [])
  const student = me?.role === 'student'
  // «Sinif rəhbəri» yalnız rəhbəri olduğu sinif varsa
  const [homeroom, setHomeroom] = useState(me?.role === 'admin')   // admin: «Bütün siniflər» baxışı üçün
  useEffect(() => {
    if (!me || me.role !== 'teacher') return
    get<any[]>('/api/homeroom').then(r => setHomeroom(r.length > 0)).catch(() => {})
  }, [me?.id, loc.pathname === '/settings'])
  const items = student ? STUDENT_NAV : TEACHER_NAV.filter(i => i.to !== '/homeroom' || homeroom)
  const tabs = student ? STUDENT_TABS : TEACHER_TABS
  const initials = (me?.full_name || '?').split(' ').slice(0, 2).map(w => w[0]).join('')
  const shortName = (me?.full_name || '').split(' ').slice(0, 2).join(' ')
  const active = (to: string) => (to === '/' ? loc.pathname === '/' : loc.pathname.startsWith(to))

  return (
    <>
      <div className="app">
        <aside className="side">
          <div className="brand"><span className="logo">M</span><div><b>Müəllim köməkçisi</b><span>{shortName} · 2026–2027</span></div></div>
          <nav className="nav" aria-label="Bölmələr">
            {items.map(i => (
              <NavLink key={i.to} to={i.to} end={i.to === "/"} className="navlink">
                {({ isActive }) => <button tabIndex={-1} aria-current={isActive ? 'page' : undefined}><Icon name={i.icon} />{t(i.label)}</button>}
              </NavLink>
            ))}
          </nav>
          <div className="side-foot">
            <p className="quote">«Hər şagirdin öz addımı var. Əsas odur ki, irəliləsin.»</p><br />
            <button className="btn ghost sm" style={{ color: 'var(--side-muted)' }} onClick={logout}>{t('Çıxış')}</button>
          </div>
        </aside>
        <main>
          <div className="topbar">
            <span className="tb-brand"><span className="logo" style={{ width: 30, height: 30, fontSize: 14 }}>M</span><b>Müəllim köməkçisi</b></span>
            <button className="tb-user" style={{ marginLeft: 'auto' }} onClick={() => nav('/settings')} aria-label={t('Tənzimləmələr')}>
              <span className="uav">{initials}</span>
              <span className="tb-uname"><b>{shortName}</b><small>{student ? t('Şagird') : me?.role === 'admin' ? 'Admin' : 'Müəllim'}</small></span>
            </button>
          </div>
          {(!online || pending > 0) && (
            <div className="banner" role="status" style={{ background: online ? 'var(--info-soft)' : 'var(--warn-soft)', color: online ? 'var(--info)' : 'var(--warn)' }}>
              {online ? '' : 'Oflayn rejim – son yüklənən məlumatlar göstərilir. '}{pending > 0 ? `${pending} jurnal yazısı göndərilməyi gözləyir${online ? ' – göndərilir…' : ' (internet qayıdanda avtomatik göndəriləcək)'}.` : ''}
            </div>)}
          {!student && (() => { try { return sessionStorage.getItem('mk-weak') === '1' } catch { return false } })() && (
            <div className="banner" style={{ background: 'var(--warn-soft)', color: 'var(--warn)' }}>Parolunuz zəifdir (8 simvoldan qısa). Tənzimləmələr → Hesab bölməsində daha uzun parol qoyun.</div>)}
          {children}
        </main>
      </div>
      <nav className="tabbar" aria-label="Əsas bölmələr">
        {tabs.map(to => { const i = items.find(x => x.to === to)!; return (
          <button key={to} aria-current={active(to) ? 'page' : undefined} onClick={() => nav(to)}><Icon name={i.icon} />{t(i.short || i.label)}</button>) })}
        <button aria-current={!tabs.some(active) ? 'page' : undefined} onClick={() => setMore(true)}><Icon name="more" />{t('Daha çox')}</button>
      </nav>
      {more && (
        <Drawer title={t('Daha çox')} onClose={() => setMore(false)}>
          <div className="nav" style={{ gap: 6 }}>
            {items.filter(i => !tabs.includes(i.to)).map(i => (
              <button key={i.to} className="btn" style={{ justifyContent: 'flex-start' }} onClick={() => { setMore(false); nav(i.to) }}><Icon name={i.icon} />{t(i.label)}</button>
            ))}
            <button className="btn danger" onClick={logout}>{t('Çıxış')}</button>
          </div>
        </Drawer>
      )}
    </>
  )
}
