# 共享机制

> **通用使用说明**：本文件提供经验和机制实例，不覆盖 [Skill](../../SKILL.md) 与 [审稿核心协议](../guides/review-core.md)；每章冲突、章末钩子、展示而非讲述都是可选技法，不是独立硬配额。项目专属资料及状态字段只在当前作品真实存在时适用。

本文件定义跨阶段共享的机制和规则。

---

## 三大黄金法则

1. **展示与概述配合** - 关键行动和人物变化适合现场描写，必要的概述与直述也可保留
2. **关注叙事推进** - 依章节功能安排冲突、关系变化、缓冲或过渡，不强制每章都有转折
3. **自然承接读者期待** - 可以用悬念、结果、情绪余波或关系变化收尾，不强制每章悬念钩子

---

## 用户偏好系统

### 存储文件

`user-preferences.json`（项目根目录，首次使用后自动创建）

### 数据结构

```json
{
  "version": 1,
  "updatedAt": "2026-04-12",
  "preferences": {
    "favoriteGenres": [],
    "preferredProtagonist": "",
    "preferredPerspective": "",
    "preferredTone": "",
    "typicalChapterCount": null,
    "styleReferences": [],
    "dislikes": [],
    "creationHistory": []
  }
}
```

### 偏好更新规则

| 时机 | 行为 |
|------|------|
| 每完成一层问答 | 静默将本层回答同步到偏好文件（追加/更新，不删除历史） |
| 用户说"记住我的偏好" | 保存当前所有配置到偏好 |
| 用户说"忘记XX偏好" | 清除指定维度的偏好 |
| 用户说"重置偏好" | 清空所有偏好数据 |
| 一部长篇创作完成 | 将作品信息追加到 `creationHistory` |

### 偏好如何影响交互

1. **启动欢迎语**：有偏好时显示"欢迎回来！" + 个性化提示
2. **选项排序**：Q1中将 `favoriteGenres` 匹配项排前面
3. **常用标记**：基调问（第二层调用一）、章节数问（第二层调用二）中对应用⭐标记"你的常用"/"上次选择"
4. **需求报告**：结合偏好给个性化建议（如"你之前喜欢悬疑+第三人称限制，这次要不要试试多视角？"）
5. **随机生成**：优先从偏好范围内随机选取，保持一致性
6. **风格参考追问**：优先推荐 `styleReferences` 中的作者

### 错误恢复

- **回退修改**：用户随时可说"重新问XX"、"修改XX"，AI 回退到指定问题重新询问
- **中途暂存**：通过 `02-写作计划.json` 实现自动暂存；下次触发SKILL时 Phase 0 自动检测未完成项目，询问"继续上次的《XXX》？"
- **偏好文件损坏**：JSON解析失败时忽略偏好，使用默认值，并在后台修复文件

---

## 标题传递机制

### 传递方式

标题通过**对话上下文**在阶段间传递，不单独持久化到文件。

**传递链路**：
1. Phase 1 Layer 3：用户选择/确认标题 → 标题存入对话上下文
2. Phase 2：从上下文读取标题 → 写入项目目录名、`02-写作计划.json`、`01-大纲.md`

### 中断恢复

若会话在 Layer 3 完成、Phase 2 开始前中断：
- Phase 0 不会找到已创建的项目目录（因为 Phase 2 尚未执行）
- 用户将重新进入 Layer 3 重新选择标题（标题选择耗时很短，重新选择成本可接受）

## 写作计划系统

### 存储文件

`02-写作计划.json`（项目文件夹内，Phase 2 创建）

### 作用

- **进度跟踪**：记录每章创作状态（pending/in_progress/completed/failed）
- **写作模式**：记录用户选择的写作模式（serial/subagent-parallel/agent-teams）
- **中断续写**：Phase 0 读取 JSON 检测未完成项目，支持从断点继续
- **校验依据**：Phase 4 基于 JSON 校验章节完成度和字数
- **并行协调**（可选）：多 Agent 并行写作时通过 JSON 状态避免冲突

### 与大纲的关系

- `01-大纲.md`：章节规划（核心事件、悬念钩子、承接上章、出场人物、场景列表）+ 设定词典（设定名词的首现与揭示跟踪），纯规划文档，不随创作进度膨胀
- `99-章节摘要.md`：逐章追加的 300-500 字摘要（连贯性参考），每章收尾时写入
- `02-写作计划.json`：章节状态、字数、重试次数、写作模式（机器可读的进度跟踪）
- Phase 3 创作每章时必须读取 `01-大纲.md` 中对应章节的规划信息，作为创作依据
- 两者严格对应：JSON 中的 `chapterNumber` 和 `title` 必须与大纲中的章节规划一致

### JSON 损坏处理

- JSON 解析失败时：提示用户，尝试从 `99-章节摘要.md` 推断完成进度
- 章节状态丢失时：通过文件存在性和字数脚本重建状态

---

## 字数检查脚本

使用 `{skillBaseDir}/scripts/check_chapter_wordcount.py` 检查章节字数。`{skillBaseDir}` 指 SKILL.md 所在的 skill 安装根目录（如 `~/.claude/skills/chinese-novelist`）——脚本不在用户项目内，**必须用 skill 安装目录的绝对路径调用**，禁止写相对路径 `scripts/...`（那只存在于 skill 源码目录，用户项目解析不到）。

```bash
# 检查单个章节（--json 输出机读结果，含 word_count 与达标状态）
python {skillBaseDir}/scripts/check_chapter_wordcount.py ./chinese-novelist/项目文件夹/第01章.md --json

# 检查所有章节（按章号数值排序，第10章不会排在第2章前面）
python {skillBaseDir}/scripts/check_chapter_wordcount.py --all ./chinese-novelist/项目文件夹/ --json

# 自定义最小字数
python {skillBaseDir}/scripts/check_chapter_wordcount.py ./chinese-novelist/项目文件夹/第01章.md 3500 --json
```

### 退出码

| 退出码 | 含义 |
|-------|------|
| 0 | 全部达标 |
| 1 | 有章节不达标 |
| 2 | 文件/目录错误 |

Agent 优先用 `--json` + 退出码判断结果：`results[].word_count` 可直接填入 `02-写作计划.json` 的 `wordCount`，无需解析文本报告。

### 使用场景

| 阶段 | 用途 |
|------|------|
| Phase 3（逐章创作） | 撰写后检查单章字数，低于3000字必须扩充 |
| Phase 4（自动校验） | 批量检查所有章节字数，不合格章节自动重写 |

低于3000字的章节必须使用 [content-expansion.md](../guides/content-expansion.md) 的扩充技巧进行扩充。

---

## 深度长篇防跑偏三大工程规则

针对多阵营、多角色、宏大世界观的深度长篇作品，为防止“设定模糊、战力通胀、人设走偏、事实冲突”，严格执行以下三大工程规则：

### 规则一：唯一权威设定源原则（Single Source of Truth, SSOT）
- **世界规则唯一源**：`01-世界观/*.md`（按专题独立建档，严禁混杂）。
- **人物基准唯一源与三级分类小传体系**：
  - `02-人物/` 是人物设定的唯一权威源。
  - **三级分类管理**：
    - `02-人物/主角/[角色名].md`（主角独立主档）
    - `02-人物/配角/[角色名].md`（核心配角、重要反派、深度队友）
    - `02-人物/辅助角色/第{XX}章-[角色名].md`（辅助角色、功能NPC、周期复现角色，以**首次登场章节**命名）
  - **核心铁律**：**理论上只要不是纯一次性出现的角色，都必须生成独立人物小传！**
  - **每章写前拦截**：动笔撰写正文前，必须核查本章出场参与人员，发现非一次性角色缺少小传的，必须先行补齐小传并登记，严禁无档角色裸奔。
- **兼容视图只读编译**：`00-人物档案.md`、`01-大纲.md`、`03-文风基准.md`、`99-章节摘要.md` 仅作为速查与只读编译视图，严禁直接在其中修改人设或设定，防止出现双向版本漂移。

### 规则二：JIT 渐进式按需读取协议（Progressive Context Loading）
- **杜绝全量灌入**：严禁动笔前将全工程数十个设定文档一次性塞入上下文（导致注意力分散与模型幻觉）。
- **精准按需加载与写前核验**：单章写作仅读取 `AGENTS.md` + 动态状态 + 当前任务卡 + **出场角色小传完备性核查与精读** + 1-2个本章直接相关的世界观专题。将写前参考上下文稳定控制在 4000-6000 tokens 以内。

### 规则三：写后验证与事实回写机制（Fact Writeback Protocol）
- **动静彻底解耦**：`02-人物/` 维护静态人格与能力边界；`07-创作记忆/人物实时状态.md` 维护随剧情发展的动态事实（伤病、所在地理位置、装备损耗、已知情报边界）。
- **每章收尾闭环**：单章正文完成后，必须经由审稿核查，及时将正文中发生的不可逆物理改变与情报变动回写到 `07-创作记忆/`，并运行同步工具重新编译索引视图。

---

## 自动化辅助脚本工具箱

深度工程模式配套以下命令行工具（位于 `{skillBaseDir}/scripts/`）：

### 1. 工程脚手架初始化 (`init_novel_workspace.py`)
```bash
# 初始化深度模块化工程（生成标准工程目录、三级人物子目录、多媒体资源库、AGENTS.md 与全套骨架模板）
python {skillBaseDir}/scripts/init_novel_workspace.py ./chinese-novelist/书名 --title 书名 --mode deep --genre 科幻军事

# 初始化标准轻量工程（生成经典 5 大文件，含三级分类人物档案）
python {skillBaseDir}/scripts/init_novel_workspace.py ./chinese-novelist/书名 --title 书名 --mode standard --genre 都市
```

### 2. 记忆同步与只读视图编译 (`sync_novel_memory.py`)
```bash
# 递归扫描 02-人物/ 下的主角、配角、辅助角色，自动编译提取 00-人物档案.md，并同步章节摘要镜像
python {skillBaseDir}/scripts/sync_novel_memory.py ./chinese-novelist/书名 --compile-views

# 校验动态状态与设定冲突（如伤病冲突、已阵亡角色出场、缺少人物主档等）
python {skillBaseDir}/scripts/sync_novel_memory.py ./chinese-novelist/书名 --check-conflicts

# 输出 JSON 机读结果供 Agent 解析
python {skillBaseDir}/scripts/sync_novel_memory.py ./chinese-novelist/书名 --json
```
