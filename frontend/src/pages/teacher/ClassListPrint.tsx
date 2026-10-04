// Sinif və qrupların şagird siyahısının çapı: ad siyahısı, IX balları ilə, boş qeyd cədvəli (davamiyyət/qiymət üçün).
// Qrupda (bölünmə / tədris) şagirdin öz sinfi göstərilir; bir sinif/qrup və ya bütün sinif və qruplarım – hər biri yeni səhifədən.
import { useState } from 'react'
import { get } from '../../api'
import { useAuth } from '../../auth'
import { AsyncBtn, Drawer, Field, Seg } from '../../ui'
import { esc, fmtD, fmtN, head, printLater, SIGN, signs, table } from '../../print'
import { kindLabel } from './common'

type C = { id: number; name: string; code: string; kind: string; parent_id: number | null; homeroom?: { id: number; name: string } | null }
type S = { id: number; full_name: string; birth_date: string | null; gender: string | null; portal_code: string; class_name: string
  score_language: number | null; score_math: number | null; score_foreign: number | null; score_total: number | null }
type Fmt = 'names' | 'scores' | 'grid'

const az = (a: S, b: S) => a.full_name.localeCompare(b.full_name, 'az')

export default function ClassListPrint({ cls, all, onClose }: { cls: C; all: C[]; onClose: () => void }) {
  const { me } = useAuth()
  const [fmt, setFmt] = useState<Fmt>('names')
  const [scope, setScope] = useState<'one' | 'all'>('one')
  const [cols, setCols] = useState({ code: true, birth: true, gender: false, cls: cls.kind === 'qrup' && !cls.parent_id })
  const [n, setN] = useState('15')
  const isGroup = (c: C) => c.kind === 'qrup'

  const body = (c: C, rows: S[]) => {
    rows = [...rows].sort(az)
    const parent = c.parent_id ? all.find(x => x.id === c.parent_id)?.name : null
    const sub = [kindLabel(c) + (parent ? ` (${parent})` : ''), `ID: ${c.code}`, `${rows.length} şagird`, `${fmtD(new Date().toISOString())} vəziyyəti`].join(' · ')
    const showCls = cols.cls || (isGroup(c) && !c.parent_id)                 // tədris qrupu – müxtəlif siniflərdən
    const who = c.homeroom && !isGroup(c) ? SIGN.homeroom(c.homeroom.name) : SIGN.teacher(me?.full_name)
    let t = ''
    if (fmt === 'names') {
      const h = ['№', 'Şagird', ...(showCls ? ['Sinif'] : []), ...(cols.code ? ['Giriş kodu'] : []), ...(cols.birth ? ['Doğum tarixi'] : []), ...(cols.gender ? ['Cins'] : [])]
      t = table(h, rows.map((s, i) => [i + 1, s.full_name, ...(showCls ? [s.class_name] : []), ...(cols.code ? [s.portal_code] : []),
        ...(cols.birth ? [fmtD(s.birth_date)] : []), ...(cols.gender ? [s.gender || ''] : [])]), [])
    } else if (fmt === 'scores') {
      t = table(['№', 'Şagird', ...(showCls ? ['Sinif'] : []), 'Giriş kodu', 'IX: dil', 'IX: riyaziyyat', 'IX: xarici', 'Yekun'],
        rows.map((s, i) => [i + 1, s.full_name, ...(showCls ? [s.class_name] : []), s.portal_code, fmtN(s.score_language), fmtN(s.score_math),
          fmtN(s.score_foreign), fmtN(s.score_total)]), showCls ? [4, 5, 6, 7] : [3, 4, 5, 6])
    } else {
      const k = Number(n)
      t = `<table class="grid-p"><thead><tr><th>№</th><th>Şagird</th>${showCls ? '<th>Sinif</th>' : ''}${'<th></th>'.repeat(k)}</tr></thead><tbody>` +
        rows.map((s, i) => `<tr><td>${i + 1}</td><td>${esc(s.full_name)}</td>${showCls ? `<td>${esc(s.class_name)}</td>` : ''}${'<td></td>'.repeat(k)}</tr>`).join('') +
        '</tbody></table><p class="note">Boş sütunlar – tarix, davamiyyət və ya qiymət qeydi üçün.</p>'
    }
    const title = fmt === 'grid' ? 'qeyd cədvəli' : fmt === 'scores' ? 'şagird siyahısı (IX sinif balları ilə)' : 'şagird siyahısı'
    return head(`${c.name}${isGroup(c) ? '' : ' sinfi'} – ${title}`, sub) + t + signs([who])
  }

  const run = async () => {
    const list = scope === 'all' ? all : [cls]
    const w = printLater()
    if (!w) return
    try {
      const parts: string[] = []
      for (const [i, c] of list.entries()) {
        const rows = await get<S[]>('/api/students', { class_id: String(c.id) })
        parts.push((i ? '<div class="pb"></div>' : '') + body(c, rows))
      }
      w.show({ title: scope === 'all' ? 'Şagird siyahıları – bütün sinif və qruplarım' : `${cls.name} – şagird siyahısı`,
        body: parts.join(''), landscape: fmt === 'grid' && Number(n) > 12 })
    } catch (e) { w.fail((e as Error).message) }
  }

  return (
    <Drawer title={`Şagird siyahısının çapı – ${cls.name}`} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Bağla</button><AsyncBtn className="btn primary" onClick={run}>Çap / PDF</AsyncBtn></>}>
      <div className="stack">
        <div className="stack" style={{ gap: 5 }}><span className="small muted">Format</span><Seg value={fmt} onChange={setFmt} options={[['names', 'Ad siyahısı'], ['scores', 'IX balları ilə'], ['grid', 'Boş qeyd cədvəli']]} /></div>
        {fmt === 'names' && <fieldset style={{ margin: 0 }}><legend>Sütunlar</legend>
          <label className="check"><input type="checkbox" checked={cols.code} onChange={e => setCols({ ...cols, code: e.target.checked })} /> Giriş kodu (ID)</label>
          <label className="check"><input type="checkbox" checked={cols.birth} onChange={e => setCols({ ...cols, birth: e.target.checked })} /> Doğum tarixi</label>
          <label className="check"><input type="checkbox" checked={cols.gender} onChange={e => setCols({ ...cols, gender: e.target.checked })} /> Cins</label>
          <label className="check"><input type="checkbox" checked={cols.cls} onChange={e => setCols({ ...cols, cls: e.target.checked })} /> Şagirdin sinfi (tədris qrupunda həmişə)</label>
        </fieldset>}
        {fmt === 'grid' && <Field label="Boş sütun sayı" hint="12-dən çox olsa – albom (yatıq) A4">
          <select value={n} onChange={e => setN(e.target.value)}>{[6, 10, 12, 15, 20, 25].map(x => <option key={x}>{x}</option>)}</select></Field>}
        <div className="stack" style={{ gap: 5 }}><span className="small muted">Nəyi çap edək</span><Seg value={scope} onChange={setScope} options={[['one', `Yalnız ${cls.name}`], ['all', `Bütün sinif və qruplarım (${all.length})`]]} /></div>
        <p className="small muted">A4, ağ-qara · şagirdlər əlifba sırası ilə · qrupda növü (bölünmə / tədris) və ana sinif başlıqda · altbilgidə tarix və səhifə nömrəsi.</p>
      </div>
    </Drawer>
  )
}
