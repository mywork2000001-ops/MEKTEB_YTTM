// Şagird portalının çapları (A4, ağ-qara): hər sənəddə şagirdin adı, sinfi, giriş kodu; sinif ortası adsızdır,
// başqa şagirdin adı heç yerdə yoxdur. Riyazi mətn MathML ilə (çapda və server PDF-də düzgün).
import { esc, fmtD, fmtN, head, kpis, mathHtml, printDoc, table } from '../../print'

const ml = (x: any) => (x ? (typeof x === 'string' ? x : x.az || x.ru || x.en || '') : '')
const L = 'ABCDE'
const NOTE = (t: string) => `<p class="note">${esc(t)}</p>`

export type Who = { full_name?: string; login?: string } | null | undefined
const whoLine = (me: Who, cls?: string) =>
  `<p><b>Şagird:</b> ${esc(me?.full_name || '')}${cls ? ` · <b>Sinif:</b> ${esc(cls)}` : ''}${me?.login ? ` · <b>Giriş kodu:</b> ${esc(me.login)}` : ''}</p>`

/** Nəticələrim: fənlər, yarımil qiymətləri, KSQ/BSQ (tapşırıq təhlili, təkrarlanacaq standartlar), sınaqlar, onlayn tapşırıqlar; istəyə görə səhvlər. */
export function printResults(d: any, ex: any, me: Who, withMistakes: boolean, tr: any[] = []) {
  const cls = d.subjects[0]?.class_name
  let body = head('Nəticələrim', `${fmtD(new Date().toISOString())} vəziyyəti`) + whoLine(me, cls)
  for (const s of d.subjects) {
    body += `<h2>${esc(s.subject)} <span class="muted">· ${esc(s.class_name)} · ${esc(s.teacher)}</span></h2>` +
      kpis([[fmtN(s.avg_grade, 2), 'orta qiymət'], [fmtN(s.attendance_pct) + '%', 'davamiyyət'], [fmtN(s.homework_pct) + '%', 'ev tapşırığı'],
        [s.semester_grades[1] ?? '—', 'I yarımil'], [s.semester_grades[2] ?? '—', 'II yarımil']])
    if (s.exams.length) body += table(['İmtahan', 'Tarix', 'Bal', '%', 'Qiymət', 'Tapşırıqlar (✓ düz, ✗ səhv)', 'Təkrarla – standart'],
      s.exams.map((e: any) => [`${e.kind}-${e.no} (${e.semester}-ci yarımil)`, fmtD(e.date) + (e.taken_on ? ` (sonradan: ${fmtD(e.taken_on)})` : ''),
        e.absent ? 'yox idi' : e.points != null ? `${fmtN(e.points, 1)} / ${e.max_points}` : '—', fmtN(e.pct), e.grade ?? '—',
        (e.items || []).map((it: any) => `${it.n}${it.ok ? '✓' : '✗'}`).join(' '), (e.weak_standards || []).join(', ')]), [2, 3, 4])
  }
  body += NOTE('Yarımil qiyməti = (KSQ ortası) × 0,4 + BSQ × 0,6.')
  if (tr.length) body += '<h2>Mövzu testləri</h2>' + table(['Fənn', 'Yazıb / verilən', 'Orta %', 'Son %', 'Dinamika', 'Sinifdə yer', 'Sinif ortası %'],
    tr.map((x: any) => [x.subject, `${x.wrote} / ${x.given}`, fmtN(x.avg_pct), fmtN(x.last_pct), x.delta == null ? '—' : (x.delta > 0 ? '+' : '') + fmtN(x.delta),
      x.place_class ? `${x.place_class}/${x.class_count}` : '—', fmtN(x.class_avg)]), [1, 2, 3, 4, 5, 6])
  const sin = (ex?.items || []).filter((x: any) => x.closed && x.status === 'yazıb')
  if (sin.length) body += '<h2>Sınaq imtahanları</h2>' + table(['Sınaq', 'Tarix', '%', 'Düz / səhv / boş', 'Sinifdə yer', 'Ümumi yer', 'Sinif ortası %'],
    sin.map((x: any) => [x.title, fmtD(x.opens_at), fmtN(x.pct), `${x.correct} / ${x.wrong} / ${x.blank}`, `${x.place_class}/${x.class_count}`,
      `${x.place_all}/${x.all_count}`, fmtN(x.avg_pct)]), [2, 4, 5, 6]) + (ex.delta != null ? NOTE(`Son dinamika: ${ex.delta > 0 ? '+' : ''}${fmtN(ex.delta)}%`) : '')
  if (d.tasks.length) body += '<h2>Onlayn tapşırıqlar</h2>' + table(['Tapşırıq', 'Düzgün', '%', 'Qiymət'],
    d.tasks.map((x: any) => [x.title + (x.auto_submitted ? ' (vaxt bitdi)' : ''), `${x.correct}/${x.total}`, fmtN(x.pct, 0), x.grade ?? (x.kind === 'sinaq' ? 'sınaq' : '—')]), [1, 2, 3])
  if (withMistakes && d.mistakes.length) body += '<div class="pb"></div>' + mistakesHtml(d.mistakes, false)
  body += NOTE('Sinif ortası adsız hesablanır – başqa şagirdlərin nəticəsi göstərilmir.')
  printDoc({ title: `Nəticələrim – ${me?.full_name || ''}`, body })
}

function mistakesHtml(list: any[], space: boolean) {
  return '<h2>Səhv dəftəri</h2>' + list.map((m: any, i: number) => {
    const opts = m.kind === 'mcq' && m.options ? `<div class="opts">${m.options.map((o: any, j: number) => `${L[j]}) ${mathHtml(ml(o))}`).join('<br>')}</div>` : ''
    const mine = m.kind === 'mcq' ? (m.given != null ? `${L[m.given]}) ${mathHtml(ml(m.options?.[m.given]))}` : '—') : esc(m.given || '—')
    const right = m.kind === 'mcq' ? `${L[m.correct]}) ${mathHtml(ml(m.options?.[m.correct]))}` : esc(String(m.answer).split('|')[0])
    return `<div class="q"><b>${i + 1}.</b> ${mathHtml(ml(m.text))} <span class="muted">· ${esc(m.task)}</span>${m.image ? `<img src="${esc(m.image)}" alt="">` : ''}${opts}` +
      `<p>Mənim cavabım: <b>${mine}</b> · Düzgün: <b>${right}</b></p>` +
      (m.explanation ? `<p class="note">İzah: ${mathHtml(ml(m.explanation))}</p>` : '') +
      (space ? '<p class="note">Yenidən həll:</p><div style="height:28mm;border:1px dashed #999"></div>' : '') + '</div>'
  }).join('')
}

/** Səhv dəftəri: sual, mənim cavabım, düzgün cavab, izah; istəyə görə yenidən həll üçün boş yer. */
export function printMistakes(d: any, me: Who, space: boolean) {
  printDoc({ title: `Səhv dəftəri – ${me?.full_name || ''}`,
    body: head('Səhv dəftəri', `${d.mistakes.length} sual · ${fmtD(new Date().toISOString())}`) + whoLine(me, d.subjects[0]?.class_name) + mistakesHtml(d.mistakes, space) })
}

/** Testin cavabları (təhvil verildikdən sonra): hər sual, variantlar, mənim cavabım, düzgün cavab, izah. */
export function printReview(d: any, me: Who) {
  const body = head(d.title, `Nəticə: ${d.correct}/${d.total}${d.grade ? ` → ${d.grade}` : ''}`) + whoLine(me) +
    d.questions.map((q: any, k: number) => {
      const opts = q.kind === 'mcq' ? `<div class="opts">${q.options.map((o: any, j: number) =>
        `${j === q.correct ? '<b>' : ''}${L[j]}) ${mathHtml(ml(o))}${j === q.correct ? ' ✓</b>' : ''}${j === q.given && j !== q.correct ? ' ← mənim cavabım ✗' : j === q.given ? ' ← mənim cavabım' : ''}`).join('<br>')}</div>`
        : `<p>Mənim cavabım: <b>${esc(q.given || '—')}</b> · Düzgün: <b>${esc(String(q.answer).split('|')[0])}</b></p>`
      return `<div class="q"><b>${k + 1}.</b> ${q.ok ? '✓' : '✗'} ${mathHtml(ml(q.text))}${q.image ? `<img src="${esc(q.image)}" alt="">` : ''}${opts}` +
        (q.explanation ? `<p class="note">İzah: ${mathHtml(ml(q.explanation))}</p>` : '') + '</div>'
    }).join('')
  printDoc({ title: `${d.title} – cavablar`, body })
}

/** Planım: seçilmiş dövrdə dərslər – tarix, saat, fənn, mövzu, qiymətləndirmə. */
export function printPlan(d: any, me: Who, period: string, examLabel: (l: any) => string) {
  const body = head('Dərs planım', `${period}: ${fmtD(d.from)} – ${fmtD(d.to)}`) + whoLine(me) +
    (d.items.length ? table(['Tarix', 'Saat', 'Fənn', 'Mövzu', 'Ev tapşırığı', 'Qiymətləndirmə', 'Qeyd'], d.items.map((i: any) => [
      `${i.weekday || ''} ${fmtD(i.date)}`, i.time || '', i.subject + (i.group ? ` (${i.class_name})` : ''), (i.plan_seq ? `№${i.plan_seq} ` : '') + (i.topic || '—'),
      i.homework || '', examLabel(i), [i.taught && 'keçilib ✓', i.held && 'mövzu davam edir', i.tt_pages && `dərslik: ${i.tt_pages}`].filter(Boolean).join('; ')]))
      : NOTE('Bu dövrdə dərs yoxdur.'))
  printDoc({ title: `Dərs planım ${fmtD(d.from)}–${fmtD(d.to)}`, body })
}

/** Gündəlik: günün dərsləri – mövzu, ev tapşırığı, davamiyyət, qiymət, müəllimin rəyi. */
export function printDay(d: any, me: Who, date: string, examLabel: (l: any) => string) {
  const ATT: Record<string, string> = { var: 'dərsdə idim', yox: 'qayıb', 'üzrlü': 'üzrlü', gecikdi: 'gecikdim' }
  const body = head('Gündəliyim', `${d.weekday ? d.weekday + ' · ' : ''}${fmtD(date)}`) + whoLine(me) +
    (d.lessons.length ? table(['Saat', 'Fənn', 'Mövzu', 'Ev tapşırığı', 'Davamiyyət', 'Qiymət', 'Müəllimin rəyi'], d.lessons.map((l: any) => [
      l.time || '', `${l.subject}${examLabel(l) ? ` (${examLabel(l)})` : ''}`, l.topic || '—', l.homework || '—', l.attendance ? ATT[l.attendance] || l.attendance : '',
      l.marks.map((m: any) => `${m.kind}: ${m.grade}${m.kind === 'test' ? ` (${m.test_correct}/${m.test_total})` : ''}`).join('; '),
      l.marks.filter((m: any) => m.comment).map((m: any) => m.comment).join('; ')]))
      : NOTE('Bu gün dərs yoxdur.')) + '<p class="sign">Valideyn: ____________</p>'
  printDoc({ title: `Gündəliyim – ${fmtD(date)}`, body })
}
