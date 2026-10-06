// «Uğurlarım»: səviyyə/XP, seriya, həftəlik hədəf, nişanlar, bölmələr üzrə proqres və sertifikatlar (docs/sertifikat-ve-motivasiya-promtu.md).
// Hamısı yalnız şagirdin özünə görünür; sertifikat şagirdin hesabına bağlıdır – yeni sertifikat tətbiq açılanda özü göstərilir.
import { useEffect, useState } from 'react'
import { get, post } from '../../api'
import { CertView, confetti, printCert, shareCert, type Cert } from '../../certificate'
import { Drawer, ErrorBox, Loading, Top, useLoad } from '../../ui'

type Ach = {
  xp: number; level: number; level_name: string; level_from: number; level_to: number | null; streak: number; best_streak: number
  tests: number; avg_pct: number | null; badges: { key: string; icon: string; title: string; how: string; earned: boolean }[]
  week: { total: number; done: number }; sections: { section: string; pct: number; tests: number }[]
  certificates: number; new_certificates: number
}
const tone = (p: number) => (p >= 85 ? 'var(--ok)' : p >= 60 ? 'var(--warn)' : 'var(--bad)')

export function Bar({ value, max, color }: { value: number; max: number; color?: string }) {
  return <div className="cmp" style={{ height: 10 }}><i style={{ width: `${Math.max(2, Math.min(100, (value * 100) / (max || 1)))}%`, background: color }} /></div>
}

export default function Achievements() {
  const [a, err] = useLoad<Ach>(() => get('/api/portal/achievements'), [])
  const [certs, err2, , reload] = useLoad<Cert[]>(() => get('/api/portal/certificates'), [])
  const [open, setOpen] = useState<Cert | null>(null)
  return (
    <>
      <Top title="Uğurlarım" sub="Səviyyən, nişanların və sertifikatların – yalnız sən görürsən" />
      <ErrorBox error={err || err2} />
      {!a ? <Loading /> : (
        <div className="stack">
          <section className="panel">
            <div className="row" style={{ alignItems: 'center', gap: 16 }}>
              <div style={{ width: 64, height: 64, borderRadius: '50%', display: 'grid', placeItems: 'center', fontSize: 26, fontWeight: 900, color: '#fff',
                background: 'linear-gradient(135deg,#8b5cf6,#3b82f6)' }}>{a.level}</div>
              <div className="grow"><b style={{ fontSize: 18 }}>{a.level_name}</b><div className="small muted">{a.xp} XP{a.level_to ? ` · növbəti səviyyəyə ${a.level_to - a.xp} XP` : ' · ən yüksək səviyyə'}</div>
                {a.level_to && <div style={{ marginTop: 6 }}><Bar value={a.xp - a.level_from} max={a.level_to - a.level_from} color="linear-gradient(90deg,#8b5cf6,#3b82f6)" /></div>}</div>
            </div>
            <div className="kpis" style={{ marginTop: 12 }}>
              <div className="kpi"><b>🔥 {a.streak}</b><span>seriya (ən yaxşı {a.best_streak})</span></div>
              <div className="kpi"><b>{a.tests}</b><span>test yazılıb</span></div>
              <div className="kpi"><b>{a.avg_pct != null ? a.avg_pct + '%' : '—'}</b><span>orta nəticə</span></div>
              <div className="kpi"><b>🏆 {a.certificates}</b><span>sertifikat</span></div>
            </div>
          </section>
          <section className="panel"><h2>Həftəlik hədəf</h2>
            {a.week.total ? <><div className="row small"><span className="grow">Bu həftə {a.week.total} test – yazılıb {a.week.done}</span>{a.week.done >= a.week.total && <b style={{ color: 'var(--ok)' }}>✓ Hədəf tamamlandı!</b>}</div>
              <Bar value={a.week.done} max={a.week.total} color={a.week.done >= a.week.total ? 'var(--ok)' : undefined} /></>
              : <p className="small muted" style={{ margin: 0 }}>Bu həftə test yoxdur.</p>}
          </section>
          <section className="panel"><h2>Nişanlar<small>{a.badges.filter(b => b.earned).length}/{a.badges.length}</small></h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(140px,1fr))', gap: 8 }}>
              {a.badges.map(b => (
                <div key={b.key} title={b.how} style={{ border: '1px solid var(--line)', borderRadius: 12, padding: 10, textAlign: 'center', opacity: b.earned ? 1 : 0.45,
                  background: b.earned ? 'var(--accent-soft)' : undefined, filter: b.earned ? undefined : 'grayscale(1)' }}>
                  <div style={{ fontSize: 28 }}>{b.icon}</div><b className="small">{b.title}</b><div className="small muted" style={{ fontSize: 11 }}>{b.how}</div>
                </div>))}
            </div>
          </section>
          {a.sections.length > 0 && <section className="panel"><h2>Bölmələr üzrə proqres</h2>
            {a.sections.map(s => (
              <div key={s.section} style={{ marginBottom: 8 }}>
                <div className="row small"><span className="grow">{s.section}</span><b style={{ color: tone(s.pct) }}>{s.pct}%</b><span className="muted">· {s.tests} test</span></div>
                <Bar value={s.pct} max={100} color={tone(s.pct)} />
                {s.pct < 75 && <span className="small muted">Növbəti hədəf: 75%</span>}
              </div>))}
          </section>}
          <section className="panel"><h2>Sertifikatlarım<small>{certs?.length ?? 0}</small></h2>
            {!certs ? <Loading /> : certs.length === 0 ? <p className="small muted" style={{ margin: 0 }}>Mövzu testində 90%-dən, sınaqda 80%-dən yuxarı nəticə və ya sinifdə ilk yerlər – sertifikat gətirir.</p> : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(220px,1fr))', gap: 10 }}>
                {certs.map(c => (
                  <button key={c.id} className="panel click" style={{ textAlign: 'left', margin: 0 }} onClick={() => setOpen(c)}>
                    <div style={{ fontSize: 24 }}>🏆</div><b>{c.title}</b>
                    <div className="small muted">{new Date(c.issued_at).toLocaleDateString('az-AZ')}{c.details.pct != null ? ` · ${Math.round(c.details.pct)}%` : ''}{c.details.place ? ` · ${c.details.place}-ci yer` : ''}</div>
                  </button>))}
              </div>)}
          </section>
        </div>)}
      {open && <CertDrawer c={open} onClose={() => { setOpen(null); reload() }} />}
    </>
  )
}

export function CertDrawer({ c, onClose, title }: { c: Cert; onClose: () => void; title?: string }) {
  return (
    <Drawer title={title || 'Sertifikat'} onClose={onClose}
      footer={<><button className="btn" onClick={() => shareCert(c)}>Paylaş</button><button className="btn primary" onClick={() => printCert(c)}>Çap / PDF</button></>}>
      <CertView c={c} />
      <p className="small muted">Yoxlama kodu: <b>{c.code}</b> – QR kodu oxudanda sertifikatın həqiqi olduğu görünür.</p>
    </Drawer>
  )
}

/** Tətbiq açılanda yeni sertifikat varsa – özü göstərilir (təbriklə), bağlananda «görüldü». */
export function CertNudge() {
  const [c, setC] = useState<Cert | null>(null)
  useEffect(() => {
    get<Cert[]>('/api/portal/certificates').then(l => { const n = l.find(x => x.new); if (n) { setC(n); confetti() } }, () => {})
  }, [])
  if (!c) return null
  return <CertDrawer c={c} title="🎉 Təbriklər! Yeni sertifikat" onClose={() => { setC(null); post('/api/portal/certificates/seen').catch(() => {}) }} />
}
