# Bulud sessiyası (claude.ai/code, ikinci hesab) – testlər üzrə iş

**Rol:** testlər, sual bankları, PDF → spec, cavab açarları, tərcümə (`pdf-oxuyucu`, `cavab-yoxlayici`, `tercumeci`, `yigici`, `kodcu` – `.claude/agents/`).
**Əsas sessiya** (müəllimin kompüterində) – review, `main`-ə birləşmə, Render deploy, canlı DB, miqrasiya. Bulud sessiyası bunları ETMİR.

## Qaydalar
1. İş yalnız öz budağında (`tests` və ya `claude/...`); `main`-ə birbaşa push YOX – iş bitəndə Pull Request (başlıq + qısa hesabat).
2. Başlanğıcda və sonda `docs/HANDOFF.md`-ə bir sətir (`CLAUDE-BULUD — başladı/bitirdi: …; budaq: …; fayllar: …`).
3. CLAUDE.md qaydaları eynidir: AZ/EN/RU, mövzu testləri yalnız `backend/app/plan_tests.py` üzərindən, `npm run build` yoxlaması.
4. Sirlər (`.env`, açarlar) repoda yoxdur və əlavə olunmur; canlı sayt / DB ilə işləmə.
5. Əsas sessiya eyni vaxtda `frontend/src/pages/teacher/*`, `backend/app/api/*` üzərində işləyə bilər – mümkünsə test/bank fayllarına (`backend/app/banks*`, `scripts/`, `docs/tasks/`) toxun; ortaq fayl dəyişirsə PR-da qeyd et.

## Mühit (Linux)
```
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && pip install -r requirements-dev.txt
python -m pytest -q tests/<aid_test>.py        # cwd = backend
cd ../frontend && npm ci && npm run build
```

## Başlanğıc promtu (claude.ai/code-a yapışdır)
```
Sən «Müəllim köməkçisi» layihəsində bulud sessiyasısan (repo mywork2000001-ops/MEKTEB_YTTM). Əvvəlcə oxu:
CLAUDE.md, docs/bulud-sessiyasi-promtu.md, docs/HANDOFF.md (son 10 sətir). Qaydalar: yalnız öz budağında işlə,
main-ə birbaşa push etmə – iş bitəndə Pull Request aç; deploy, canlı DB, miqrasiya etmə; sirlər repoya getmir.
Agentlər .claude/agents/-dədir (pdf-oxuyucu, cavab-yoxlayici, tercumeci, yigici, kodcu) – işi onlara payla.
Hər yeni interfeys mətni AZ/EN/RU. Yoxlama: aid pytest (backend qovluğundan) + `npm run build`.
İstifadəçi azərbaycanlı müəllimdir, proqramçı deyil – cavabları sadə dildə, rusca yaz, işi sona qədər özün et.

TAPŞIRIQ: <istifadəçi burada yazacaq>

Sonda: HANDOFF-a sətir, PR (nə edildi, testlər, build, açıq qalanlar).
```
