import { Component, lazy as reactLazy, Suspense, useState, type ComponentType, type ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth'
import { I18nCtx, type Lang } from './i18n'
import { Layout } from './Layout'
import Login from './pages/Login'
import Join from './pages/Join'
import { Loading, ToastHost } from './ui'

// Yeni yayımdan sonra açıq səhifə köhnə hissəni (chunk) tapmırsa – bir dəfə avtomatik yenilənir (ağ ekran olmasın)
function lazy<T extends ComponentType<any>>(f: () => Promise<{ default: T }>) {
  return reactLazy(() => f().then(m => { try { sessionStorage.removeItem('mk-chunk-reload') } catch { /* noop */ } return m }).catch(e => {
    let tried = false
    try { tried = sessionStorage.getItem('mk-chunk-reload') === '1'; sessionStorage.setItem('mk-chunk-reload', '1') } catch { /* noop */ }
    if (!tried) { location.reload(); return new Promise<{ default: T }>(() => {}) }
    throw e
  }))
}

class Boundary extends Component<{ children: ReactNode }, { err: boolean }> {
  state = { err: false }
  static getDerivedStateFromError() { return { err: true } }
  render() {
    return this.state.err ? (
      <div className="empty"><p>Səhifə yüklənmədi (tətbiq yenilənmiş ola bilər).</p>
        <button className="btn primary" onClick={() => { try { sessionStorage.removeItem('mk-chunk-reload') } catch { /* noop */ } location.reload() }}>Yenilə</button></div>
    ) : this.props.children
  }
}

const T = {
  Home: lazy(() => import('./pages/teacher/Home')),
  Classes: lazy(() => import('./pages/teacher/Classes')),
  Journal: lazy(() => import('./pages/teacher/Journal')),
  Plan: lazy(() => import('./pages/teacher/Plan')),
  Timetable: lazy(() => import('./pages/teacher/Timetable')),
  Tasks: lazy(() => import('./pages/teacher/Tasks')),
  Materials: lazy(() => import('./pages/teacher/Materials')),
  Reports: lazy(() => import('./pages/teacher/Reports')),
  Settings: lazy(() => import('./pages/teacher/Settings')),
}
const S = {
  Today: lazy(() => import('./pages/student/Today')),
  Lesson: lazy(() => import('./pages/student/Lesson')),
  Tasks: lazy(() => import('./pages/student/Tasks')),
  Materials: lazy(() => import('./pages/student/Materials')),
  Plan: lazy(() => import('./pages/student/Plan')),
  Results: lazy(() => import('./pages/student/Results')),
  Analytics: lazy(() => import('./pages/student/Analytics')),
  Settings: lazy(() => import('./pages/student/Settings')),
}
const Chat = lazy(() => import('./pages/Chat'))

export default function App() {
  const { me, ready } = useAuth()
  const [guestLang, setGuestLang] = useState<Lang>(() => (localStorage.getItem('mk-lang') as Lang) || 'az')
  const lang: Lang = me?.language || guestLang
  const join = location.pathname.match(/^\/join\/([\w-]+)$/)
  if (join) return <I18nCtx.Provider value={lang}><Join token={join[1]} /><ToastHost /></I18nCtx.Provider>
  if (!ready) return <Loading />
  return (
    <I18nCtx.Provider value={lang}>
      {!me ? (
        <Login lang={lang} setLang={l => { setGuestLang(l); try { localStorage.setItem('mk-lang', l) } catch { /* noop */ } }} />
      ) : (
        <Layout>
          <Boundary><Suspense fallback={<Loading />}>
            {me.role === 'student' ? (
              <Routes>
                <Route path="/" element={<S.Today />} />
                <Route path="/lesson" element={<S.Lesson />} />
                <Route path="/tasks" element={<S.Tasks />} />
                <Route path="/materials" element={<S.Materials />} />
                <Route path="/plan" element={<S.Plan />} />
                <Route path="/results" element={<S.Results />} />
                <Route path="/analytics" element={<S.Analytics />} />
                <Route path="/chat" element={<Chat />} />
                <Route path="/settings" element={<S.Settings />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            ) : (
              <Routes>
                <Route path="/" element={<T.Home />} />
                <Route path="/classes" element={<T.Classes />} />
                <Route path="/journal" element={<T.Journal />} />
                <Route path="/plan" element={<T.Plan />} />
                <Route path="/timetable" element={<T.Timetable />} />
                <Route path="/tasks" element={<T.Tasks />} />
                <Route path="/materials" element={<T.Materials />} />
                <Route path="/reports" element={<T.Reports />} />
                <Route path="/chat" element={<Chat />} />
                <Route path="/settings" element={<T.Settings />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            )}
          </Suspense></Boundary>
        </Layout>
      )}
      <ToastHost />
    </I18nCtx.Provider>
  )
}
