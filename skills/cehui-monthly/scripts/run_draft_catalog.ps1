<#
阶段A：初稿资讯目录生成（采集 → 初筛 → 批注回灌 → 核验 → 目录与原文归档 → Word 交付件 → 自检）

用法：
  powershell -File run_draft_catalog.ps1 -PeriodDir "<工作根 ToolRoot>\2026年8-9月测绘动态资讯"
  powershell -File run_draft_catalog.ps1 -PeriodDir <期次目录> -From 25            # 从第 25 步续跑
  powershell -File run_draft_catalog.ps1 -PeriodDir <期次目录> -Only 07,14,32,17  # 只跑指定步骤
  powershell -File run_draft_catalog.ps1 -PeriodDir <期次目录> -SkipWeekly        # 跳过周讯线索

说明：脚本本身是唯一代码副本（<ToolRoot>\99_脚本），期次数据与选目 JSON 都在期次目录里；
运行前会设置 CEHUI_PERIOD_DIR，所有脚本据此定位期次目录与 period.json。
#>
param(
    [Parameter(Mandatory = $true)][string]$PeriodDir,
    [string]$ToolRoot = $env:CEHUI_TOOL_ROOT,          # 工作根目录：内含 99_脚本 与 编制排版
    [string]$Python = "python",                      # 或 -Python <解释器路径>
    [string[]]$Only = @(),
    [string]$From = "",
    [switch]$SkipWeekly,
    [string]$LeaderDoc = "",
    [string]$LeaderLabel = "",
    [switch]$NoLog
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $PeriodDir)) {
    New-Item -ItemType Directory -Force -Path $PeriodDir | Out-Null     # 开期：新建期次目录
    Write-Host "[开期] 已新建期次目录：$PeriodDir"
}
$PeriodDir = (Resolve-Path -LiteralPath $PeriodDir).Path
if (-not $ToolRoot) {
    throw "请用 -ToolRoot 或设置环境变量 CEHUI_TOOL_ROOT 指向工作根目录（内含 99_脚本 与 编制排版）"
}
$ScriptDir = Join-Path $ToolRoot "99_脚本"
if (-not (Test-Path (Join-Path $ScriptDir "period_config.py"))) {
    throw "找不到脚本目录：$ScriptDir（请用 -ToolRoot 指定工作根目录）"
}
# 解析一个装了依赖的 Python：优先 -Python 参数，其次 CEHUI_PYTHON，再依次探测
function Resolve-Python {
    param([string]$Preferred)
    $cands = @()
    foreach ($c in @($Preferred, $env:CEHUI_PYTHON, "python", "python3", "py")) {
        if ($c -and ($cands -notcontains $c)) { $cands += $c }
    }
    # Codex 桌面版自带的 Python 运行时（若存在，通常已装好依赖）
    $codexPy = Get-ChildItem "$env:USERPROFILE\.cache\codex-runtimes\*\dependencies\python\python.exe" -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
    if ($codexPy -and ($cands -notcontains $codexPy)) { $cands += $codexPy }
    foreach ($c in $cands) {
        try {
            & $c -c "import pdfplumber, docx, openpyxl, lxml" 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) { return $c }
        } catch { }
    }
    Write-Warning "未找到同时具备 pdfplumber / python-docx / openpyxl / lxml 的 Python，改用 $($cands[0])"
    return $cands[0]
}

$Python = Resolve-Python $Python

$env:CEHUI_PERIOD_DIR = $PeriodDir
$env:CEHUI_TOOL_ROOT = $ToolRoot
$env:PYTHONIOENCODING = "utf-8"

# ---- 开期校验：目录结构与 period.json ----
foreach ($sub in @("_raw", "02_原文", "Word版", "_备查", "03_参考_山东周讯", "99_脚本")) {
    $p = Join-Path $PeriodDir $sub
    if (-not (Test-Path $p)) { New-Item -ItemType Directory -Force -Path $p | Out-Null }
}
$periodJson = Join-Path $PeriodDir "99_脚本\period.json"
if (-not (Test-Path $periodJson)) {
    $tpl = Join-Path $PSScriptRoot "..\assets\period.template.json"
    Copy-Item -LiteralPath $tpl -Destination $periodJson
    Write-Warning "已按模板生成 $periodJson，请补齐窗口/期号后重跑。"
    exit 2
}
$period = Get-Content -LiteralPath $periodJson -Raw -Encoding utf8 | ConvertFrom-Json
foreach ($k in @("window_from", "window_to", "collect_date", "title_range", "issue_label")) {
    if (-not $period.$k -or $period.$k -match "X|N") {
        Write-Warning "period.json 字段 $k 未填写：$($period.$k)"
    }
}

# ---- 步骤表 ----
$steps = @(
    @{ id = "03"; file = "03_harvest_sources.py"; args = @() },
    @{ id = "04"; file = "04_fetch_details.py"; args = @() },
    @{ id = "20"; file = "20_zrzyb.py"; args = @("a-list", "--cid", "测绘", "--pages", "2") },
    @{ id = "21"; file = "21_taibo.py"; args = @("a-list", "--page", "1") },
    @{ id = "22"; file = "22_zhejiang.py"; args = @("a-search", "--q", "测绘", "--cate", "动态信息") },
    @{ id = "26"; file = "26_add_manual_source.py"; args = @(); weekly = $false },
    @{ id = "01"; file = "01_shandong_weekly.py"; weekly = $true },
    @{ id = "10"; file = "10_weekly_qr.py"; weekly = $true },
    @{ id = "11"; file = "11_weekly_pdf.py"; weekly = $true },
    @{ id = "12"; file = "12_extract_weekly_pdf.py"; weekly = $true },
    @{ id = "24"; file = "24_auto_shortlist.py" },
    @{ id = "23"; file = "23_rebuild_boards.py" },
    @{ id = "29"; file = "29_apply_leader_edits.py"; needsLeader = $true },
    @{ id = "31"; file = "31_build_draft_selection.py" },
    @{ id = "25"; file = "25_verify_source_entity.py" },
    @{ id = "08"; file = "08_verify.py" },
    @{ id = "09"; file = "09_make_verify_doc.py" },
    @{ id = "07"; file = "07_build_catalog.py" },
    @{ id = "14"; file = "14_weekly_pool.py" },
    @{ id = "32"; file = "32_export_backups.py" },
    @{ id = "17"; file = "17_make_docx.py" },
    @{ id = "28"; file = "28_check_standard_consistency.py"; check = $true },
    @{ id = "30"; file = "30_regression_leader.py"; check = $true }
)

$logDir = Join-Path $PeriodDir "_raw\_run_logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir ("{0}_draft.log" -f (Get-Date).ToString("yyyyMMdd_HHmmss"))
function Write-Log([string]$text) {
    Write-Host $text
    if (-not $NoLog) { Add-Content -LiteralPath $logPath -Value $text -Encoding utf8 }
}

Write-Log ("[期次] " + $period.issue_name + "｜窗口 " + $period.window_from + " ~ " + $period.window_to +
           "｜期号 " + $period.issue_label)
Write-Log ("[目录] " + $PeriodDir)
Write-Log ("[日志] " + $logPath)

$started = ($From -eq "")
foreach ($s in $steps) {
    if ($Only.Count -gt 0 -and ($Only -notcontains $s.id)) { continue }
    if (-not $started) { $started = ($s.id -eq $From); if (-not $started) { continue } }
    if ($SkipWeekly -and $s.weekly) { continue }
    if ($s.needsLeader) {
        if (-not $LeaderDoc) { Write-Log "[跳过] 29 领导批注解析（未提供 -LeaderDoc）"; continue }
        $label = "leader"
        if ($LeaderLabel) { $label = $LeaderLabel }
        $s.args = @("--doc", $LeaderDoc, "--label", $label)
    }
    $args = @((Join-Path $ScriptDir $s.file)) + ($s.args | Where-Object { $_ })
    $sw = [Diagnostics.Stopwatch]::StartNew()
    Write-Log ("=== [" + $s.id + "] " + $s.file)
    Push-Location $PeriodDir
    try {
        & $Python @args 2>&1 | ForEach-Object { Write-Log ("    " + $_) }
        $code = $LASTEXITCODE
    } finally { Pop-Location }
    $sw.Stop()
    Write-Log ("--- [" + $s.id + "] 退出码 " + $code + "｜耗时 " + [int]$sw.Elapsed.TotalSeconds + "s")
    if ($code -ne 0) {
        Write-Log ("[中止] 步骤 " + $s.id + " 失败，日志：" + $logPath)
        exit 1
    }
}

# ---- 收尾清单 ----
$md = Join-Path $PeriodDir "00_资讯目录.md"
if (Test-Path $md) {
    $text = Get-Content -LiteralPath $md -Raw -Encoding utf8
    $total = ([regex]::Match($text, "- 条目总数：(\d+)")).Groups[1].Value
    Write-Log ("[汇总] 目录条数 " + $total)
}
foreach ($b in @("政策类", "技术应用类", "科技前沿类")) {
    $dir = Join-Path $PeriodDir ("02_原文\" + $b)
    if (Test-Path $dir) { Write-Log ("[汇总] " + $b + " 原文归档 " + (Get-ChildItem $dir -File).Count + " 份") }
}
Write-Log "[完成] 阶段A 结束；若 28/30 未出现在本次步骤中，请单独跑一次收尾自检。"
