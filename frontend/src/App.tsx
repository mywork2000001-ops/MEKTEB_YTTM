import { lazy, Suspense, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth'
import { I18nCtx, type Lang } from './i18n'
import { Layout } from './Layout'
import Login from './pages/Login'
import { Loading, ToastHost } from './ui'

const T = {
  Home: lazy(() => import('./pages/teacher/Home')),
  Classes: lazy(() => import('./pages/teacher/Classes')),
  Journal: lazy(() => import('./pages/teacher/Journal')),
  Plan: lazy(() => import('./pages/teacher/Plan')),
  Timetable: lazy(() => import('./pages/teacher/Timetable')),
  Tasks: lazy(() => import('./pages/teacher/Tasks')),
  Reports: lazy(() => import('./pages/teacher/Reports')),
  Settings: lazy(() => import('./pages/teacher/Settings')),
}
const S = {
  Today: lazy(() => import('./pages/student/Today')),
  Lesson: lazy(() => import('./pages/student/Lesson')),
  Tasks: lazy(() => import('./pages/student/Tasks')),
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
  if (!ready) return <Loading />
  return (
    <I18nCtx.Provider value={lang}>
      {!me ? (
        <Login lang={lang} setLang={l => { setGuestLang(l); try { localStorage.setItem('mk-lang', l) } catch { /* noop */ } }} />
      ) : (
        <Layout>
          <Suspense fallback={<Loading />}>
            {me.role === 'student' ? (
              <Routes>
                <Route path="/" element={<S.Today />} />
                <Route path="/lesson" element={<S.Lesson />} />
                <Route path="/tasks" element={<S.Tasks />} />
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
                <Route path="/reports" element={<T.Reports />} />
                <Route path="/chat" element={<Chat />} />
                <Route path="/settings" element={<T.Settings />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            )}
          </Suspense>
        </Layout>
      )}
      <ToastHost />
    </I18nCtx.Provider>
  )
}
