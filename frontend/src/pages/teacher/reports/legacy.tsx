// Köhnə ünvanlar → «Analitika və hesabat» (/reports?g=<qrup>&t=<tab>).
//   /tests?s=netice&v=X[&student=ID][&kind=…]  və  /results-center[?tab=X][&student=ID]
import { Navigate, useLocation } from 'react-router-dom'

const TEST_TABS = ['rating', 'missing', 'class', 'overall', 'matrix']

export function legacyReportsUrl(q: URLSearchParams, v: string | null): string {
  const n = new URLSearchParams()
  const student = q.get('student')
  if (student || v === 'student') {
    n.set('g', 'student'); n.set('t', 'student')
    if (student) n.set('student', student)
  } else {
    n.set('g', 'tests')
    if (v && TEST_TABS.includes(v)) n.set('t', v)
  }
  for (const k of ['kind', 'ta']) if (q.get(k)) n.set(k, q.get(k)!)
  return `/reports?${n}`
}

/** `/results-center` (köhnə ünvan) – parametrlər saxlanır. */
export function ResultsCenterRedirect() {
  const q = new URLSearchParams(useLocation().search)
  return <Navigate to={legacyReportsUrl(q, q.get('tab'))} replace />
}
