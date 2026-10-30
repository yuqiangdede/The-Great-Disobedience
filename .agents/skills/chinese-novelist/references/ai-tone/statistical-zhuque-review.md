# 小说正文：统计证据层与朱雀交叉验证 V1

## 适用性和边界

- **只用于已写出的正式正文**。简写、章纲、卷纲及全书梗概沿用 `references/guides/outline-review.md`，仅审故事设计和情节套路化；禁止使用本文的文字统计、朱雀 API 或“AI占比”比较。
- 此检测是“对文本中可能妨碍阅读的程式化现象找线索”，不是鉴别作者是否为AI。腾讯朱雀结果也不能证明作者身份或版权归属。
- 本地特征、朱雀外部分类、G1—G4、独立反方审稿、正文七维得分 **互不冒充**。统计层只产生待核证据，不因阈值或模型结果新增阻断条件、扣分维度或直接改稿。

## 技术实现

- 入口：`scripts/novel_style_statistics.py`，Python标准库，无第三方依赖；`scan_ai_tone.py` 原四关默认附加统计证据层；用 `--no-style-stats` 可关闭。
- 逐章提取正文段落、原始行号；去标题、代码围栏等；统计句长均值与变异系数、段长变异系数、不同字二元组比例、修饰词密度。
- 标记空洞拔高、模板担当台词、罐头反应、公文语以及同段强化词聚集；跨段连续八个汉字一致生成复现候选，同时指向首次出现行。每类最多显示8条，`candidate_counts` 保留原始总数，不把抽样显示当全章频率。
- 已定稿文风基线通过多次 `--baseline` 提供，至少3份、每份100汉字以上才展示数值偏差。**区分旁白/台词、战斗/日常的基线由审稿人选用同类参考篇章实现**；当前不是分类器，也没有语料训练或统计显著性计算。基线只是参照。
- 基于关键词、字符片段的检测有假阳性和漏检；同音词、不同词同义套路、同类场景之间的语义相似性仍依赖审稿模型/人工检查。
- 每个候选须核对前后段、人物声口、战术口令/装备参数/伤病数字、必要复述、有意复沓、新增因果、后果与读者感受。应列举成立和反例；主审判定成立、部分成立、被推翻或待核实。

## 结构模式审查（外部检测只作辅助）

在本地统计与第三方片段信号之外，正式正文按照 [12 项文风与 7 项情节模板风险](ai-writing-signals-12.md) 审查天气与氛围开场、物品清单、密集比喻、人物播报设定、道德情绪齐整化、情节过分顺滑和结尾再次复述主题。必须保留原文、上下文、反证和净收益评估，不能将第三方检测分值认作实际 AI 作者概率或自动改稿阈值。

具体作品的朱雀报告统计及原始案例放在各小说项目的审稿案例库中，不随通用 Skill 强制加载。

## 朱雀官方 API 可选，默认不联网

官方文档：https://edgeone.ai/zh/document/220768452149075968

- **仅**添加 `--zhuque` 时联网，使用环境变量 `MAKERS_MODELS_KEY`。POST 到 `https://ai-gateway.edgeone.link/v1/providers/zhuque-text/classify`，请求体 `{"text":"...","is_merge":false}`；服务可能计费/消耗额度，必须确认上传第三方的风险。不得将 API Key 硬编码、写入 Git、日志或报告。
- 解析官方 `labels_ratio`：0=人工、1=AI、2=疑似AI；`segment_labels` 保留分段标签、位置、置信度，`softmax_confidence`、`ratio_confidence` 独立原样展示，**不得重新命名为原创率/文学质量/AI创作确定概率**。
- 默认不调用、未配置密钥或接口失败时，本地统计和 G1—G4 继续工作，记录 NOT_REQUESTED/SKIPPED/ERROR，不伪称调用成功。官方来源可能改变协议；以使用时官方文档为准。
- API 属于可选第三方校验，ChatGPT 对话插件没有自动取得小说全文或腾讯密钥的权限，不得声称自己运行了脚本、腾讯检测或独立子智能体，除非真实执行并拿到结果。

## 执行（PowerShell/命令行）

```powershell
python .agents/skills/chinese-novelist/scripts/novel_style_statistics.py "06-正文/第一卷/第001章.md" --json
python .agents/skills/chinese-novelist/scripts/scan_ai_tone.py "06-正文/第一卷/第001章.md" --project-dir . --auto-report --json
python .agents/skills/chinese-novelist/scripts/scan_ai_tone.py "06-正文/第一卷/第001章.md" --baseline "06-正文/第一卷/第002章.md" --baseline "06-正文/第一卷/第003章.md" --baseline "06-正文/第一卷/第004章.md" --auto-report
# 手动设置环境变量后方可运行：
$env:MAKERS_MODELS_KEY = "<只保存在当前本机环境的密钥>"
python .agents/skills/chinese-novelist/scripts/novel_style_statistics.py "06-正文/第一卷/第001章.md" --zhuque --report "08-审稿/第001章-文风统计.md"
```

## 审查报告约定

在原正文报告第5节下追加“统计证据层”子表，写明：运行环境/命令及实际结果（不可用时标未执行）、统计范围和行号、局部候选、对照基线、需要保留的反例、反方攻击与主审裁决。朱雀只在真实成功调用后单独展示服务端返回字段；不以其数值直接裁决 AI 味专项或换算七维质量分。不得按“尽可能降低官方AI占比”自动重写小说。

对每个成立缺陷执行 `references/guides/change-benefit-gate.md`：收益明确大于损害才改，改完比较原文与新稿并核对邻章。