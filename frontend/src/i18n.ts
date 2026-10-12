// İnterfeys dili: AZ (əsas), EN, RU. Açar – Azərbaycan mətni; tərcümə yoxdursa AZ göstərilir.
// Rəsmi sənədlər (çap, plan) həmişə Azərbaycan dilindədir.
import { createContext, useContext } from 'react'

export type Lang = 'az' | 'en' | 'ru'

const D: Record<string, [string, string]> = {
  'Əsas səhifə': ['Home', 'Главная'],
  'Siniflər və qruplar': ['Classes & groups', 'Классы и группы'],
  'Bu gün': ['Today', 'Сегодня'],
  'Jurnal': ['Journal', 'Журнал'],
  'Perspektiv plan': ['Long-term plan', 'Перспективный план'],
  'Həftəlik cədvəl': ['Weekly timetable', 'Недельное расписание'],
  'Onlayn tapşırıqlar': ['Online tasks', 'Онлайн-задания'],
  'Analitika və hesabat': ['Analytics & reports', 'Аналитика и отчёты'],
  'Sinif rəhbəri': ['Class teacher', 'Классный руководитель'],
  'Rəhbər': ['Class teacher', 'Кл. рук.'],
  'Dərs sayı': ['Lesson count', 'Количество уроков'],
  'Müvəffəqiyyət': ['Achievement', 'Успеваемость'],
  'Dərslər': ['Lessons', 'Уроки'],
  'Qiymət cədvəli': ['Grade sheet', 'Сводная ведомость'],
  'Valideynlər': ['Parents', 'Родители'],
  'Rəhbərin jurnalı': ['Class teacher log', 'Журнал кл. руководителя'],
  'Çat': ['Chat', 'Чат'],
  'Şagird sorğusu': ['Student survey', 'Опрос учеников'],
  'Sorğu': ['Survey', 'Опрос'],
  'Sorğular': ['Surveys', 'Опросы'],
  'Tənzimləmələr': ['Settings', 'Настройки'],
  'Dərs': ['Lesson', 'Урок'],
  'Tapşırıqlar': ['Tasks', 'Задания'],
  'Plan': ['Plan', 'План'],
  'Nəticələrim': ['My results', 'Мои результаты'],
  'Analitika': ['Analytics', 'Аналитика'],
  'Daxil ol': ['Sign in', 'Войти'],
  'Çıxış': ['Sign out', 'Выйти'],
  'Login': ['Login', 'Логин'],
  'Parol': ['Password', 'Пароль'],
  'Giriş kodu': ['Login code', 'Код входа'],
  'Yadda saxla': ['Save', 'Сохранить'],
  'Ləğv et': ['Cancel', 'Отмена'],
  'Bağla': ['Close', 'Закрыть'],
  'Əlavə et': ['Add', 'Добавить'],
  'Sil': ['Delete', 'Удалить'],
  'Arxiv': ['Archive', 'Архив'],
  'Geri qaytar': ['Restore', 'Восстановить'],
  'Axtar': ['Search', 'Поиск'],
  'Sinif': ['Class', 'Класс'],
  'Şagird': ['Student', 'Ученик'],
  'Şagirdlər': ['Students', 'Ученики'],
  'Tarix': ['Date', 'Дата'],
  'Mövzu': ['Topic', 'Тема'],
  'Ev tapşırığı': ['Homework', 'Домашнее задание'],
  'Davamiyyət': ['Attendance', 'Посещаемость'],
  'Qiymət': ['Grade', 'Оценка'],
  'Yüklənir…': ['Loading…', 'Загрузка…'],
  'Görünüş': ['Appearance', 'Внешний вид'],
  'Dil': ['Language', 'Язык'],
  'Rəng çaları': ['Colour theme', 'Цветовая тема'],
  'Rejim': ['Mode', 'Режим'],
  'Avtomatik': ['Automatic', 'Авто'],
  'İşıqlı': ['Light', 'Светлый'],
  'Qaranlıq': ['Dark', 'Тёмный'],
  'Böyük şrift': ['Large text', 'Крупный шрифт'],
  'PIN-i dəyiş': ['Change PIN', 'Сменить PIN'],
  'Yuxarıda seçim edin': ['Make a selection above', 'Сделайте выбор выше'],
  'Həftə': ['Week', 'Неделя'],
  'Gün': ['Day', 'День'],
  'Ay': ['Month', 'Месяц'],
  'Yarımil': ['Semester', 'Полугодие'],
  'Müəllim otağı': ['Staff room', 'Учительская'],
  'Başla': ['Start', 'Начать'],
  'Təhvil ver': ['Submit', 'Сдать'],
  'Qalan vaxt': ['Time left', 'Осталось времени'],
  'İmtahana qalıb': ['Until the exam', 'До экзамена'],
  'gün': ['days', 'дн.'],
  'Müəllimlərim': ['My teachers', 'Мои учителя'],
  'Səhvlərim': ['My mistakes', 'Мои ошибки'],
  'Nailiyyətlər': ['Achievements', 'Достижения'],
  'Sinif ortası': ['Class average', 'Среднее по классу'],
  'Mən': ['Me', 'Я'],
  'Mesaj yazın…': ['Type a message…', 'Напишите сообщение…'],
  'Göndər': ['Send', 'Отправить'],
  'Daha çox': ['More', 'Ещё'],
  'Hesab': ['Account', 'Аккаунт'],
  'Məktəb': ['School', 'Школа'],
  'Siniflər': ['Classes', 'Классы'],
  'Kilid': ['Lock', 'Блокировка'],
  'Müəllimlər': ['Teachers', 'Учителя'],
  'Test bazası': ['Question bank', 'База тестов'],
  'Audit jurnalı': ['Audit log', 'Журнал аудита'],
  'Gündəlik': ['Daily', 'Ежедневно'],
  'KSQ / BSQ': ['Summatives', 'СО / БСО'],
  'Mövzular': ['Topics', 'Темы'],
  'Xülasə': ['Summary', 'Сводка'],
  'İcmal': ['Overview', 'Обзор'],
  'Reytinq': ['Rating', 'Рейтинг'],
  'Güclü / orta / zəif': ['Strong / middle / weak', 'Сильные / средние / слабые'],
  'Risk': ['Risk', 'Риск'],
  'Çap / PDF': ['Print / PDF', 'Печать / PDF'],
  'Həftəlik dərs cədvəli': ['Weekly timetable', 'Недельное расписание'],
  'Sinif / qrup': ['Class / group', 'Класс / группа'],
  'Əvvəlki': ['Previous', 'Назад'],
  'Növbəti': ['Next', 'Вперёд'],
  'Bu həftə': ['This week', 'Эта неделя'],
  'Çap et': ['Print', 'Печать'],
  'Yeni tapşırıq': ['New task', 'Новое задание'],
  'Yeni material': ['New material', 'Новый материал'],
  'Nəticələr': ['Results', 'Результаты'],
  'Cavablar': ['Answers', 'Ответы'],
  'Qeydiyyat linki': ['Registration link', 'Ссылка регистрации'],
  'Şagird qeydiyyatı': ['Student registration', 'Регистрация ученика'],
  'Materiallar': ['Materials', 'Материалы'],
  'Salam': ['Hello', 'Здравствуйте'],
  // şagird: testlər (12.10.2026)
  "Bu test sizin üçün deyil və ya silinib": ["This test is not for you or has been deleted", "Этот тест не для вас или удалён"],
  "Test hələ açılmayıb: {t}": ["The test is not open yet: {t}", "Тест ещё не открыт: {t}"],
  "Test": ["Test", "Тест"],
  "açıq": ["open", "открыт"],
  "həll edilir": ["in progress", "решается"],
  "gözlənilir": ["upcoming", "ожидается"],
  "buraxılıb": ["missed", "пропущен"],
  "təhvil verilib": ["submitted", "сдан"],
  "bağlanıb": ["closed", "закрыт"],
  "Vaxtlı testlər – açılma və bağlanma vaxtına diqqət edin": ["Timed tests — mind the opening and closing times", "Тесты со временем — обратите внимание на время открытия и закрытия"],
  "Bölmə": ["Section", "Раздел"],
  "Mövzu testləri": ["Topic tests", "Тематические тесты"],
  "Sınaqlar": ["Trial exams", "Пробные экзамены"],
  "{n} açıq": ["{n} open", "открыто: {n}"],
  "Sınaqda yeriniz və balınız test bağlanandan sonra «Nəticələrim»dədir.": ["Your place and score appear in «My results» after the exam closes.", "Ваше место и балл появятся в «Мои результаты» после закрытия экзамена."],
  "Mövzu üzrə": ["By topic", "По теме"],
  "Ad üzrə": ["By name", "По названию"],
  "Mövzu testi yoxdur.": ["No topic tests.", "Тематических тестов нет."],
  "Sınaq yoxdur.": ["No trial exams.", "Пробных экзаменов нет."],
  "Bu dövrdə test yoxdur – «‹ ›» ilə başqa dövrə keçin və ya «Hamısı»nı seçin.": ["No tests in this period — switch with «‹ ›» or choose «All».", "В этот период тестов нет — переключитесь «‹ ›» или выберите «Все»."],
  "mövzu №{n}": ["topic #{n}", "тема №{n}"],
  "{n} dəq": ["{n} min", "{n} мин"],
  "{n} sual": ["{n} questions", "вопросов: {n}"],
  "bal": ["pts", "балл."],
  "Davam et": ["Continue", "Продолжить"],
  "Cavablara bax": ["View answers", "Посмотреть ответы"],
  "PDF 25 MB-dan böyükdür – şəkillərin sayını azaldın": ["The PDF is over 25 MB — use fewer photos", "PDF больше 25 МБ — уменьшите число фото"],
  "Həll göndərildi ({n} şəkil, bir PDF)": ["Solution sent ({n} photos, one PDF)", "Решение отправлено ({n} фото, один PDF)"],
  "Xəta": ["Error", "Ошибка"],
  "📷 Həllin şəkilləri (müəllimə bir PDF kimi gedir)": ["📷 Photos of your solution (sent to the teacher as one PDF)", "📷 Фото решения (отправляются учителю одним PDF)"],
  "{n} şəkil seçilib": ["{n} photos selected", "выбрано фото: {n}"],
  "Yenidən şəkil seç": ["Choose photos again", "Выбрать фото заново"],
  "📷 Həlli göndər": ["📷 Send solution", "📷 Отправить решение"],
  "Göndərilir…": ["Sending…", "Отправка…"],
  "PDF kimi göndər": ["Send as PDF", "Отправить как PDF"],
  "Təmizlə": ["Clear", "Очистить"],
  "✓ göndərilib – bax": ["✓ sent — view", "✓ отправлено — посмотреть"],
  "Vaxt bitdi – təhvil verildi": ["Time is up — submitted", "Время вышло — сдано"],
  "Təhvil verildi": ["Submitted", "Сдано"],
  "🏆 Yeni sertifikat: {t} – «Uğurlarım»da": ["🏆 New certificate: {t} — see «Achievements»", "🏆 Новый сертификат: {t} — в «Мои достижения»"],
  "Geri": ["Back", "Назад"],
  "⚠ Tam ekrandan çıxdınız": ["⚠ You left full screen", "⚠ Вы вышли из полноэкранного режима"],
  "Test tam ekranda yazılır": ["The test runs in full screen", "Тест проходит в полноэкранном режиме"],
  "Testə qayıtmaq üçün tam ekrana keçin. Vaxt dayanmır – qalan vaxt: ": ["Return to full screen to continue. The timer keeps running — time left: ", "Чтобы вернуться к тесту, включите полный экран. Время идёт — осталось: "],
  "Başlamaq üçün tam ekrana keçin. Qalan vaxt: ": ["Switch to full screen to start. Time left: ", "Чтобы начать, включите полный экран. Осталось: "],
  "Tam ekrandan çıxma: {n} dəfə.": ["Left full screen: {n} times.", "Выходов из полного экрана: {n}."],
  "Tam ekrana keç": ["Go full screen", "Полный экран"],
  "cavablanıb": ["answered", "отвечено"],
  "cavabsız": ["unanswered", "без ответа"],
  "Sual": ["Question", "Вопрос"],
  "cəmi 100": ["total 100", "всего 100"],
  "Cavabınızı yazın": ["Type your answer", "Введите ответ"],
  "sizin cavab": ["your answer", "ваш ответ"],
  "Sizin cavab": ["Your answer", "Ваш ответ"],
  "Düzgün": ["Correct", "Правильно"],
  "İzah": ["Explanation", "Объяснение"],
}

export const I18nCtx = createContext<Lang>('az')

// Modul səviyyəli funksiyalar (komponentdən kənar `ml(...)`, `tt(...)`) üçün cari dil — App hər render-də yeniləyir.
let CURRENT: Lang = 'az'

/** Tərcümə; `{n}` kimi yer tutucular vars-dan doldurulur (açar Azərbaycan mətni yer tutucularla). */
export function tr(lang: Lang, s: string, vars?: Record<string, string | number>): string {
  const e = lang === 'az' ? undefined : D[s]
  let out = e ? e[lang === 'en' ? 0 : 1] : s
  if (vars) for (const [k, v] of Object.entries(vars)) out = out.split(`{${k}}`).join(String(v))
  return out
}

export function useT() {
  const lang = useContext(I18nCtx)
  return (s: string, vars?: Record<string, string | number>) => tr(lang, s, vars)
}

/** Komponentdən kənar (toast və s.) — cari dildə. */
export const tt = (s: string, vars?: Record<string, string | number>) => tr(CURRENT, s, vars)

export const LANGS: [Lang, string][] = [['az', 'Azərbaycanca'], ['en', 'English'], ['ru', 'Русский']]

/** Sual/variant/izah mətni ({az,ru,en} və ya sətir) — istifadəçinin dilində; tərcümə yoxdursa AZ (12.10.2026, rusdilli şagird). */
export function pickLang(x: any, lang: Lang): string {
  if (!x) return ''
  if (typeof x === 'string') return x
  return x[lang] || x.az || x.ru || x.en || ''
}

export function useMl() {
  const lang = useContext(I18nCtx)
  return (x: any) => pickLang(x, lang)
}

export function setCurrentLang(l: Lang) { CURRENT = l }
export const ml = (x: any) => pickLang(x, CURRENT)
