import { esc, fmtD, head, printDoc, table } from './print'
import { ml, tt } from './i18n'

export type CardData = {
  student_id: number; full_name: string; code: string
  exam: { kind: string; no: number; extra_seq: number; max_points: number; date: string }
  questions: { slot: number; kind: string; text: any; key: string; points: number; ref?: string | null }[]
  sources: Record<string, { points: number | null; grade: number | null; answers: Record<string, { value: string; ok: boolean | null; void: boolean; earned: number | null }> }>
  final: { points: number | null; grade: number | null; chosen: string | null }
}

const plain = (x: any) => String(ml(x) ?? '').replace(/\s+/g, ' ').slice(0, 90)

/** «🖨 Cavab kartlarını çap et»: hər şagirdə 1 səhifə – ad, variant, sual cədvəli (cavab, düz cavab, ✓/✗), bal, qiymət.
 *  withRef – müəllim nüsxəsində sualın bank ünvanı (şagird vərəqində yox). */
export function printCards(title: string, cls: string, cards: CardData[], withRef = true) {
  const body = cards.map(c => {
    // cədvəl üçün mənbə: jurnala gedən balı verən (yoxdursa kağız, sonra onlayn)
    const srcs = Object.entries(c.sources)
    const pick = srcs.find(([, s]) => s.points === c.final.points) || srcs.find(([k]) => k === 'paper') || srcs[0]
    const a = pick?.[1].answers || {}
    const rows = c.questions.map(q => {
      const r = a[q.slot]
      return [q.slot, plain(q.text) + (withRef && q.ref ? `  [${q.ref}]` : ''), r?.value || '—', q.key, r?.void ? '⊘' : r?.ok ? '✓' : '✗', r?.void ? '' : r?.earned ?? '']
    })
    const both = srcs.length > 1 ? `<p class="sub">${esc(tt('Onlayn'))}: ${esc(c.sources.online?.points ?? '—')} · ${esc(tt('Yazılı'))}: ${esc(c.sources.paper?.points ?? '—')}</p>` : ''
    return `<section style="page-break-after:always">${head(`${cls} – ${title}`, `${c.full_name} · ${tt('variant')} ${c.code} · ${fmtD(c.exam.date)}`)}` +
      table(['№', tt('Sual'), tt('Cavabın'), tt('Düz cavab'), '', tt('Bal')], rows, [0, 5]) + both +
      `<p><b>${esc(tt('Bal'))}: ${esc(c.final.points ?? '—')}</b> · <b>${esc(tt('Qiymət'))}: ${esc(c.final.grade ?? '—')}</b></p></section>`
  }).join('')
  printDoc({ title: `${cls} – ${title}`, body })
}
