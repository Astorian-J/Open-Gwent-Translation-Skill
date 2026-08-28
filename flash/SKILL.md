---
name: gwent-translation-flash
description: |
  Gwent (昆特牌) FASTEST translation for live chat — single pass, ZERO scripts,
  ZERO verification. One turn: read the message, translate, reply. For fast-paced
  chat where waiting a minute means missing the conversation.
  Triggered by: 昆特秒翻, 昆特极速翻译, 昆特快翻, gwent flash translate, translate fast.
  Trade-off: card names come from model memory with NO machine check. When the
  content matters or has unfamiliar card names, use gwent-translation-lite (adds
  a machine term gate). For full articles, use gwent-translation-style.
agent_created: true
---

# Gwent Translation Flash (昆特极速翻译)

> 三层速查：完整文章用 `gwent-translation-style`（全量门禁）；
> 聊天要保底用 `gwent-translation-lite`（prepare + finish --lite 机器核对）；
> **本 skill = 聊天抢速度：一轮直翻，不跑任何脚本，不核对。**

## 你现在的任务

**本 skill 一被调用 = 你现在要做昆特牌翻译。** 不是聊天、不是分析。
拿到内容 → 判断方向（EN↔CN）→ **直接翻译，立刻回复译文**。
不存文件、不跑脚本、不查库、不自我验证流程——一轮完成。

## 何时用 / 何时不用

- **用**：直播聊天、群消息连发、别人已经刷屏的场景，用户催速度
- **不用**：不确定的卡名 / 正式内容 / 用户没催速度——用 `gwent-translation-lite`（多一轮机器核对，防翻错卡名）

---

## 翻译规则

- **EN → CN**：B 站玩家口语。短句、主动语态、阿拉伯数字（5点 / 12人口 / R3）、中文括号「（）」
- **CN → EN**：native player 口气。casual 不书面，英文括号 ( )
- **禁用破折号**：别用「——」引出或补充文字（AI 味重），改用逗号 / 句号 / 括号；英文方向同理不用 —
- **修辞 / 夸张 / 反讽**：译意图不译字面（`loud design` → 存在感太强，不是「太大声」）
- **黑话保留味道**：`bleed` → 逼牌，`brick` → 卡手，`tutor` → 检索

## 专有名词规则（无核对版，凭记忆要稳）

- 卡名 / 人名用你记忆里**最通行的官方译名**，禁止自创新译名
- **阵营缩写别搞反**：NG = 尼弗迦德（Nilfgaard），NR = 北方领域（Northern Realms），字形近但完全两个阵营
- 没把握的冷门名，照官方名最接近的写法翻，宁可保留原味也别造词
- 翻完直接发。**本版本不核对**——发现翻错了，下一条消息更正即可

---

## 速查表

### 阵营

| 缩写 | 英文 | 中文 |
|------|------|------|
| MO | Monsters | 怪兽 |
| NR | Northern Realms | 北方领域 |
| NG | Nilfgaard | 尼弗迦德 |
| SK | Skellige | 史凯利格 |
| ST | Scoia'tael | 松鼠党 |
| SY | Syndicate | 辛迪加 |
| NE | Neutral | 中立 |

### 高频术语

| 英文 | 中文 | 备注 |
|------|------|------|
| provision | 人口 | 不是「费用」 |
| deploy | 部署 | 最常见关键词 |
| bleed | 逼牌 | R1 消耗对手资源 |
| brick | 卡手 | 抽到打不出的牌 |
| thin | 滤牌 / 压缩 | 减少牌组 |
| dry pass | 空过 | 直接过小局 |
| blue coin | 蓝币 | = 先手 |
| red coin | 红币 | = 后手 |
| coin flip | 先后手 / 硬币 | 开局先后手归属 |
| tutor | 检索 | 找特定牌 |
| highroll / lowroll | 上限发挥 / 下限发挥 | 最好 / 最坏情况 |
| tempo | 节奏 | 每回合点数 |

### 社区黑话（卡组 / 俗称）

| 英文 | 中文 |
|------|------|
| no unit archetype | 气宗 |
| Arachas Swarm | 蟹蜘蛛 |
| Fruits / Fruits midrange | 蛆妈 / 破烂怪 |
| Devotion Knights (NR) | 赤诚骑士北 |
| Armor abuse (SK) | 互口岛 |
| enemy boost (NG) | 毒奶 |

> 表里没有的词凭记忆翻。这条消息发出后对话还在继续，错了下一轮更正——速度优先。
