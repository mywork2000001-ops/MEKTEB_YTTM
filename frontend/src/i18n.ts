// İnterfeys dili: AZ (əsas), EN, RU. Açar – Azərbaycan mətni; tərcümə yoxdursa AZ göstərilir.
// Rəsmi sənədlər (çap, plan) həmişə Azərbaycan dilindədir.
import { createContext, useContext } from 'react'

export type Lang = 'az' | 'en' | 'ru'

const D: Record<string, [string, string]> = {
  'Əsas səhifə': ['Home', 'Главная'], 'Siniflər və qruplar': ['Classes & groups', 'Классы и группы'],
  'Bu gün': ['Today', 'Сегодня'], 'Jurnal': ['Journal', 'Журнал'], 'Perspektiv plan': ['Long-term plan', 'Перспективный план'],
  'Həftəlik cədvəl': ['Weekly timetable', 'Недельное расписание'], 'Onlayn tapşırıqlar': ['Online tasks', 'Онлайн-задания'],
  'Analitika və hesabat': ['Analytics & reports', 'Аналитика и отчёты'], 'Çat': ['Chat', 'Чат'],
  'Tənzimləmələr': ['Settings', 'Настройки'], 'Dərs': ['Lesson', 'Урок'], 'Tapşırıqlar': ['Tasks', 'Задания'],
  'Plan': ['Plan', 'План'], 'Nəticələrim': ['My results', 'Мои результаты'], 'Analitika': ['Analytics', 'Аналитика'],
  'Daxil ol': ['Sign in', 'Войти'], 'Çıxış': ['Sign out', 'Выйти'], 'Login': ['Login', 'Логин'],
  'Parol': ['Password', 'Пароль'], 'Giriş kodu': ['Login code', 'Код входа'], 'Yadda saxla': ['Save', 'Сохранить'],
  'Ləğv et': ['Cancel', 'Отмена'], 'Bağla': ['Close', 'Закрыть'], 'Əlavə et': ['Add', 'Добавить'],
  'Sil': ['Delete', 'Удалить'], 'Arxiv': ['Archive', 'Архив'], 'Geri qaytar': ['Restore', 'Восстановить'],
  'Axtar': ['Search', 'Поиск'], 'Sinif': ['Class', 'Класс'], 'Şagird': ['Student', 'Ученик'],
  'Şagirdlər': ['Students', 'Ученики'], 'Tarix': ['Date', 'Дата'], 'Mövzu': ['Topic', 'Тема'],
  'Ev tapşırığı': ['Homework', 'Домашнее задание'], 'Davamiyyət': ['Attendance', 'Посещаемость'],
  'Qiymət': ['Grade', 'Оценка'], 'Yüklənir…': ['Loading…', 'Загрузка…'], 'Görünüş': ['Appearance', 'Внешний вид'],
  'Dil': ['Language', 'Язык'], 'Rəng çaları': ['Colour theme', 'Цветовая тема'], 'Rejim': ['Mode', 'Режим'],
  'Avtomatik': ['Automatic', 'Авто'], 'İşıqlı': ['Light', 'Светлый'], 'Qaranlıq': ['Dark', 'Тёмный'],
  'Böyük şrift': ['Large text', 'Крупный шрифт'], 'PIN-i dəyiş': ['Change PIN', 'Сменить PIN'],
  'Yuxarıda seçim edin': ['Make a selection above', 'Сделайте выбор выше'], 'Həftə': ['Week', 'Неделя'],
  'Gün': ['Day', 'День'], 'Ay': ['Month', 'Месяц'], 'Yarımil': ['Semester', 'Полугодие'],
  'Müəllim otağı': ['Staff room', 'Учительская'], 'Başla': ['Start', 'Начать'], 'Təhvil ver': ['Submit', 'Сдать'],
  'Qalan vaxt': ['Time left', 'Осталось времени'], 'İmtahana qalıb': ['Until the exam', 'До экзамена'],
  'gün': ['days', 'дн.'], 'Müəllimlərim': ['My teachers', 'Мои учителя'], 'Səhvlərim': ['My mistakes', 'Мои ошибки'],
  'Nailiyyətlər': ['Achievements', 'Достижения'], 'Sinif ortası': ['Class average', 'Среднее по классу'],
  'Mən': ['Me', 'Я'], 'Mesaj yazın…': ['Type a message…', 'Напишите сообщение…'], 'Göndər': ['Send', 'Отправить'],
  'Daha çox': ['More', 'Ещё'], 'Salam': ['Hello', 'Здравствуйте'],
}

export const I18nCtx = createContext<Lang>('az')

export function tr(lang: Lang, s: string): string {
  if (lang === 'az') return s
  const e = D[s]
  return e ? e[lang === 'en' ? 0 : 1] : s
}

export function useT() {
  const lang = useContext(I18nCtx)
  return (s: string) => tr(lang, s)
}

export const LANGS: [Lang, string][] = [['az', 'Azərbaycanca'], ['en', 'English'], ['ru', 'Русский']]
