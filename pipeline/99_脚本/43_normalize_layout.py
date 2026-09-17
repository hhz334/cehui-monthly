# -*- coding: utf-8 -*-
"""设置中文标点压缩参数（决定 Word/WPS 与 PDF 的分页口径）。

背景（2026-09-17 用户反馈“Word 版与 PDF 版页码、排版不一致”）：
文档里写着 `<w:characterSpacingControl w:val="compressPunctuation"/>`（中文标点压缩）。
WPS 压缩得很激进（每行多塞几个字，全刊 51 页），LibreOffice 压缩很少（54 页），
两个引擎分页不同 → 目录页码、页脚页码在 Word 里和 PDF 里对不上。

两种口径（2026-09-17 按《政策要情》第 100 期定为 compress，并改用 WPS 出 PDF）：

* `compress`（默认，等同 100 期标准）：保留中文标点压缩。WPS 压缩更紧（本刊 51 页），
  LibreOffice 压得少（54 页）——因此**页码与 PDF 必须都用 WPS 出**，两边才一致（见 45 号脚本）。
* `nocompress`：关掉压缩，两个引擎分页一致（本刊都是 54 页），可用 LibreOffice 出 PDF。

用法：
    python 43_normalize_layout.py <成刊.docx> [--mode compress|nocompress] [-o <输出.docx>]
"""
import argparse
import os
import sys
import zipfile

from lxml import etree

sys.stdout.reconfigure(encoding="utf-8")
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
TARGETS = {"compress": "compressPunctuation", "nocompress": "doNotCompress"}


def normalize(xml_bytes, target):
    root = etree.fromstring(xml_bytes)
    cs = root.find(W + "characterSpacingControl")
    old = cs.get(W + "val") if cs is not None else None
    if cs is None:
        cs = etree.SubElement(root, W + "characterSpacingControl")
    cs.set(W + "val", target)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True), old


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("-o", "--out", default="")
    ap.add_argument("--mode", choices=["compress", "nocompress"], default="compress",
                    help="compress=保留标点压缩（100 期标准，配 WPS 出 PDF）；nocompress=关掉压缩（配 LibreOffice）")
    ap.add_argument("--report", default="")
    a = ap.parse_args()
    target = TARGETS[a.mode]
    out = a.out or a.src
    zin = zipfile.ZipFile(a.src)
    items = [(it, zin.read(it.filename)) for it in zin.infolist()]
    zin.close()
    old = None
    tmp = out + ".tmp43"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for it, data in items:
            if it.filename == "word/settings.xml":
                data, old = normalize(data, target)
            zout.writestr(it, data)
    os.replace(tmp, out)
    print("标点压缩：%s → %s（%s）" % (old, target, out))
    if a.report:
        with open(a.report, "w", encoding="utf-8") as f:
            f.write("# 标点压缩参数\n\n- 文件：`%s`\n- characterSpacingControl：%s → %s\n"
                    % (out, old, target))
    return 0


if __name__ == "__main__":
    sys.exit(main())
