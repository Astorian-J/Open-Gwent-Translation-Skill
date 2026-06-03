# Gwent Translation Skill

A Claude Code Skill for translating Gwent: The Witcher Card Game content between English and Chinese. Optimized for accurate terminology, community deck names, and natural expression.

## Features

- **Bidirectional Translation**: EN↔CN with separate workflows for each direction
- **68 Verified Deck Names**: Community-recognized Chinese nicknames for competitive decks
- **42 Leader Names**: Aligned with official Gwent v12.8.0 card data
- **Faction Slang**: Unified Syndicate faction alias to 迪迦
- **Terminology Injection**: Auto-detects card names and injects standard translations into prompts
- **Human Review Buffer**: New terms go through `pending_terms.md` before permanent adoption

## Quick Install

One-line installation:

```bash
curl -fsSL https://raw.githubusercontent.com/Astorian-J/Open-Gwent-Translation-Skill/main/install.sh | bash
```

Or clone manually:

```bash
git clone --depth 1 https://github.com/Astorian-J/Open-Gwent-Translation-Skill.git ~/.claude/skills/gwent-translation-style
```

## Update

```bash
cd ~/.claude/skills/gwent-translation-style && git pull
```

## Uninstall

```bash
rm -rf ~/.claude/skills/gwent-translation-style
```

## Usage

After installation, restart Claude Code. The skill activates when you:

- Type `/gwent-translation-style`
- Say "translate Gwent article"
- Say "Gwent translation"

## File Structure

```
~
└── .claude/skills/gwent-translation-style/
    ├── SKILL.md                 # 10-step workflow + constraints
    ├── references/              # 15 reference files
    │   ├── card_names.md        # Card name translations (official)
    │   ├── terminology_map.md   # EN→CN terminology
    │   ├── reverse_terminology_map.md  # CN→EN terminology
    │   ├── keywords_map.md      # Keyword translations
    │   ├── category_map.md      # Card category translations
    │   ├── competitive_terms.md # Deck names + community slang
    │   ├── cn_fuzzy_fixes.md    # Chinese typo/abbreviation fixes
    │   ├── correction_guide.md  # Translation rules
    │   ├── common_pitfalls.md   # Common mistakes to avoid
    │   ├── style_reference.md   # Style guidelines
    │   ├── style_fingerprint.md # Author style markers
    │   ├── ambiguous_names.md   # Disambiguation guide
    │   ├── version_map.md       # Version-specific terms
    │   ├── pending_terms.md     # Terms awaiting human review
    │   └── changelog.md         # Update history
    └── scripts/                 # 10 utility scripts
        ├── translate.py
        ├── check_translation.py
        ├── diff_review.py
        ├── backtranslate.py
        ├── lookup.py
        ├── format_skeleton.py
        ├── context_lock.py
        ├── learn.py
        ├── health_check.py
        └── backtranslate.py
```

## Terminology System

### Leader Names (Official)

| English | Chinese | ID |
|---------|---------|-----|
| Blaze of Glory | 荣耀圣焰 | 202576 |
| Patricidal Fury | 鸣镝动怒 | 202119 |
| Inspired Zeal | 灼心狂热 | 200168 |
| Lined Pockets | 盆满钵满 | 122105 |
| Off the Books | 黑市买卖 | 202328 |
| Hidden Cache | 军备宝箱 | 202577 |
| Jackpot | 头号大奖 | 202373 |

### Community Deck Names

| English | Chinese |
|---------|---------|
| Viraxas Zeal | 大金北 |
| GN Movement | 孽鬼跳松 |
| Devotion Knights | 赤诚骑士北 |
| Lined Pockets Crimes | 宝箱罪行迪迦 |
| Aristocrats | 状态帝国 |
| Blaze of Glory Eist Warriors | 荣耀圣焰征战 |
| Patricidal Fury Warriors | 鸣镝动怒征战 |
| Renfri Blaze of Glory | 鸣镝动怒鸟岛 |
| Lippy decks | 现冥卡组 |
| Armor Exploit deck | 互口岛 |

### Faction Aliases

| Faction | Alias |
|---------|-------|
| Northern Realms | 北 |
| Skellige | 岛 |
| Monsters | 怪 |
| Nilfgaard | 帝 |
| Scoia'tael | 松 |
| Syndicate | 迪迦 |

## Translation Rules

### Unknown Deck Names

When encountering a deck name without a community alias, follow this pattern:

**Format**: `Card/Mechanic + Leader + Faction Alias`

Examples:
- `Blaze of Glory Eist Warriors` → 荣耀圣焰征战岛 (but community uses 荣耀圣焰征战)
- `Patricidal Fury Warriors` → 鸣镝动怒战士岛 (but community uses 鸣镝动怒征战)

Always prioritize community names when available.

## Contributing

1. Fork the repository
2. Add or update terms in `references/`
3. New terms must pass through `pending_terms.md` before permanent adoption
4. Submit a pull request

## License

See [LICENSE](LICENSE).
