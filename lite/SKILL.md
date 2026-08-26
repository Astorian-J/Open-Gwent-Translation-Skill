---
name: gwent-translation-lite
description: |
  Gwent (昆特牌) lightweight translation for short chat content — group messages,
  Discord/QQ comments, single sentences, brief remarks. 3-step flow with a
  lightweight machine term gate (prepare -> translate -> finish --lite).
  Triggered by: 昆特聊天翻译, 昆特群消息翻译, 昆特短句翻译, Gwent chat translation, quick Gwent translate.
  For full articles (meta reports, BC proposals, card analysis), use gwent-translation-style instead.
agent_created: true
---

# Gwent Translation Lite (昆特聊天短翻译)

> 短聊天内容用本 skill。完整文章（meta report / BC 提案 / 卡牌分析）用 `gwent-translation-style`
> （同一条流水线跑全量门禁，不带 `--lite`）。

## 你现在的任务

**本 skill 一被调用 = 你现在要做昆特牌翻译。** 不是聊天、不是分析。
立刻：拿到要翻的内容 → 判断方向（EN↔CN）→ 按下方 3 步走。
用户贴了昆特牌中/英文没明说「翻译」，默认就是要翻译，直接翻。

## 何时用

- 群消息、Discord/QQ/Kook 评论、单句、短段落（< ~200 字）
- 非正式口语内容
- 用户说「翻一下这句」「这段聊天什么意思」「quick translate」

**不要用本 skill**：长文章翻译——用 `gwent-translation-style`（不带 `--lite` 的完整门禁）。

---

## 专有名词铁律（最重要的一条）

源文里的人名 / 卡牌名 / 关键词 / 机制词，凡疑似昆特牌专有名词：
**一律用官方译名（prepare 锁表 / lookup 查询结果），禁止凭记忆自创译名。**
你自己「记得」的译名可能是错的——这正是机器核对存在的原因。

---

## 流程（3 步：prepare → 翻译 → finish --lite 机器核对）

先定位主 skill 目录（首次使用时跑一次，后续命令复用 `$GWENT_SKILL_DIR`）：

```bash
# 三选一：环境变量 > Claude Code 默认 > hermes 默认
GWENT_SKILL_DIR="${GWENT_SKILL_DIR:-$HOME/.claude/skills/gwent-translation-style}"
[ -d "$GWENT_SKILL_DIR" ] || GWENT_SKILL_DIR="$HOME/.hermes/skills/gwent-translation-style"
```

> **两条默认路径都不存在时**（自定义 INSTALL_DIR 装的，如 `~/.agents/skills/`）：
> 主 skill 就在本 lite 目录的上一级的兄弟目录——`<本文件所在目录>/../gwent-translation-style`
> （install.sh 的标准布局）。按你读到本文件的实际路径推算后 `export GWENT_SKILL_DIR=<该路径>`。

### 第 1 步：prepare（存文件 + 拿锁表）

把要翻的内容存成临时文件，跑 prepare 生成术语锁表 pack：

```bash
printf '%s\n' "要翻译的内容" > /tmp/gwent-lite-src.md
python3 "$GWENT_SKILL_DIR/scripts/translate.py" prepare /tmp/gwent-lite-src.md
```

读生成的 `/tmp/gwent-lite-src.pack.md`，重点看：

- **[COPY] MANDATORY Term Lock Table** — 锁定术语，必须照抄这些译名
- **[COPY] Ambiguous Names** — 歧义卡名：按语境线索选版本，用全名
- **专有名词铁律**（pack 顶部）— 锁表没锁但疑似卡名的词，先查再翻：
  `python3 "$GWENT_SKILL_DIR/scripts/lookup.py" "<词>" --plain`

短内容的 pack 很小（几 KB），放心读。

### 第 2 步：翻译

按方向翻译（EN→CN 或 CN→EN），照 pack 的 [COPY] 节译名 + 快速参考表：

- **EN → CN**：B 站玩家口语。短句、主动语态、阿拉伯数字（5点 / 12人口 / R3）、中文括号「（）」
- **CN → EN**：native player 口气。casual 不书面，英文括号 ( )
- **修辞 / 夸张 / 反讽**：译意图不译字面（`loud design` → 存在感太强，不是「太大声」）
- **黑话保留味道**：`bleed` → 逼牌，`brick` → 卡手，`tutor` → 检索——不要书面化

译完存文件：

```bash
printf '%s\n' "你的译文" > /tmp/gwent-lite-out.md
```

### 第 3 步：finish --lite（机器核对，修到 PASS 才算完）

```bash
python3 "$GWENT_SKILL_DIR/scripts/translate.py" finish /tmp/gwent-lite-out.md \
  --source /tmp/gwent-lite-src.md --lite
```

- **PASS** → 把译文发给用户，完成。
- **BLOCKED** → 每条违规都带官方译法（`「term」 -> 官方译名`），照着改译文文件，重跑第 3 步。
  最多改 3 轮；仍 BLOCKED 就把违规清单和你的译文一起给用户看，说明哪些词查不到官方译名。

`--lite` 只跑术语 / 残留 / 译名权威核对（聊天内容够用），跳过文章级的风格检查和新词学习。

**不要跑以下脚本**（这些是完整文章用的）：

- `auto_pipeline.py` / `phase_c_check.py` / `term_enforcer.py` / `completeness_guard.py` — 已在 prepare / finish 内部运行，别手动跑
- `learn.py` / `diff_review.py` / `backtranslate.py` / `format_skeleton.py` — 完整文章流程用
- finish **不带** `--lite` — 会跑文章级风格检查，对聊天短句误报

---

## 快速参考（高频，查表代替 lookup）

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

> 表里没有的具体卡名 / 冷门术语，调 `lookup.py` 查（第 1 步 prepare 的锁表通常已覆盖）。
