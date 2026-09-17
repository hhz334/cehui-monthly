# 用 WPS(COM) 打开 docx 重新分页，输出总页数与每篇文章所在页码。
#
# 用途：核对 Word/WPS 里的分页与页码是否与导出的 PDF 一致（两边分页不同，目录页码必然对不上）。
# 用法：powershell -NoProfile -File 44_check_wps_pagination.ps1 -Docx "<成刊.docx>"
# 注意：本脚本必须以 UTF-8 带 BOM 保存，否则 Windows PowerShell 5.1 会按 ANSI 读、报语法错误。
param(
    [Parameter(Mandatory = $true)][string]$Docx
)
$ErrorActionPreference = "Stop"
$tmp = Join-Path $env:TEMP ("wps_pagecheck_" + [System.IO.Path]::GetFileName($Docx))
Copy-Item -LiteralPath $Docx -Destination $tmp -Force

$w = New-Object -ComObject KWPS.Application
$w.Visible = $false
try { $w.DisplayAlerts = 0 } catch {}
$doc = $w.Documents.Open($tmp, $false, $true)   # ConfirmConversions=false, ReadOnly=true
$doc.Repaginate()
Write-Output ("WPS 页数：" + $doc.ComputeStatistics(2))

$i = 0
$rows = @()
foreach ($p in $doc.Paragraphs) {
    $t = $p.Range.Text
    if ($t -and $t.StartsWith([char]0x3010)) {          # 【 开头的文章标题
        $pn = $p.Range.Information(3)                   # wdActiveEndPageNumber
        $title = ($t -replace "[\r\n\a]", "")
        if ($title.Length -gt 30) { $title = $title.Substring(0, 30) }
        $rows += [pscustomobject]@{ No = $i; WpsPage = $pn; Title = $title }
        $i++
    }
}
$rows | Format-Table -AutoSize | Out-String | Write-Output
$doc.Close(0)
$w.Quit()
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc) | Out-Null
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($w) | Out-Null
