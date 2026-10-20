// «Kim nəyi işləyib»: sinif üzrə şagird × test cədvəli (docs/tasks/sinif-test-matrisi.md).
// Sətir – şagird, sütun – mövzu testləri (№ + mövzu), sınaqlar (adla), kağız KSQ/BSQ; xana – nəticə. Çap (PDF) və Excel – rəsmi, AZ.
import { useT } from '../../i18n'
import { get } from '../../api'
import { AsyncBtn, ErrorBox, fmt, Loading, Seg, useLoad } from '../../ui'
import { fmtD } from '../../print'
import { download } from './StudentReport'
import { useEffect, useState } from 'react'

type Cell = { status: 'yazıb' | 'yazmayıb' | 'təyin olunmayıb' | 'gözlənilir' | 'işlənməyib' | 'nəşr olunmayıb'; pct: number | null; grade: number | null; published: boolean }
type Col = { key: string; kind: 'movzu' | 'sinaq' | 'ksq' | 'bsq'; no: string | null; title: string; date: string | null; assigned_count: number; wrote_count: number; avg_pct: number | null }
type Row = { student_id: number; full_name: string; cells: Record<string, Cell>; wrote: number; given: number; avg_pct: number | null }
type MData = { class_name: string; subject: string; columns: Col[]; rows: Row[] }
type MissItem = { key: string; kind: 'movzu' | 'sinaq' | 'ksq' | 'bsq'; no: string | null; title: string; date: string | null; status: string }
type MissData = { class_name: string; subject: string; students: number; total: number; rows: { student_id: number; full_name: string; lang: string; items: MissItem[] }[] }
type MK ='all' | 'movzu' | 'sinaq'

const tone = (p: number | null) => (p == null ? undefined : p >= 80 ? 'var(--ok)' : p >= 50 ? 'var(--warn)' : 'var(--bad)')
const shade = (c?: string) => (c ? `color-mix(in srgb, ${c} 22%, transparent)` : undefined)
const short = (s: string, n = 22) => (s.length > n ? s.slice(0, n - 1) + '…' : s)

function CellView({ x }: { x: Cell }) {
  const t = useT()
  if (x.status === 'yazıb') return <td className="c" style={{ background: shade(tone(x.pct)), fontWeight: 600 }}>{fmt(x.pct)}</td>
  if (x.status === 'nəşr olunmayıb') return <td className="c" style={{ background: shade(tone(x.pct)) }} title={t('nəşr olunmayıb')}>({fmt(x.pct)})</td>
  if (x.status === 'yazmayıb') return <td className="c" style={{ color: 'var(--bad)', fontWeight: 600 }}>✗ {t('yazmayıb')}</td>
  if (x.status === 'gözlənilir') return <td className="c" title={t('hələ açıqdır')}>⏳</td>
  if (x.status === 'işlənməyib') return <td className="c" style={{ color: 'var(--warn)' }} title={t('işlənməyib')}>⏳</td>
  return <td className="c muted" title={t('təyin olunmayıb')}>—</td>
}

export default function ClassMatrix({ ta, params, label, onStudent, onResend }: {
  ta: number; params: Record<string, string>; label: string; onStudent: (id: number) => void; onResend: () => void
}) {
  const t = useT()
  const [kind, setKind] = useState<MK>('all')
  const q = { kind, ...(params.date_from ? { from: params.date_from } : {}), ...(params.date_to ? { to: params.date_to } : {}) }
  const [mode, setMode] = useState<'all' | 'missing'>(() => { try { return sessionStorage.getItem('mk-matrix-missing') === '1' ? 'missing' : 'all' } catch { return 'all' } })
  useEffect(() => { try { sessionStorage.removeItem('mk-matrix-missing') } catch { /* noop */ } }, [])
  const [d, err, loading] = useLoad<MData | null>(() => mode === 'all' ? get(`/api/results-center/class/${ta}/matrix`, q) : Promise.resolve(null), [ta, kind, label, mode])
  const [ml_, err2, loading2] = useLoad<MissData | null>(() => mode === 'missing' ? get(`/api/results-center/class/${ta}/missing-list`, q) : Promise.resolve(null), [ta, kind, label, mode])
  const file = (fmtName: 'xlsx' | 'pdf') => download(`/api/results-center/class/${ta}/matrix?` + new URLSearchParams({ ...q, format: fmtName }).toString(), `matris-${d?.class_name || ta}.${fmtName}`)
  const mfile = (fmtName: 'xlsx' | 'pdf', per: boolean) => download(`/api/results-center/class/${ta}/missing-list?` + new URLSearchParams({ ...q, format: fmtName, per_student: per ? '1' : '0' }).toString(),
    `islenmeyenler-${ml_?.class_name || ta}${per ? '-sagird' : ''}.${fmtName}`)
  return (
    <>
      <div className="toolbar no-print">
        <Seg label={t('Növ')} value={kind} onChange={setKind} options={[['all', 'Hamısı'], ['movzu', 'Mövzu testləri'], ['sinaq', 'Sınaqlar']]} />
        <Seg label={t('Görünüş')} value={mode} onChange={setMode} options={[['all', 'Hamısı'], ['missing', 'Yalnız işlənməyənlər']]} />
        {mode === 'all' ? <>
          <AsyncBtn className="btn sm right" ok={t('PDF hazırdır')} onClick={() => file('pdf')}>🖨 {t('Çap')}</AsyncBtn>
          <AsyncBtn className="btn sm" ok={t('Fayl hazırdır')} onClick={() => file('xlsx')}>⬇ Excel</AsyncBtn></> : <>
          <AsyncBtn className="btn sm right" ok={t('PDF hazırdır')} onClick={() => mfile('pdf', false)}>🖨 {t('Sinif üzrə çap')}</AsyncBtn>
          <AsyncBtn className="btn sm" ok={t('PDF hazırdır')} onClick={() => mfile('pdf', true)}>🖨 {t('Hər şagirdə ayrıca')}</AsyncBtn>
          <AsyncBtn className="btn sm" ok={t('Fayl hazırdır')} onClick={() => mfile('xlsx', false)}>⬇ Excel</AsyncBtn></>}
        <button className="btn sm" onClick={onResend}>{t('Yazmayanlara yenidən göndər')}</button>
      </div>
      <ErrorBox error={mode === 'all' ? err : err2} />
      {mode === 'missing' && (loading2 && !ml_ ? <Loading /> : ml_ && (ml_.rows.length === 0 ? <div className="empty">{t('İşlənməyən test və sınaq yoxdur.')}</div> : (
        <section className="panel">
          <h2>{t('Yalnız işlənməyənlər')} <small>{ml_.class_name} · {ml_.subject}</small>{' '}
            <span className="pill warn">{t('{n} şagird · {m} işlənməmiş test', { n: ml_.students, m: ml_.total })}</span></h2>
          <div className="stack" style={{ gap: 8 }}>
            {ml_.rows.map(r => (
              <div key={r.student_id} className="row" style={{ alignItems: 'flex-start', gap: 10, borderBottom: '1px solid var(--line)', paddingBottom: 8 }}>
                <b className="click" style={{ minWidth: 190 }} onClick={() => onStudent(r.student_id)}>{r.full_name}</b>
                <span className="row grow" style={{ gap: 6, flexWrap: 'wrap' }}>
                  {r.items.map(i => <span key={i.key} className="pill" title={fmtD(i.date)}>
                    {i.kind === 'movzu' ? `${i.no ? '№' + i.no + ' ' : ''}${i.title}` : i.kind === 'sinaq' ? t('Sınaq: {name}', { name: i.title }) : i.title}{i.status === 'gözlənilir' || i.status === 'işlənməyib' ? ' ⏳' : ''}</span>)}
                </span>
                <span className="pill bad">{t('{n} işlənməmiş', { n: r.items.length })}</span>
              </div>))}
          </div>
        </section>)))}
      {mode === 'all' && (loading && !d ? <Loading /> : d && (d.columns.length === 0 ? <div className="empty">{t('Bu dövrdə test və sınaq yoxdur.')}</div> : (
        <section className="panel">
          <h2>{t('Kim nəyi işləyib')} <small>{d.class_name} · {d.subject}</small></h2>
          <p className="small muted">{t('✗ – yazmayıb · ⏳ – hələ açıqdır · — – təyin olunmayıb · (xx) – nəticə şagirdə hələ nəşr olunmayıb')}</p>
          <div style={{ overflowX: 'auto', maxWidth: '100%' }}>
            <style>{'.mx .c{text-align:center}.mx th,.mx td{padding:4px 6px}'}</style>
            <table className="mx" style={{ minWidth: 'max-content' }}>
              <thead><tr>
                <th style={{ position: 'sticky', left: 0, background: 'var(--surface)', zIndex: 1, textAlign: 'left' }}>{t('Şagird')}</th>
                {d.columns.map(c => (
                  <th key={c.key} className="c" title={`${c.no ? c.no + ' ' : ''}${c.title}`} style={{ minWidth: 76, fontWeight: 600 }}>
                    {c.no ? <b>{c.no}</b> : null}{c.no ? ' ' : ''}{short(c.title)}<br /><small className="muted">{fmtD(c.date)}</small></th>))}
                <th className="c">{t('Yazıb/təyin')}</th><th className="c">{t('Orta, %')}</th>
              </tr></thead>
              <tbody>
                {d.rows.map(r => (
                  <tr key={r.student_id}>
                    <td className="click" onClick={() => onStudent(r.student_id)} style={{ position: 'sticky', left: 0, background: 'var(--surface)', whiteSpace: 'nowrap', fontWeight: 600 }}>{r.full_name}</td>
                    {d.columns.map(c => <CellView key={c.key} x={r.cells[c.key]} />)}
                    <td className="c">{r.wrote}/{r.given}</td><td className="c"><b>{r.avg_pct == null ? '—' : fmt(r.avg_pct)}</b></td>
                  </tr>))}
                <tr>
                  <td style={{ position: 'sticky', left: 0, background: 'var(--surface)' }}><b>{t('Yazan / təyin olunan')}</b></td>
                  {d.columns.map(c => <td key={c.key} className="c">{c.wrote_count}/{c.assigned_count}</td>)}<td /><td />
                </tr>
                <tr>
                  <td style={{ position: 'sticky', left: 0, background: 'var(--surface)' }}><b>{t('Orta, %')}</b></td>
                  {d.columns.map(c => <td key={c.key} className="c">{c.avg_pct == null ? '—' : fmt(c.avg_pct)}</td>)}<td /><td />
                </tr>
              </tbody>
            </table>
          </div>
        </section>)))}
    </>
  )
}
