# Common Pitfalls (常见陷阱)

Systematic error patterns. Check this list before finalizing any translation.

## Category 1: Provision Terminology (人口术语)

### Trap 1.1: "费" in formal contexts

| Severity | Pattern | Example |
|----------|---------|---------|
| Critical | 数字 + 费/费用/消耗 | "12费用" → "12人口" |
| Critical | 高费/低费 (formal) | "高费铜卡" → "高人口铜卡" |
| Medium | 费/费换 (in parentheses) | "(5费换7战力)" → "(5人口换7战力)" |

**Rule**: In deck-building contexts, provision is always "人口". "费" is only allowed in casual shorthand like "4费战士" or "低费" when consistently used within one article.

### Trap 1.2: Identical numbers in "X人口Y战力"

| Severity | Pattern | Example |
|----------|---------|---------|
| Critical | "X人口X战力" (same number) | "5人口5战力" → check if reversed |

**Rule**: "X for Y" means X=power, Y=provision. Output "Y人口X战力". If both numbers are identical, you likely reversed them or made a copy-paste error.

### Trap 1.3: Number reversal

| Severity | Pattern | Example |
|----------|---------|---------|
| High | Population much higher than power | "9人口3战力" for "3 for 9" |

**Rule**: Most cards have provision >= power, or close to it. If you see "20人口5战力", double-check the source.

## Category 2: Card Name Errors (卡名错误)

### Trap 2.1: Half-translated card names

| Severity | Pattern | Example |
|----------|---------|---------|
| High | Base name only, missing subtitle | "杰洛特" → should specify which Geralt |
| High | Wrong subtitle translation | "雷吉斯的鸣镝动怒" → "雷吉斯：血欲化身" |

**Rule**: Cards with colons (Geralt: Igni, Regis: Bloodlust) must include both parts. Check ambiguous_names.md when uncertain.

### Trap 2.2: Outdated card names

| Severity | Old | Correct |
|----------|-----|---------|
| Medium | 沙暴 | 沙尘暴 |
| Medium | 伊魅柯 | 伊魅珂 |
| Medium | 埃斯特·图尔赛赫 | 埃斯特·图尔赛克 |
| Medium | 夜宴 | 女巫夜宴 |
| Medium | 怀柔 (as Tactical Decision) | 战术决策 |

**Rule**: Check card_overrides.md "Renamed / Corrected" section for outdated names.

### Trap 2.3: Leader name confusion

| Severity | Wrong | Correct | Why |
|----------|-------|---------|-----|
| High | 怀柔 = Tactical Decision | 战术决策 | "怀柔" is shorthand for 怀柔兼济 (Double Cross) |
| High | 鸣镝动怒 = Regis | 雷吉斯：血欲化身 | 鸣镝动怒 is a SK leader, not Regis |
| Medium | 帝国阵线 | 帝国列阵 | Wrong character |

**Rule**: Leaders have specific names. Don't use shorthand from one leader for another.

## Category 3: Voice and Tone (语态和语气)

### Trap 3.1: Passive voice

| Severity | Wrong | Correct |
|----------|-------|---------|
| Medium | 未被解掉 | 对手不管她 |
| Medium | 被削弱 | 来了一刀 / 挨削 |
| Medium | 被增强 | 加强了 |
| Low | 被打出 | 拍下 / 塞进 |

**Rule**: Active voice reads more naturally in Chinese. Add the subject (对手, 玩家) when needed.

### Trap 3.2: Machine translation tone

| Severity | Wrong | Correct |
|----------|-------|---------|
| Medium | 获得利润 | 赚翻 |
| Medium | 加入卡组 | 塞进卡组 |
| Medium | 打出卡牌 | 拍下 |
| Low | 移除单位 | 处理掉 |
| Low | 站住/存活 | 撑过 |

**Rule**: Use oral Chinese verbs. See correction_guide.md Section 4.

## Category 4: Number Format (数字格式)

### Trap 4.1: Chinese numerals

| Severity | Wrong | Correct |
|----------|-------|---------|
| Medium | 五点战力 | 5点战力 |
| Medium | 十二人口 | 12人口 |
| Medium | 第三小局 | R3 |

**Rule**: Always Arabic numerals in Gwent context.

### Trap 4.2: Round notation

| Severity | Wrong | Correct |
|----------|-------|---------|
| Low | 第一轮/第一局 | R1 / 第一小局 |
| Low | 第二局 | R2 / 第二小局 |

**Rule**: "R1/R2/R3" is standard in competitive discussion. "小局" is acceptable in casual context.

## Category 5: Punctuation (标点符号)

### Trap 5.1: English parentheses

| Severity | Wrong | Correct |
|----------|-------|---------|
| Low | (补充说明) | （补充说明） |

**Rule**: Use Chinese brackets 「（）」not English ().

### Trap 5.2: English colon in card names

| Severity | Wrong | Correct |
|----------|-------|---------|
| Medium | 米尔瓦:神射手 | 米尔瓦：神射手 |
| Medium | 丹德里恩:传奇诗人 | 丹德里恩：传奇诗人 |

**Rule**: Card name separators use Chinese colon "：".

### Trap 5.3: Quotes

| Severity | Wrong | Correct |
|----------|-------|---------|
| Low | "咯咯哒"艾伯伦特 | "咯咯哒"艾伯伦特 |

**Rule**: Follow server data exactly for quote style.

## Category 6: Terminology Consistency (术语一致性)

### Trap 6.1: Mixed terminology within article

| Severity | Wrong | Correct |
|----------|-------|---------|
| High | 正文用"人口"，括号用"费" | 统一用"人口" |
| Medium | 前文用"康博"，后文用"协同效应" | 统一用词 |

**Rule**: Pick one translation per article and stick to it.

### Trap 6.2: Synonym inconsistency

| Severity | Wrong | Correct |
|----------|-------|---------|
| Medium | 增强/加强/提升 混用 | 选一种，全文统一 |
| Medium | 削弱/来一刀/挨削 混用 | 根据语气统一 |

**Rule**: See terminology_map.md "Flexible" section for guidance.

## Category 7: Abbreviation Handling (缩写处理)

### Trap 7.1: Unexpanded abbreviations

| Severity | Wrong | Correct |
|----------|-------|---------|
| Medium | BC | 平衡委员会 (first mention) |
| Medium | OP | 超模 / Overpowered (first mention) |
| Low | R1 | R1 (OK, widely understood) |
| Low | CA | 卡差 (first mention: 卡差(card advantage)) |

**Rule**: Expand abbreviations on first use in an article. R1/R2/R3 and NG/NR/MO/SK/ST/SY are exceptions (widely understood).

### Trap 7.2: Wrong abbreviation expansion

| Severity | Wrong | Correct |
|----------|-------|---------|
| High | BC = Behind Cover | BC = Balance Council |
| Medium | OP = Original Poster | OP = Overpowered |
| Medium | RSS = Really Simple Syndication | RSS = Redanian Secret Service |

**Rule**: Context matters. "OP" in card discussion means Overpowered, not Original Poster.

## Pre-Submission Checklist

Before delivering translation, verify:

- [ ] No "费/费用" in formal provision contexts
- [ ] "X for Y" translated as "Y人口X战力" (numbers not identical)
- [ ] Card names match card_names_4lang.json (official card names)
- [ ] Ambiguous card names include full subtitle
- [ ] Passive voice converted to active
- [ ] Arabic numerals throughout
- [ ] Chinese parentheses 「（）」used
- [ ] Chinese colon "：" in card names
- [ ] Abbreviations expanded on first use
- [ ] Terminology consistent within article
