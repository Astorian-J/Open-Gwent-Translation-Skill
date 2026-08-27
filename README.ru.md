# Gwent Translation Skill

**[English](README.md)** | [中文](README.zh-CN.md) | [Polski](README.pl.md) | **[Русский](README.ru.md)**

> **Внимание:** это русскоязычный перевод документации, созданный машинным переводом и **требующий вычитки носителем русского языка**. Сам инструмент переводит только **английский ↔ китайский** (EN↔CN) — он не поддерживает русский ни как исходный, ни как целевой язык. Самая актуальная версия: [английская](README.md).

> Точный двунаправленный перевод контента по *Gwent: The Witcher Card Game* между английским и китайским — официальная карточная терминология, названия колод сообщества, сленг и естественный тон игроков Bilibili. Работает с любым AI-агентом или переводчиком-человеком.
>
> **Неофициальный фанатский проект — не связан с CD PROJEKT RED и не одобрен им.** Тексты карт загружаются при сборке из публичного api.gwent.one и не коммитятся в этот репозиторий; полные сведения об авторских правах/лицензии — в [NOTICE](NOTICE).

Машинный перевод контента по Гвинту ломается предсказуемым образом: официальные названия карт переводятся дословно, прозвища колод сообщества превращаются в бессмыслицу, английский сленг вроде "on steroids" или "sweet spot" становится абракадаброй, а весь текст звучит деревянно. Этот набор инструментов исправляет это трёхслойным конвейером: блокирует данные карт, направляет риторику и ловит остатки.

## Возможности

- **Двунаправленный и направленно-осознанный** — EN→CN с тоном сообщества игроков Bilibili (короткие рубленые фразы, активный залог); CN→EN в естественный английский, сохраняющий термины сообщества. У каждого направления свой конвейер, поэтому CN→EN не пометит английские названия карт как непереведённые остатки.
- **1366 карт, заблокированных дословно** — Официальное EN/CN-название каждой карты, категория, атрибуты (редкость / фракция) и текст способности загружаются из официальных данных CDPR и исполняются дословно. Данные карт никогда не переводятся заново. Данные карт загружаются при установке (запустите `install.sh` или `scripts/build_effect_reference.py --fetch`); они не коммитятся в репозиторий — см. NOTICE.
- **200+ названий колод сообщества** — Прозвища, которые реально используют китайские игроки (大金北, 孽鬼跳松, 赤诚骑士北, 状态帝国...), а не дословные переводы.
- **Инъекция сленга и жаргона** — Английский сленг (op, brick, tutor, mulligan, on steroids, sweet spot...) обнаруживается в исходнике и предварительно наполняется целевым переводом, чтобы перестать быть абракадаброй.
- **Сохранение риторики и тона** — Метафоры, гипербола и сарказм переводятся по *намерению*, а не слово в слово. "Loud design" не станет "слишком громким".
- **Трёхслойная защита** — Жёсткий слой исполняет данные карт дословно; мягкий слой направляет риторику и стиль; слой обнаружения ловит остатки и пропущенные термины в конце.
- **Независим от агента** — У каждого скрипта есть флаг `--json` с унифицированным конвертом `{success, exit_code, data, errors}`. Работает с Claude Code, OpenClaw, Hermes или любым агентом. Только стандартная библиотека Python 3.10+, ноль зависимостей.

## До / После

| Исходный текст | Обычный машинный перевод | Этот инструмент |
|---|---|---|
| This build's sweet spot is at 8 provisions — loud design, on steroids. | 这个构建在8人口有甜点位置——大声的设计，在类固醇上。 | 这套的**甜点位**就在 8 人口——**存在感太强**，简直**打了鸡血**。 |
| Devotion Knights is the meta pick, but it bricks without a tutor. | 奉献骑士是元选择，但没有家庭教师它会变砖。 | **赤诚骑士北**是版本答案,没**检索**就会**卡手**。 |

(Примеры показывают EN→CN, поскольку инструмент работает с английским ↔ китайским.)

## Как это работает

Детерминированный двухэтапный конвейер — `translate.py` — оборачивает каждый автоматический шаг вокруг единственного шага перевода LLM, поэтому предобработку и финальный шлюз нельзя пропустить:

| Шаг | Что происходит | Кто запускает |
|---|---|---|
| 1. Prepare | Загружает ссылки, блокирует термины карт, вводит официальные эффекты + подсказки сленга, извлекает скелет формата → создаёт пакет перевода | `translate.py prepare` (детерминированный) |
| 2. Перевод | Вы или ваш агент переводите, ведомые таблицей терминов из пакета | Единственный шаг LLM |
| 3. Finish | Жёсткий шлюз: остатки / терминологический авторитет / Phase C / полнота перепроверяются; BLOCKED = не финализировать | `translate.py finish` (детерминированный) |

`auto_pipeline.py`, `phase_c_check.py`, `term_enforcer.py` и `completeness_guard.py` теперь **внутренние шаги** `translate.py` — не запускайте их вручную.

Данные карт **блокируются, а не предлагаются**: если название карты или официальный эффект встречается в источнике, перевод должен использовать официальную китайскую форму. Новые термины сообщества проходят через буфер проверки (`pending_terms.md`) перед окончательным принятием. Буфер — локальные данные пользователя: установка или обновление skill никогда его не сбрасывает.

## Облегчённая версия (перевод чата)

Для **короткого чата** — сообщения в группах, комментарии в Discord / QQ / Kook, отдельные предложения — полный конвейер избыточен. Облегчённый навык **lite** (`gwent-translation-lite`) сокращает перевод до трёх шагов:

1. **Запрос по требованию** — имена карт и термины запрашиваются через `lookup.py` только тогда, когда они встречаются в исходнике; никакой полной предзагрузки таблицы терминов.
2. **Перевод** — тот же тон игроков Bilibili / нейтральный английский, официальные названия карт и терминов.
3. **Самопроверка** — мысленный проход; без скриптов проверки.

Никакой инъекции `pre`, никакого `completeness_guard`, никакого `term_enforcer`. Lite переиспользует `scripts/` и `references/` основного навыка (ноль дублирования данных) через переменную `$GWENT_SKILL_DIR`, поэтому работает с Claude Code, hermes, opencode и другими агентами.

| Контент | Навык |
|---------|-------|
| Длинные статьи (мета-отчёты, BC-предложения, разбор карт) | `gwent-translation-style` (полный конвейер) |
| Сообщения чата, комментарии, отдельные предложения | `gwent-translation-lite` (3 шага) |

Оба навыка устанавливаются вместе через `install.sh`. Интерфейс lite для агентов: [`lite/AGENTS.md`](lite/AGENTS.md).

## О потреблении токенов

Инструмент вводит заблокированную таблицу терминов, официальные эффекты карт и подсказки сленга для обеспечения точности. Полный прогон (prepare → перевод → finish) обрабатывает примерно **30–60K токенов** в зависимости от длины статьи — примерно **в 3 раза больше обычного перевода** (измерено ~31K на средней BC-статье; сама таблица терминов ~6K, основная масса — статья + справочные документы). Поскольку большая часть конвейера механическая (блокировка терминов, обнаружение остатков, проверка формата), он хорошо работает на **более дешёвых или бесплатных моделях** (Claude Haiku/Sonnet, GPT-4o-mini, DeepSeek и т.д.) или любом агенте с бесплатной квотой — вам не нужна самая дорогая модель.

*Количество токенов на основе измерения инъекции на этапе pre на реальной BC-статье; фактическое использование зависит от длины статьи.*

## Быстрая установка

```bash
curl -fsSL https://raw.githubusercontent.com/Astorian-J/Open-Gwent-Translation-Skill/main/install.sh | bash
```

Или клонируйте вручную — после этого ОБЯЗАТЕЛЬНО запустите `install.sh`. База данных карт (`card_names_4lang.json`, `effect_text.json`) — это данные CDPR под авторским правом и **не входят в репозиторий**; `install.sh` собирает её локально. Без этого skill не может блокировать названия карт:

```bash
git clone --depth 1 https://github.com/Astorian-J/Open-Gwent-Translation-Skill.git
cd Open-Gwent-Translation-Skill
bash install.sh
```

Требуется Python 3.10+. Нет сторонних зависимостей.

## Использование

```bash
# 1. Prepare — создайте пакет перевода (заблокированные термины, официальные эффекты, правила стиля)
python scripts/translate.py prepare source.md --date 2026-07 --type general --direction encn

# 2. Переведите, используя сгенерированный source.pack.md (единственный шаг LLM), сохраните в translated.txt

# 3. Finish — жёсткий шлюз; перевод не финальный, пока это не пройдёт (PASS)
python scripts/translate.py finish translated.txt --source source.md --direction encn
```

Добавьте `--json` к любой команде для машиночитаемого вывода. Полный интерфейс агента: [AGENTS.md](AGENTS.md).

## Структура файлов

```
gwent-translation-style/
├── SKILL.md                 # Claude Code workflow + constraints
├── AGENTS.md                # Agent-agnostic interface (commands / JSON / exit codes)
├── agent.json               # Machine-readable command manifest
├── install.sh               # One-line installer
├── references/              # 20 reference files
│   ├── card_overrides.md       # Hand-maintained card aliases / renamed (committed)
│   ├── card_names_4lang.json   # Card names EN<->CN (build-time, gitignored)
│   ├── terminology_map.md       # EN->CN terminology
│   ├── reverse_terminology_map.md  # CN->EN terminology
│   ├── keywords_map.md          # Keyword translations
│   ├── category_map.md          # Card categories (relict, construct...)
│   ├── card_attributes_map.md   # Rarity + faction names / aliases
│   ├── competitive_terms.md     # 200+ deck names + community slang
│   ├── slang_map.md             # Slang / jargon hints (op, brick, tutor...)
│   ├── effect_text.json         # official ability text (build-time, fetched; see NOTICE)
│   ├── cn_fuzzy_fixes.md        # Chinese typo / abbreviation fixes
│   ├── correction_guide.md      # Translation rules
│   ├── common_pitfalls.md       # Common mistakes
│   ├── style_reference.md       # Style + rhetoric guidelines
│   ├── style_fingerprint.md     # Author style markers
│   ├── ambiguous_names.md       # Disambiguation
│   ├── version_map.md           # Version-specific terms
│   ├── phase_c_checklist.md     # Self-check rules
│   ├── translation_workflow.md  # Workflow reference
│   ├── pending_terms.md         # Terms awaiting review (runtime data, gitignored)
│   ├── pending_terms.template.md # Tracked template; installs seed the buffer from it
│   └── changelog.md             # Update history
├── scripts/                 # 15 Python scripts
│   ├── translate.py             # Main entry: prepare→translate→finish pipeline
│   ├── auto_pipeline.py         # Pre-processing + residue scan (internal to translate.py)
│   ├── check_translation.py     # Residue + slang detection
│   ├── completeness_guard.py    # Final gate
│   ├── phase_c_check.py         # Self-check
│   ├── term_enforcer.py         # Card data verification
│   ├── context_lock.py          # Context / abbreviation lock
│   ├── effect_verifier.py       # Official effect text check
│   ├── build_effect_reference.py  # Build effect_text.json (fetch-at-build: online/offline)
│   ├── format_skeleton.py       # Format preservation
│   ├── diff_review.py           # Diff review
│   ├── backtranslate.py         # Back-translation check
│   ├── lookup.py                # Term lookup
│   ├── learn.py                 # Learn new terms
│   ├── health_check.py          # Integrity check (63 PASS)
│   └── _shared.py               # Shared logic (TermAuthority)
└── lite/                    # Облегчённый навык (перевод чата, 3 шага)
    ├── SKILL.md                 # Определение навыка lite (перевод чата)
    └── AGENTS.md                # Агент-независимый интерфейс lite
```

## Ключевые термины

Небольшая выборка — полный набор в `references/`.

**Названия колод** (признанные сообществом):

| Английский | Китайский |
|---|---|
| Devotion Knights | 赤诚骑士北 |
| GN Movement | 孽鬼跳松 |
| Aristocrats | 状态帝国 |
| Lined Pockets Crimes | 宝箱罪行迪迦 |
| Blaze of Glory Eist Warriors | 荣耀圣焰征战 |

**Алиасы фракций**: Northern Realms → 北, Skellige → 岛, Monsters → 怪, Nilfgaard → 帝, Scoia'tael → 松, Syndicate → 迪迦.

## Пользователи Claude Code

Установите в `~/.claude/skills/gwent-translation-style/` и перезапустите Claude Code. Триггеры: `/gwent-translation-style`, "translate Gwent article", "Gwent translation".

`install.sh` устанавливает **оба** навыка вместе — основной `gwent-translation-style` и облегчённый `gwent-translation-lite`. Навык lite срабатывает на перевод чата / короткого контента (например, «翻一下这句» и подобные триггеры перевода сообщений).

## Содействие

1. Сделайте форк репозитория
2. Добавьте или обновите термины в `references/`
3. Новые термины сообщества должны пройти через `pending_terms.md`
4. Запустите `python scripts/health_check.py` перед отправкой
5. Откройте pull request

## Лицензия

См. [LICENSE](LICENSE).
