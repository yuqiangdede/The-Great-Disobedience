# 文件名：run-chapter-review.ps1
# Windows PowerShell 5.1 / PowerShell 7：每章启动独立的 codex exec 会话。
# 用法：.\run-chapter-review.ps1 -RepoRoot 'D:\novels\The-Great-Disobedience' -Start 1 -End 3
[CmdletBinding()]
param(
    [string]$RepoRoot = '.',
    [ValidateRange(1, 99999)][int]$Start = 1,
    [ValidateRange(0, 99999)][int]$End = 0,
    [string]$Volume = '',
    [ValidateSet('read-only', 'workspace-write', 'danger-full-access')]
    [string]$Sandbox = 'workspace-write',
    [switch]$Force,
    [switch]$AllowDirty,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$utf8 = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = $utf8
[Console]::OutputEncoding = $utf8

function Fail([string]$message) { throw $message }
function CanonicalPath([string]$path) {
    return [System.IO.Path]::GetFullPath($path).TrimEnd([char[]]@('\', '/'))
}

$RepoRoot = CanonicalPath (Resolve-Path -LiteralPath $RepoRoot).Path
$bodyDir = Join-Path $RepoRoot '06-正文'
$promptFile = Join-Path $PSScriptRoot 'chapter-review-prompt.md'
$schemaFile = Join-Path $PSScriptRoot 'chapter-review-result.schema.json'

if (-not (Test-Path -LiteralPath $bodyDir -PathType Container)) { Fail "未找到正式正文目录：$bodyDir" }
if (-not (Test-Path -LiteralPath $promptFile -PathType Leaf)) { Fail "未找到提示词文件：$promptFile" }
if (-not (Test-Path -LiteralPath $schemaFile -PathType Leaf)) { Fail "未找到 JSON Schema 文件：$schemaFile" }

$git = Get-Command git -ErrorAction SilentlyContinue
if (-not $git) { Fail '未找到 git。请安装 Git for Windows。' }
$gitTop = (& git -C $RepoRoot rev-parse --show-toplevel 2>$null)
$gitExitCode = $LASTEXITCODE
if ($gitExitCode -ne 0 -or -not $gitTop) { Fail '指定目录不是可用的 Git 仓库。' }
if (-not [string]::Equals((CanonicalPath $gitTop), $RepoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    Fail "RepoRoot 必须是仓库根目录，当前 Git 根目录：$gitTop"
}
$branch = (& git -C $RepoRoot branch --show-current)
$gitExitCode = $LASTEXITCODE
if ($gitExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($branch)) { Fail '当前为 detached HEAD 或无法读取分支，停止。' }
$dirtyFiles = @(& git -C $RepoRoot status --porcelain --untracked-files=all)
$gitExitCode = $LASTEXITCODE
if ($gitExitCode -ne 0) { Fail '无法读取 Git 工作区状态。' }
if ($dirtyFiles.Count -gt 0 -and -not $AllowDirty -and -not $DryRun) {
    Fail "运行前工作区存在 $($dirtyFiles.Count) 项已有修改，已停止。请先保存/隔离这些修改；确认可保留原样续跑时才传 -AllowDirty。"
}

$codexCommand = Get-Command codex.cmd -ErrorAction SilentlyContinue
if (-not $codexCommand) { $codexCommand = Get-Command codex -ErrorAction SilentlyContinue }
if (-not $codexCommand -and -not $DryRun) { Fail '未找到 Codex CLI，请先安装并完成 codex login。' }

# 执行记录放在仓库外，避免工作区产生无关未跟踪文件。
$hashAlgorithm = [System.Security.Cryptography.SHA256]::Create()
try {
    $hashBytes = $hashAlgorithm.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($RepoRoot.ToLowerInvariant()))
    $repoHash = ([System.BitConverter]::ToString($hashBytes) -replace '-', '').Substring(0, 12)
} finally { $hashAlgorithm.Dispose() }
$stateBase = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { $HOME }
$safeBranch = $branch -replace '[^a-zA-Z0-9._-]', '_'
$stateDir = Join-Path $stateBase ("CodexChapterReviews\$repoHash\$safeBranch")
if (-not $DryRun) { New-Item -ItemType Directory -Force -Path $stateDir | Out-Null }

$chapters = @(
    Get-ChildItem -LiteralPath $bodyDir -Recurse -File -Filter '*.md' |
        ForEach-Object {
            $basename = [System.IO.Path]::GetFileNameWithoutExtension($_.Name)
            if ($basename -match '^第(?<Number>\d+)章(?:[-－].+)?$') {
                $chapterNum = [int]$Matches['Number']
                $vol = $_.Directory.Name
                $relative = $_.FullName.Substring($RepoRoot.Length).TrimStart([char[]]@('\', '/')).Replace('\', '/')
                [pscustomobject]@{
                    Number = $chapterNum
                    Volume = $vol
                    Path = $_.FullName
                    RelativePath = $relative
                    BaseName = $basename
                }
            }
        } |
        Sort-Object Number, RelativePath |
        Where-Object {
            $_.Number -ge $Start -and ($End -eq 0 -or $_.Number -le $End) -and
            ([string]::IsNullOrWhiteSpace($Volume) -or $_.Volume -eq $Volume)
        }
)
if ($chapters.Count -eq 0) { Fail '未找到符合条件的正式正文章节。' }
$duplicate = @($chapters | Group-Object Number | Where-Object { $_.Count -gt 1 })
if ($duplicate.Count -gt 0) { Fail '发现重复章节编号，无法保证唯一选择。请限制 -Volume 或调整文件命名。' }

Write-Host "Git 分支：$branch；符合条件章节：$($chapters.Count)；日志目录：$stateDir"
if ($dirtyFiles.Count -gt 0) { Write-Warning "工作区预先已有 $($dirtyFiles.Count) 项修改。脚本不会自动清理；Codex 已被明确禁止覆盖无关文件。" }
if ($DryRun) {
    $chapters | ForEach-Object { Write-Host ("[预览] {0:D3}  {1}" -f $_.Number, $_.RelativePath) }
    return
}

$promptTemplate = Get-Content -LiteralPath $promptFile -Raw -Encoding UTF8

# 让审稿协议或批处理提示词变更后，旧的“已通过”记录自动失效。
$protocolFiles = @(
    $promptFile,
    $schemaFile,
    (Join-Path $RepoRoot '.agents/skills/chinese-novelist/SKILL.md'),
    (Join-Path $RepoRoot '.agents/skills/chinese-novelist/references/guides/review-core.md'),
    (Join-Path $RepoRoot '.agents/skills/chinese-novelist/references/guides/chapter-review-default.md'),
    (Join-Path $RepoRoot '.agents/skills/chinese-novelist/references/guides/ai-style-37-checks.md'),
    (Join-Path $RepoRoot 'novel.project.json'),
    (Join-Path $RepoRoot 'AGENTS.md')
)
$projectConfigPath = Join-Path $RepoRoot 'novel.project.json'
if (Test-Path -LiteralPath $projectConfigPath -PathType Leaf) {
    try {
        $projectConfig = Get-Content -LiteralPath $projectConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($projectConfig.paths.story_rules) {
            $protocolFiles += (Join-Path $RepoRoot ([string]$projectConfig.paths.story_rules))
        }
    } catch { Fail "novel.project.json 无法解析：$_" }
}
$protocolMaterial = @($protocolFiles | Select-Object -Unique | ForEach-Object {
    if (Test-Path -LiteralPath $_ -PathType Leaf) {
        $_ + ':' + (Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash
    } else { $_ + ':MISSING' }
}) -join "`n"
$protocolHasher = [System.Security.Cryptography.SHA256]::Create()
try {
    $protocolHashBytes = $protocolHasher.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($protocolMaterial))
    $protocolHash = ([System.BitConverter]::ToString($protocolHashBytes) -replace '-', '')
} finally { $protocolHasher.Dispose() }

$doneCount = 0
$skipCount = 0
foreach ($ch in $chapters) {
    $prefix = ('chapter-{0:D4}' -f $ch.Number)
    $donePath = Join-Path $stateDir "$prefix.done.json"
    $finalPath = Join-Path $stateDir "$prefix.final.json"
    $logPath = Join-Path $stateDir "$prefix.codex.log"
    $reportRelative = "审查记录/$($ch.Volume)-$($ch.BaseName)-审查记录.md"
    $reportFull = Join-Path $RepoRoot ($reportRelative.Replace('/', [System.IO.Path]::DirectorySeparatorChar))

    # 断点续跑：只有成功验收且正文、协议与提示词均未改变，才跳过。
    if ((Test-Path -LiteralPath $donePath -PathType Leaf) -and -not $Force) {
        try {
            $previous = Get-Content -LiteralPath $donePath -Raw -Encoding UTF8 | ConvertFrom-Json
            $currentHash = (Get-FileHash -LiteralPath $ch.Path -Algorithm SHA256).Hash
            if ($previous.status -eq 'PASS' -and
                $previous.chapter_path -eq $ch.RelativePath -and
                $previous.source_hash_after -eq $currentHash -and
                $previous.protocol_hash -eq $protocolHash -and
                (Test-Path -LiteralPath $reportFull -PathType Leaf)) {
                Write-Host "[跳过] $($ch.RelativePath)（已验收且正文未变）"
                $skipCount++
                continue
            }
        } catch {
            Write-Warning "旧断点记录无法使用，重新检查 $($ch.RelativePath)：$_"
        }
    }

    $prompt = $promptTemplate
    $prompt = $prompt.Replace('{{CHAPTER_NUMBER}}', ('{0:D3}' -f $ch.Number))
    $prompt = $prompt.Replace('{{CHAPTER_PATH}}', $ch.RelativePath)
    $prompt = $prompt.Replace('{{VOLUME_NAME}}', $ch.Volume)
    $prompt = $prompt.Replace('{{REPORT_PATH}}', $reportRelative)

    $oldReportWriteTime = if (Test-Path -LiteralPath $reportFull -PathType Leaf) {
        (Get-Item -LiteralPath $reportFull).LastWriteTimeUtc
    } else { [DateTime]::MinValue }
    Write-Host "`n[开始] 第$('{0:D3}' -f $ch.Number)章 — $($ch.RelativePath)"
    Remove-Item -LiteralPath $finalPath -Force -ErrorAction SilentlyContinue
    $exitCode = 1
    $savedAction = $ErrorActionPreference
    try {
        # 每次 exec 都创建新会话。不使用 resume、fork 或 --worktree。
        # 使用 stdin 传输中文长提示词，并保存结构化最终回答。
        $ErrorActionPreference = 'Continue'
        $prompt | & $codexCommand.Source exec --cd $RepoRoot --sandbox $Sandbox `
            --json --output-schema $schemaFile --output-last-message $finalPath - 2>&1 |
            Out-File -LiteralPath $logPath -Encoding utf8
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $savedAction
    }

    if ($exitCode -ne 0) { Fail "Codex 执行失败（退出码 $exitCode），停止在 $($ch.RelativePath)。日志：$logPath" }
    if (-not (Test-Path -LiteralPath $finalPath -PathType Leaf)) { Fail "Codex 没有生成结构化最终结果，停止。日志：$logPath" }
    try {
        $result = Get-Content -LiteralPath $finalPath -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch { Fail "最终结果不是有效 JSON，停止。文件：$finalPath；错误：$_" }
    if ($result.chapter_path -ne $ch.RelativePath) { Fail "最终结果章节路径不匹配，停止。结果：$finalPath" }
    if ($result.review_report_path -ne $reportRelative) { Fail "报告路径不匹配，停止。预期：$reportRelative；实际：$($result.review_report_path)" }
    if (-not (Test-Path -LiteralPath $reportFull -PathType Leaf)) { Fail "章节报告未落盘，停止。预期：$reportFull" }
    if ((Get-Item -LiteralPath $reportFull).LastWriteTimeUtc -le $oldReportWriteTime) {
        Fail "本次运行没有更新章节审查报告，停止。报告：$reportFull"
    }
    $branchAfter = (& git -C $RepoRoot branch --show-current)
    $gitExitCode = $LASTEXITCODE
    if ($gitExitCode -ne 0 -or $branchAfter -ne $branch) { Fail "Codex 执行后 Git 分支发生变化，停止。原分支：$branch；现分支：$branchAfter" }
    if ($result.optimization_rounds -lt 0 -or $result.optimization_rounds -gt 5 -or
        $null -eq $result.initial_score -or $null -eq $result.final_score -or
        $result.initial_score -lt 0 -or $result.initial_score -gt 100 -or
        $result.final_score -lt 0 -or $result.final_score -gt 100) {
        Fail "评分或轮次缺失/越界，停止。结果：$finalPath"
    }
    if ($result.status -ne 'PASS' -or $result.workflow_complete -ne $true -or $result.ai_review_status -ne '通过') {
        Fail "章节未通过全部验收（$($result.status) / $($result.ai_review_status)），停止，不进入下一章。结果：$finalPath；报告：$reportFull"
    }

    $afterHash = (Get-FileHash -LiteralPath $ch.Path -Algorithm SHA256).Hash
    $marker = [ordered]@{
        status = 'PASS'
        chapter_path = $ch.RelativePath
        source_hash_after = $afterHash
        protocol_hash = $protocolHash
        branch = $branch
        reviewed_at = [DateTime]::Now.ToString('s')
        report_path = $reportRelative
        codex_result = $finalPath
        codex_log = $logPath
    }
    $marker | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $donePath -Encoding UTF8
    Write-Host "[通过] 第$('{0:D3}' -f $ch.Number)章；$($result.initial_score) → $($result.final_score)；优化 $($result.optimization_rounds) 轮"
    Write-Host "       报告：$reportFull"
    $doneCount++
}
Write-Host "`n全部结束：本次通过 $doneCount 章，跳过 $skipCount 章；日志：$stateDir"
