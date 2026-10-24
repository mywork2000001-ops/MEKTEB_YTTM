// Vaxt aralıqlarını rəqəmlə yox, sözlə göstərmək: «iki həftədən bir», «раз в две недели», «every two weeks», «bir dərs (45 dəq)».
// Ədəd sözlükləri burada (mətn deyil, say adlarıdır); cümlə şablonları isə i18n.ts-dədir (t()).
import type { Lang } from './i18n'

const AZ = ['sıfır', 'bir', 'iki', 'üç', 'dörd', 'beş', 'altı', 'yeddi', 'səkkiz', 'doqquz', 'on', 'on bir', 'on iki']
const EN = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve']
const RU_M = ['ноль', 'один', 'два', 'три', 'четыре', 'пять', 'шесть', 'семь', 'восемь', 'девять', 'десять', 'одиннадцать', 'двенадцать']
const RU_F = RU_M.map((w, i) => i === 1 ? 'одна' : i === 2 ? 'две' : w)

/** 1–12 sözlə (ru: `fem` – qadın cinsi: одна/две); 12-dən böyük – rəqəm. */
export function numWord(n: number, lang: Lang, fem = false): string {
  if (!Number.isInteger(n) || n < 1 || n > 12) return String(n)
  return lang === 'az' ? AZ[n] : lang === 'en' ? EN[n] : (fem ? RU_F : RU_M)[n]
}

type Unit = 'day' | 'week' | 'month' | 'hour' | 'lesson' | 'minute'
// ru: [1, 2–4, 5+] – təkcə say üçün; `acc` – təklikdə vinitelny (одну неделю)
const RU_FORMS: Record<Unit, [string, string, string]> = {
  day: ['день', 'дня', 'дней'], week: ['неделя', 'недели', 'недель'], month: ['месяц', 'месяца', 'месяцев'],
  hour: ['час', 'часа', 'часов'], lesson: ['урок', 'урока', 'уроков'], minute: ['минута', 'минуты', 'минут'],
}
const RU_FEM: Record<Unit, boolean> = { day: false, week: true, month: false, hour: false, lesson: false, minute: true }
const AZ_UNIT: Record<Unit, string> = { day: 'gün', week: 'həftə', month: 'ay', hour: 'saat', lesson: 'dərs', minute: 'dəq' }
const EN_UNIT: Record<Unit, [string, string]> = {
  day: ['day', 'days'], week: ['week', 'weeks'], month: ['month', 'months'], hour: ['hour', 'hours'], lesson: ['lesson', 'lessons'], minute: ['min', 'min'],
}

/** «iki həftə» / «две недели» / «two weeks»; `acc` – ru üçün vinitelny (как «на неделю», «одну неделю»). */
export function countUnit(n: number, unit: Unit, lang: Lang, acc = false): string {
  if (lang === 'az') return `${numWord(n, 'az')} ${AZ_UNIT[unit]}`
  if (lang === 'en') return `${numWord(n, 'en')} ${EN_UNIT[unit][n === 1 ? 0 : 1]}`
  const f = RU_FORMS[unit]
  const m10 = n % 10, m100 = n % 100
  const form = m10 === 1 && m100 !== 11 ? 0 : (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) ? 1 : 2
  let w = f[form]
  if (acc && form === 0 && RU_FEM[unit]) w = unit === 'week' ? 'неделю' : 'минуту'
  const num = n >= 1 && n <= 12 ? numWord(n, 'ru', RU_FEM[unit]) : String(n)
  const numAcc = acc && n === 1 && RU_FEM[unit] ? 'одну' : num
  return `${numAcc} ${w}`
}

const UNIT_OF = { day: 'day', week: 'week', month: 'month' } as const

/** Tezlik: hər gün / iki gündən bir / hər həftə / iki həftədən bir / hər ay / üç aydan bir. */
export function everyText(period: 'day' | 'week' | 'month', every: number, lang: Lang): string {
  const n = Math.max(1, every || 1)
  const u = UNIT_OF[period]
  if (lang === 'az') {
    if (n === 1) return period === 'day' ? 'hər gün' : period === 'week' ? 'hər həftə' : 'hər ay'
    return `${numWord(n, 'az')} ${period === 'day' ? 'gündən' : period === 'week' ? 'həftədən' : 'aydan'} bir`
  }
  if (lang === 'en') {
    if (n === 1) return `every ${u}`
    return `every ${numWord(n, 'en')} ${u}s`
  }
  if (n === 1) return period === 'day' ? 'каждый день' : period === 'week' ? 'каждую неделю' : 'каждый месяц'
  const f = RU_FORMS[u]
  const m10 = n % 10, m100 = n % 100
  const w = m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14) ? f[1] : f[2]
  return `раз в ${numWord(n, 'ru', period === 'week')} ${w}`
}

/** Dəqiqə müddəti: 45 – «bir dərs (45 dəq)», 60 – «bir saat», 90 – «iki dərs (90 dəq)», 120 – «iki saat»; qalanı «N dəq». */
export function spanMinutes(min: number, lang: Lang): string {
  if (min === 45 || min === 90) return `${countUnit(min / 45, 'lesson', lang, true)} (${min} ${lang === 'ru' ? 'мин' : lang === 'en' ? 'min' : 'dəq'})`
  if (min >= 60 && min % 60 === 0 && min <= 720) return countUnit(min / 60, 'hour', lang, true)
  return `${min} ${lang === 'ru' ? 'мин' : lang === 'en' ? 'min' : 'dəq'}`
}

/** Saat müddəti: 24 – «bir gün», 48 – «iki gün», 168 – «bir həftə», 336 – «iki həftə»; qalanı «N saat». */
export function spanHours(h: number, lang: Lang): string {
  if (h >= 168 && h % 168 === 0 && h <= 168 * 12) return countUnit(h / 168, 'week', lang, true)
  if (h >= 24 && h % 24 === 0 && h < 168) return countUnit(h / 24, 'day', lang, true)
  return `${h} ${lang === 'ru' ? 'ч' : lang === 'en' ? 'h' : 'saat'}`
}

/** Seriyanın əhatə etdiyi müddət: «on həftəlik» / «на десять недель» / «about ten weeks» üçün say + vahid (şablon i18n-də). */
export function coverText(n: number, period: 'day' | 'week' | 'month', every: number, lang: Lang): string {
  const total = Math.max(1, n) * Math.max(1, every || 1)
  if (lang === 'az') return `${numWord(total, 'az')} ${period === 'day' ? 'günlük' : period === 'week' ? 'həftəlik' : 'aylıq'}`
  return countUnit(total, UNIT_OF[period], lang, true)
}

/** Seriyanın son sınağının tarixi: ilk tarix + (n-1) addım. */
export function lastDate(first: Date, n: number, period: 'day' | 'week' | 'month', every: number): Date {
  const d = new Date(first)
  const k = Math.max(0, n - 1) * Math.max(1, every || 1)
  if (period === 'month') d.setMonth(d.getMonth() + k)
  else d.setDate(d.getDate() + k * (period === 'week' ? 7 : 1))
  return d
}

export const LOCALE: Record<Lang, string> = { az: 'az-AZ', en: 'en-GB', ru: 'ru-RU' }
/** «26 dekabr» / «26 декабря» / «26 December». */
export function dayMonth(d: Date, lang: Lang): string {
  try { return d.toLocaleDateString(LOCALE[lang], { day: 'numeric', month: 'long' }) } catch { return d.toISOString().slice(0, 10) }
}

/** Azərbaycan dilində vaxtın sonuna qoşulan şəkilçi: 15:00 → da, 15:20 → də (son say adının saitinə görə). */
export function azTimeSuffix(hhmm: string): string {
  const m = Number((hhmm.split(':')[1] || '0'))
  const u = m % 10
  if (u === 0) return [0, 10, 30, 40].includes(m) ? 'da' : 'də'     // sıfır/on/otuz/qırx – a; iyirmi/əlli – ə
  return [6, 9].includes(u) ? 'da' : 'də'
}

/** Tezlik seçimləri (period, every): UI-də rəqəm sahəsi yoxdur. */
export const FREQS: [('day' | 'week' | 'month'), number][] = [['day', 1], ['day', 2], ['week', 1], ['week', 2], ['week', 3], ['week', 4], ['month', 1], ['month', 2]]
export const WINDOW_HOURS = [24, 48, 72, 168, 336]
export const SOLVE_MINUTES = [45, 60, 90, 120, 180]
export const TEST_MINUTES = [45, 60, 90, 120, 180, 240, 300]
