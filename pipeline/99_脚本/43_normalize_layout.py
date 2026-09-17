# -*- coding: utf-8 -*-
"""统一排版参数，让 WPS/Word 与 LibreOffice 的分页一致。

背景（2026-09-17 用户反馈“Word 版与 PDF 版页码、排版不一致”）：
文档里写着 `<w:characterSpacingControl w:val="compressPunctuation"/>`（中文标点压缩）。
WPS 压缩得很激进（每行多塞几个字，全刊 51 页），LibreOffice 压缩很少（54 页），
两个引擎分页不同 → 目录页码、页脚页码在 Word 里和 PDF 里对不上。

实测：把该项设成 `doNotCompress` 后，WPS 与 LibreOffice 都是 54 页，且逐篇文章的起始页完全一致。

用法：
    python 43_normalize_layout.py <成刊.docx> [-o <输出.docx>] [--report x.md]
"""
import argparse
import os
import sys
import zipfile

from lxml import etree

sys.stdout.reconfigure(encoding="utf-8")
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
TARGET = "doNotCompress"


def normalize(xml_bytes):
    root = etree.fromstring(xml_bytes)
    cs = root.find(W + "characterSpacingControl")
    old = cs.get(W + "val") if cs is not None else None
    if cs is None:
        cs = etree.SubElement(root, W + "characterSpacingControl")
    cs.set(W + "val", TARGET)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True), old


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("-o", "--out", default="")
    ap.add_argument("--report", default="")
    a = ap.parse_args()
    out = a.out or a.src
    zin = zipfile.ZipFile(a.src)
    items = [(it, zin.read(it.filename)) for it in zin.infolist()]
    zin.close()
    old = None
    tmp = out + ".tmp43"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for it, data in items:
            if it.filename == "word/settings.xml":
                data, old = normalize(data)
            zout.writestr(it, data)
    os.replace(tmp, out)
    print("标点压缩：%s → %s（%s）" % (old, TARGET, out))
    if a.report:
        with open(a.report, "w", encoding="utf-8") as f:
            f.write("# 排版参数统一（跨渲染器分页一致）\n\n- 文件：`%s`\n- characterSpacingControl：%s → %s\n"
                    % (out, old, TARGET))
    return 0


if __name__ == "__main__":
    sys.exit(main())
