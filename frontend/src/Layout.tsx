import { lazy, Suspense, useEffect, useState, type ReactNode } from 'react'
import { flushOutbox, get, outbox, put } from './api'
import { toast } from './ui'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from './auth'
import { useT } from './i18n'
import { Drawer, Icon } from './ui'
import { SurveyNudge } from './pages/student/Surveys'
import GlobalScan from './GlobalScan'
// yeni sertifikat pəncərəsi (QR kitabxanası ilə) – yalnız şagirdə, ayrıca yüklənir
const CertNudge = lazy(() => import('./pages/student/Achievements').then(m => ({ default: m.CertNudge })))

export type NavItem = { to: string; icon: string; label: string; short?: string; group?: string }

export const TEACHER_NAV: NavItem[] = [
  { to: '/', icon: 'home', label: 'Əsas səhifə', short: 'Əsas', group: 'Dərs' },
  { to: '/journal', icon: 'journal', label: 'Jurnal', group: 'Dərs' },
  { to: '/daily', icon: 'edit', label: 'Gündəlik plan', short: 'Gündəlik', group: 'Dərs' },
  { to: '/plan', icon: 'plan', label: 'Perspektiv plan', short: 'Plan', group: 'Dərs' },
  { to: '/timetable', icon: 'topics', label: 'Həftəlik cədvəl', short: 'Cədvəl', group: 'Dərs' },
  { to: '/tests', icon: 'online', label: 'Testlər və sınaqlar', short: 'Testlər', group: 'Qiymətləndirmə' },   // mövzu testləri + sınaqlar + nəticələr
  { to: '/reports', icon: 'reports', label: 'Analitika və hesabat', short: 'Hesabat', group: 'Qiymətləndirmə' },
  { to: '/surveys', icon: 'star', label: 'Şagird sorğusu', short: 'Sorğu', group: 'Qiymətləndirmə' },
  { to: '/classes', icon: 'classes', label: 'Siniflər və qruplar', short: 'Siniflər', group: 'Siniflər' },
  { to: '/homeroom', icon: 'classes', label: 'Sinif rəhbəri', short: 'Rəhbər', group: 'Siniflər' },
  { to: '/materials', icon: 'clip', label: 'Materiallar', group: 'Siniflər' },
  { to: '/chat', icon: 'feedback', label: 'Çat', group: 'Ünsiyyət' },
  { to: '/settings', icon: 'settings', label: 'Tənzimləmələr', short: 'Tənzimləmə', group: 'Ünsiyyət' },
]
const TEACHER_TABS = ['/', '/journal', '/chat', '/reports']

export const STUDENT_NAV: NavItem[] = [
  { to: '/', icon: 'today', label: 'Bu gün' },
  { to: '/lesson', icon: 'journal', label: 'Dərs' },
  { to: '/tasks', icon: 'online', label: 'Tapşırıqlar' },
  { to: '/materials', icon: 'clip', label: 'Materiallar' },
  { to: '/extra', icon: 'groups', label: 'Əlavə məşğələlər', short: 'Məşğələ' },
  { to: '/plan', icon: 'plan', label: 'Plan' },
  { to: '/results', icon: 'rating', label: 'Nəticələrim', short: 'Nəticə' },
  { to: '/achievements', icon: 'star', label: 'Uğurlarım', short: 'Uğurlar' },
  { to: '/analytics', icon: 'reports', label: 'Analitika' },
  { to: '/surveys', icon: 'star', label: 'Sorğular' },
  { to: '/chat', icon: 'feedback', label: 'Çat' },
  { to: '/settings', icon: 'settings', label: 'Tənzimləmələr', short: 'Tənzimləmə' },
]
const STUDENT_TABS = ['/', '/lesson', '/tasks', '/results']

function readOpen(key: string): Record<string, boolean> {
  try { const v = JSON.parse(localStorage.getItem(key) || '{}'); return v && typeof v === 'object' ? v : {} } catch { return {} }
}

/** Qruplu menyu: başlıq düyməsi + açılıb-bağlanan siyahı (sidebar və telefonun «Daha çox» pəncərəsi üçün ortaq). */
function NavGroups({ items, storageKey, defaultOpen, isActive, idPrefix, renderItem }: {
  items: NavItem[]; storageKey: string; defaultOpen: (g: string) => boolean; isActive: (to: string) => boolean; idPrefix: string; renderItem: (i: NavItem) => ReactNode
}) {
  const t = useT()
  const loc = useLocation()
  const [open, setOpen] = useState<Record<string, boolean>>(() => readOpen(storageKey))
  const groups: { name: string; list: NavItem[] }[] = []
  for (const i of items) {
    const name = i.group || ''
    const last = groups[groups.length - 1]
    if (last && last.name === name) last.list.push(i); else groups.push({ name, list: [i] })
  }
  const activeGroup = groups.find(g => g.list.some(i => isActive(i.to)))?.name
  const save = (o: Record<string, boolean>) => { try { localStorage.setItem(storageKey, JSON.stringify(o)) } catch { /* yaddaş əlçatmazdır */ } }
  // aktiv səhifənin qrupu hər keçiddə açılır
  useEffect(() => {
    if (!activeGroup) return
    setOpen(o => { if (o[activeGroup] === true) return o; const n = { ...o, [activeGroup]: true }; save(n); return n })
  }, [loc.pathname, activeGroup])
  const toggle = (g: string, cur: boolean) => setOpen(o => { const n = { ...o, [g]: !cur }; save(n); return n })
  return (
    <>
      {groups.map((g, k) => {
        const isOpen = open[g.name] ?? (g.name === activeGroup || defaultOpen(g.name))
        const id = `${idPrefix}-${k}`
        const gname = t(g.name)
        return (
          <div key={g.name} className={'nav-sec' + (isOpen ? ' open' : '')}>
            <button type="button" className="nav-ghead" aria-expanded={isOpen} aria-controls={id}
              aria-label={isOpen ? t('{g} bölməsini bağla', { g: gname }) : t('{g} bölməsini aç', { g: gname })}
              onClick={() => toggle(g.name, isOpen)}>
              <span className="ng-name">{gname}</span>
              {!isOpen && g.name === activeGroup && <span className="ng-dot" aria-hidden="true" />}
              <span className="ng-cnt" aria-hidden="true">{g.list.length}</span>
              <span className="ng-arrow" aria-hidden="true">▾</span>
            </button>
            <div className="nav-body" id={id} inert={!isOpen}>
              <div className="nav-body-in">{g.list.map(renderItem)}</div>
            </div>
          </div>)
      })}
    </>
  )
}

export function Layout({ children }: { children: ReactNode }) {
  const { me, logout } = useAuth()
  const t = useT()
  const nav = useNavigate()
  const loc = useLocation()
  const [more, setMore] = useState(false)
  const [online, setOnline] = useState(navigator.onLine)
  const [pending, setPending] = useState(outbox().length)
  useEffect(() => {
    const sync = async () => { const r = await flushOutbox(); if (r.sent) toast(t('{sent} oflayn yazı göndərildi', { sent: r.sent })); if (r.failed) toast(t('{failed} yazı göndərilmədi (məlumat səhvdir)', { failed: r.failed })) }
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
  const moreItems = items.filter(i => !tabs.includes(i.to))
  const initials = (me?.full_name || '?').split(' ').slice(0, 2).map(w => w[0]).join('')
  const shortName = (me?.full_name || '').split(' ').slice(0, 2).join(' ')
  const active = (to: string) => (to === '/' ? loc.pathname === '/' : loc.pathname.startsWith(to))

  return (
    <>
      <div className={'app' + (me?.workspace === 'private' ? ' ws-private' : '')}>
        <aside className="side">
          <div className="brand"><span className="logo">M</span><div><b>Müəllim köməkçisi</b><span>{shortName} · 2026–2027</span></div></div>
          <nav className="nav" aria-label={t('Bölmələr')}>
            {(() => {
              const row = (i: NavItem) => (
                <NavLink key={i.to} to={i.to} end={i.to === "/"} className="navlink" title={t(i.label)}>
                  {({ isActive }) => <button tabIndex={-1} aria-current={isActive ? 'page' : undefined}><Icon name={i.icon} /><span className="nav-lbl">{t(i.label)}</span></button>}
                </NavLink>)
              return items.some(i => i.group)
                ? <NavGroups items={items} storageKey="mk-nav-open" defaultOpen={g => g === 'Dərs'} isActive={active} idPrefix="ng-d" renderItem={row} />
                : items.map(row)
            })()}
          </nav>
          <div className="side-foot">
            <p className="quote">«{t('Hər şagirdin öz addımı var. Əsas odur ki, irəliləsin.')}»</p><br />
            <button className="btn ghost sm" style={{ color: 'var(--side-muted)' }} onClick={logout}>{t('Çıxış')}</button>
          </div>
        </aside>
        <main>
          <div className="topbar">
            <span className="tb-brand"><span className="logo" style={{ width: 30, height: 30, fontSize: 14 }}>M</span><b>Müəllim köməkçisi</b></span>
            {!student && me?.has_private && <WorkspaceSwitch />}
            <button className="tb-user" style={{ marginLeft: me?.has_private ? 0 : 'auto' }} onClick={() => nav('/settings')} aria-label={t('Tənzimləmələr')}>
              <span className="uav">{initials}</span>
              <span className="tb-uname"><b>{shortName}</b><small>{student ? t('Şagird') : me?.role === 'admin' ? t('Admin') : t('Müəllim')}</small></span>
            </button>
          </div>
          {(!online || pending > 0) && (
            <div className="banner" role="status" style={{ background: online ? 'var(--info-soft)' : 'var(--warn-soft)', color: online ? 'var(--info)' : 'var(--warn)' }}>
              {online ? '' : t('Oflayn rejim – son yüklənən məlumatlar göstərilir.') + ' '}{pending > 0 ? t('{n} jurnal yazısı göndərilməyi gözləyir', { n: pending }) + ' ' + (online ? t('– göndərilir…') : t('(internet qayıdanda avtomatik göndəriləcək)')) + '.' : ''}
            </div>)}
          {!student && (() => { try { return sessionStorage.getItem('mk-weak') === '1' } catch { return false } })() && (
            <div className="banner" style={{ background: 'var(--warn-soft)', color: 'var(--warn)' }}>{t('Parolunuz zəifdir (8 simvoldan qısa). Tənzimləmələr → Hesab bölməsində daha uzun parol qoyun.')}</div>)}
          {children}
        </main>
      </div>
      <GlobalScan />
      {student && <SurveyNudge />}
      {student && <Suspense fallback={null}><CertNudge /></Suspense>}
      <nav className="tabbar" aria-label={t('Əsas bölmələr')}>
        {tabs.map(to => { const i = items.find(x => x.to === to)!; return (
          <button key={to} aria-current={active(to) ? 'page' : undefined} onClick={() => nav(to)}><Icon name={i.icon} />{t(i.short || i.label)}</button>) })}
        <button aria-current={!tabs.some(active) ? 'page' : undefined} onClick={() => setMore(true)}><Icon name="more" />{t('Daha çox')}</button>
      </nav>
      {more && (
        <Drawer title={t('Daha çox')} onClose={() => setMore(false)}>
          <div className="nav nav-more" style={{ gap: 6 }}>
            {(() => {
              const row = (i: NavItem) => (
                <button key={i.to} className="btn" style={{ justifyContent: 'flex-start' }} onClick={() => { setMore(false); nav(i.to) }}><Icon name={i.icon} />{t(i.label)}</button>)
              return moreItems.some(i => i.group)
                ? <NavGroups items={moreItems} storageKey="mk-nav-open-m" defaultOpen={() => true} isActive={active} idPrefix="ng-m" renderItem={row} />
                : moreItems.map(row)
            })()}
            <button className="btn danger" onClick={logout}>{t('Çıxış')}</button>
          </div>
        </Drawer>
      )}
    </>
  )
}


/** Məkan: məktəb və ya fərdi hazırlıq (repetitor) – fərdi məkan məktəbin hesabatlarına və siyahılarına düşmür. */
function WorkspaceSwitch() {
  const t = useT()
  const { me } = useAuth()
  const [busy, setBusy] = useState(false)
  const go = async (kind: 'school' | 'private') => {
    if (busy || me?.workspace === kind) return
    setBusy(true)
    try {
      const ws = await get<{ id: number; kind: string }[]>('/api/workspaces')
      const w = ws.find(x => x.kind === kind)
      if (w) { await put('/api/workspaces/active', { school_id: w.id }); location.reload() }
    } catch { toast(t('Məkan dəyişdirilmədi')); setBusy(false) }
  }
  return (
    <div className="ws-switch" role="group" aria-label={t('Məkan')} style={{ marginLeft: 'auto' }}>
      <button aria-pressed={me?.workspace !== 'private'} onClick={() => go('school')} title={t('Məktəb')}>{t('Məktəb')}</button>
      <button aria-pressed={me?.workspace === 'private'} onClick={() => go('private')} title={t('Fərdi hazırlıq – məktəbə aid deyil')}>{t('Fərdi')}</button>
    </div>
  )
}
