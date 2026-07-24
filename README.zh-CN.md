# 昆特牌翻译 Skill

**[English](README.md)** | **[中文](README.zh-CN.md)** | [Polski](README.pl.md) | [Русский](README.ru.md)

> 面向《昆特牌：巫师之昆特牌》内容的英中双向翻译工具——官方卡牌术语、社区卡组名、玩家黑话，以及地道的 Bilibili 玩家口吻。兼容任何 AI agent 或人工译者。
>
> **非官方粉丝作品——与 CD PROJEKT RED 无隶属、未经其认可。** 卡牌能力文本在构建时从公开 api.gwent.one 拉取，不入库；完整版权/许可边界见 [NOTICE](NOTICE)。

机翻昆特内容会在几个固定地方翻车：官方卡牌名被直译、社区卡组绰号变不知所云、英文黑话（on steroids / sweet spot）翻出来看不懂、整篇生硬。本工具用三层流水线解决：硬层锁定卡牌数据、软层引导修辞、检测层兜底漏译残留。

## 特性

- **双向 + 方向感知** —— EN→CN 用 Bilibili 玩家社区口吻（短句、主动语态）；CN→EN 译成自然英文并保留社区术语。两个方向各自独立流水线，CN→EN 不会把英文卡名误判为"未翻译残留"。
- **1366 张卡逐字锁定** —— 每张卡的官方中英文名、类别、属性（稀有度/阵营）、效果文本从 CDPR 官方数据加载并逐字强制，卡牌信息绝不"再翻译"。卡牌数据在安装时拉取（运行 `install.sh` 或 `scripts/build_effect_reference.py --fetch`），不入库——见 NOTICE。
- **200+ 社区卡组名** —— 中文玩家真正在用的绰号（大金北、孽鬼跳松、赤诚骑士北、状态帝国……），不是直译。
- **黑话/行话注入** —— 源文里的英文黑话（op、brick、tutor、mulligan、on steroids、sweet spot……）会被检测并预注入意向译法，不再翻成看不懂的东西。
- **修辞与语气保留** —— 比喻、夸张、反讽按*意图*翻译，而非逐字。"loud design"不会变成"太大声"。
- **三层防御** —— 硬层逐字强制卡牌数据；软层引导修辞与风格；检测层在最后兜底捕捉残留和漏译。
- **Agent 无关** —— 每个脚本都带 `--json` flag 和统一信封 `{success, exit_code, data, errors}`。兼容 Claude Code、OpenClaw、Hermes 或任意 agent。Python 3.10+ 标准库，零依赖。

## 翻译前后对比

| 源文 | 机翻 | 本工具 |
|---|---|---|
| This build's sweet spot is at 8 provisions — loud design, on steroids. | 这个构建在8人口有甜点位置——大声的设计，在类固醇上。 | 这套的**甜点位**就在 8 人口——**存在感太强**，简直**打了鸡血**。 |
| Devotion Knights is the meta pick, but it bricks without a tutor. | 奉献骑士是元选择，但没有家庭教师它会变砖。 | **赤诚骑士北**是版本答案，没**检索**就会**卡手**。 |

## 工作原理

五个阶段，除实际翻译外全部自动化：

| 阶段 | 做什么 | 脚本 |
|---|---|---|
| A. 译前预处理 | 加载 references、锁定卡牌术语、注入官方效果 + 黑话提示、提取格式骨架 | `auto_pipeline.py pre` |
| B. 翻译 | 你（或你的 agent）按锁定术语表翻译 | — |
| C. 自检 | 检查措辞、残留、修辞、完整性 | `phase_c_check.py` |
| D. 术语权威 | 逐字复核所有锁定的卡牌数据 | `term_enforcer.py` |
| E. 后处理 + 门禁 | 最终的残留/术语/完整性闸门 | `auto_pipeline.py post`、`completeness_guard.py` |

卡牌数据是**锁定而非建议**：源文里出现的卡牌名或官方效果，译文必须用官方中文形式。新社区术语需经审核缓冲区（`pending_terms.md`）才能正式采纳。

## 精简版（聊天翻译）

对于**短聊天内容**——群消息、Discord / QQ / Kook 评论、单句翻译——完整的五阶段流水线就太重了。**精简版** skill（`gwent-translation-lite`）把翻译精简为三步：

1. **按需查询** —— 仅在源文出现卡牌名/术语时才通过 `lookup.py` 查询；不做全量术语表预加载。
2. **翻译** —— 同样的 Bilibili 玩家 / 原生玩家口吻，官方卡牌和术语译法。
3. **自检** —— 译后心里过一遍；不跑校验脚本。

没有 `pre` 注入、没有 `completeness_guard`、没有 `term_enforcer`。精简版通过 `$GWENT_SKILL_DIR` 变量复用主 skill 的 `scripts/` 和 `references/`（零数据重复），因此在 Claude Code、hermes、opencode 等任意 agent 上都能用。

| 内容 | Skill |
|---------|-------|
| 长文章（meta 报告、BC 提案、卡牌分析） | `gwent-translation-style`（完整流水线） |
| 聊天消息、评论、单句 | `gwent-translation-lite`（3 步） |

两个 skill 由 `install.sh` 一起安装。精简版 agent 接口：[`lite/AGENTS.md`](lite/AGENTS.md)。

## 关于 token 消耗

本 skill 会注入锁定术语表、官方卡牌效果、黑话提示来保证准确。一次完整流程（pre → 翻译 → post → guard）大约消耗 **3-6 万 tokens**，视文章长度而定——约为裸翻译的 **3 倍**（中等 BC 文章实测约 31K；术语表本身约 6K，大头是文章+参考文档）。因为流水线大部分是机械操作（术语锁定、残留检测、格式检查），用**便宜或免费模型**（Claude Haiku/Sonnet、GPT-4o-mini、DeepSeek 等）或任何带免费额度的 agent 就能跑得很好，不需要最贵的模型。

*token 数值基于真实 BC 文章的 pre 阶段注入实测；实际消耗随文章长度变化。*

## 快速安装

```bash
curl -fsSL https://raw.githubusercontent.com/Astorian-J/Open-Gwent-Translation-Skill/main/install.sh | bash
```

或手动克隆：

```bash
git clone --depth 1 https://github.com/Astorian-J/Open-Gwent-Translation-Skill.git
```

需要 Python 3.10+。无第三方依赖。

## 用法

```bash
# 1. 译前预处理源文（锁定术语、注入 reference）
python scripts/auto_pipeline.py pre source.md --date 2026-07 --type general

# 2. 翻译（你或你的 agent），按锁定术语表来

# 3. 后处理并校验
python scripts/auto_pipeline.py post source.md translated.txt

# 4. 最终门禁
python scripts/completeness_guard.py translated.txt --source source.md
```

任意命令加 `--json` 获取机器可读输出。完整 agent 接口见 [AGENTS.md](AGENTS.md)。

## 文件结构

```
gwent-translation-style/
├── SKILL.md                 # Claude Code 工作流 + 约束
├── AGENTS.md                # Agent 无关接口（命令/JSON/退出码）
├── agent.json               # 机器可读命令清单
├── install.sh               # 一行安装器
├── references/              # 20 个 reference 文件
│   ├── card_overrides.md       # 卡牌别名/修正（人工维护，committed）
│   ├── card_names_4lang.json   # 卡牌名 EN<->CN（构建期生成，gitignored）
│   ├── terminology_map.md       # EN->CN 术语
│   ├── reverse_terminology_map.md  # CN->EN 术语
│   ├── keywords_map.md          # 关键词翻译
│   ├── category_map.md          # 卡牌类别（遗物、构造体……）
│   ├── card_attributes_map.md   # 稀有度 + 阵营名/缩写
│   ├── competitive_terms.md     # 200+ 卡组名 + 社区黑话
│   ├── slang_map.md             # 黑话/行话提示（op、brick、tutor……）
│   ├── effect_text.json         # 官方效果文本（构建期生成，由 build_effect_reference.py 拉取；见 NOTICE）
│   ├── cn_fuzzy_fixes.md        # 中文错字/缩写修正
│   ├── correction_guide.md      # 翻译规则
│   ├── common_pitfalls.md       # 常见错误
│   ├── style_reference.md       # 风格 + 修辞指南
│   ├── style_fingerprint.md     # 作者风格标记
│   ├── ambiguous_names.md       # 歧义消解
│   ├── version_map.md           # 版本特定术语
│   ├── phase_c_checklist.md     # 自检规则
│   ├── translation_workflow.md  # 工作流参考
│   ├── pending_terms.md         # 待审核术语（运行时数据）
│   └── changelog.md             # 更新历史
├── scripts/                 # 16 个 Python 脚本
│   ├── auto_pipeline.py         # 唯一编排入口
│   ├── check_translation.py     # 残留 + 黑话检测
│   ├── completeness_guard.py    # 最终门禁
│   ├── phase_c_check.py         # 自检
│   ├── term_enforcer.py         # 卡牌数据校验
│   ├── context_lock.py          # 上下文/缩写锁定
│   ├── effect_verifier.py       # 官方效果文本检查
│   ├── build_effect_reference.py  # 构建 effect_text.json（fetch-at-build：在线/离线）
│   ├── format_skeleton.py       # 格式保留
│   ├── diff_review.py           # diff 审查
│   ├── backtranslate.py         # 回译检查
│   ├── lookup.py                # 术语查询
│   ├── learn.py                 # 学习新术语
│   ├── health_check.py          # 完整性检查（44 PASS）
│   ├── _shared.py               # 共享逻辑（TermAuthority）
│   └── agent_utils.py           # JSON 信封辅助
└── lite/                    # 精简版 skill（聊天翻译）
    ├── SKILL.md                 # 精简版 skill 工作流（聊天翻译）
    └── AGENTS.md                # Agent 无关接口
```

## 术语示例

小部分样例——完整数据在 `references/`。

**卡组名**（社区公认）：

| 英文 | 中文 |
|---|---|
| Devotion Knights | 赤诚骑士北 |
| GN Movement | 孽鬼跳松 |
| Aristocrats | 状态帝国 |
| Lined Pockets Crimes | 宝箱罪行迪迦 |
| Blaze of Glory Eist Warriors | 荣耀圣焰征战 |

**阵营别名**：Northern Realms→北、Skellige→岛、Monsters→怪、Nilfgaard→帝、Scoia'tael→松、Syndicate→迪迦。

## Claude Code 用户

安装到 `~/.claude/skills/gwent-translation-style/` 并重启 Claude Code。触发方式：`/gwent-translation-style`、"翻译这篇昆特牌文章"、"昆特翻译"。

`install.sh` 会**一起安装主 skill 和精简版 skill**。精简版（`gwent-translation-lite`）在聊天/短内容翻译时触发——比如"翻一下这句"、聊天消息翻译。

## 贡献

1. Fork 仓库
2. 在 `references/` 增改术语
3. 新社区术语必须先经 `pending_terms.md`
4. 提交前跑 `python scripts/health_check.py`
5. 发起 pull request

## 许可证

见 [LICENSE](LICENSE)。
