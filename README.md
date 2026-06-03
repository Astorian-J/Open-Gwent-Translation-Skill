# Open Gwent Translation Skill

Dedicated to translating Gwent: The Witcher Card Game content. Supports EN-CN bidirectional translation with accurate terminology, community deck names, and auto-updating vocabulary.

## Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/Astorian-J/Open-Gwent-Translation-Skill/main/install.sh | bash
```

Or manually:

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

After installation, restart Claude Code or type `/` to activate the skill.

Trigger phrases:
- "Translate Gwent article"
- "Gwent translation"
- `/gwent-translation-style`

## Features

- **68 verified deck names** with community Chinese nicknames
- **42 leader names** aligned with official v12.8.0 card data
- **Faction slang**: SY (Syndicate) unified to 迪迦
- **Terminology injection**: Auto-detects card names and injects into prompts
- **Bidirectional**: EN→CN and CN→EN workflows

## License

See [LICENSE](LICENSE).
