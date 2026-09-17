# -*- coding: utf-8 -*-
"""给成刊目录加内部书签与超链接，让 Word、WPS 与导出的 PDF 都能点击跳转。

做三件事：
1. 在每条正文标题段（`【省份】标题》）上插入 `w:bookmarkStart/End`；
2. 把目录页对应条目的标题文字做成 `HYPERLINK \\l "书签名" \\h` 域（WPS 与 Word 都认；WPS 不认 Word 原生的
   `w:hyperlink w:anchor`，会提示“无法打开指定文件”）。字体字号不动，制表位与页码留在域之外；
3. 可选：按渲染出来的 PDF 回读页码（`--pdf`），把目录上的页码改成文档自身页脚的真实页码。

LibreOffice / Word 导出 PDF 时会保留内部超链接，点击目录即可跳到对应文章。

用法：
    python 34_add_toc_links.py <成稿.docx> [-o <输出.docx>] [--pdf <成稿.pdf>] [--report <报告.md>]
"""
import argparse
import copy
import glob
import os
import re
import subprocess
import sys

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TOC_RE = re.compile(r"^(?P<num>\d+)[.．]\s*(?P<title>.+?)\t(?P<page>\d+)\s*$")
BODY_RE = re.compile(r"^【(?P<prov>[^】]{1,6})】\s*(?P<title>.+)$")
FOOT_RE = re.compile(r"—\s*(\d+)\s*—")
SOFFICE_CANDIDATES = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "soffice",
]


def norm(s):
    return re.sub(r"[\s\u3000]+", "", s or "")


def key_of(title):
    return norm(re.sub(r"^[^：:]{1,4}[：:]", "", (title or "").strip()))


def similar(a, b):
    a, b = key_of(a)[:24], key_of(b)[:24]
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 0.95
    return len(set(a) & set(b)) / max(1, len(set(a) | set(b)))


def split_runs(par):
    """返回 (标题 run 列表, 页码 run 列表)。

    目录行形如 `<标题…><tab><页码>`；页码常被拆成多个 run（如 24 = `2` + `4`），
    因此页码一侧要收全 tab 之后的全部 run。
    """
    title, page_els = [], []
    runs = list(par.runs)
    for i, r in enumerate(runs):
        el = r._element
        if el.find(qn("w:tab")) is not None:
            if el.findall(qn("w:t")):          # tab 与页码同处一个 run 的情况
                page_els.append(el)
            page_els += [x._element for x in runs[i + 1:]]
            break
        title.append(el)
    return title, page_els


def page_text(page_els):
    return "".join(t.text or "" for el in page_els for t in el.findall(qn("w:t")))


def set_page_text(page_els, value):
    """把页码写成 `value`，多余的页码 run 清空（不动 tab 与字体属性）。"""
    first = True
    for el in page_els:
        for t in el.findall(qn("w:t")):
            t.text = str(value) if first else ""
            first = False


def add_bookmark(par, name, bookmark_id):
    for start in par._p.findall(qn("w:bookmarkStart")):
        if start.get(qn("w:name")) == name:      # 重跑时复用已有书签
            return
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), str(bookmark_id))
    start.set(qn("w:name"), name)
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), str(bookmark_id))
    p = par._p
    pPr = p.find(qn("w:pPr"))
    if pPr is not None:
        pPr.addnext(start)
    else:
        p.insert(0, start)
    p.append(end)


def wrap_hyperlink(par, run_elements, anchor):
    p = par._p
    hl = OxmlElement("w:hyperlink")
    hl.set(qn("w:anchor"), anchor)
    p.insert(list(p).index(run_elements[0]), hl)
    for el in run_elements:
        hl.append(el)          # append 即“移动”，run 属性保持不变


def _field_run(kind, rPr=None):
    r = OxmlElement("w:r")
    if rPr is not None:
        r.append(copy.deepcopy(rPr))
    if kind:
        f = OxmlElement("w:fldChar")
        f.set(qn("w:fldCharType"), kind)
        r.append(f)
    return r


def wrap_hyperlink_field(par, run_elements, anchor):
    """用 HYPERLINK 域做内部跳转——WPS 与 Word 都认（WPS 自身就是这么写的）。

    此前用 Word 原生的 `w:hyperlink w:anchor`，WPS 会把它当外部文件，点击提示“无法打开指定文件”。
    域形式：`{ HYPERLINK \\l "书签名" \\h }`，域结果为标题文字（保留原字体格式）。
    """
    p = par._p
    first = run_elements[0]
    rPr = first.find(qn("w:rPr"))
    idx = list(p).index(first)
    begin = _field_run("begin", rPr)
    instr = _field_run(None, rPr)
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = ' HYPERLINK \\l "%s" \\h ' % anchor
    instr.append(it)
    sep = _field_run("separate", rPr)
    for el in (begin, instr, sep):
        p.insert(idx, el)
        idx += 1
    end = _field_run("end", rPr)
    run_elements[-1].addnext(end)


def unwrap_hyperlinks(par):
    """拆掉已有的 `w:hyperlink`／HYPERLINK 域与书签（保证脚本可重复运行）。"""
    p = par._p
    for hl in list(p.findall(qn("w:hyperlink"))):
        idx = list(p).index(hl)
        for el in list(hl):
            p.insert(idx, el)
            idx += 1
        p.remove(hl)
    # 删掉之前生成的 HYPERLINK 域：只去掉 fldChar／instrText 这些“域标记”run，保留标题文字 run
    in_field, drop = False, []
    for el in list(p):
        if el.tag != qn("w:r"):
            continue
        fc = el.find(qn("w:fldChar"))
        kind = fc.get(qn("w:fldCharType")) if fc is not None else None
        if kind == "begin":
            in_field = True
            drop.append(el)
            continue
        if kind == "end":
            in_field = False
            drop.append(el)
            continue
        if kind == "separate" or (in_field and el.find(qn("w:instrText")) is not None):
            drop.append(el)
    for el in drop:
        el.getparent().remove(el)
    ids = set()
    for start in list(p.findall(qn("w:bookmarkStart"))):
        if (start.get(qn("w:name")) or "").startswith("toc_"):
            ids.add(start.get(qn("w:id")))
            p.remove(start)
    for end in list(p.findall(qn("w:bookmarkEnd"))):
        if end.get(qn("w:id")) in ids:
            p.remove(end)


def render_pdf(docx_path, outdir):
    os.makedirs(outdir, exist_ok=True)
    for exe in SOFFICE_CANDIDATES:
        if os.path.sep in exe and not os.path.exists(exe):
            continue
        try:
            subprocess.run([exe, "--headless", "--convert-to", "pdf",
                            "--outdir", outdir, docx_path],
                           check=False, capture_output=True, timeout=300)
        except (OSError, subprocess.SubprocessError):
            continue
        hit = os.path.join(outdir, os.path.basename(docx_path)[:-5] + ".pdf")
        if os.path.exists(hit):
            return hit
    return ""


def page_numbers(pdf):
    """返回 (每页正文字符串, 每页页脚页码)。"""
    import pdfplumber
    texts, feet, first_body = [], [], 1
    with pdfplumber.open(pdf) as doc:
        for i, pg in enumerate(doc.pages, 1):
            t = pg.extract_text() or ""
            texts.append(norm(t))
            m = FOOT_RE.search(t)
            feet.append(int(m.group(1)) if m else 0)
            if first_body == 1 and "来源：" in t:
                first_body = i
    return texts, feet, first_body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("-o", "--out", default="")
    ap.add_argument("--pdf", default="", help="成稿 PDF；给了就回读页码修正目录数字")
    ap.add_argument("--style", choices=["field", "anchor"], default="field",
                    help="field=HYPERLINK 域（WPS/Word 通用，默认）；anchor=Word 原生 w:hyperlink w:anchor")
    ap.add_argument("--report", default="")
    a = ap.parse_args()
    fields = (a.style == "field")
    out = a.out or os.path.splitext(a.src)[0] + "_可跳转.docx"

    d = docx.Document(a.src)
    toc, body = [], []
    for p in d.paragraphs:
        t = (p.text or "").strip()
        m = TOC_RE.match(t)
        if m:
            unwrap_hyperlinks(p)          # 允许对已处理过的文件重跑
            toc.append((p, m.group("title")))
            continue
        mb = BODY_RE.match(t)
        if mb:
            body.append((p, mb.group("title")))

    pdf = a.pdf or render_pdf(a.src, os.path.join(os.path.dirname(out) or ".", "_toc_tmp"))
    texts, feet, first_body = page_numbers(pdf) if pdf else ([], [], 1)

    log, used = [], set()
    for n, (par, toc_title) in enumerate(toc, 1):
        best, score = None, 0.0
        for bp, btitle in body:
            if id(bp) in used:
                continue
            s = similar(toc_title, btitle)
            if s > score:
                best, score = (bp, btitle), s
        if best is None or score < 0.5:
            log.append(("未匹配", toc_title, "", "", score))
            continue
        bp, btitle = best
        used.add(id(bp))
        anchor = "toc_%02d" % n
        add_bookmark(bp, anchor, 1000 + n)
        if fields:
            runs, page_els = split_runs(par)
        else:
            runs, page_els = split_runs(par)
        if runs:
            if fields:
                wrap_hyperlink_field(par, runs, anchor)
            else:
                wrap_hyperlink(par, runs, anchor)
        note = ""
        if texts and page_els:
            key = norm(btitle)[:16]
            hit = next((i for i in range(first_body - 1, len(texts)) if key and key in texts[i]), None)
            if hit is not None:
                real = feet[hit] or (hit + 1)
                old = page_text(page_els)
                if old.strip() != str(real):
                    set_page_text(page_els, real)
                    note = "页码 %s→%s" % (old.strip(), real)
        log.append(("已加链接", toc_title, btitle, note, score))

    d.save(out)
    ok = sum(1 for r in log if r[0] == "已加链接")
    print("目录 %d 条，加链接 %d 条 → %s" % (len(toc), ok, out))
    for row in log:
        print("  [%s] %s ←→ %s %s（%.2f）" % row)
    if a.report:
        with open(a.report, "w", encoding="utf-8") as f:
            f.write("# 目录跳转链接\n\n- 输入：`%s`\n- 输出：`%s`\n- 目录 %d 条，加链接 %d 条\n\n"
                    % (a.src, out, len(toc), ok))
            f.write("| 结果 | 目录条目 | 正文标题 | 页码修正 | 相似度 |\n| --- | --- | --- | --- | --- |\n")
            for row in log:
                f.write("| %s | %s | %s | %s | %.2f |\n" % row)


if __name__ == "__main__":
    main()
