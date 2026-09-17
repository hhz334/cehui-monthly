# -*- coding: utf-8 -*-
"""导出成刊 PDF：默认**保留原版字体**，缺字体时报警而不是悄悄顶替。

背景（2026-09-17 用户反馈“导出的 pdf 字体丢失”）：
本机没装 **楷体_GB2312**（用户字体目录里只有 方正小标宋简体 和 仿宋_GB2312），
LibreOffice 导出 PDF 时把 楷体_GB2312 换成 微软雅黑，于是成刊的二级标题“（一）…”和“来源：…”行不再是楷体。

用法（默认要原版字体）：
    python 41_export_pdf.py <成刊.docx> -o <输出.pdf>
    # 缺字体时只报警、不替换；把字体装到系统里再跑一次即可得到原版字体 PDF。

    # 确实需要临时顶替（例如先出个样子）时：
    python 41_export_pdf.py <成刊.docx> --allow-substitute --map 楷体_GB2312=楷体

字体安装位置（本机为用户字体目录，与已有的 仿宋_GB2312.ttf 同处）：
    %LOCALAPPDATA%\\Microsoft\\Windows\\Fonts\\楷体_GB2312.ttf
"""
import argparse
import os
import shutil
import struct
import subprocess
import sys
import zipfile

from lxml import etree

sys.stdout.reconfigure(encoding="utf-8")
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SOFFICE = [r"C:\Program Files\LibreOffice\program\soffice.exe",
           r"C:\Program Files (x86)\LibreOffice\program\soffice.exe", "soffice"]
PARTS = ("word/document.xml", "word/styles.xml", "word/fontTable.xml")
DEFAULT_MAP = [("楷体_GB2312", "楷体")]
FONT_DIRS = [r"C:\Windows\Fonts",
             os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\Windows\Fonts")]


def installed_font_names():
    """扫描本机字体文件的内部名称（含中文名）。"""
    names = set()
    for d in FONT_DIRS:
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if not f.lower().endswith((".ttf", ".ttc", ".otf")):
                continue
            try:
                data = open(os.path.join(d, f), "rb").read()
            except OSError:
                continue
            offsets = [0]
            if data[:4] == b"ttcf":
                n = struct.unpack(">L", data[8:12])[0]
                offsets = [struct.unpack(">L", data[12 + 4 * i:16 + 4 * i])[0] for i in range(n)]
            for off in offsets:
                try:
                    num = struct.unpack(">H", data[off + 4:off + 6])[0]
                except struct.error:
                    continue
                for i in range(num):
                    rec = off + 12 + 16 * i
                    if data[rec:rec + 4] != b"name":
                        continue
                    noff = struct.unpack(">L", data[rec + 8:rec + 12])[0]
                    cnt = struct.unpack(">H", data[noff + 2:noff + 4])[0]
                    soff = struct.unpack(">H", data[noff + 4:noff + 6])[0]
                    for j in range(cnt):
                        r = noff + 6 + 12 * j
                        _, _, _, nid, ln, o = struct.unpack(">HHHHHH", data[r:r + 12])
                        if nid not in (1, 4):
                            continue
                        raw = data[noff + soff + o:noff + soff + o + ln]
                        for enc in ("utf-16-be", "gb18030", "latin-1"):
                            try:
                                s = raw.decode(enc).strip()
                            except (UnicodeDecodeError, LookupError):
                                continue
                            if s and s.isprintable():
                                names.add(s)
                                break
                    break
    return names


def docx_fonts(src):
    """docx 里出现过的东亚字体名。"""
    z = zipfile.ZipFile(src)
    out = set()
    for name in z.namelist():
        if not name.startswith("word/") or not name.endswith(".xml"):
            continue
        if not any(k in name for k in ("document", "footer", "header", "styles")):
            continue
        root = etree.fromstring(z.read(name))
        for rf in root.iter(W + "rFonts"):
            v = rf.get(W + "eastAsia")
            if v:
                out.add(v)
    return out


def remap_fonts(src, dst, mapping):
    """把 docx 里缺失的字体名替换成等价字体，另存为 dst。"""
    zin = zipfile.ZipFile(src)
    items = [(it, zin.read(it.filename)) for it in zin.infolist()]
    zin.close()
    hits = {}
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for it, data in items:
            if it.filename.endswith(".xml") and it.filename.startswith("word/"):
                try:
                    text = data.decode("utf-8")
                except UnicodeDecodeError:
                    zout.writestr(it, data)
                    continue
                for old, new in mapping:
                    if old in text:
                        hits[old] = hits.get(old, 0) + text.count(old)
                        text = text.replace(old, new)
                data = text.encode("utf-8")
            zout.writestr(it, data)
    return hits


def to_pdf(docx, outdir):
    for exe in SOFFICE:
        if os.path.sep in exe and not os.path.exists(exe):
            continue
        try:
            subprocess.run([exe, "--headless", "--convert-to", "pdf", "--outdir", outdir, docx],
                           check=False, capture_output=True, timeout=600)
        except (OSError, subprocess.SubprocessError):
            continue
        hit = os.path.join(outdir, os.path.basename(docx)[:-5] + ".pdf")
        if os.path.exists(hit):
            return hit
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("-o", "--out", default="")
    ap.add_argument("--map", action="append", default=[])
    ap.add_argument("--allow-substitute", action="store_true",
                    help="缺字体时允许用等价字体顶替（默认不允许，只报警）")
    ap.add_argument("--report", default="")
    a = ap.parse_args()
    out = a.out or os.path.splitext(a.src)[0] + ".pdf"
    mapping = [tuple(m.split("=", 1)) for m in a.map] or DEFAULT_MAP
    installed = installed_font_names()
    used = docx_fonts(a.src)
    missing = sorted(f for f in used if f not in installed)
    if missing:
        print("！！本机缺少字体：%s" % "、".join(missing))
        print("   这些字体在导 PDF 时会被替代字体顶替。要原版字体，请把字体文件装到：")
        for d in FONT_DIRS:
            print("     %s" % d)
        if not a.allow_substitute:
            print("   已按“原版字体优先”导出：不替换字体名（缺的字体由 LibreOffice 自行回退）。")
            mapping = []
    elif not a.allow_substitute:
        mapping = []
    tmpdir = os.path.join(os.path.dirname(os.path.abspath(a.src)), "_pdfexport_tmp")
    os.makedirs(tmpdir, exist_ok=True)
    tmp_docx = os.path.join(tmpdir, "export_source.docx")
    hits = remap_fonts(a.src, tmp_docx, mapping)
    pdf = to_pdf(tmp_docx, tmpdir)
    if not pdf:
        print("导出失败：找不到可用的 LibreOffice")
        return 1
    shutil.copyfile(pdf, out)
    shutil.rmtree(tmpdir, ignore_errors=True)
    print("字体替换：%s" % (hits or "无需要替换"))
    print("输出：%s（%d 字节）" % (out, os.path.getsize(out)))
    if a.report:
        with open(a.report, "w", encoding="utf-8") as f:
            f.write("# PDF 导出（含字体替换）\n\n- 输入：`%s`\n- 输出：`%s`\n\n" % (a.src, out))
            f.write("| 缺失字体 | 替换为 | 处理处数 |\n| --- | --- | --- |\n")
            for old, new in mapping:
                f.write("| %s | %s | %d |\n" % (old, new, hits.get(old, 0)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
