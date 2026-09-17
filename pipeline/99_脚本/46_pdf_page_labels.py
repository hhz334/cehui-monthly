# -*- coding: utf-8 -*-
"""给 PDF 打页码标签：前 N 页（封面、目录）标 i、ii…，正文从 1 开始。

这样 PDF 阅读器的页码框与页脚页码、目录页码一致（封面与目录不计入正文页码）。

用法：
    python 46_pdf_page_labels.py <成刊.pdf> [--front 2]
"""
import argparse
import os
import sys

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NumberObject

sys.stdout.reconfigure(encoding="utf-8")


def set_labels(pdf_path, front):
    reader = PdfReader(pdf_path)
    writer = PdfWriter(clone_from=reader)
    nums = ArrayObject()
    nums.append(NumberObject(0))
    nums.append(DictionaryObject({NameObject("/S"): NameObject("/R"),
                                  NameObject("/St"): NumberObject(1)}))
    nums.append(NumberObject(front))
    nums.append(DictionaryObject({NameObject("/S"): NameObject("/D"),
                                  NameObject("/St"): NumberObject(1)}))
    writer._root_object[NameObject("/PageLabels")] = DictionaryObject({NameObject("/Nums"): nums})
    tmp = pdf_path + ".labels"
    with open(tmp, "wb") as fh:
        writer.write(fh)
    os.replace(tmp, pdf_path)
    return len(reader.pages)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--front", type=int, default=2)
    a = ap.parse_args()
    n = set_labels(a.pdf, a.front)
    print("已加页码标签（前 %d 页 i/ii…，正文从 1 起）｜页数 %d ｜%s" % (a.front, n, a.pdf))
    return 0


if __name__ == "__main__":
    sys.exit(main())
