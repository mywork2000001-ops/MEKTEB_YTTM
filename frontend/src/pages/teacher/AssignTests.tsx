// «🧪 Testləri təyin et»: perspektiv plandan mövzu testləri – bir sinif, bir neçə sinif və ya bütün siniflərim (önbaxış → təsdiq).
// Bütün məntiq serverdə: app/plan_tests.py (docs/plan-testleri-skripti-promtu.md).
import { useState } from 'react'
import { post } from '../../api'
import { TEST_MINUTES } from '../../humanTime'
import { Drawer, DurationSelect, ErrorBox, Field, fmtDate, isoDate, Pill, toast } from '../../ui'
import { useT } from '../../i18n'
import type { MyLesson } from './common'

type Row = { ta_id: number; class_name: string; date: string | null; seq: number; topic_no: string | null; topic: string; file: string | null
  source: string | null; questions: number; status: string; reason: string; will_create: boolean; created: boolean; warn?: string | null }
type Report = { rows: Row[]; will_create: number; created: number; applied: boolean }

export const STATUS_LABEL: Record<string, string> = { ok: 'Uyğun', weak: 'Şübhəli', none: 'Tapılmadı', pending: 'Gözlənilir', manual: 'Seçilib',
  has_test: 'Test var', summative: 'Summativ/sınaq', derived: 'Törəmə dərs', past: 'Keçib', missing: 'Çatışan' }
const TONE: Record<string, 'ok' | 'warn' | 'bad' | 'info' | undefined> = { ok: 'ok', manual: 'ok', missing: 'ok', weak: 'warn', none: 'bad', has_test: 'info' }

const addDays = (d: Date, n: number) => { const x = new Date(d); x.setDate(x.getDate() + n); return x }

export default function AssignTests({ ta, lessons, onClose, onDone }: { ta: number; lessons: MyLesson[] | null; onClose: () => void; onDone: () => void }) {
  const t = useT()
  const [scope, setScope] = useState<'this' | 'all'>('this')
  const [period, setPeriod] = useState<'week' | 'month' | 'dates'>('week')
  const [d1, setD1] = useState(isoDate(new Date()))
  const [d2, setD2] = useState(isoDate(addDays(new Date(), 7)))
  const [missing, setMissing] = useState(false)
  const [weak, setWeak] = useState(false)
  const [duration, setDuration] = useState(45)
  const [n, setN] = useState(15)
  const [rep, setRep] = useState<Report | null>(null)
  const [err, setErr] = useState<unknown>()
  const [busy, setBusy] = useState(false)

  const body = () => {
    const from = period === 'dates' ? d1 : isoDate(new Date())
    const to = period === 'dates' ? d2 : isoDate(addDays(new Date(), period === 'week' ? 7 : 31))
    return { ta_ids: scope === 'this' ? [ta] : (lessons || []).map(l => l.id), date_from: missing && period !== 'dates' ? null : from, date_to: to,
      opts: { n_questions: n, duration, missing, include_weak: weak } }
  }
  const run = async (kind: 'preview' | 'assign') => {
    setBusy(true); setErr(undefined)
    try {
      const r = await post<Report>(`/api/plan-tests/${kind}`, body())
      setRep(r)
      if (kind === 'assign') { toast(t('{n} test yaradıldı', { n: r.created })); onDone() }
    } catch (e) { setErr(e) } finally { setBusy(false) }
  }
  const sum = (s: string) => rep?.rows.filter(r => r.status === s).length || 0

  return (
    <Drawer title={t('Testləri təyin et')} onClose={onClose}
      footer={<><span className="small muted grow">{rep ? t('Yaradılacaq: {n}', { n: rep.will_create }) : ''}</span>
        <button className="btn" onClick={onClose}>{t('Bağla')}</button>
        <button className="btn" disabled={busy} onClick={() => run('preview')}>{t('Önbaxış')}</button>
        <button className="btn primary" disabled={busy || !rep || rep.applied || rep.will_create === 0} onClick={() => run('assign')}>{t('Təsdiq et')}</button></>}>
      <div className="stack">
        <div className="banner small">{t('Mövzu testi perspektiv plandan avtomatik seçilir: bir mövzuya bir test (mövzunun son dərsinə), müəllimin əl ilə seçdiyi fayl və artıq yaradılmış testlər toxunulmaz qalır.')}</div>
        <div className="fg">
          <Field label={t('Siniflər')}><select className="sel" value={scope} onChange={e => { setScope(e.target.value as typeof scope); setRep(null) }}>
            <option value="this">{t('Bu sinif')}</option><option value="all">{t('Bütün siniflərim')}</option></select></Field>
          <Field label={t('Dövr')}><select className="sel" value={period} onChange={e => { setPeriod(e.target.value as typeof period); setRep(null) }}>
            <option value="week">{t('Bu həftə (7 gün)')}</option><option value="month">{t('Bu ay (31 gün)')}</option><option value="dates">{t('Tarixlər')}</option></select></Field>
          {period === 'dates' && <><Field label={t('Başlanğıc')}><input type="date" value={d1} onChange={e => { setD1(e.target.value); setRep(null) }} /></Field>
            <Field label={t('Son')}><input type="date" value={d2} onChange={e => { setD2(e.target.value); setRep(null) }} /></Field></>}
          <Field label={t('Həll müddəti')}><DurationSelect unit="min" options={TEST_MINUTES} value={duration} onChange={v => { setDuration(Math.max(45, v)); setRep(null) }} /></Field>
          <Field label={t('Sual sayı')}><input type="number" min={1} max={100} value={n} onChange={e => { setN(Math.max(1, Number(e.target.value) || 15)); setRep(null) }} /></Field>
        </div>
        <label className="check small"><input type="checkbox" checked={missing} onChange={e => { setMissing(e.target.checked); setRep(null) }} /> {t('Çatışmayanları da (keçilmiş dərslər)')}</label>
        <label className="check small"><input type="checkbox" checked={weak} onChange={e => { setWeak(e.target.checked); setRep(null) }} /> {t('Şübhəlilər də')}</label>
        <ErrorBox error={err} />
        {rep && <>
          <div className="row" style={{ flexWrap: 'wrap', gap: 6 }}>
            {Object.keys(STATUS_LABEL).filter(s => sum(s)).map(s => <Pill key={s} tone={TONE[s]}>{t(STATUS_LABEL[s])}: {sum(s)}</Pill>)}
            {rep.rows.length === 0 && <span className="muted">{t('Bu dövrdə mövzu yoxdur.')}</span>}
          </div>
          <div className="tbl-wrap"><table>
            <thead><tr><th>{t('Sinif')}</th><th>{t('Tarix')}</th><th>№</th><th>{t('Mövzu')}</th><th>{t('Fayl')}</th><th>{t('Sual')}</th><th>{t('Status')}</th></tr></thead>
            <tbody>{rep.rows.map((r, i) => <tr key={i} title={t(r.reason)}>
              <td>{r.class_name}</td><td>{r.date ? fmtDate(r.date) : '—'}</td><td>{r.topic_no || r.seq}</td><td>{r.topic}</td><td>{r.file || '—'}</td><td>{r.questions || ''}</td>
              <td><Pill tone={TONE[r.status]}>{r.created ? '✓ ' : ''}{t(STATUS_LABEL[r.status] || r.status)}</Pill> <span className="muted small">{t(r.reason)}</span>
                {r.warn && <> <Pill tone="warn">⚠ {t('təkrar suallar: {n}', { n: r.warn.match(/\d+/)?.[0] ?? '' })}</Pill></>}</td></tr>)}</tbody>
          </table></div></>}
      </div>
    </Drawer>
  )
}
