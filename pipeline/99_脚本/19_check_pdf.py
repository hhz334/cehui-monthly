# -*- coding: utf-8 -*-
"""对 Word 版交付件的 PDF 渲染结果做程序化版式体检。

检查项：页数、空白页、正文是否越出页边距（左右下）、表格是否压到页边、
目录条目是否齐全（67 条标题是否都出现在 PDF 文本中）。
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_utils import ROOT  # noqa: E402

import openpyxl  # noqa: E402
import pdfplumber  # noqa: E402

RENDER_DIR = os.path.join(ROOT, "Word版", "_render")
TOL = 6  # 容许 6pt 误差（边框、字距）


def check(path):
    name = os.path.basename(path)
    problems = []
    with pdfplumber.open(path) as pdf:
        pages = len(pdf.pages)
        total_words = 0
        for i, page in enumerate(pdf.pages, 1):
            words = page.extract_words()
            total_words += len(words)
            if not words:
                problems.append(f"第{i}页无文本")
                continue
            left = min(w["x0"] for w in words)
            right = max(w["x1"] for w in words)
            bottom = max(w["bottom"] for w in words)
            limit_l = min(page.width * 0.06, 60)
            limit_r = page.width - min(page.width * 0.06, 60) + TOL
            limit_b = page.height - 30
            if left < limit_l - TOL:
                problems.append(f"第{i}页左侧越界 x0={left:.1f}")
            if right > limit_r:
                problems.append(f"第{i}页右侧越界 x1={right:.1f} > {limit_r:.1f}")
            if bottom > limit_b:
                problems.append(f"第{i}页底部越界 bottom={bottom:.1f}")
            words_sorted = sorted(words, key=lambda w: (round(w["top"], 1), w["x0"]))
            for a_idx in range(len(words_sorted) - 1):
                a = words_sorted[a_idx]
                for b in words_sorted[a_idx + 1:a_idx + 6]:
                    ox = min(a["x1"], b["x1"]) - max(a["x0"], b["x0"])
                    oy = min(a["bottom"], b["bottom"]) - max(a["top"], b["top"])
                    if ox > 4 and oy > 4:
                        problems.append(f"第{i}页文字重叠：「{a['text']}」×「{b['text']}」")
                        break
    return {"file": name, "pages": pages, "words": total_words, "problems": problems}


def catalog_coverage():
    ws = openpyxl.load_workbook(os.path.join(ROOT, "00_资讯目录.xlsx"))["资讯目录"]
    header = [c.value for c in ws[1]]
    rows = [dict(zip(header, r)) for r in ws.iter_rows(min_row=2, values_only=True)]
    pdf_path = os.path.join(RENDER_DIR, "01_测绘动态资讯目录", "01_测绘动态资讯目录.pdf")
    with pdfplumber.open(pdf_path) as pdf:
        raw = "".join((p.extract_text() or "") for p in pdf.pages)
    text = re.sub(r"[\s\W_]+", "", raw)
    missing = []
    for r in rows:
        key = re.sub(r"[\s\W_]+", "", str(r["标题"]))[:12]
        if key and key not in text:
            missing.append(r["标题"])
    return missing


def main():
    results = []
    if os.path.isdir(RENDER_DIR):
        for d in sorted(os.listdir(RENDER_DIR)):
            sub = os.path.join(RENDER_DIR, d)
            if not os.path.isdir(sub):
                continue
            for f in sorted(os.listdir(sub)):
                if f.lower().endswith(".pdf"):
                    results.append(check(os.path.join(sub, f)))
    for r in results:
        flag = "OK" if not r["problems"] else "需关注"
        print(f"[{flag}] {r['file']}：{r['pages']} 页，{r['words']} 词")
        for p in r["problems"][:12]:
            print("    -", p)
        if len(r["problems"]) > 12:
            print(f"    …… 另有 {len(r['problems']) - 12} 处")
    missing = catalog_coverage()
    print(f"\n目录完整性：缺失 {len(missing)} 条")
    for m in missing[:10]:
        print("    -", m)


if __name__ == "__main__":
    main()
