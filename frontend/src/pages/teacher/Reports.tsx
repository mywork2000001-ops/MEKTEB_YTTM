// «Analitika və hesabat» – bütün hesabat, statistika, reytinq, analiz və hesabat çapları bir yerdə
// (docs/audit/hesabatlar-ve-islenmeyenler-audit-2026-10-20.md §III). Qrup + tab URL-də: /reports?g=<qrup>&t=<tab>[&student=ID].
// Ortaq sinif seçimi (lazım olan yerdə «Bütün siniflərim») və yarımil; sonuncu açılan tab brauzerdə yadda qalır.
// Tabların özləri reports/ qovluğunda və ResultsCenter / ClassMatrix / StudentReport / MissingReport / SchoolReport komponentlərindədir (köçürülüb, təkrarlanmayıb).
import { useEffect, useState, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { get } from '../../api'
import { useAuth } from '../../auth'
import { ErrorBox, fmtDate, Loading, PickFirst, Seg, Top, useLoad } from '../../ui'
import { useT } from '../../i18n'
import { useMyLessons, usePick } from './common'
import CertificatesPanel from './CertificatesPanel'
import ResultsCenter, { type Tab as RcTab } from './ResultsCenter'
import SchoolReport from './SchoolReport'
import { Attendance, LessonCounts, Levels, Overview, Performance, Rating, Risk } from './reports/ClassTabs'
import PrintCenter from './reports/PrintCenter'
import type { Sem } from './reports/common'


type TabDef = {
  k: string; label: string; sub?: string
  all?: boolean        // «Bütün siniflərim» mənalıdır (sinif seçilməsə – hamısı)
  cls?: boolean        // tək sinif lazımdır
  sem?: boolean        // yarımil seçimi
}
type Group = { k: string; label: string; tabs: TabDef[]; admin?: boolean }

const GROUPS: Group[] = [
  { k: 'overview', label: 'İcmal', tabs: [{ k: 'overview', label: 'Sinif icmalı', cls: true, sem: true }] },
  { k: 'academic', label: 'Akademik nəticələr', tabs: [
    { k: 'performance', label: 'Müvəffəqiyyət', cls: true, sem: true },
    { k: 'total', label: 'Ümumi reytinq', cls: true, sem: true, sub: 'Qiymət 40% · KSQ 30% · ev tapşırığı 15% · davamiyyət 15% – jurnal əsasında kompleks reytinq (test reytinqindən fərqlidir).' },
    { k: 'levels', label: 'Güclü / orta / zəif', cls: true, sem: true },
    { k: 'lessons', label: 'Dərs sayı', cls: true },
  ] },
  { k: 'tests', label: 'Testlər və sınaqlar', tabs: [
    { k: 'missing', label: 'İşlənməyənlər', all: true },
    { k: 'matrix', label: 'Kim nəyi işləyib', cls: true },
    { k: 'rating', label: 'Test reytinqi', all: true, sub: 'Onlayn mövzu testləri və sınaqların nəticələri üzrə reytinq (jurnal qiyməti və davamiyyət daxil deyil).' },
    { k: 'class', label: 'Sinif və qrup', all: true },
    { k: 'overall', label: 'Ümumi' },
  ] },
  { k: 'student', label: 'Şagird', tabs: [
    { k: 'student', label: 'Şagird hesabatı' },
    { k: 'risk', label: 'Risk', cls: true, sem: true },
  ] },
  { k: 'attendance', label: 'Davamiyyət', tabs: [{ k: 'attendance', label: 'Davamiyyət', cls: true, sem: true }] },
  { k: 'print', label: 'Çap mərkəzi', tabs: [{ k: 'docs', label: 'Bütün sənədlər', sem: true }] },
  { k: 'school', label: 'Məktəb üzrə', admin: true, tabs: [{ k: 'school', label: 'Məktəb hesabatı' }, { k: 'certs', label: 'Sertifikatlar', cls: true }] },
]
const RC_TABS = ['missing', 'matrix', 'rating', 'class', 'overall', 'student']
const LAST = 'mk-reports-last'
const readLast = (): { g: string; t: string } | null => { try { const v = JSON.parse(localStorage.getItem(LAST) || 'null'); return v && v.g && v.t ? v : null } catch { return null } }
const lastLesson = (): number | null => { try { const s = localStorage.getItem('mk-last-lesson'); return s ? Number(s) : null } catch { return null } }

/** Sinfin analitikasını (bir dəfə) yükləyir; tab-lar `a` ilə işləyir. */
function WithA({ ta, sem, children }: { ta: number; sem: Sem; children: (a: any, params: Record<string, string>) => ReactNode }) {
  const params: Record<string, string> = sem === 'all' ? {} : { semester: sem }
  const [a, err, loading] = useLoad<any>(() => get(`/api/analytics/${ta}`, params), [ta, sem])
  return (
    <>
      <ErrorBox error={err} />
      {loading && !a ? <Loading /> : a && (<>
        <p className="small muted no-print" style={{ margin: '0 0 8px' }}>{a.class_name} · {a.subject} · {fmtDate(a.from)} – {fmtDate(a.to)}</p>
        {children(a, params)}
      </>)}
    </>
  )
}

export default function Reports() {
  const t = useT()
  const { me } = useAuth()
  const isAdmin = me?.role === 'admin'
  const [sp, setSp] = useSearchParams()
  const [lessons, err0] = useMyLessons()
  const [taPick, setTaPick] = usePick('reports')
  const [allSel, setAllSel] = useState(true)             // «Bütün siniflərim» (yalnız `all` tablarda)
  const [semPick, setSem] = useState<Sem | null>(null)

  const groups = GROUPS.filter(g => !g.admin || isAdmin)
  const last = readLast()
  const gParam = sp.get('g')
  const group = groups.find(g => g.k === gParam) ?? (!gParam ? groups.find(g => g.k === last?.g) : undefined) ?? groups[0]
  const tParam = sp.get('t')
  const tab = group.tabs.find(x => x.k === tParam) ?? (!tParam && last?.g === group.k ? group.tabs.find(x => x.k === last.t) : undefined) ?? group.tabs[0]
  useEffect(() => { try { localStorage.setItem(LAST, JSON.stringify({ g: group.k, t: tab.k })) } catch { /* noop */ } }, [group.k, tab.k])

  // köhnə/xarici keçidlər: ?ta=ID – sinfi seçir və parametri silir
  useEffect(() => {
    const x = sp.get('ta')
    if (!x) return
    setTaPick(Number(x)); setAllSel(false)
    setSp(prev => { const n = new URLSearchParams(prev); n.delete('ta'); return n }, { replace: true })
  }, [])   // eslint-disable-line react-hooks/exhaustive-deps

  const go = (g: string, tb?: string, extra: Record<string, string> = {}, replace = false) => {
    const n = new URLSearchParams({ g, ...(tb ? { t: tb } : {}), ...extra })
    setSp(n, { replace })
  }
  const lastId = lastLesson()
  const known = (id: number | null) => (id != null && (lessons || []).some(l => l.id === id) ? id : null)
  const single = known(taPick) ?? (taPick == null ? known(lastId) : null)
  const ta: number | null = tab.all && allSel ? null : single
  const cur = lessons?.find(l => l.id === (ta ?? single))
  const sem: Sem = semPick ?? (cur?.semester ? (String(cur.semester) as Sem) : '1')
  const needClass = !!(tab.cls || tab.all)

  const student = sp.get('student') ? Number(sp.get('student')) : null
  const rcTab = (RC_TABS.includes(tab.k) ? tab.k : 'rating') as RcTab
  const onRcTab = (x: RcTab) => (x === 'student' ? go('student', 'student', student ? { student: String(student) } : {}) : go('tests', x))
  const onStudent = (id: number | null) => go('student', 'student', id ? { student: String(id) } : {})

  const body = (): ReactNode => {
    if (tab.cls && ta == null) return <PickFirst />
    switch (group.k + '/' + tab.k) {
      case 'overview/overview': return <WithA ta={ta!} sem={sem}>{a => <Overview a={a} />}</WithA>
      case 'academic/performance': return <Performance ta={ta!} sem={sem} />
      case 'academic/total': return <WithA ta={ta!} sem={sem}>{a => <Rating a={a} />}</WithA>
      case 'academic/levels': return <WithA ta={ta!} sem={sem}>{a => <Levels a={a} />}</WithA>
      case 'academic/lessons': return <LessonCounts ta={ta!} />
      case 'student/risk': return <WithA ta={ta!} sem={sem}>{a => <Risk a={a} ta={ta!} />}</WithA>
      case 'attendance/attendance': return <WithA ta={ta!} sem={sem}>{(a, params) => <Attendance ta={ta!} params={params} a={a} />}</WithA>
      case 'print/docs': return <PrintCenter ta={single} sem={sem} isAdmin={isAdmin} />
      case 'school/school': return <SchoolReport />
      case 'school/certs': return <CertificatesPanel ta={ta!} />
    }
    if (RC_TABS.includes(tab.k)) return <ResultsCenter embedded ta={ta} tab={rcTab} onTab={onRcTab} student={student} onStudent={onStudent} />
    return null
  }

  return (
    <>
      <Top title="Analitika və hesabat" sub="Bütün hesabatlar, statistika, reytinq və çap sənədləri bir yerdə – bölmə və tabı seçin." />
      <ErrorBox error={err0} />
      <div className="hub-bar no-print">
        <label className="hub-pick"><span>{t('Bölmə')}</span>
          <select value={group.k} onChange={e => go(e.target.value)}>
            {groups.map(g => <option key={g.k} value={g.k}>{t(g.label)}</option>)}
          </select></label>
        {(needClass || group.k === 'print') && <label className="hub-pick"><span>{t('Sinif')}</span>
          <select value={tab.all && allSel ? '' : single ?? ''} onChange={e => { if (e.target.value) { setTaPick(Number(e.target.value)); setAllSel(false) } else if (tab.all) setAllSel(true) }}>
            {tab.all ? <option value="">{t('Bütün siniflərim')}</option> : <option value="">{t('— Sinif / qrup seçin —')}</option>}
            {(lessons || []).map(l => <option key={l.id} value={l.id}>{l.class_name}{l.subject !== 'Riyaziyyat' ? ` · ${l.subject}` : ''}</option>)}
          </select></label>}
        {tab.sem && (ta != null || group.k === 'print') && <Seg value={sem} onChange={setSem} options={[['1', 'I yarımil'], ['2', 'II yarımil'], ['all', 'Bütün il']]} />}
      </div>
      {group.tabs.length > 1 && <div className="tabs rtabs no-print">{group.tabs.map(x =>
        <button key={x.k} aria-selected={tab.k === x.k} onClick={() => go(group.k, x.k, student && group.k === 'student' ? { student: String(student) } : {})}>{t(x.label)}</button>)}</div>}
      {tab.sub && <p className="small muted no-print" style={{ margin: '0 0 10px' }}>{t(tab.sub)}</p>}
      {body()}
    </>
  )
}
