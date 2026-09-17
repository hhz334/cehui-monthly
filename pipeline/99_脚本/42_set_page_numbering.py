# -*- coding: utf-8 -*-
"""设置整本刊的页码编号方式，让 PDF 阅读器页码 = 页脚页码 = 目录页码。

两种口径（2026-09-17 用户反馈“PDF 里目录和对应页码不对”后新增）：

* `pdf`（默认）：**封面、目录也计入页码**（这两页不打印数字），正文从第 3 页开始编号。
  这样读者在 PDF 里跳到“第 20 页”看到的就是页脚“— 20 —”，目录写的也是 20。
* `body`：正文从 1 开始编号（《政策要情》的公文汇编口径），封面与目录不计入。
  此时 PDF 阅读器页码 = 页脚页码 + 2。

用法：
    python 42_set_page_numbering.py <成刊.docx> [--mode pdf|body] [-o <输出.docx>]
"""
import argparse
import os
import sys
import zipfile

from lxml import etree

sys.stdout.reconfigure(encoding="utf-8")
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def set_numbering(xml_bytes, mode):
    root = etree.fromstring(xml_bytes)
    sects = list(root.iter(W + "sectPr"))
    for i, sect in enumerate(sects):
        pn = sect.find(W + "pgNumType")
        if pn is None:
            pn = etree.Element(W + "pgNumType")
            sect.insert(0, pn)
        pn.set(W + "fmt", "decimal")
        # 第一卷（封面＋目录）永远从 1 开始
        # pdf 模式：后续分节“接着数”（不计入 start）；body 模式：正文分节重新从 1 开始
        if i == 0:
            pn.set(W + "start", "1")
        elif mode == "body" and i == 1:      # 只有第一节正文重新从 1 开始
            pn.set(W + "start", "1")
        elif pn.get(W + "start") is not None:
            del pn.attrib[W + "start"]
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("-o", "--out", default="")
    ap.add_argument("--mode", choices=["pdf", "body"], default="pdf")
    ap.add_argument("--report", default="")
    a = ap.parse_args()
    out = a.out or a.src
    zin = zipfile.ZipFile(a.src)
    items = [(it, zin.read(it.filename)) for it in zin.infolist()]
    zin.close()
    changed = False
    tmp = out + ".tmp42"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for it, data in items:
            if it.filename == "word/document.xml":
                new = set_numbering(data, a.mode)
                changed = new != data
                data = new
            zout.writestr(it, data)
    os.replace(tmp, out)
    print("页码口径：%s（%s）→ %s"
          % (a.mode, "封面/目录计入，正文从第3页起" if a.mode == "pdf" else "正文从第1页起，封面/目录不计入", out))
    if a.report:
        with open(a.report, "w", encoding="utf-8") as f:
            f.write("# 页码口径\n\n- 输入/输出：`%s`\n- 口径：%s\n" % (out, a.mode))
    return 0 if changed else 0


if __name__ == "__main__":
    sys.exit(main())
