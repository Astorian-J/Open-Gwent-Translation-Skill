# Changelog

## 2026-08-20 — 触发词收窄 + 检查器 fail-closed（H1/H2/M5/M9）

审查报告 6 项修复，核心是消除"假 PASS"与 skill 触发劫持：

- **H3 触发词收窄**：主版 `SKILL.md` frontmatter 的「英文翻译」改为「昆特牌英文翻译」；
  lite 版 7 个无限定触发词（聊天翻译 / 群消息翻译 / 短句翻译 / chat translation /
  quick translate / 翻一下这句 / 这段说什么）逐个加昆特限定或删除，普通翻译请求
  不再被劫持成昆特翻译。已安装副本（~/.claude/skills/gwent-translation-lite）同步。
- **H1 term_enforcer 崩溃 fail-closed**：`check_translation.py` 与 `phase_c_check.py`
  中 term_enforcer 非零退出且 stdout 无合法 JSON envelope（或缺 `data` 键）时，不再
  静默返回空违规列表，改为产出 `[checker error] term_enforcer crashed (exit N)` issue，
  进入报告并影响退出码。
- **H2 `--fix` 保留 TA 违规**：`check_translation.py --fix` 重跑后整体重赋值 issues 导致
  term authority 违规丢失；现 TA 违规单独收集、重跑后并回，修复后仍在输出与退出码中。
- **M5 CJK suppress 裸吞异常**：`term_enforcer.py` 的 `_build_cjk_suppress` 加载
  TermAuthority 失败时向 stderr 打 WARN（suppress 不完整、可能假阳性），不再静默 pass；
  `ta._cn_entries` 私有访问改为 `_shared.py` 新增的公开 `cn_entries` property。
- **M9 guard lock 构建失败 fail-closed**：`completeness_guard.py` 提供了 `--source` 但
  lock 构建失败时，term_authority 检查判不通过（status=error），整体 BLOCKED；未提供
  source 的 `skipped` 语义不变。lock 构建失败的 `[WARN]` 诊断改打 stderr，保持 stdout
  纯 JSON。

### 返工（终审 ⚠️ Needs fixes：2 条 Important + 回归测试）

- **R1 守卫判值不判键**：`json_output` 的错误 envelope 恒含 `"data": null`（键存在、值
  为 null），旧守卫 `"data" not in parsed` 放行后在 `None.get` 上 AttributeError。
  `check_translation.py` 与 `phase_c_check.py` 两处守卫改为
  `not isinstance(parsed, dict) or not isinstance(parsed.get("data"), dict)`，
  消息优先拼 envelope `errors` 字段（比 stderr 尾巴可读），否则取 stderr 末尾。
- **R2 M5 降级信号进数据面**：stderr WARN 在管线里被 `capture_output=True` 丢弃，损坏
  references 会把 BLOCKED 翻成假 PASS。现 `_build_cjk_suppress` 返回
  `(suppress, degraded)`，`enforce_terms` 结果带 `warnings` 进 JSON envelope；
  降级计入 term_enforcer 自身退出码与 plain 输出 `Issues:` 总数；三个调用方
  （check_translation / phase_c_check / completeness_guard）读到 `data.warnings`
  一律转成 `[checker warning] term_enforcer degraded: ...` 计issue、卡退出码。
  端到端语义：references 损坏时管线必 FAIL/带降级 issue，不得干净 PASS。
- **R3 回归用例**：`test_rebuild.py` 新增 4 条（H1 守卫含 null-envelope 分支 / H2
  `--fix` 保留 TA / M9 lock 构建失败 / M5 降级传播），总数 7→11，health_check 自动纳入。

## 2026-07-23 — CDPR 版权文本清理（effect_text.json 改 fetch-at-build + NOTICE）

公开仓库原 git 跟踪 references/effect_text.json（1366 张卡的 CDPR 官方能力文本），
属第三方版权内容分发。本轮清理（经 4 路 workflow 对抗验证：版权严格派 vs 务实派 /
影响面 / 技术方案）：

- effect_text.json 移出 git 跟踪（.gitignore + git rm --cached），改为**构建期产物**。
- scripts/build_effect_reference.py 新增 `--fetch` 在线模式（urllib stdlib，零依赖）：
  从 api.gwent.one 拉 en+cn 单语言端点，按 card_id join；保留 `--src` 本地离线模式。
  原子写（tempfile + os.replace）防崩溃半写损坏。install.sh 安装时自动跑 `--fetch`
  （失败降级，翻译不受影响）。
- health_check：effect_text.json 缺失从 FAIL 改为 INFO（构建期产物缺失非仓库损坏，
  附 build 提示）；保留文件存在时的 parse/count 检查。
- 新增 NOTICE：CDPR 归属 + GPL 边界切分（只覆盖原创代码，不覆盖 CDPR 数据）+
  unofficial 标注 + 非商业 + 数据源溯源 + 撤回风险。
- card_names.md / keywords_map.md **保留**（事实信息 + 核心运行时依赖，缺失会让
  skill 停摆），NOTICE 已声明其 CDPR 衍生属性不在 GPL 内。
- 四语种 README 目录树 effect_text.json 注释改 build-time + 加 unofficial 标注。

## 2026-06-30 — Slang 预防 + 检测（黑话"看不懂"修复）

用户痛点：英文黑话（slang/jargon）翻出来"看不懂"。预防为主、检测兜底，两者都做。
黑话词典刻意不进术语强制锁（保留硬层卡牌信息 / 软层修辞分层）。

### 预防层（pre 注入，主力）
- 新增 `references/slang_map.md`（30 条：评价俚语 / 习语比喻 / 动作机制），3 列对齐 category_map。
- `_shared.py`：`_load_slang_map` + `get_slang_for_text`（小写扫描源文黑话，多词短语 re.escape），**不调 _register**（不进强制锁）。
- `auto_pipeline.py pre`：扫源文黑话，注入 `slang_hints`（封顶 `SLANG_HINTS_CAP=15`，复用 official_effects 模式）。
- `SKILL.md` Phase A：提示 `slang_hints` 为意向译参考（hint 非硬锁）。

### 检测层（check_translation warn，兜底）
- `check_translation` 加 `source_text` 参数，返回 `(issues, warnings)`。
- 反向扫描：源文黑话（gameplay 上下文）+ 译文缺意向译 → warn（不 block）。
- `_slang_in_context` 误报控制（±20 字符窗口需含 card/deck/meta 等语境词）。
- warnings 不进 exit code（exit 只看 issues）；JSON 加 `warnings`/`warning_count`。
- 调用方适配：`phase_c_check.py:110` 解包；subprocess 调用方零改。

## 2026-06-24 — Card-info Enforcement (categories / attributes / effects)

用户原则：**所有卡牌信息（名称/词条/效果/阵营/边框/稀有度/类别）必须强制用既定译法**；
修辞/语气走引导。审计发现硬层有漏，本轮补齐。

### Phase 1 — 类别（category_map 之前是孤儿，relict→遗物 的根因）
- `scripts/_shared.py`：新增 `_load_category_map()`，按现有 loader 约定解析三张表，
  `—`/空 CN 跳过、通用词黑名单 SKIP_CATEGORY 跳过，注册 Gwent 专属类别
  （relict/insectoid/construct/...）。
- 新增 **小写类别词扫描**（仿已有的歧义名扫描）：类别词在散文里通常小写
  （"GN relicts"），大写短语提取器抓不到；扫描后 relict 等才会被锁定+强制
  （译文写"遗物"触发 term_missing_or_literal → completeness_guard 拦截）。

### Phase 2 — 卡牌属性（稀有度 + 阵营缺口）
- 新增 `references/card_attributes_map.md`：稀有度（common/rare/epic/legendary↔普通/稀有/史诗/传奇）、
  阵营全名+缩写（补 Neutral/中立、缩写 NR/MO/SK/ST/NE，原先只有 NG/SY 偶然漏入）。
- `scripts/_shared.py`：新增 `_load_card_attributes_map()`；阵营缩写经 _add_abbrev 注册后
  被 extract_abbreviations 锁定强制；非通用阵营全名（Nilfgaard/Skellige/...）加小写扫描，
  通用 Monsters/Neutral 走缩写 MO/NE 避免误伤。
- 边框颜色 gold/bronze 已在 keywords_map 强制（文件里注明），silver 随版本移除。

### Phase 3 — 官方效果文本（注入 + 自检；term-lock 不适合长句）
- 新增 `scripts/build_effect_reference.py`：从 `~/gwent-card-db/tables/cards_{en,cn}.json`
  生成 `references/effect_text.json`（1366 卡，EN+CN 官方 ability，0 NULL）。
- `scripts/_shared.py`：新增 `_load_effect_text()` + `get_official_ability(en)`。
- `scripts/auto_pipeline.py` pre：新增 OFFICIAL EFFECT TEXT 表 + JSON 字段 official_effects，
  把源文出现的卡的官方 CN 效果注入给 agent 逐字照抄（长句强制的实际手段）。
- 新增 `scripts/effect_verifier.py`：**信息性**自检（官方效果是否在译文逐字出现），
  不进 block 门（效果缺席可能只是没引用）。
- `references/phase_c_checklist.md`：加 manual 自检 encn-12 / cnen-10（引用效果与官方一致）。

### 验证
health_check 通过；encn 回归 issue_count=7 不变；relict→遗物 端到端被拦、残物通过；
阵营缩写/全名强制生效；pre 注入官方效果；effect_verifier 信息性输出。

## 2026-06-24 — Figurative Language & Tone Judgment

### Added
- `references/style_reference.md`: new section 《修辞与语气判断》 — rules + a
  real-example table for metaphor / hyperbole / sarcasm / mockery
  (译意图不译字面，保留"咬人味"). Grounded in an actual BC33 Reddit translation
  (on steroids / loud design / sweet spot / guess what / sink / toxic /
  dismissive tone).
- `SKILL.md` Phase B: added a "Rhetoric" row to both the EN→CN and CN→EN tables.
- `references/phase_c_checklist.md`: added manual checks encn-11 / cnen-09
  (figurative intent preserved, irony not flattened).

### Why
Translation notes from real BC content showed figurative / sarcastic lines were
handled inconsistently — some kept the bite (沉底 / 你猜怎么着), others got flattened
(sweet spot → 该去的位置) or translated too literally (loud design → 太大声). The
skill steered the overall tone but never told the agent to judge rhetoric on a
per-sentence basis.

## 2026-06-03 — Server Verification & Restructure

### Structural Changes
- Reorganized from flat files to `references/` subdirectory
- Eliminated redundancy between SKILL.md and reference files
- Added `keywords_map.md` (game keyword translations from server data)
- Added `card_names.md` with server-verified mappings
- Added `changelog.md` (this file)

### Corrections (from server card_data.json verification)
- `沙暴` → `沙尘暴` [202205]
- `伊魅柯` → `伊魅珂` [202370]
- `埃斯特·图尔赛赫` → `埃斯特·图尔赛克` [202883]
- `咯咯哒 艾伯伦特` → `"咯咯哒"艾伯伦特` (quote format)
- `布洛妮` → `布蕾恩` [142209]
- `雷吉斯的鸣镝动怒` → `雷吉斯：血欲化身` [202195] (原映射错误: 鸣镝动怒是领袖名)
- `怀柔` → `战术决策` [200164] (原映射错误: 怀柔是怀柔兼济的简称)
- `夜宴` → `女巫夜宴` [203054]

### Fixes to Incorrect Mappings
- `Tactical Decision` was incorrectly mapped to `怀柔`; corrected to `战术决策`
- `Regis: Bloodlust` was incorrectly mapped to `雷吉斯的鸣镝动怒`; corrected to `雷吉斯：血欲化身`
- Added note: "蟹蜘蛛" is community slang for deck/leader, not a single card

### Added
- 42 verified leader names
- 50+ game keywords with frequencies from server data
- Faction full names (English + Chinese)
- Self-check checklist in SKILL.md workflow

## 2026-06-03 — Supplemental References & Auto-Detection

### New Reference Files
- `ambiguous_names.md` — 40+ cards with multiple versions (e.g., 杰洛特 x6, 雷吉斯 x4, 特莉丝 x4)
- `competitive_terms.md` — 150+ competitive/community terms, including blog glossary data (16 terms from https://cngwentbd.top/glossary/)
- `common_pitfalls.md` — 7 categories of systematic errors with severity levels
- `category_map.md` — 60+ card category translations (人类, 猎魔人, 吸血鬼, 构造体, etc.)

### Script Enhancements (check_translation.py)
- Auto-detects ambiguous card names (flags "杰洛特" without subtitle)
- Auto-detects abbreviations (BC, OP, CA, etc.) and suggests expansion
- Auto-detects English parentheses and English colons
- Auto-detects Chinese numerals
- Rules loaded dynamically from references/ (no hardcoded duplication)
- Fixed word-boundary regex for CJK+Latin mixed text

## 2026-06-03 — Self-Evolution (Learn Mode)

### New: Learning System
- `scripts/learn.py` — Scans source+translated text to discover unknown terms
  - Detects card names with colons, capitalized phrases, all-caps abbreviations
  - Compares against all reference files to find gaps
  - Outputs preview or auto-writes to pending_terms.md
- `references/pending_terms.md` — Buffer for unverified terms
  - Human-reviewed before moving to confirmed references
  - Prevents pollution of verified data with uncertain translations
- SKILL.md Step 7: Learn — Post-translation self-evolution workflow
  - Scan → Compare → Record → Suggest
  - Never writes directly to confirmed files without human verification

### Self-Evolution Design
```
Translation ──► Detect Unknown Terms ──► pending_terms.md
                                            │
                         Human Review ◄─────┘
                                            │
                         Confirmed ──► terminology_map.md / card_names.md
```

## 2026-06-03 — Advanced Features (6 New Capabilities)

### 1. Version-Aware Translation (版本感知)
- `references/version_map.md` — Expansion timeline with card ID prefixes
- Date-based lookup rules for pre-2020 / 2020-2021 / post-2021 articles
- Resolves ambiguous card names by article date (e.g., Regis base vs. Regis: Rebirth)

### 2. Context Lock (上下文一致性锁)
- `scripts/context_lock.py` — Per-document terminology lock table
- Build lock from source → Lock translations → Enforce consistency across article
- Prevents "蟹蜘蛛" in paragraph 3 and "蛛群" in paragraph 15

### 3. Format Skeleton Preservation (格式骨架保留)
- `scripts/format_skeleton.py` — Extract/restore Markdown structure
- Preserves headings, lists, blockquotes, tables while translating content only
- Separates format from content for clean translation workflow

### 4. Diff Review Mode (审校差异模式)
- `scripts/diff_review.py` — Structured comparison of source vs. user translation
- Detects: terminology errors, numeric mismatches, omissions, additions
- Output grouped by severity (high/medium/low) with specific fix suggestions
- Does NOT retranslate—only analyzes and reports issues

### 5. Back-Translation Validation (回译验证)
- `scripts/backtranslate.py` — Framework for semantic drift detection
- Compares original English with back-translated English from Chinese output
- Flags: missing key information, wrong numbers, reversed causality
- Requires LLM for actual back-translation step

### 6. Style Fingerprint (个性化风格指纹)
- `references/style_fingerprint.md` — User's personal translation preferences
- Records term choice distribution (e.g., nerf → 削弱 80% / 来一刀 20%)
- Tracks preferred oral verbs, sentence split ratio, formatting choices
- Updated after each user correction session

### SKILL.md Workflow Restructure
- Added Step 0: Context Setup (date, type, style fingerprint)
- Added Step 2: Context Lock (for long articles)
- Added Step 3: Format Skeleton (for formatted articles)
- Renumbered subsequent steps
- Added "Special Modes" section for Diff Review and Back-Translation

## 2026-06-03 — Workflow Tools (3 New Scripts)

### 1. lookup.py — Terminology Quick Search
- One-command search across all 13 reference files
- Exact match + fuzzy matching support
- Groups results by source file with formatted output
- Usage: `python scripts/lookup.py "部署"`

### 2. translate.py — Workflow Orchestrator
- Chains all 6 workflow steps into a single command
- Auto-detects article context (date → version range)
- Outputs step-by-step translation guide with next actions
- Supports `--check-only` mode for post-translation verification
- Usage: `python scripts/translate.py article.md --date 2026-05`

### 3. health_check.py — Skill Health Check
- Verifies all 13 reference files and 7 scripts are present
- Checks SKILL.md structure and required sections
- Tests script syntax and basic functionality
- Data integrity checks (card count, pending terms, version history)
- Outputs color-coded PASS/FAIL/WARN/INFO summary
- Usage: `python scripts/health_check.py`

## 2026-06-03 — Bidirectional Translation Support

### CN → EN Translation
- `references/reverse_terminology_map.md` — Reverse term lookup (中文 → 英文)
- Covers: core terms, number formulas, slang reverse mappings, oral verbs
- Style notes for preserving Bilibili tone in natural English

### Updated Components
- SKILL.md: Split workflow into EN→CN and CN→EN variants
- Added direction-specific reference loading instructions
- Added CN→EN self-check checklist
- lookup.py: Searches both terminology_map.md and reverse_terminology_map.md
- health_check.py: Verifies reverse_terminology_map.md exists

## 2026-05-30 — Initial Release

### Based On
- 4 rounds of manual correction by 进
- Triangulation: program translation vs manual correction vs source
- Shinmiri-Lerio three-way comparison

### Key Rules Established
- provision → 人口 (formal), "5P"/"4费" (casual)
- "X for Y" → "Y人口X战力" format
- Active voice mandate
- Community slang standardization (气宗, 孽鬼店店, 互口岛, etc.)
