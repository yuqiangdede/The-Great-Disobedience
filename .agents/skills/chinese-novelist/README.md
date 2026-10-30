# chinese-novelist

> 个人维护的中文小说创作与质量审查 Skill。用于小说规划、章节写作、审稿、改稿和长篇连续性管理。适用于多个小说工程，作品事实从项目配置和项目文件读取。

## 定位

这是一个**项目内可直接调用的独立 Skill**，不依赖上游项目的宣传站点、截图、赞助配置和发布流程。遵循仓库根目录的 `AGENTS.md` 以及权威小说设定；核心入口为 [`SKILL.md`](SKILL.md)。

主要能力：

1. **规划与写作**：世界观、人物小传、全书／分卷／章节规划；按“概要设定 → 约 500 字简写 → 作者审批 → 详写”逐章推进。
2. **正文生产**：吸收 Webnovel Writer v8 的十段资料包、单章草稿版本、七维审读、候选事实核对；不要求安装其 DSH 原生运行时。
3. **双模式审查**：简写只评价剧情因果、钩子、人物和世界运行；正式正文还要检查语言、叙事、翻译腔、AI 式模式化表达、战术与连续性。
4. **对抗与净收益改稿**：审查意见须有原文证据、反证及保留价值；只有修改收益明确大于损害才动稿；无法调用真实子 Agent 时必须标注降级。
5. **事实与交付**：以项目正文和已确认设定为准，记录人物状态、时间、装备与伏笔；当前项目要求 Markdown 与 TXT 副本时保持一致；无此交付格式的项目不强制生成。
6. **项目工作台**：通过本仓 Python 脚本完成查询、学习候选、体检、只读 HTML 面板和写前备料。

## 目录

```text
.agents/skills/chinese-novelist/
├── SKILL.md                 # 唯一 Skill 入口及强制规则
├── README.md                # 本文件：能力与使用说明
├── LICENSE                  # 必须保留的上游 MIT 许可声明
├── references/
│   ├── ai-tone/             # 正文 AI 式表达及对抗审查规则
│   ├── flows/               # 规划、写作、复核及 v8 流程适配
│   └── guides/              # 人物、卷纲、对白、改稿及审查指南
└── scripts/                 # 初始化、备料、扫描、对账、导出与测试脚本
```

已清除上游的 `.github/`、`assets/`、`docs/superpowers/`、原作者路线图和 Skill 内部 `.gitignore`，业务规则与可执行脚本不因此改变。

## 不同小说的配置与隔离

每个小说项目根目录单独维护 `novel.project.json`，可配置编号章范围、简写目标、插章篇幅、地理审查关键字与装备重复候选；`paths.story_rules` 指向此书专属规则文档。角色/势力/既定章节只在该小说项目保留，不在本 Skill 的通用脚本中写死。

配置字段、默认值、优先级与示例见 [项目配置说明](references/guides/project-config.md)。新增项目由 `scripts/init_novel_workspace.py` 自动生成配置；已有项目可以补建配置，不能覆盖已有事实。全部按标准库 Python 运行，不要求第三方包。

## 与对话小说质量检测插件对齐

历史插件对齐记录见 [对齐快照](references/guides/plugin-review-parity.md)；**当前执行以 [review-core.md](references/guides/review-core.md) 为唯一准则**，正文七维总分、37项 AI 味裁决、正收益改稿及实际交付分开处理。旧 [0—10节报告](references/guides/novel-review-report-0-10.md)、[重复频率](references/guides/repetition-frequency-review.md)、[对白专项](references/guides/slogan-dialogue-review.md) 仅在需要细化证据时按需加载，不叠加必查关卡。没有重新核验插件时不得宣称双方实时一致。

**审稿质量与写作交付独立**：字数只做质量报告的中性提示；项目仍可在实际交付时设置字数硬门禁。对话插件只对质量判定负责，Skill 的自动脚本的旧 overall_status 不等于独立语义审稿通过。

## 使用

在该仓库的 Agent 环境中，读取 `AGENTS.md` 和 `SKILL.md`，根据任务加载 `references/` 的对应规范。可直接提出以下意图：

- “规划下一章”：根据已确认设定编写任务卡、概要和待审核简写。
- “写第 N 章正文”：只有该章简写**明确获批**后才进入详写与质量门禁。
- “审查第二卷简写”：仅检查剧情与结构，不运行词句级 AI 味扫描。
- “审查第二卷正文”：执行正文七维、37项 AI 味复核、连续性与对抗审读。
- “查询人物或修复连续性”：先查正文证据和人物动态账本，再提出净收益为正的最小修改。

示例命令（在小说项目根目录运行，需要 Python 3）：

```powershell
python .agents/skills/chinese-novelist/scripts/novel_workbench.py --project-dir . doctor
python .agents/skills/chinese-novelist/scripts/novel_workbench.py --project-dir . query "人物姓名" --scope 人物 --limit 30
python .agents/skills/chinese-novelist/scripts/novel_workbench.py --project-dir . dashboard --output .novel-work/dashboard/index.html
```

更多工作流与检查器见 [`SKILL.md`](SKILL.md)、[`v8 适配协议`](references/flows/webnovel-writer-v8-adapter.md) 和 [`章节检查清单`](references/flows/chapter-checklist.md)。`webnovel-*` 在本仓是任务意图适配，不代表已经注册了上游斜杠命令；真实工具不可用时不得伪造执行。

## 维护与许可

- **维护归属**：`yuqiangdede/The-Last-Watch` 内的自有定制 Skill，后续业务规则在此目录维护，不需要单独的桥接 Skill。
- **上游许可**：该 Skill 包含基于 [PenglongHuang/chinese-novelist-skill](https://github.com/PenglongHuang/chinese-novelist-skill) 修改的 MIT 授权材料，因此保留原始 [`LICENSE`](LICENSE) 及其版权声明。改成个人维护版本不意味着能够删除原作者许可。
- **v8 工作流参考**：借鉴 [lingfengQAQ/webnovel-writer](https://github.com/lingfengQAQ/webnovel-writer) 的流程理念，不内置其 DSH 运行时或复制 GPL 源码；具体边界以本仓适配协议为准。
