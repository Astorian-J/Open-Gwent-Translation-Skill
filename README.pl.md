# Gwent Translation Skill

**[English](README.md)** | [中文](README.zh-CN.md) | **[Polski](README.pl.md)** | [Русский](README.ru.md)

> **Uwaga:** To jest polskie tłumaczenie dokumentacji, wygenerowane maszynowo i **wymagające korekty przez native speakera języka polskiego**. Narzędzie tłumaczy wyłącznie **angielski ↔ chiński** (EN↔CN) — nie obsługuje języka polskiego jako języka źródłowego ani docelowego. Najbardziej aktualna jest [wersja angielska](README.md).

> Dokładne dwukierunkowe tłumaczenie treści *Gwent: The Witcher Card Game* między angielskim a chińskim — oficjalna terminologia kart, nazwy talii społeczności, slang i naturalny ton graczy Bilibili. Działa z dowolnym agentem AI lub tłumaczem.

Tłumaczenie maszynowe treści o Gwincie zawodzi w przewidywalny sposób: oficjalne nazwy kart są tłumaczone dosłownie, przydomki talii społeczności stają się nonsensem, angielski slang typu "on steroids" czy "sweet spot" zamienia się w bełkot, a cały tekst brzmi sztywno. Ten zestaw narzędzi rozwiązuje to trzywarstwowym potokiem, który blokuje dane kart, prowadzi retorykę i wyłapuje resztki.

## Możliwości

- **Dwukierunkowe i świadome kierunku** — EN→CN z tonem społeczności graczy Bilibili (krótkie, dosadne zdania, strona czynna); CN→EN w naturalny angielski zachowujący terminy społeczności. Każdy kierunek ma własny potok, więc CN→EN nie oflaguje angielskich nazw kart jako nieprzetłumaczonych resztek.
- **1366 kart zablokowanych dosłownie** — Oficjalna nazwa EN/CN każdej karty, kategoria, atrybuty (rzadkość / frakcja) i tekst zdolności są ładowane z oficjalnych danych CDPR i egzekwowane dosłownie. Dane kart nigdy nie są ponownie tłumaczone.
- **200+ nazw talii społeczności** — Przydomki, których faktycznie używają chińscy gracze (大金北, 孽鬼跳松, 赤诚骑士北, 状态帝国...), nie tłumaczenia dosłowne.
- **Wstrzykiwanie slangu i żargonu** — Angielski slang (op, brick, tutor, mulligan, on steroids, sweet spot...) jest wykrywany w źródle i wstępnie wstrzykiwany z docelowym tłumaczeniem, więc przestaje być bełkotem.
- **Zachowanie retoryki i tonu** — Metafory, hiperbola i sarkazm są tłumaczone przez *intencję*, nie słowo w słowo. "Loud design" nie stanie się "zbyt głośnym".
- **Trójwarstwowa obrona** — Warstwa twarda egzekwuje dane kart dosłownie; warstwa miękka prowadzi retorykę i styl; warstwa detekcji wyłapuje resztki i pominięte terminy na końcu.
- **Niezależne od agenta** — Każdy skrypt ma flagę `--json` z ujednoliconą kopertą `{success, exit_code, data, errors}`. Działa z Claude Code, OpenClaw, Hermes lub dowolnym agentem. Tylko biblioteka standardowa Python 3.10+, zero zależności.

## Przed / Po

| Tekst źródłowy | Zwykłe tłumaczenie maszynowe | To narzędzie |
|---|---|---|
| This build's sweet spot is at 8 provisions — loud design, on steroids. | 这个构建在8人口有甜点位置——大声的设计，在类固醇上。 | 这套的**甜点位**就在 8 人口——**存在感太强**，简直**打了鸡血**。 |
| Devotion Knights is the meta pick, but it bricks without a tutor. | 奉献骑士是元选择，但没有家庭教师它会变砖。 | **赤诚骑士北**是版本答案，没**检索**就会**卡手**。 |

(Przykłady pokazują EN→CN, ponieważ narzędzie obsługuje angielski ↔ chiński.)

## Jak to działa

Pięć faz, z których każda — poza samym tłumaczeniem — jest zautomatyzowana:

| Faza | Co się dzieje | Skrypt |
|---|---|---|
| A. Przetwarzanie wstępne | Ładuje referencje, blokuje terminy kart, wstrzykuje oficjalne efekty + podpowiedzi slangu, wyodrębnia szkielet formatu | `auto_pipeline.py pre` |
| B. Tłumaczenie | Ty lub Twój agent tłumaczycie, prowadzeni zablokowaną tabelą terminów | — |
| C. Autokontrola | Sprawdza sformułowanie, resztki, retorykę, kompletność | `phase_c_check.py` |
| D. Autorytet terminów | Ponownie weryfikuje wszystkie zablokowane dane kart dosłownie | `term_enforcer.py` |
| E. Przetwarzanie końcowe + bramka | Końcowa bramka resztek / terminów / kompletności | `auto_pipeline.py post`, `completeness_guard.py` |

Dane kart są **zablokowane, nie sugerowane**: jeśli nazwa karty lub oficjalny efekt pojawia się w źródle, tłumaczenie musi użyć oficjalnej formy chińskiej. Nowe terminy społeczności przechodzą przez bufor weryfikacji (`pending_terms.md`) przed trwałym przyjęciem.

## Uwaga o zużyciu tokenów

Narzędzie wstrzykuje zablokowaną tabelę terminów, oficjalne efekty kart i podpowiedzi slangu, aby zapewnić dokładność. Pełny przebieg (pre → tłumaczenie → post → guard) przetwarza około **30–60K tokenów** w zależności od długości artykułu — około **3× zwykłego tłumaczenia** (zmierzone ~31K na średnim artykule BC; sama tabela terminów to ~6K, większość to artykuł + dokumenty referencyjne). Ponieważ większość potoku jest mechaniczna (blokowanie terminów, detekcja resztek, sprawdzanie formatu), działa dobrze na **tańszych modelach lub w darmowym pakiecie** (Claude Haiku/Sonnet, GPT-4o-mini, DeepSeek itd.) lub dowolnym agencie z darmowym limitem — nie potrzebujesz najdroższego modelu.

*Liczba tokenów na podstawie pomiaru wstrzykiwania w fazie pre na rzeczywistym artykule BC; rzeczywiste użycie zależy od długości artykułu.*

## Szybka instalacja

```bash
curl -fsSL https://raw.githubusercontent.com/Astorian-J/Open-Gwent-Translation-Skill/main/install.sh | bash
```

Lub sklonuj ręcznie:

```bash
git clone --depth 1 https://github.com/Astorian-J/Open-Gwent-Translation-Skill.git
```

Wymaga Python 3.10+. Brak zewnętrznych zależności.

## Użycie

```bash
# 1. Przetwórz wstępnie źródło (blokuje terminy, wstrzykuje referencje)
python scripts/auto_pipeline.py pre source.md --date 2026-07 --type general

# 2. Przetłumacz (Ty lub Twój agent), używając zablokowanej tabeli terminów

# 3. Przetwórz i zweryfikuj
python scripts/auto_pipeline.py post source.md translated.txt

# 4. Końcowa bramka
python scripts/completeness_guard.py translated.txt --source source.md
```

Dodaj `--json` do dowolnej komendy, aby uzyskać wyjście czytelne maszynowo. Pełny interfejs agenta: [AGENTS.md](AGENTS.md).

## Struktura plików

```
gwent-translation-style/
├── SKILL.md                 # Claude Code workflow + constraints
├── AGENTS.md                # Agent-agnostic interface (commands / JSON / exit codes)
├── agent.json               # Machine-readable command manifest
├── install.sh               # One-line installer
├── references/              # 20 reference files
│   ├── card_names.md            # Card names (official EN<->CN)
│   ├── terminology_map.md       # EN->CN terminology
│   ├── reverse_terminology_map.md  # CN->EN terminology
│   ├── keywords_map.md          # Keyword translations
│   ├── category_map.md          # Card categories (relict, construct...)
│   ├── card_attributes_map.md   # Rarity + faction names / aliases
│   ├── competitive_terms.md     # 200+ deck names + community slang
│   ├── slang_map.md             # Slang / jargon hints (op, brick, tutor...)
│   ├── effect_text.json         # 1366 cards' official ability text
│   ├── cn_fuzzy_fixes.md        # Chinese typo / abbreviation fixes
│   ├── correction_guide.md      # Translation rules
│   ├── common_pitfalls.md       # Common mistakes
│   ├── style_reference.md       # Style + rhetoric guidelines
│   ├── style_fingerprint.md     # Author style markers
│   ├── ambiguous_names.md       # Disambiguation
│   ├── version_map.md           # Version-specific terms
│   ├── phase_c_checklist.md     # Self-check rules
│   ├── translation_workflow.md  # Workflow reference
│   ├── pending_terms.md         # Terms awaiting review (runtime data)
│   └── changelog.md             # Update history
└── scripts/                 # 16 Python scripts
    ├── auto_pipeline.py         # Single orchestration entry point
    ├── check_translation.py     # Residue + slang detection
    ├── completeness_guard.py    # Final gate
    ├── phase_c_check.py         # Self-check
    ├── term_enforcer.py         # Card data verification
    ├── context_lock.py          # Context / abbreviation lock
    ├── effect_verifier.py       # Official effect text check
    ├── build_effect_reference.py  # Rebuild effect_text.json
    ├── format_skeleton.py       # Format preservation
    ├── diff_review.py           # Diff review
    ├── backtranslate.py         # Back-translation check
    ├── lookup.py                # Term lookup
    ├── learn.py                 # Learn new terms
    ├── health_check.py          # Integrity check (44 PASS)
    ├── _shared.py               # Shared logic (TermAuthority)
    └── agent_utils.py           # JSON envelope helpers
```

## Najważniejsze terminy

Mała próbka — pełny zestaw znajduje się w `references/`.

**Nazwy talii** (rozpoznawane przez społeczność):

| Angielski | Chiński |
|---|---|
| Devotion Knights | 赤诚骑士北 |
| GN Movement | 孽鬼跳松 |
| Aristocrats | 状态帝国 |
| Lined Pockets Crimes | 宝箱罪行迪迦 |
| Blaze of Glory Eist Warriors | 荣耀圣焰征战 |

**Aliasy frakcji**: Northern Realms → 北, Skellige → 岛, Monsters → 怪, Nilfgaard → 帝, Scoia'tael → 松, Syndicate → 迪迦.

## Użytkownicy Claude Code

Zainstaluj w `~/.claude/skills/gwent-translation-style/` i uruchom ponownie Claude Code. Wyzwalacze: `/gwent-translation-style`, "translate Gwent article", "Gwent translation".

## Współtworzenie

1. Sforkuj repozytorium
2. Dodaj lub zaktualizuj terminy w `references/`
3. Nowe terminy społeczności muszą przejść przez `pending_terms.md`
4. Uruchom `python scripts/health_check.py` przed przesłaniem
5. Otwórz pull request

## Licencja

Zobacz [LICENSE](LICENSE).
