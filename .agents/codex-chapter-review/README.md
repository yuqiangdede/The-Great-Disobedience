# Codex 逐章独立会话审稿（Windows）

三份文件放在同一目录（**建议放在小说 Git 仓库之外**）：

- `run-chapter-review.ps1` — 串行调度、状态检查与断点续跑
- `chapter-review-prompt.md` — 各章独立会话的完整审稿提示词
- `chapter-review-result.schema.json` — 供脚本验收的最终结果结构

需先安装 Git for Windows、Codex CLI，并运行 `codex login`。具体安装方式请参考 Codex 官方文档。

```powershell
# 从这三个文件所在目录打开 PowerShell
# 替换成真实小说本地仓库根路径
$repo = 'D:\novels\The-Great-Disobedience'

# 预览
.\run-chapter-review.ps1 -RepoRoot $repo -Start 1 -End 3 -DryRun

# 小规模测试：第1章
.\run-chapter-review.ps1 -RepoRoot $repo -Start 1 -End 1

# 第一卷第1—18章
.\run-chapter-review.ps1 -RepoRoot $repo -Start 1 -End 18 -Volume '第一卷-沉默之城'

# 全部已有正式正文章节，按编号串行，跳过已验收且正文未变的章节
.\run-chapter-review.ps1 -RepoRoot $repo

# 从第10章起继续
.\run-chapter-review.ps1 -RepoRoot $repo -Start 10

# 强制重新审查第5章
.\run-chapter-review.ps1 -RepoRoot $repo -Start 5 -End 5 -Force

# 当工作区已有其他修改，而你确认相关修改不会被覆写时（需格外谨慎）
.\run-chapter-review.ps1 -RepoRoot $repo -Start 10 -AllowDirty
```

**注意**：

1. 默认拒绝在启动前存在未提交改动的仓库中工作；但完成一章后产生的修改不会阻止本脚本继续下一章。中断后如果工作区带有上次运行的未提交改动，需核实后使用 `-AllowDirty`。这不是强制保护，无法保证模型完全不触碰其他文件，建议先备份或在专门工作副本执行。
2. Codex CLI 每次 `exec` 都是新会话：脚本不使用 `resume`/`fork`；章节之间仍共享同一 Git 工作树上的**文件状态**。请勿并发启动多个此脚本实例。
3. 完整的 Codex 原始日志、最终 JSON 和通过标记保存在 `%LOCALAPPDATA%\CodexChapterReviews\<仓库标识>\<分支>`，不会自动加入仓库。单章审稿报告按提示词保存在仓库 `审查记录/` 下。
4. 如果 Codex 进程退出码非零、无 JSON、报告不存在或最终状态不为 PASS，立即停止。`PASS` 是 Codex 的申报结果再经有限文件校验，不是独立人工验收；重要修改仍应抽查。
5. `--sandbox workspace-write` 不等于 Codex 可以执行所有需要联网、管理员权限或沙箱外写入的命令；被阻断时应据实返回 `FAILED` / `NEEDS_AUTHOR`，不要虚报已完成。
6. 本脚本既不提交也不推送 Git，日志成功标记并不代表已经备份或发布结果。建议每卷结束后人工检查 `git diff` 并提交。
7. 本脚本默认以本仓库 `06-正文` 内的 `第NNN章*.md` 为正式正文，不会对 `05-章节简写` 等文件执行正文审稿。
