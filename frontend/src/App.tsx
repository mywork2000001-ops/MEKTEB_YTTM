import { Component, lazy as reactLazy, Suspense, useState, type ComponentType, type ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './auth'
import { I18nCtx, setCurrentLang, type Lang } from './i18n'
import { Layout } from './Layout'
import { GuideGate } from './GuideModal'
import Login from './pages/Login'
import Join from './pages/Join'
import QrLogin from './pages/QrLogin'
const SurveyPublic = lazy(() => import('./pages/SurveyPublic'))
const Verify = lazy(() => import('./pages/Verify'))
import { Loading, ToastHost } from './ui'
import { UpdateBanner } from './version'
import { ResultsCenterRedirect } from './pages/teacher/reports/legacy'

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
  DailyPlan: lazy(() => import('./pages/teacher/DailyPlan')),
  Timetable: lazy(() => import('./pages/teacher/Timetable')),
  Tasks: lazy(() => import('./pages/teacher/Tasks')),
  OnlineExams: lazy(() => import('./pages/teacher/OnlineExams')),
  ResultsCenter: lazy(() => import('./pages/teacher/ResultsCenter')),
  TestsHub: lazy(() => import('./pages/teacher/TestsHub')),
  Surveys: lazy(() => import('./pages/teacher/Surveys')),
  ExtraCourses: lazy(() => import('./pages/teacher/ExtraCourses')),
  Materials: lazy(() => import('./pages/teacher/Materials')),
  Reports: lazy(() => import('./pages/teacher/Reports')),
  Homeroom: lazy(() => import('./pages/teacher/Homeroom')),
  Settings: lazy(() => import('./pages/teacher/Settings')),
}
const S = {
  Today: lazy(() => import('./pages/student/Today')),
  Lesson: lazy(() => import('./pages/student/Lesson')),
  Tasks: lazy(() => import('./pages/student/Tasks')),
  Extra: lazy(() => import('./pages/student/Extra')),
  Materials: lazy(() => import('./pages/student/Materials')),
  Plan: lazy(() => import('./pages/student/Plan')),
  Results: lazy(() => import('./pages/student/Results')),
  Surveys: lazy(() => import('./pages/student/Surveys')),
  Analytics: lazy(() => import('./pages/student/Analytics')),
  Achievements: lazy(() => import('./pages/student/Achievements')),
  Settings: lazy(() => import('./pages/student/Settings')),
}
const Chat = lazy(() => import('./pages/Chat'))
const Guide = lazy(() => import('./pages/Guide'))

/** Köhnə ünvan → «Testlər və sınaqlar» (sorğu parametrləri saxlanır: ?tab= → görünüş, ?student= → şagird profili). */
function ToTests({ s }: { s: string }) {
  const q = new URLSearchParams(useLocation().search)
  q.set('s', s)
  if (q.get('tab')) { q.set('v', q.get('tab')!); q.delete('tab') }
  if (q.get('student')) q.set('v', 'student')
  return <Navigate to={`/tests?${q}`} replace />
}

export default function App() {
  const { me, ready } = useAuth()
  const [guestLang, setGuestLang] = useState<Lang>(() => (localStorage.getItem('mk-lang') as Lang) || 'az')
  const lang: Lang = me?.language || guestLang
  setCurrentLang(lang)                                  // sual mətnləri (ml) istifadəçinin dilində
  const changeGuestLang = (l: Lang) => { setGuestLang(l); try { localStorage.setItem('mk-lang', l) } catch { /* noop */ } }
  const join = location.pathname.match(/^\/join\/([\w-]+)$/)
  if (join) return <I18nCtx.Provider value={lang}><Join token={join[1]} lang={lang} setLang={changeGuestLang} /><ToastHost /></I18nCtx.Provider>
  const qr = location.pathname.match(/^\/q\/([\w.-]+)$/)          // giriş vərəqəsindəki QR – avtomatik giriş
  if (qr) return <I18nCtx.Provider value={lang}><QrLogin token={qr[1]} /></I18nCtx.Provider>
  const sv = location.pathname.match(/^\/s\/([\w-]+)$/)          // anonim şagird sorğusu (WhatsApp / QR linki) – girişsiz
  if (sv) return <I18nCtx.Provider value={lang}><Suspense fallback={<Loading />}><SurveyPublic token={sv[1]} /></Suspense></I18nCtx.Provider>
  const vf = location.pathname.match(/^\/v\/([\w-]+)$/)          // sertifikatın yoxlanması (QR) – girişsiz
  if (vf) return <I18nCtx.Provider value={lang}><Suspense fallback={<Loading />}><Verify code={vf[1]} /></Suspense></I18nCtx.Provider>
  if (!ready) return <Loading />
  return (
    <I18nCtx.Provider value={lang}>
      {!me ? (
        <Login lang={lang} setLang={changeGuestLang} />
      ) : (
        <Layout>
          <GuideGate />
          <Boundary><Suspense fallback={<Loading />}>
            {me.role === 'student' ? (
              <Routes>
                <Route path="/" element={<S.Today />} />
                <Route path="/lesson" element={<S.Lesson />} />
                <Route path="/tasks" element={<S.Tasks />} />
                <Route path="/t/:id" element={<S.Tasks />} />
                <Route path="/materials" element={<S.Materials />} />
                <Route path="/extra" element={<S.Extra />} />
                <Route path="/plan" element={<S.Plan />} />
                <Route path="/results" element={<S.Results />} />
                <Route path="/surveys" element={<S.Surveys />} />
                <Route path="/analytics" element={<S.Analytics />} />
                <Route path="/achievements" element={<S.Achievements />} />
                <Route path="/chat" element={<Chat />} />
                <Route path="/guide" element={<Guide />} />
                <Route path="/settings" element={<S.Settings />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            ) : (
              <Routes>
                <Route path="/" element={<T.Home />} />
                <Route path="/classes" element={<T.Classes />} />
                <Route path="/journal" element={<T.Journal />} />
                <Route path="/plan" element={<T.Plan />} />
                <Route path="/daily" element={<T.DailyPlan />} />
                <Route path="/timetable" element={<T.Timetable />} />
                <Route path="/tests" element={<T.TestsHub />} />
                {/* köhnə ünvanlar – «Testlər və sınaqlar»a (parametrlər saxlanır) */}
                <Route path="/tasks" element={<ToTests s="movzu" />} />
                <Route path="/exams-online" element={<ToTests s="sinaq" />} />
                <Route path="/results-center" element={<ResultsCenterRedirect />} />
                <Route path="/surveys" element={<T.Surveys />} />
                <Route path="/extra" element={<Navigate to="/classes?tab=extra" replace />} />
                <Route path="/t/:id" element={<Navigate to="/tests" replace />} />
                <Route path="/materials" element={<T.Materials />} />
                <Route path="/reports" element={<T.Reports />} />
                <Route path="/homeroom" element={<T.Homeroom />} />
                <Route path="/chat" element={<Chat />} />
                <Route path="/guide" element={<Guide />} />
                <Route path="/settings" element={<T.Settings />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            )}
          </Suspense></Boundary>
        </Layout>
      )}
      <ToastHost />
      <UpdateBanner />
    </I18nCtx.Provider>
  )
}
