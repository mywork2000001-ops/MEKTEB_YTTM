import { useT } from '../../i18n'
import { Top } from '../../ui'
import { LookPanel, PasswordPanel } from '../shared'

export default function Settings() {
  const t = useT()
  return (
    <>
      <Top title={t('Tənzimləmələr')} />
      <div className="stack">
        <PasswordPanel student />
        <LookPanel />
      </div>
    </>
  )
}
