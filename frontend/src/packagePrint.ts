// Nəticə paketi (kartın skanı + öz testi, altmövzu və №) – çap / PDF. Mövcud mexanizm: print.ts (printDoc – önbaxış + «PDF yüklə»,
// downloadPdf – serverdə Chromium; yalnız data: şəkillər, ona görə kart şəkli data-URL kimi qoyulur).
import { downloadPdf, esc, fmtD, mathHtml, printDoc } from './print'
import { ml } from './i18n'

export type Pkg = {
  exam: { kind: string; no: number; extra_seq: number; date: string; subject?: string | null; title?: string | null }
  code: string
  scan: { scan_id: number; image: boolean; online: boolean; source: string }
  questions: { n: number; kind: string; my_answer: string; void: boolean; text?: any; image?: string | null; options?: any[] | null; key?: string
    ok?: boolean | null; points?: number; earned?: number | null; topic?: string | null; topic_no?: string | null; explanation?: any }[]
  total: { points: number | null; max: number; pct: number | null; grade: number | null } | null
  published: boolean
  full_name?: string
}

const LET = 'ABCDEFGH'

/** Kart şəklini kiçildilmiş data-URL kimi (PDF serverinə xarici sorğu icazəsi yoxdur; HTML 4 MB-dan böyük olmasın). */
export async function imageData(url: string, maxW = 900, q = 0.6): Promise<string | null> {
  try {
    const r = await fetch(url, { credentials: 'same-origin' })
    if (!r.ok) return null
    const bmp = await createImageBitmap(await r.blob())
    const k = Math.min(1, maxW / bmp.width)
    const c = document.createElement('canvas')
    c.width = Math.round(bmp.width * k); c.height = Math.round(bmp.height * k)
    c.getContext('2d')!.drawImage(bmp, 0, 0, c.width, c.height)
    return c.toDataURL('image/jpeg', q)
  } catch { return null }
}

/** Bir şagirdin paketi: başlıq, bal, kart şəkli, test kağızdakı sıra ilə (sual, variantlar, öz/düz cavab), altında «Altmövzu: … · №n». */
export function packageSection(p: Pkg, img: string | null, T: (s: string) => string, first: boolean): string {
  const ex = p.exam
  const label = `${ex.kind}-${ex.no}${ex.extra_seq ? ` · ${T('əlavə')} ${ex.extra_seq}` : ''}`
  const t = p.total
  const head = `<h2>${esc(label)}${ex.subject ? ' · ' + esc(ex.subject) : ''} · ${esc(fmtD(ex.date))}</h2>` +
    `<p class="sub">${p.full_name ? `<b>${esc(p.full_name)}</b> · ` : ''}${esc(T('variant'))} ${esc(p.code)}` +
    (t && t.points != null ? ` · <b>${esc(T('Bal'))}: ${esc(t.points)} / ${esc(t.max)}</b>${t.grade ? ` · <b>${esc(T('Qiymət'))}: ${esc(t.grade)}</b>` : ''}` : '') + '</p>'
  const card = img ? `<p><img src="${img}" alt="" style="max-width:100%;max-height:120mm"></p>` : ''
  const qs = p.questions.map(q => {
    const opts = (q.options || []).map((o, i) => {
      const l = LET[i]
      const mine = q.my_answer === l, right = q.key === l
      return `<div>${mine ? (right ? '✓ ' : '✗ ') : right ? '→ ' : '&nbsp;&nbsp;&nbsp;'}<b>${l})</b> ${mathHtml(String(ml(o) ?? ''))}</div>`
    }).join('')
    const status = q.void ? esc(T('sayılmır')) : `${q.ok ? '✓' : '✗'} ${esc(q.earned ?? 0)} / ${esc(q.points ?? '')}`
    const sub = q.topic ? `<div class="note">${esc(T('Altmövzu'))}: ${esc(q.topic)}${q.topic_no ? ' · ' + esc(q.topic_no) : ''}</div>` : ''
    const expl = q.explanation ? `<div class="note">${esc(T('İzah'))}: ${mathHtml(String(ml(q.explanation) ?? ''))}</div>` : ''
    return `<div class="q"><b>${q.n}.</b> ${mathHtml(String(ml(q.text) ?? ''))}${q.image ? `<img src="${esc(q.image)}" alt="">` : ''}` +
      `<div class="opts">${opts}</div><div class="note">${esc(T('Sənin cavabın'))}: <b>${esc(q.my_answer || '—')}</b> · ${esc(T('Düz cavab'))}: <b>${esc(q.key || '—')}</b> · ${status}</div>${sub}${expl}</div>`
  }).join('')
  return `<section class="${first ? '' : 'pb'}">${head}${card}${qs}</section>`
}

/** Şagirdin öz paketi – PDF yüklənir (şagirdin dilində). */
export async function downloadPackagePdf(p: Pkg, imgUrl: string | null, T: (s: string) => string) {
  const img = p.scan.image && imgUrl ? await imageData(imgUrl) : null
  const label = `${p.exam.kind}-${p.exam.no}`
  await downloadPdf({ title: `${label} ${T('nəticə paketi')}`, body: packageSection(p, img, T, true) })
}

/** Müəllim: bütün sinif, hər şagird ayrıca səhifədən (rəsmi çap – Azərbaycan dili). Kart şəkilləri kiçildilir; HTML çox böyüyürsə atılır. */
export async function printPackages(cls: string, subject: string, pkgs: (Pkg & { full_name: string })[], imgBase: string) {
  const T = (s: string) => s
  const imgs = await Promise.all(pkgs.map(p => p.scan.image ? imageData(`${imgBase}/${p.scan.scan_id}`, 700, 0.55) : Promise.resolve(null)))
  const size = imgs.reduce((a, x) => a + (x?.length || 0), 0)
  const use = size < 2_500_000
  const body = pkgs.map((p, i) => packageSection(p, use ? imgs[i] : null, T, i === 0)).join('')
  printDoc({ title: `${cls} – ${subject} – nəticə paketləri`, body })
}
