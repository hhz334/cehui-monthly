# -*- coding: utf-8 -*-
"""修页脚：把“— N —”页码在页脚文本框里居中，并统一各分节的页脚高度。

背景（2026-09-17 用户反馈“页脚歪了”）：
- 页脚页码在文本框内是**左对齐**的，文本框本身居中，于是页码落在页面中心偏左约 1.8cm；
- 各分节的 `w:pgMar/@w:footer` 不一致（政策法规／技术应用类 1247，科技前沿类 992），
  页码在不同板块高低不同（相差约 13pt）。

本脚本：给页脚文本框内的段落加 `w:jc=center`、去掉遗留制表位；把各分节页脚距离统一。

用法：
    python 40_fix_footer_layout.py <docx> [-o <输出.docx>] [--footer-twips 1247] [--report x.md]
"""
import argparse
import os
import re
import sys
import zipfile

from lxml import etree

sys.stdout.reconfigure(encoding="utf-8")
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
FOOTER_RE = re.compile(r"^word/footer\d*\.xml$")


def center_footer_paragraphs(xml_bytes):
    """页脚部件：让文本框内的页码居中。返回 (新XML, 处理段落数)。"""
    root = etree.fromstring(xml_bytes)
    n = 0
    for txbx in root.iter(W + "txbxContent"):        # 文本框内容在 w 命名空间下
        for par in txbx.iter(W + "p"):
            has_page = any("PAGE" in (it.text or "") for it in par.iter(W + "instrText"))
            if not has_page:
                continue
            pPr = par.find(W + "pPr")
            if pPr is None:
                pPr = etree.Element(W + "pPr")
                par.insert(0, pPr)
            for tabs in pPr.findall(W + "tabs"):
                pPr.remove(tabs)
            for jc in pPr.findall(W + "jc"):
                pPr.remove(jc)
            jc = etree.SubElement(pPr, W + "jc")
            jc.set(W + "val", "center")
            n += 1
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True), n


def unify_footer_distance(xml_bytes, twips, skip_first=True):
    """把各分节的页脚距离统一（跳过封面/目录那节）。返回 (新XML, 改了几节)。"""
    root = etree.fromstring(xml_bytes)
    n = 0
    for i, sect in enumerate(root.iter(W + "sectPr")):
        if skip_first and i == 0:
            continue
        mar = sect.find(W + "pgMar")
        if mar is None:
            continue
        if mar.get(W + "footer") != str(twips):
            mar.set(W + "footer", str(twips))
            n += 1
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True), n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("-o", "--out", default="")
    ap.add_argument("--footer-twips", type=int, default=1247)
    ap.add_argument("--report", default="")
    a = ap.parse_args()
    out = a.out or a.src
    zin = zipfile.ZipFile(a.src)
    items = [(it, zin.read(it.filename)) for it in zin.infolist()]
    zin.close()
    log = []
    tmp_out = out + ".tmp40"
    with zipfile.ZipFile(tmp_out, "w", zipfile.ZIP_DEFLATED) as zout:
        for it, data in items:
            if FOOTER_RE.match(it.filename):
                data, k = center_footer_paragraphs(data)
                if k:
                    log.append((it.filename, "页码居中", k))
            elif it.filename == "word/document.xml":
                data, k = unify_footer_distance(data, a.footer_twips)
                if k:
                    log.append((it.filename, "页脚距离统一为 %d twips" % a.footer_twips, k))
            zout.writestr(it, data)
    os.replace(tmp_out, out)
    for part, note, k in log:
        print("  %-22s %s（%d 处）" % (part, note, k))
    print("输出：%s" % out)
    if a.report:
        with open(a.report, "w", encoding="utf-8") as f:
            f.write("# 页脚版式修正\n\n- 输入：`%s`\n- 输出：`%s`\n\n" % (a.src, out))
            f.write("| 部件 | 处理 | 处数 |\n| --- | --- | --- |\n")
            for part, note, k in log:
                f.write("| %s | %s | %d |\n" % (part, note, k))
    return 0


if __name__ == "__main__":
    sys.exit(main())
