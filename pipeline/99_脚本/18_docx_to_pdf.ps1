# 用本机 WPS（KWPS.Application）把 Word 版交付件导出为 PDF，供版式体检使用。
param(
    [string]$Dir = "<工作根 ToolRoot>\2026年8-9月测绘动态资讯\Word版",
    [string]$OutDir = ""
)
$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($OutDir)) { $OutDir = Join-Path $Dir "_pdf" }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$app = New-Object -ComObject KWPS.Application
$app.Visible = $false
try {
    foreach ($f in Get-ChildItem -LiteralPath $Dir -Filter *.docx | Sort-Object Name) {
        $pdf = Join-Path $OutDir ($f.BaseName + ".pdf")
        $doc = $app.Documents.Open($f.FullName, $false, $true)
        try {
            $doc.ExportAsFixedFormat($pdf, 17)
        } catch {
            $doc.SaveAs2($pdf, 17)
        }
        $doc.Close(0)
        "$($f.Name) -> $(Test-Path $pdf) ($((Get-Item $pdf -ErrorAction SilentlyContinue).Length) 字节)"
    }
} finally {
    $app.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) | Out-Null
}
