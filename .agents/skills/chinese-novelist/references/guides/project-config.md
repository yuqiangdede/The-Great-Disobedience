# 小说项目配置说明

本 Skill 可用于不同的小说工程，且不在自身文件中固化任何小说的人物、势力、章节剧情或固有字数。小说根目录的 `novel.project.json` 负责数值配置；`paths.story_rules` 指向当前小说自己的规则和事实索引。

## JSON 示例（在小说项目根目录）

```json
{
  "schema_version": 1,
  "title": "我的小说",
  "writing": {
    "brief_target_han": 500,
    "chapter_min_han": 3000,
    "chapter_max_han": 5000,
    "interlude_unbounded": false,
    "author_approval_required": true
  },
  "review": {
    "travel_location_terms": ["千里", "数百里", "小说特定地名"],
    "instant_travel_terms": ["顷刻间", "瞬息"],
    "repeated_equipment_terms": ["需要关注重复描述的装备名"]
  },
  "paths": {
    "story_rules": "04-文风/项目专属写作规则.md"
  }
}
```

## 字段与行为

- `writing.brief_target_han`：概要审批前的简写目标（流程与模型读取；非语言 AIGC 审查阈值）。
- `writing.chapter_min_han` / `chapter_max_han`：编号章正文汉字数下限/建议上限，由 `scan_chapter.py`、`scan_ai_tone.py`、`verify_chapter_consistency.py`、`check_chapter_wordcount.py` 调用统一模块读取。
- `writing.interlude_unbounded`：为 true 时，名字包含“插章”的独立插章默认不受字数上下限约束；命令行显式指定仍覆盖自动豁免。
- `writing.author_approval_required`：明确作者审批政策，不能仅凭打包工具检测到“已通过”字样就假称作者已批准。本 Skill 当前正文详写流程默认要求逐章明确批准。
- `review.travel_location_terms` / `instant_travel_terms`：位移合理性扫描只对同章同时出现的地名/路程词、瞬时位移词给出**人工复核候选**；不基于关键词自动断言物理错误。地名应存当前项目，不写在通用脚本。
- `review.repeated_equipment_terms`：在 `scan_chapter.py` 中检测重复提及，输出候选行号，不自动扣分或修改；其他扫描维度仍保持原有语义审查。
- `paths.story_rules`：相对小说项目根目录的 Markdown 路径，写前备料将纳入材料包，并附 SHA256；路径不得越过项目目录。

## 查找与优先级

脚本从显式 `--project-dir`（支持该参数时）或章节路径向父目录查找 `novel.project.json`，找不到时按 `AGENTS.md` 确定工程根。若无配置使用兼容默认：简写 500、编号章 3000—5000、插章无自动豁免；**不会把另一部小说的设定当作默认值**。若 JSON 损坏或字段类型非法，报错而非静默沿用错误数据。

显式 CLI `--min-words` / `--max-words` 优先于配置；项目本身的 `AGENTS.md` 及人物／剧情权威记录优先于 Skill 泛用示例。已有作品修改前应核对原合同。

## 快速验证

```powershell
python .agents/skills/chinese-novelist/scripts/test_project_config.py
python .agents/skills/chinese-novelist/scripts/novel_workbench.py --project-dir . doctor
python .agents/skills/chinese-novelist/scripts/scan_chapter.py 06-正文/第一卷/第001章.md --json
```

此处的测试脚本只做配置和机械接口回归，不能代替人工的剧情、人物、叙事和 AI 味审核。
