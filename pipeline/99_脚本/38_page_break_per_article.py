# -*- coding: utf-8 -*-
"""给成刊做“每篇文章另起一页”（固定规则，2026-09-17 定）。

规则：每条文章标题段（`【省份】标题`）设 `w:pageBreakBefore`，让它从新页开始；
但**紧跟分节符的板块首条**已经有分节符另页，不再设分页，避免产生空白页。

用法：
    python 38_page_break_per_article.py <成刊.docx> [-o <输出.docx>] [--report <报告.md>]
"""
import argparse
import os
import re
import sys

import docx
from docx.oxml.ns import qn

sys.stdout.reconfigure(encoding="utf-8")
BODY_RE = re.compile(r"^【[^】]{1,6}】\s*\S")


def has_sect_pr(par):
    pPr = par._p.find(qn("w:pPr"))
    return pPr is not None and pPr.find(qn("w:sectPr")) is not None


def is_blank(par):
    """真空段（无文字、无图、无分节符）——标题前的条间空行。"""
    if (par.text or "").strip():
        return False
    if has_sect_pr(par):
        return False
    if par._p.findall(".//" + qn("w:drawing")) or par._p.findall(".//" + qn("w:pict")):
        return False
    return True


def strip_leading_blanks(par, limit=10):
    """删掉标题前紧邻的空段落，避免“空段被顶到新页 + 标题另起一页”产生空白页。"""
    n = 0
    prev = par._p.getprevious()
    while n < limit and prev is not None and prev.tag == qn("w:p"):
        obj = docx.text.paragraph.Paragraph(prev, par._parent)
        if not is_blank(obj):
            break
        nxt = prev.getprevious()
        prev.getparent().remove(prev)
        prev = nxt
        n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("-o", "--out", default="")
    ap.add_argument("--report", default="")
    a = ap.parse_args()
    out = a.out or a.src

    d = docx.Document(a.src)
    log, prev_sect, first_title = [], False, True
    for i, p in enumerate(d.paragraphs):
        t = (p.text or "").strip()
        if BODY_RE.match(t):
            if first_title or prev_sect:
                log.append(("跳过（本就另页）", i, t[:40]))
            else:
                p.paragraph_format.page_break_before = True
                removed = strip_leading_blanks(p)
                log.append(("已设另起一页" + ("（并删 %d 个空段）" % removed if removed else ""),
                            i, t[:40]))
            first_title = False
        prev_sect = has_sect_pr(p)      # 上一段是否就是携带分节符的那一段
    d.save(out)
    n = sum(1 for r in log if r[0].startswith("已设另起一页"))
    print("条目 %d 条：另起一页 %d 条，跳过 %d 条 → %s" % (len(log), n, len(log) - n, out))
    for row in log:
        print("  [%s] 段%d %s" % row)
    if a.report:
        with open(a.report, "w", encoding="utf-8") as f:
            f.write("# 每篇文章另起一页\n\n- 输入：`%s`\n- 输出：`%s`\n- 条目 %d 条：另起一页 %d 条，跳过 %d 条\n\n"
                    % (a.src, out, len(log), n, len(log) - n))
            f.write("| 结果 | 段落序号 | 标题 |\n| --- | --- | --- |\n")
            for row in log:
                f.write("| %s | %d | %s |\n" % row)


if __name__ == "__main__":
    main()
