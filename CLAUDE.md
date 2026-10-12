# Müəllim köməkçisi — qaydalar

## Dil: hər dəyişiklikdə AZ / EN / RU (istifadəçi tələbi, 12.10.2026)
Tətbiqdə rusdilli şagird və müəllimlər var. Ona görə **hər yeni və ya dəyişdirilən interfeys mətni avtomatik tərcümə olunur** —
ayrıca xahiş gözlənilmir:
- Frontend: mətn `t('…')` (komponentdə `useT()`) və ya `tt('…')` (komponentdən kənar) ilə; lüğət `frontend/src/i18n.ts`
  (`'AZ mətni': ['English', 'Русский']`), dəyişən hissələr `{n}` yer tutucusu ilə: `t('{n} sual', { n })`.
- Sual / variant / izah mətni (`{az,ru,en}`) — `ml(x)` ilə (istifadəçinin dilində).
- Server mesajları şagirdə görünürsə — EN/RU qarşılığı da (docs/rus-dili-promtu.md, mərhələ 4).
- Rəsmi sənədlər (jurnal, perspektiv plan, rəsmi çap formaları) — yalnız Azərbaycan dilində.
- Yoxlama: **`npm run build`** (frontend qovluğunda; `tsc -b` – Render də məhz bunu işlədir). `npx tsc --noEmit -p .` HEÇ NƏ YOXLAMIR (kök tsconfig yalnız istinadlardır) – 12.10.2026-da buna görə 11 deploy uğursuz oldu. Lüğətdə təkrar açar (tək və ya cüt dırnaqla) xəta verir.

Ətraflı: `docs/rus-dili-promtu.md`.
