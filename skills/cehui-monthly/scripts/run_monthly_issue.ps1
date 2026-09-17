<#
阶段B：月刊排版（校验定稿选目 → 出刊 → 渲染 PDF/预览 → 版式体检）

用法：
  powershell -File run_monthly_issue.ps1 -PeriodDir "<工作根 ToolRoot>\2026年8-9月测绘动态资讯"
  powershell -File run_monthly_issue.ps1 -PeriodDir <期次目录> -RebuildTemplate   # 先用参考件重建三栏目模板
  powershell -File run_monthly_issue.ps1 -PeriodDir <期次目录> -Forward          # 干跑：输出到 _raw\_forward，不覆盖正式刊
#>
param(
    [Parameter(Mandatory = $true)][string]$PeriodDir,
    [string]$ToolRoot = "<工作根 ToolRoot>",
    [string]$Python = "C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe",
    [switch]$RebuildTemplate,
    [switch]$Forward,
    [switch]$NoPng
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $PeriodDir)) { throw "期次目录不存在：$PeriodDir" }
$PeriodDir = (Resolve-Path -LiteralPath $PeriodDir).Path
$ScriptDir = Join-Path $ToolRoot "99_脚本"
$LayoutDir = Join-Path $ToolRoot "编制排版"
# 解析一个装了依赖的 Python：优先 -Python 参数，其次 CEHUI_PYTHON，再依次探测
function Resolve-Python {
    param([string]$Preferred)
    $cands = @()
    foreach ($c in @($Preferred, $env:CEHUI_PYTHON, "python", "python3", "py")) {
        if ($c -and ($cands -notcontains $c)) { $cands += $c }
    }
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

$periodJson = Join-Path $PeriodDir "99_脚本\period.json"
if (-not (Test-Path $periodJson)) { throw "缺少 $periodJson，请先跑阶段A（run_draft_catalog.ps1）完成开期。" }
$period = Get-Content -LiteralPath $periodJson -Raw -Encoding utf8 | ConvertFrom-Json
$stem = "测绘动态工作_" + $period.issue_label

# ---- 前置校验 ----
$sel = Join-Path $PeriodDir "99_脚本\catalog_selection_final.json"
if (-not (Test-Path $sel)) { throw "缺少定稿选目 $sel，请先跑阶段A（至少 25 号脚本）。" }
$md = Join-Path $PeriodDir "00_资讯目录.md"
if (-not (Test-Path $md)) { throw "缺少 $md，请先跑阶段A的 07 号脚本生成目录。" }

$mdText = Get-Content -LiteralPath $md -Raw -Encoding utf8
$mdTotal = [int]([regex]::Match($mdText, "- 条目总数：(\d+)").Groups[1].Value)
$selItems = Get-Content -LiteralPath $sel -Raw -Encoding utf8 | ConvertFrom-Json
if ($selItems.Count -ne $mdTotal) {
    throw "定稿选目 $($selItems.Count) 条与目录 $mdTotal 条不一致，请先重跑阶段A的 07 号脚本。"
}
$pending = @($selItems | Where-Object { $_.'正文来源' -like "待补*" })
if ($pending.Count -gt 0) { Write-Warning "有 $($pending.Count) 条正文待补，成刊将不含其全文。" }
Write-Host ("[校验] 定稿选目 $($selItems.Count) 条；期号 $($period.issue_label)")

# ---- 模板 ----
$tpl = Join-Path $LayoutDir "测绘动态月刊_模板.docx"
if ($RebuildTemplate -or -not (Test-Path $tpl)) {
    Write-Host "[模板] 重建三栏目模板（参考件：政策要情第一百期）"
    & $Python (Join-Path $LayoutDir "_build_monthly_template.py")
    if ($LASTEXITCODE -ne 0) { throw "模板重建失败" }
    Write-Host "[模板] 修正页脚版式（页码居中＋各节页脚高度统一）"
    & $Python (Join-Path $ToolRoot "99_脚本\40_fix_footer_layout.py") $tpl | Out-Null
    & $Python (Join-Path $ToolRoot "99_脚本\40_fix_footer_layout.py") `
        ([System.IO.Path]::ChangeExtension($tpl, ".dotx")) | Out-Null
}

# ---- 出刊 ----
if ($Forward) {
    $fwdDir = Join-Path $PeriodDir "_raw\_forward"
    New-Item -ItemType Directory -Force -Path $fwdDir | Out-Null
    $env:ISSUE_FINAL = Join-Path $fwdDir ($stem + "_干跑.docx")
    Write-Host "[干跑] 正式刊不会被覆盖，输出：$($env:ISSUE_FINAL)"
}
Write-Host "[出刊] $stem"
& $Python (Join-Path $LayoutDir "_make_issue.py")
if ($LASTEXITCODE -ne 0) { throw "出刊失败（检查页码是否收敛）" }

# ---- 文本核校（空格／标点／漏字，2026-09-17 增补）----
$docx0 = if ($env:ISSUE_FINAL) { $env:ISSUE_FINAL } else { Join-Path $LayoutDir ($stem + ".docx") }
$clean = [System.IO.Path]::Combine([System.IO.Path]::GetDirectoryName($docx0),
                                   [System.IO.Path]::GetFileNameWithoutExtension($docx0) + "_核校版.docx")
Write-Host "[核校] 体例体检 27 + 空格标点核校 33"
& $Python (Join-Path $ToolRoot "99_脚本\27_text_qa.py") --doc $docx0 `
    --out (Join-Path $PeriodDir "_备查\文本体例检查.md")
$out33 = & $Python (Join-Path $ToolRoot "99_脚本\33_fix_docx_text.py") $docx0 -o $clean `
    --report (Join-Path $PeriodDir "_备查\成稿空格核校.md") 2>&1
$out33 | ForEach-Object { Write-Host ("    " + $_) }
if ($out33 -match "命中：无") {
    Write-Host "    文本已干净，沿用原成稿文件"
} elseif (Test-Path $clean) {
    $docx0 = $clean
}

# ---- 目录加内部跳转链接（Word 与 PDF 都能点击）----
Write-Host "[跳转] 目录书签与超链接 34"
& $Python (Join-Path $ToolRoot "99_脚本\34_add_toc_links.py") $docx0 -o $docx0 `
    --report (Join-Path $PeriodDir "_备查\目录跳转链接.md") | Out-Null

# ---- 刷新页脚 PAGE 域缓存（WPS 默认按缓存显示页码，缓存过期就会和目录对不上）----
Write-Host "[页码] 刷新页脚域缓存 39"
& $Python (Join-Path $ToolRoot "99_脚本\39_fix_footer_page_cache.py") $docx0 -o $docx0 `
    --report (Join-Path $PeriodDir "_备查\页脚页码缓存刷新.md") | Out-Null

# ---- 页脚版式：页码居中 + 各节页脚高度统一 ----
Write-Host "[页脚] 版式修正 40"
& $Python (Join-Path $ToolRoot "99_脚本\40_fix_footer_layout.py") $docx0 `
    --report (Join-Path $PeriodDir "_备查\页脚版式修正.md") | Out-Null

# ---- 渲染与体检 ----
$docx = $docx0
$outdir = if ($Forward) { Join-Path $PeriodDir "_raw\_forward\预览" } else { Join-Path $LayoutDir "月刊预览" }
$checkArgs = @((Join-Path $PSScriptRoot "render_and_check.py"), $PeriodDir, "--docx", $docx, "--outdir", $outdir,
               "--expect-items", "$($selItems.Count)")
if ($NoPng) { $checkArgs += "--no-png" }
& $Python @checkArgs
$code = $LASTEXITCODE
# 把渲染出的 PDF 复制到成刊同目录（文件名与成刊一致），随刊交付可点击的 PDF
if ($code -eq 0) {
    $pdf = Get-ChildItem -LiteralPath $outdir -Filter *.pdf -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime | Select-Object -Last 1
    if ($pdf) {
        $target = Join-Path ([System.IO.Path]::GetDirectoryName($docx)) ([System.IO.Path]::GetFileNameWithoutExtension($docx) + ".pdf")
        Copy-Item -LiteralPath $pdf.FullName -Destination $target -Force
        Write-Host "[交付] PDF：$target"
    }
}
if ($code -eq 0) { Write-Host "[完成] 阶段B 结束：$docx" } else { Write-Warning "版式体检未全部通过，请逐项核对。" }
exit $code
