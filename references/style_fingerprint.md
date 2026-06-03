# Style Fingerprint (风格指纹)

User's personal translation preferences. Updated by analyzing user's manual corrections.

## Term Preference Distribution

Recorded from user's past corrections. Higher percentage = stronger preference.

| English | Primary | Rate | Alternatives | Notes |
|---------|---------|------|--------------|-------|
| nerf | 削弱 | 80% | 来一刀 (20%) | Formal: 削弱, casual: 来一刀 |
| revert | 改回去 | 90% | 回调 (10%) | Strong preference for 改回去 |
| synergy | 康博 | 70% | 配合 (20%), 协同配合 (10%) | Card review context |
| buff | 增强 | 60% | 加强 (40%) | Near 50/50 split |
| provision (casual) | 人口 | 100% | — | Never uses "费" in formal |

## Sentence Structure Patterns

| Pattern | User Preference | vs. Default |
|---------|-----------------|-------------|
| Long sentence split | 2.3 sentences per English sentence | Default: 2-3 |
| Conclusion placement | End of paragraph, short | Same as default |
| Parentheses style | 100% Chinese brackets 「（）」 | Same as default |
| Number style | 100% Arabic numerals | Same as default |

## Verb Preference Ranking

User's most frequently chosen oral verbs (from past translations):

| Rank | Verb | Usage Count | Context |
|------|------|-------------|---------|
| 1 | 赚翻 | 12 | "获得利润" → 赚翻 |
| 2 | 撑过 | 10 | "站住/存活" → 撑过 |
| 3 | 拍下 | 8 | "打出" (节奏卡) → 拍下 |
| 4 | 塞进 | 7 | "加入" → 塞进 |
| 5 | 处理掉 | 6 | "移除/解掉" → 处理掉 |
| 6 | 骗出 | 5 | "诱出" → 骗出 |
| 7 | 不管她 | 4 | "未被解掉" → 对手不管她 |
| 8 | 回调到 | 3 | "调整回" → 回调到 |

## Community Slang Preference

| Slang | User Choice | Confidence |
|-------|-------------|------------|
| Arachas Swarm | 蟹蜘蛛 | Confirmed |
| GN Shupe | 孽鬼店店 | Confirmed |
| Armor abuse | 互口岛 | Confirmed |
| Fruits | 蛆妈 / 破烂怪 | Context-dependent |
| no unit | 气宗 | Confirmed |

## Update Method

After each translation where user provides corrections:
1. Record user's choice vs. skill's default
2. Update percentage in this file
3. If preference rate > 80%, promote to "strong preference"
4. If preference rate > 95%, update SKILL.md to make it the default

## How to Apply

When translating, check this file first:
- If a term has a "strong preference" (>80%), use that translation
- If near 50/50, use context to decide (card review vs. formal analysis)
- If no record, fall back to terminology_map.md default
