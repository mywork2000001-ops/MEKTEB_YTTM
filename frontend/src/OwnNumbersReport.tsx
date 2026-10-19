// «Hər şagirdə öz rəqəmləri» hesabatı: neçə sualda ədəd dəyişdi, hansılar dəyişmir və niyə (server: own_numbers hesabatı).
import { useT } from './i18n'
import { Disclosure } from './ui'

export type OwnReport = { changed: number; fixed: number; items: { slot: number; changed: boolean; reason: string | null }[] }

export default function OwnNumbersReport({ r }: { r: OwnReport | null | undefined }) {
  const t = useT()
  if (!r) return null
  return (
    <div className="card" style={{ margin: '8px 0' }}>
      <div style={{ fontWeight: 600 }}>{t('🔢 {n} sualda rəqəmlər dəyişdi, {m} sual dəyişmir', { n: r.changed, m: r.fixed })}</div>
      <Disclosure variant="flat" title={t('Hansı suallar və niyə')} style={{ marginTop: 6 }}>
        <ul className="small" style={{ margin: '6px 0 0', paddingLeft: 18 }}>
          {r.items.map(x => (
            <li key={x.slot}>{x.changed ? t('Sual {n}: rəqəmlər dəyişdi', { n: x.slot }) : t('Sual {n}: dəyişmir ({r})', { n: x.slot, r: t(x.reason || '—') })}</li>))}
        </ul>
      </Disclosure>
      <div className="muted small" style={{ marginTop: 6 }}>{t('Hər şagirdin öz açarı var – açar çapında hər vərəq üçün ayrıca cavablar göstərilir')}</div>
    </div>
  )
}
