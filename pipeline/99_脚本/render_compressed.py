# -*- coding: utf-8 -*-
"""按《政策要情》100 期口径渲染 PDF：保留中文标点压缩，且与 Word/WPS 分页一致。

为什么不能直接用 LibreOffice 打开 docx 导 PDF：
  docx 里写的是 `characterSpacingControl = compressPunctuation`（标点压缩），
  LibreOffice 导入时把它的内部设置 `CharacterCompressionType` 读成了 0（不压缩）→ 分页变松（本刊 54 页），
  而 WPS 按压缩排版（51 页），两边页码必然对不上。

做法（实测可让两边分页一致）：
  1. docx → odt（LibreOffice）；
  2. 把 ODT 的 `CharacterCompressionType` 改成 1（只压缩标点，等同 100 期口径）；
  3. odt → pdf（LibreOffice）。

用法：
    from render_compressed import compressed_pdf
    pdf = compressed_pdf("成刊.docx", "输出目录")
"""
import os
import re
import subprocess
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")
SOFFICE = [r"C:\Program Files\LibreOffice\program\soffice.exe",
           r"C:\Program Files (x86)\LibreOffice\program\soffice.exe", "soffice"]
ITEM = ('<config:config-item config:name="CharacterCompressionType" config:type="short">'
        '%d</config:config-item>')


def soffice():
    for exe in SOFFICE:
        if os.path.sep in exe and not os.path.exists(exe):
            continue
        return exe
    return ""


def convert(src, fmt, outdir):
    exe = soffice()
    if not exe:
        return ""
    os.makedirs(outdir, exist_ok=True)
    try:
        subprocess.run([exe, "--headless", "--convert-to", fmt, "--outdir", outdir, src],
                       check=False, capture_output=True, timeout=900)
    except (OSError, subprocess.SubprocessError):
        return ""
    out = os.path.join(outdir, os.path.splitext(os.path.basename(src))[0] + "." + fmt)
    return out if os.path.exists(out) else ""


def set_compression(odt_path, value=1):
    """把 ODT 的标点压缩设置改成 value（1=只压缩标点）。返回新文件路径。"""
    dst = odt_path.replace(".odt", "_c%d.odt" % value)
    zin = zipfile.ZipFile(odt_path)
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for it in zin.infolist():
            data = zin.read(it.filename)
            if it.filename == "settings.xml":
                t = data.decode("utf-8")
                if ITEM % value in t:
                    pass
                elif re.search(r'config:name="CharacterCompressionType"[^>]*>\d+<', t):
                    t = re.sub(r'(config:name="CharacterCompressionType"[^>]*>)\d+(<)', r"\g<1>%d\g<2>" % value, t)
                else:
                    t = t.replace("</office:settings>", "  " + (ITEM % value) + "\n</office:settings>")
                data = t.encode("utf-8")
            zout.writestr(it, data)
    return dst


def compressed_pdf(docx, outdir, value=1):
    """返回按“标点压缩”口径渲染出来的 PDF 路径。"""
    odt = convert(docx, "odt", outdir)
    if not odt:
        return ""
    patched = set_compression(odt, value)
    return convert(patched, "pdf", outdir)


if __name__ == "__main__":
    print(compressed_pdf(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "."))
