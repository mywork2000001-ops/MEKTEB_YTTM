// KSQ/BSQ kağız variantları: hər şagirdə bir A4 vərəq (iki üz) + cavab kartı (docs/ksq-bsq-kagiz-promtu.md §3).
// Ön üz: başlıq + suallar 1–16; arxa üz: 17–30 + cavab kartı (4 küncdə marker, imzalı QR, test dairələri, açıq cavab xanaları).
// Sığmazsa şrift avtomatik kiçilir (açılan pəncərədə ölçülür). Rəsmi çap – başlıqlar AZ, suallar şagirdin dilində.
import QRCode from 'qrcode'
import { esc, fmtD, mathHtml } from './print'
import { toast } from './ui'
import { tt } from './i18n'

export type KsqQ = { slot: number; kind: 'mcq' | 'open' | 'score'; points: number; text: string; options: string[] | null; image?: string | null }
export type KsqSheet = { student_id: number; full_name: string; code: string; lang: string; qr: string; questions: KsqQ[] }
export type KsqPrint = {
  exam: { id: number; kind: string; no: number; semester: number; date: string; class_name: string; subject: string; school: string; teacher: string
    title?: string | null; label?: string }
  sheets: KsqSheet[]; key: { code: string; full_name: string; answers: { slot: number; value: string; points: number; topic?: string | null; ref?: string | null }[] }[]
}

const L = 'ABCDE'
const SCORE = ['0', '¼', '½', '¾', '1']          // «Müəllim balı» dairələri (həlli yazılan suallar; skan oxuyur)
/** Ümumi vərəqənin adı: sınağın/işin adı, yoxsa «KSQ-1» */
const nm = (ex: KsqPrint['exam']) => (ex.title && ex.title.trim()) || ex.label || `${ex.kind}-${ex.no}`
const front = (n: number) => Math.ceil(n * 16 / 30)   // ön üzdə ~53% (30 sualda 1–16)
const CELLS = 8                     // açıq cavab xanaları (backend CARD_MAX)
const HELP: Record<string, string> = {
  az: 'Test (1–9): düzgün cavabın dairəsini tam qaralayın (düzgün ●, səhv ⊗ ✓). Açıq (10–30): hər xanaya bir simvol, soldan: 0–9  -  ,  /  ;   Nümunə: 3/7 · 2,5 · -4 · 1;4',
  ru: 'Тест (1–9): полностью закрасьте кружок верного ответа (верно ●, неверно ⊗ ✓). Открытые (10–30): по одному символу в клетку, слева: 0–9  -  ,  /  ;   Пример: 3/7 · 2,5 · -4 · 1;4',
  en: 'Test (1–9): fill the circle of the correct answer completely (right ●, wrong ⊗ ✓). Open (10–30): one character per box, from the left: 0–9  -  ,  /  ;   Example: 3/7 · 2,5 · -4 · 1;4',
}

/** Kartın izahı – sual növlərinə görə; yalnız test olanda açıq hissə yazılmır (DİM sinif testi, 13.10.2026). */
function help(lang: string, kinds: string[]): string {
  const n = kinds.length, nMcq = kinds.filter(k => k === 'mcq').length, nOpen = kinds.filter(k => k === 'open').length
  const h = (HELP[lang] || HELP.az).replace('1–9', `1–${nMcq}`).replace('10–30', `${nMcq + 1}–${nMcq + nOpen}`)
  const base = nOpen === 0 ? h.split('.')[0] + '.' : h
  return nMcq === 0 && nOpen === 0 && n ? '' : base
}

const CSS = `
@page{size:A4;margin:8mm}
*{box-sizing:border-box}
body{margin:0;font-family:Arial,Helvetica,sans-serif;color:#000;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.side{width:194mm;height:280mm;overflow:hidden;position:relative;display:flex;flex-direction:column;page-break-after:always;break-after:page}
.side:last-child{page-break-after:auto;break-after:auto}
@media screen{body{background:#e5e7eb;padding:8px}.side{background:#fff;margin:0 auto 10px;padding:0;box-shadow:0 0 0 1px #bbb}}
.band{display:flex;justify-content:space-between;align-items:center;background:#1f2937;color:#fff;border-radius:2.5mm;padding:2mm 4mm;font-size:9pt;margin-bottom:2mm}
.band b.t{font-size:14pt;letter-spacing:.04em}
.who{display:flex;gap:3mm;align-items:stretch;margin-bottom:2.5mm;font-size:9pt}
.who .nm{flex:1;border:1px solid #000;border-radius:2mm;padding:1.5mm 3mm}.who .nm b{font-size:11.5pt}
.who .sc{display:flex;gap:2mm}.who .sc div{border:1.2px solid #000;border-radius:2mm;padding:1mm 3mm;min-width:20mm;text-align:center;font-size:8pt}
.who .sc div b{display:block;font-size:12pt;line-height:6mm;color:#bbb}
.hd{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:1.5px solid #000;padding-bottom:1.5mm;margin-bottom:2mm;font-size:8.5pt;gap:4mm}
.qs{flex:1 1 0;min-height:0;column-count:2;column-gap:6mm;column-fill:balance;column-rule:.5px solid #bbb;font-size:10pt;line-height:1.28;overflow:hidden}
.q{break-inside:avoid;margin:0 0 2.2mm}
.q .n{display:inline-flex;align-items:center;justify-content:center;min-width:5.2mm;height:5.2mm;border-radius:50%;background:#1f2937;color:#fff;font-weight:700;font-size:.8em;margin-right:1.2mm;padding:0 .8mm}
.q .p{float:right;font-size:.8em;border:1px solid #000;border-radius:2mm;padding:0 1.2mm;margin-left:1.5mm}
.q ol{margin:.6mm 0 0;padding:0;list-style:none;display:flex;flex-wrap:wrap;gap:.4mm 4mm}
.q img{max-width:100%;max-height:30mm;display:block;margin:1mm 0}
.card{position:relative;flex:0 0 auto;height:114mm;border-top:1.2px dashed #000;padding:8mm 10mm 5mm;margin-top:2mm}
.cut{position:absolute;top:-3mm;left:50%;transform:translateX(-50%);background:#fff;font-size:7pt;padding:0 2mm}
.mk{position:absolute;width:6mm;height:6mm;background:#000}
.ctop{display:flex;gap:4mm;align-items:flex-start;margin-bottom:2mm}
.ctop img{width:22mm;height:22mm}
.cinfo{font-size:9pt;line-height:1.35;flex:1}
.cinfo .nm{font-size:11.5pt;font-weight:700}
.help{font-size:7.5pt;margin-top:1mm;color:#222}
.mcq{display:grid;grid-template-columns:repeat(3,1fr);gap:1.6mm 6mm;margin-bottom:2.5mm}
.row{display:flex;align-items:center;gap:1.6mm;font-size:9pt}
.row .no{width:6mm;text-align:right;font-weight:700}
.bub{width:5mm;height:5mm;border:1.1px solid #000;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:6.5pt;color:#777}
.open{display:grid;grid-template-columns:repeat(3,1fr);gap:1.8mm 4mm}
.bx{display:flex}
.box{width:5.4mm;height:6mm;border:1.1px solid #000;display:block;flex:0 0 auto;margin-left:-1.1px}
.box:first-of-type{margin-left:0}
.ln{display:inline-block;border-bottom:1px solid #000;height:4.5mm;vertical-align:bottom}
.scoreh{font-size:8pt;font-weight:700;margin:2mm 0 1mm}
.cfoot{position:absolute;left:10mm;right:10mm;bottom:5mm;display:flex;justify-content:space-between;font-size:8pt}
.cinfo .bx{display:inline-flex;vertical-align:middle}
.bk{column-count:2;column-gap:6mm;column-rule:.5px solid #bbb;font-size:10pt;line-height:1.3;padding:2mm}
.bkh{border-bottom:1.5px solid #000;margin-bottom:3mm;padding:2mm;display:flex;justify-content:space-between}
.key table{border-collapse:collapse;width:100%;font-size:8.5pt;margin-bottom:5mm;break-inside:avoid}
.key td,.key th{border:1px solid #000;padding:.6mm 1mm;text-align:center}
.key th{background:#eee}
`

function question(q: KsqQ): string {
  const opts = q.kind === 'mcq' && q.options?.length
    ? `<ol>${q.options.map((o, i) => `<li><b>${L[i]})</b> ${mathHtml(o)}</li>`).join('')}</ol>` : ''
  const pts = String(q.points).replace('.', ',')
  return `<div class="q"><span class="p">${pts} b</span><span class="n">${q.slot}</span>${mathHtml(q.text)}${q.image ? `<img src="${esc(q.image)}" alt="">` : ''}${opts}</div>`
}

/** Ümumi cavab vərəqəsi (bütün növlər: mövzu testi, sınaq, sərbəst iş, KSQ, BSQ): başlıq + QR/kod + şagird + A–E + 8 xana +
 *  «Müəllim balı» + yekun bal/imza + 4 künc oriyentiri. QR sol-üstdə, cavab zonası onun altında (ksq_scan.ZONE ilə eyni). */
function card(s: KsqSheet, ex: KsqPrint['exam'], qr: string): string {
  const blank = s.student_id === 0
  const mcq = s.questions.filter(q => q.kind === 'mcq'), open = s.questions.filter(q => q.kind === 'open'), score = s.questions.filter(q => q.kind === 'score')
  const mk = ['top:2mm;left:2mm', 'top:2mm;right:2mm', 'bottom:2mm;left:2mm', 'bottom:2mm;right:2mm'].map(p => `<i class="mk" style="${p}"></i>`).join('')
  const who = blank
    ? `<div class="nm">Ad, soyad: <span class="ln" style="width:70mm"></span></div>`
    : `<div class="nm">${esc(s.full_name)}</div>`
  const code = blank ? `Kod: <span class="bx">${'<span class="box"></span>'.repeat(4)}</span>` : `variant <b>${esc(s.code)}</b>`
  return `<div class="card" data-name="${esc(s.full_name || s.code)}"><span class="cut">✂ CAVAB KARTI</span>${mk}
    <div class="ctop"><img src="${qr}" alt="">
      <div class="cinfo">${who}
        ${esc(ex.school)} · ${esc(ex.class_name)} · ${esc(ex.subject)} · <b>${esc(nm(ex))}</b> · ${fmtD(ex.date)} · ${code} · 100 bal
        <div class="help">${esc(help(s.lang, s.questions.map(q => q.kind)))}</div></div></div>
    <div class="mcq">${mcq.map(q => `<div class="row"><span class="no">${q.slot}</span>${[...L].map(c => `<span class="bub">${c}</span>`).join('')}</div>`).join('')}</div>
    <div class="open">${open.map(q => `<div class="row"><span class="no">${q.slot}</span><span class="bx">${'<span class="box"></span>'.repeat(CELLS)}</span></div>`).join('')}</div>
    ${score.length ? `<div class="scoreh">Müəllim balı (yoxlayan müəllim qaralayır)</div><div class="open">${score.map(q => `<div class="row"><span class="no">${q.slot}</span>${SCORE.map(c => `<span class="bub">${c}</span>`).join('')}</div>`).join('')}</div>` : ''}
    <div class="cfoot"><span>Yekun bal: <span class="ln" style="width:16mm"></span> / 100</span><span>Şagird imzası: <span class="ln" style="width:30mm"></span></span><span>Müəllim imzası: <span class="ln" style="width:30mm"></span></span></div>
  </div>`
}

function sheet(s: KsqSheet, ex: KsqPrint['exam'], qr: string, cardOnly = false): string {
  const blank = s.student_id === 0
  const head = `<div class="band"><span><b class="t">${esc(nm(ex))}</b> · ${esc(ex.subject)} · ${esc(ex.class_name)}</span><span>${esc(ex.school)} · ${fmtD(ex.date)}</span></div>
    <div class="who"><div class="nm">${blank ? 'Ad, soyad: <span class="ln" style="width:80mm"></span>' : esc(s.full_name)}<br><b>${blank ? 'cavab vərəqi (boş forma)' : 'variant ' + esc(s.code)}</b> · ${s.questions.length} sual · 100 bal</div>
      <div class="sc"><div>Bal<b>____</b>/100</div><div>Qiymət<b>__</b></div></div></div>`
  if (cardOnly) return `<section class="side">${head}<div style="flex:1"></div>${card(s, ex, qr)}</section>`   // sualları ayrıca kitabça daşıyır
  const F = front(s.questions.length)
  const fr = s.questions.filter(q => q.slot <= F), back = s.questions.filter(q => q.slot > F)
  return `<section class="side">${head}<div class="qs">${fr.map(question).join('')}</div></section>
    <section class="side"><div class="hd" style="font-size:8pt"><span>${esc(s.full_name)} · ${esc(s.code)}</span><span>${esc(nm(ex))} · 2-ci üz</span></div>
      <div class="qs">${back.map(question).join('')}</div>${card(s, ex, qr)}</section>`
}

/** Şəkillər yüklənənə qədər gözlə (13.10.2026: ölçmə şəkillərdən əvvəl aparılırdı – şəkil sonra yüklənib sualları
 *  «overflow:hidden» altına itələyirdi, 1-ci səhifədə suallar kəsilirdi: kağızda 30 əvəzinə 28–29 sual). */
async function imagesReady(doc: Document) {
  await Promise.all([...doc.images].map(im => im.complete ? Promise.resolve() : new Promise<void>(ok => {
    const t = setTimeout(ok, 15000); im.onload = im.onerror = () => { clearTimeout(t); ok() } })))
  try { await (doc as any).fonts?.ready } catch { /* noop */ }
}

const over = (el: HTMLElement) => el.scrollWidth > el.clientWidth + 2 || el.scrollHeight > el.clientHeight + 2

/** Bir sütun bloku sığana qədər: şrift 10 → 7 pt, sonra şəkillər 26 → 16 mm, sonra şrift 6,5 pt. Sığdısa – true. */
function shrink(el: HTMLElement): boolean {
  let pt = parseFloat(el.style.fontSize) || 10
  while (over(el) && pt > 7) { pt -= 0.25; el.style.fontSize = pt + 'pt' }
  for (let mm = 26; over(el) && mm >= 16; mm -= 2) el.querySelectorAll<HTMLElement>('img').forEach(im => { im.style.maxHeight = mm + 'mm' })
  if (over(el)) el.style.fontSize = '6.5pt'
  return !over(el)
}

/** Vərəqlər: hər sual görünməlidir. Ön üz sığmırsa – sonuncu suallar arxa üzə keçir; arxa üz sığmırsa – qırmızı
 *  çərçivə və şagirdin adı (çapdan əvvəl müəllim görsün). Qaytarır: sığmayan şagirdlərin adları. */
async function fit(doc: Document): Promise<{ bad: string[]; moved: string[] }> {
  await imagesReady(doc)
  const bad: string[] = [], moved: string[] = []
  const sides = [...doc.querySelectorAll<HTMLElement>('section.side')]
  for (let i = 0; i + 1 < sides.length; i += 2) {
    const fr = sides[i].querySelector<HTMLElement>('.qs'), bk = sides[i + 1].querySelector<HTMLElement>('.qs')
    if (!fr || !bk) continue
    fr.style.fontSize = bk.style.fontSize = ''
    const name = sides[i].querySelector('.who .nm')?.childNodes[0]?.textContent?.trim() || String(i / 2 + 1)
    // köhnə çap (13.10-dan əvvəl) 10 pt ilə, şəkillər sonra yüklənərək – bu suallar kəsilmiş ola bilər
    const cut = [fr, bk].flatMap(el => { const r = el.getBoundingClientRect()
      return [...el.querySelectorAll<HTMLElement>('.q')].filter(q => { const b = q.getBoundingClientRect(); return b.bottom > r.bottom + 1 || b.right > r.right + 1 })
        .map(q => q.querySelector('.n')?.textContent || '?') })
    if (cut.length) moved.push(`${name} (${cut.join(', ')})`)
    while (!shrink(fr) && fr.children.length > 1) {                // ön üzdən arxaya – sual itmir
      bk.insertBefore(fr.lastElementChild!, bk.firstChild)
      fr.style.fontSize = ''
      fr.querySelectorAll<HTMLElement>('img').forEach(im => { im.style.maxHeight = '' })
    }
    if (!shrink(bk)) { bk.style.outline = '2px solid red'; bad.push(name) }
    if (over(fr)) { fr.style.outline = '2px solid red' }
  }
  for (const cd of doc.querySelectorAll<HTMLElement>('.card')) {                  // cavab kartının bütün sətirləri vərəqdədir?
    const side = cd.closest('section.side') as HTMLElement
    if (cd.scrollHeight > cd.clientHeight + 2 || cd.getBoundingClientRect().bottom > side.getBoundingClientRect().bottom + 1) {
      cd.style.outline = '2px solid red'; bad.push((cd.dataset.name || '?') + ' – ' + tt('cavab kartı'))
    }
  }
  return { bad, moved }
}

function open(title: string, body: string, after?: (d: Document) => void) {
  const w = window.open('', '_blank')
  if (!w) { toast('Brauzer yeni pəncərəni blokladı – pop-up icazəsi verin'); return }
  w.document.open()
  w.document.write(`<!doctype html><html lang="az"><head><meta charset="utf-8"><title>${esc(title)}</title><style>${CSS}
    #bar{position:sticky;top:0;background:#f3f4f6;border-bottom:1px solid #ccc;padding:8px;display:flex;gap:8px;font:14px Arial;z-index:9}
    @media print{#bar{display:none}}</style></head><body><div id="bar"><button id="p" style="padding:8px 14px">Çap et (iki üzlü)</button>
    <button id="c" style="padding:8px 14px">Bağla</button><span id="m" style="align-self:center;color:#555"></span></div>${body}</body></html>`)
  w.document.close()
  ;(w.document.getElementById('p') as HTMLButtonElement).onclick = () => w.print()
  ;(w.document.getElementById('c') as HTMLButtonElement).onclick = () => w.close()
  if (after) setTimeout(() => after(w.document), 300)
}

/** Köhnə çap (13.10.2026-dan əvvəl: 10 pt, şəkillər ölçmədən sonra yüklənirdi) hər vərəqdə hansı sualları kəsərdi –
 *  gizli çərçivədə vərəqlər qurulur, şəkillər gözlənilir, sütunlardan kənara çıxan suallar sayılır. {student_id: [slot]} */
export async function estimateOldCut(d: KsqPrint): Promise<Record<number, number[]>> {
  const fr = document.createElement('iframe')
  Object.assign(fr.style, { position: 'fixed', left: '-5000px', top: '0', width: '900px', height: '1400px', border: '0' })
  document.body.appendChild(fr)
  try {
    const doc = fr.contentDocument!
    const qrs = await Promise.all(d.sheets.map(s => QRCode.toDataURL(s.qr, { margin: 0, width: 300, errorCorrectionLevel: 'M' })))
    doc.open(); doc.write(`<!doctype html><html><head><meta charset="utf-8"><style>${CSS}</style></head><body>${d.sheets.map((s, i) => sheet(s, d.exam, qrs[i])).join('')}</body></html>`); doc.close()
    await imagesReady(doc)
    const sides = [...doc.querySelectorAll<HTMLElement>('section.side')]
    const out: Record<number, number[]> = {}
    d.sheets.forEach((s, k) => {
      const cut: number[] = []
      for (const side of [sides[2 * k], sides[2 * k + 1]]) {
        const el = side?.querySelector<HTMLElement>('.qs'); if (!el) continue
        const r = el.getBoundingClientRect()
        el.querySelectorAll<HTMLElement>('.q').forEach(q => { const b = q.getBoundingClientRect()
          if (b.bottom > r.bottom + 1 || b.right > r.right + 1) cut.push(Number(q.querySelector('.n')?.textContent)) })
      }
      if (cut.length) out[s.student_id] = cut.filter(Boolean)
    })
    return out
  } finally { fr.remove() }
}

/** Sual kitabçası: sinifə BİR nüsxə (hamıya eyni suallar) – 2 sütun, cavab vərəqəsi ayrıca (printSheets cardOnly). */
export function printBooklet(d: KsqPrint) {
  const ex = d.exam, s = d.sheets[0]
  if (!s) return
  open(`${ex.class_name} – ${nm(ex)} kitabça`, `<div class="bkh"><span><b>${esc(nm(ex))}</b> · ${esc(ex.subject)} · ${esc(ex.class_name)}</span><span>${esc(ex.school)} · ${fmtD(ex.date)} · sual kitabçası</span></div>
    <div class="bk">${s.questions.map(question).join('')}</div>`)
}

export async function printSheets(d: KsqPrint, opts: { cardOnly?: boolean } = {}) {
  const qrs = await Promise.all(d.sheets.map(s => QRCode.toDataURL(s.qr, { margin: 0, width: 300, errorCorrectionLevel: 'M' })))
  const ex = d.exam
  open(`${ex.class_name} – ${nm(ex)} vərəqlər`, d.sheets.map((s, i) => sheet(s, ex, qrs[i], !!opts.cardOnly)).join(''), doc => {
    const m = doc.getElementById('m'), p = doc.getElementById('p') as HTMLButtonElement | null
    if (m) m.textContent = tt('Şəkillər yüklənir, səhifələr yoxlanılır…')
    if (p) p.disabled = true
    fit(doc).then(({ bad, moved }) => {
      if (p) p.disabled = false
      if (m) m.textContent = tt('{n} şagird · {p} səhifə (iki üzlü çap edin)', { n: d.sheets.length, p: d.sheets.length * (opts.cardOnly ? 1 : 2) })
        + (bad.length ? ' · ⚠ ' + tt('suallar sığmır (qırmızı): {names}', { names: bad.join(', ') }) : ' · ✓ ' + tt('bütün suallar səhifədədir'))
        + (moved.length ? ' · ' + tt('13.10-dan əvvəl çap olunubsa, bu vərəqlərdə suallar kəsilmiş ola bilər – yenidən çap edin: {names}', { names: moved.join(', ') }) : '')
    })
  })
}

export function printKey(d: KsqPrint) {
  const ex = d.exam
  const body = `<div class="key" style="padding:4mm"><h2 style="margin:0 0 3mm">${ex.kind}-${ex.no} · ${esc(ex.class_name)} · ${fmtD(ex.date)} — müəllim açarı</h2>
    ${d.key.map(k => `<table><tr><th colspan="15" style="text-align:left">${esc(k.code)} · ${esc(k.full_name)}<span style="font-weight:400;color:#555"> — ${esc([...new Set(k.answers.map(a => a.topic).filter(Boolean))].join(' · '))}</span></th></tr>
      ${[0, 15].map(o => `<tr>${k.answers.slice(o, o + 15).map(a => `<th>${a.slot}</th>`).join('')}</tr><tr>${k.answers.slice(o, o + 15).map(a => `<td><b>${esc(a.value)}</b></td>`).join('')}</tr>`).join('')}
      ${k.answers.some(a => a.ref) ? `<tr><td colspan="15" style="font-size:7pt;color:#555;text-align:left">${k.answers.map(a => `${a.slot}) ${esc(a.ref || '')}`).join(' · ')}</td></tr>` : ''}
    </table>`).join('')}</div>`
  open(`${ex.class_name} – ${ex.kind}-${ex.no} açar`, body)
}
