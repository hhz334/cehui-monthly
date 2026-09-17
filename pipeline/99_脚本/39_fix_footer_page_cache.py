# -*- coding: utf-8 -*-
"""刷新页脚 PAGE 域的缓存值，并打开“文档打开时更新域”，解决 WPS 里页脚页码与目录对不上。

背景（2026-09-17 实测）：页脚用的是 `PAGE \\* MERGEFORMAT` 域，域里保存的是**上次排版时的缓存值**。
文档改版后缓存会过期（本期技术应用类缓存 42、科技前沿类缓存 60，实际应为 25、47）。
Word/LibreOffice 打开会重算，WPS 默认按缓存显示 → 页脚页码和目录不一致。

本脚本：
1. 用 LibreOffice 渲染 PDF，按每个板块首页的页脚值算出该分节的起始页码；
2. 把对应 footer 部件里的 PAGE 域缓存值改成这个数字（WPS 不重算时显示也正确）；
3. 在 `word/settings.xml` 写入 `<w:updateFields w:val="true"/>`，打开文档时强制更新域。

用法：
    python 39_fix_footer_page_cache.py <成刊.docx> [-o <输出.docx>] [--report <报告.md>]
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import zipfile

from lxml import etree

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_compressed import compressed_pdf   # noqa: E402
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
SOFFICE = [r"C:\Program Files\LibreOffice\program\soffice.exe",
           r"C:\Program Files (x86)\LibreOffice\program\soffice.exe", "soffice"]
BOARDS = ["政策法规类", "技术应用类", "科技前沿类"]


def render_pdf(docx, outdir):
    os.makedirs(outdir, exist_ok=True)
    for exe in SOFFICE:
        if os.path.sep in exe and not os.path.exists(exe):
            continue
        try:
            subprocess.run([exe, "--headless", "--convert-to", "pdf", "--outdir", outdir, docx],
                           check=False, capture_output=True, timeout=300)
        except (OSError, subprocess.SubprocessError):
            continue
        hit = os.path.join(outdir, os.path.basename(docx)[:-5] + ".pdf")
        if os.path.exists(hit):
            return hit
    return ""


def page_numbers(pdf):
    """返回 [(页脚数字, 页首栏目名)]。"""
    import pdfplumber
    out = []

    def board_of(t):
        for b in BOARDS:
            for name in (b, b.rstrip("类")):        # 页眉可能写“政策法规”（四个字）
                if name and t.startswith(name):
                    return b
        return ""

    with pdfplumber.open(pdf) as doc:
        for pg in doc.pages:
            flat = re.sub(r"\s+", "", pg.extract_text() or "")
            m = re.search(r"—(\d+)—", flat)
            rest = re.sub(r"—\d+—", "", flat)
            out.append((int(m.group(1)) if m else None, board_of(rest)))
    return out


def section_footers(docx):
    """按文档顺序返回每个分节的默认页脚部件名（除去封面/目录那节）。"""
    z = zipfile.ZipFile(docx)
    rels = etree.fromstring(z.read("word/_rels/document.xml.rels"))
    rid2part = {}
    for rel in rels:
        rid2part[rel.get("Id")] = rel.get("Target").lstrip("/")
    root = etree.fromstring(z.read("word/document.xml"))
    out = []
    for sect in root.iter(W + "sectPr"):
        ref = None
        for fr in sect.findall(W + "footerReference"):
            if (fr.get(W + "type") or "default") == "default":
                ref = fr.get(R + "id")
                break
        part = rid2part.get(ref, "")
        out.append("word/" + part if part and not part.startswith("word/") else part)
    return [p for p in out if p]


def set_cached_page(xml_bytes, value):
    """把部件里所有 PAGE 域的缓存结果改成 value，返回 (新XML, 改了几个)。"""
    root = etree.fromstring(xml_bytes)
    n = 0
    for par in root.iter(W + "p"):
        runs = list(par.iter(W + "r"))
        i = 0
        while i < len(runs):
            fc = runs[i].find(W + "fldChar")
            if fc is not None and fc.get(W + "fldCharType") == "separate":
                j = i + 1
                first = True
                while j < len(runs):
                    e = runs[j].find(W + "fldChar")
                    if e is not None and e.get(W + "fldCharType") == "end":
                        break
                    for t in runs[j].findall(W + "t"):
                        t.text = str(value) if first else ""
                        if str(value) != str(value).strip():
                            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                        first = False
                    j += 1
                n += 1
                i = j
            i += 1
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True), n


def force_update_fields(xml_bytes):
    root = etree.fromstring(xml_bytes)
    if root.find(W + "updateFields") is None:
        el = etree.SubElement(root, W + "updateFields")
        el.set(W + "val", "true")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("-o", "--out", default="")
    ap.add_argument("--report", default="")
    a = ap.parse_args()
    out = a.out or a.src
    tmp = os.path.join(os.path.dirname(os.path.abspath(out)), "_pagecache_tmp")
    # 必须按标点压缩口径渲染，否则分节首页页码会算成未压缩的布局
    pdf = compressed_pdf(a.src, tmp) or render_pdf(a.src, tmp)
    if not pdf:
        print("渲染失败，无法确定实际页码")
        return 1
    pages = page_numbers(pdf)
    first_of_board = {}
    for no, board in pages:
        if board and board not in first_of_board and no:
            first_of_board[board] = no
    print("各板块首页页脚：%s" % first_of_board)

    all_parts = section_footers(a.src)
    # 第一节是封面＋目录（页脚为空），板块分节从第二节开始
    parts = all_parts[1:] if len(all_parts) > len(BOARDS) else all_parts
    print("分节页脚部件（含封面节）：%s → 用 %s" % (all_parts, parts))
    plan = []
    for board in BOARDS:
        if board in first_of_board and len(plan) < len(parts):
            plan.append((parts[len(plan)], first_of_board[board]))
    print("将写入：%s" % plan)

    zin = zipfile.ZipFile(a.src)
    changes = []
    items = [(it, zin.read(it.filename)) for it in zin.infolist()]   # 全部读进内存，允许原地覆盖
    zin.close()
    tmp_out = out + ".tmp39"
    with zipfile.ZipFile(tmp_out, "w", zipfile.ZIP_DEFLATED) as zout:
        for it, data in items:
            if it.filename == "word/settings.xml":
                data = force_update_fields(data)
                changes.append(("settings.xml", "已打开“打开时更新域”", 0))
            for part, val in plan:
                if it.filename == part:
                    data, n = set_cached_page(data, val)
                    changes.append((part, "缓存页码→%s" % val, n))
            zout.writestr(it, data)
    os.replace(tmp_out, out)
    for part, note, n in changes:
        print("  %-22s %s（%d 处）" % (part, note, n))
    print("输出：%s" % out)
    if a.report:
        with open(a.report, "w", encoding="utf-8") as f:
            f.write("# 页脚页码缓存刷新\n\n- 输入：`%s`\n- 输出：`%s`\n\n" % (a.src, out))
            f.write("| 部件 | 处理 | 处数 |\n| --- | --- | --- |\n")
            for part, note, n in changes:
                f.write("| %s | %s | %d |\n" % (part, note, n))
            f.write("\n- 各板块首页页脚：%s\n" % first_of_board)
    shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
