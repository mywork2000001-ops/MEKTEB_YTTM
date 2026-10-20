// «Sinif rəhbəri» qrupunun tabları: fənlər üzrə müvəffəqiyyət / əlaçı-zərbəçi və davamiyyət hesabatı (Homeroom.tsx / HomeroomAttendance.tsx-dən köçürülüb).
import { get } from '../../../api'
import { ErrorBox, Loading, useLoad } from '../../../ui'
import { useT } from '../../../i18n'
import { Month } from '../HomeroomAttendance'
import { HomeroomPeriodAttendance, HomeroomSuccess } from './HomeroomReports'
import type { Sem } from './common'

export default function HomeroomTabs({ cid, sem, tab }: { cid: number; sem: Sem; tab: 'success' | 'attendance' }) {
  const t = useT()
  const [h, err, loading] = useLoad<any>(() => get(`/api/homeroom/${cid}`, sem === 'all' ? {} : { semester: sem }), [cid, sem])
  if (err) return <ErrorBox error={err} />
  if (loading && !h) return <Loading />
  if (!h) return null
  return tab === 'success' ? <HomeroomSuccess h={h} /> : (
    <>
      <Month cid={cid} className={h.class.name} />
      <h2 style={{ margin: '20px 0 8px', fontSize: 16 }}>{t('Dövr üzrə (seçilmiş yarımil)')}</h2>
      <HomeroomPeriodAttendance h={h} />
    </>
  )
}
