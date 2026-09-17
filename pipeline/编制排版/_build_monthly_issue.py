# -*- coding: utf-8 -*-
"""用月刊模板与资讯目录生成《测绘动态工作（测绘地理信息月刊）》第一期。

版式全部克隆自模板（标题 方正小标宋 / 来源行 楷体 / 正文 仿宋首行缩进），只填内容。
目录页码由第二轮写入：第一轮生成后渲染 PDF，按条目标题定位页码，再重跑本脚本填页码。
"""
import copy
import json
import os
import re
import sys

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH

BASE = os.path.dirname(os.path.abspath(__file__))
TOOL_ROOT = os.environ.get("CEHUI_TOOL_ROOT") or os.path.dirname(BASE)
sys.path.insert(0, os.path.join(TOOL_ROOT, "99_脚本"))
from period_config import P  # noqa: E402

TPL = os.path.join(BASE, "测绘动态月刊_模板.docx")
# 允许指定其它模板（例如先用临时模板试排）
TPL = os.environ.get("CEHUI_TEMPLATE") or TPL
ISSUE_DIR = P.issue_dir
SEL = os.path.join(P.sel_dir, "catalog_selection_final.json")
TOC_MAP = os.path.join(BASE, "_tmpl_tmp", "toc_pages.json")
# 允许外部指定输出（迭代时写工作副本，避免用户正打开正式文件导致写入失败）
OUT = os.environ.get("ISSUE_OUT") or os.path.join(BASE, P.issue_file_stem + ".docx")
os.makedirs(os.path.dirname(OUT) or BASE, exist_ok=True)   # 全新环境下没有 _tmpl_tmp 时自动创建

BOARDS = ["政策类", "技术应用类", "科技前沿类"]      # 2026-09-17 起取消“媒体动态类”，改为三栏目
# 正文一律用全文：02_原文 归档与选目里的"原文正文"本就是原发布方全文，
# 此前 1500 字的节选是排版时人为截断，现取消。
CAP = None
PUBLICATION = "测绘动态工作（测绘地理信息月刊）"


def is_drawing_run(run):
    """判断 run 里是否带图形（封面红字刊名文本框等）——替换文字时不能删掉它。"""
    el = run._element
    if el.find(qn("w:drawing")) is not None or el.find(qn("w:pict")) is not None:
        return True
    MC_ALT = "{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent"
    return el.find(MC_ALT) is not None


def set_text(par, text, keep_drawing=False):
    runs = par.runs
    if not runs:
        par.add_run(text)
        return
    runs[0].text = text
    for r in runs[1:]:
        if keep_drawing and is_drawing_run(r):
            continue
        r._element.getparent().remove(r._element)


def east_font(par):
    """读段落的东亚字体名（run.font.name 读的是西文属性，改过西文字体后不可用）。"""
    pPr = par._p.find(qn("w:pPr"))
    if pPr is not None:
        rPr = pPr.find(qn("w:rPr"))
        if rPr is not None:
            rf = rPr.find(qn("w:rFonts"))
            if rf is not None and rf.get(qn("w:eastAsia")):
                return rf.get(qn("w:eastAsia"))
    r = par.runs[0]._element if par.runs else None
    if r is not None:
        rPr = r.find(qn("w:rPr"))
        if rPr is not None:
            rf = rPr.find(qn("w:rFonts"))
            if rf is not None and rf.get(qn("w:eastAsia")):
                return rf.get(qn("w:eastAsia"))
    return ""


def load_items():
    items = json.load(open(SEL, encoding="utf-8"))
    for it in items:
        it.setdefault("原文正文", it.get("摘要") or "")
    order = {"部级": 0, "行业与官媒": 1, "外省": 2}
    items.sort(key=lambda s: (BOARDS.index(s["board"]), order.get(s.get("level", ""), 9),
                              s.get("date_override") or ""))
    return items


def body_paragraphs(text, hard_cap=800):
    """原文正文的换行即段落边界（抓取时已按块级标签换行），不再合并段落。

    此前为兼容"整篇只有一行"的抓取结果做 ≤500 字合并，会把源文相邻段落并成一段；
    2026-09-17 改为：一行即一段，只有超过 hard_cap 的超长行才按句号断开。
    """
    raw = [t.strip() for t in (text or "").replace("\r", "").split("\n") if t.strip()]
    out = []
    for line in raw:
        if len(line) <= hard_cap:
            out.append(line)
            continue
        buf = ""
        for seg in re.split(r"(?<=[。！？；])", line):
            if buf and len(buf) + len(seg) > hard_cap:
                out.append(buf)
                buf = seg
            else:
                buf += seg
        if buf:
            out.append(buf)
    return out


def main():
    items = load_items()
    toc_pages = json.load(open(TOC_MAP, encoding="utf-8")) if os.path.exists(TOC_MAP) else {}

    d = docx.Document(TPL)
    paras = d.paragraphs

    # ---- 版式样板：按占位符文字与样式定位，避免下标漂移 ----
    def find(pred, label):
        for par in paras:
            if pred(par):
                return par._p
        raise SystemExit(f"未找到版式样板：{label}")

    pat_title = find(lambda p: (p.text or "").strip() in ("【单位：文件标题】", "【文件标题】",
                                                          "【报道标题】", "【案例标题】"),
                     "文章标题")
    # 来源行样板允许几种写法（模板可能被人工改过）；实在没有就退回正文段落样板
    try:
        pat_source = find(lambda p: (p.text or "").strip().startswith(("【发文字号】", "【来源", "来源：")),
                          "来源行")
    except SystemExit:
        pat_source = find(lambda p: (p.text or "").strip().startswith("【正文段落"), "正文段落")
        print("  ! 模板缺少“来源行”样板，已改用正文段落样板")
    pat_body = find(lambda p: (p.text or "").strip().startswith("【正文段落"), "正文段落")

    # ---- 正文三级样板（与《政策要情》一致）：一级黑体小四、二级楷体小四加粗、正文小标题仿宋小四加粗 ----
    def find_opt(token, label):
        try:
            return find(lambda p: token in (p.text or ""), label)
        except SystemExit:
            print("  ! 模板缺少“%s”样板，将沿用正文段落格式" % label)
            return None

    pat_h1 = find_opt("【一级标题】", "一级标题")
    pat_h2 = find_opt("【二级标题】", "二级标题")
    pat_h3 = find_opt("【正文小标题】", "正文小标题")

    # 正文行分级：一、→一级标题；（一）/(一)→二级标题；1./1、→正文小标题；其余为正文
    RE_H1 = re.compile(r"^\s*[一二三四五六七八九十百]+\s*[、.．]")
    RE_H2 = re.compile(r"^\s*[（(]\s*[一二三四五六七八九十百]+\s*[）)]")
    RE_H3 = re.compile(r"^\s*\d{1,2}\s*[、.．]")

    def level_of(line):
        if RE_H1.match(line):
            return "h1"
        if RE_H2.match(line):
            return "h2"
        if RE_H3.match(line):
            return "h3"
        return "body"

    def split_h3(line):
        """正文小标题：把“1.标签：”部分单独拿出来加粗（与《政策要情》一致）。"""
        m = re.match(r"^(.{0,24}?[：:])(.+)$", line)
        return (m.group(1), m.group(2)) if m else ("", line)

    def split_heading(line, max_len=40):
        """标题与正文写在同一段时（如“（一）加快构建国家数字空间基准。一是……”），
        只把到第一个句号为止的标题部分按标题排版，其余按正文排版。"""
        m = re.match(r"^(.{1,%d}?。)(.+)$" % max_len, line)
        return (m.group(1), m.group(2)) if m else (line, "")

    pat_toc = find(lambda p: (p.style.name or "").startswith("WPSOffice手动目录"), "目录条目")
    pat_head = find(lambda p: bool(p.runs) and east_font(p).startswith("黑体")
                    and (p.text or "").strip()[:2] in ("一、", "二、", "三、", "四、"), "栏目名")

    title_p = docx.text.paragraph.Paragraph(pat_title, d)
    source_p = docx.text.paragraph.Paragraph(pat_source, d)
    body_p = docx.text.paragraph.Paragraph(pat_body, d)

    def clone(pattern, text):
        el = copy.deepcopy(pattern)
        par = docx.text.paragraph.Paragraph(el, d)
        set_text(par, text)
        return el

    def clone_keep(pattern, text):
        """标题与来源行加"与下段同页"，避免标题落在页底。"""
        el = clone(pattern, text)
        docx.text.paragraph.Paragraph(el, d).paragraph_format.keep_with_next = True
        return el

    def clone_h3(pattern, label, rest):
        """正文小标题：标签加粗、其后正文不加粗（沿用样板的中文字体与字号）。"""
        el = copy.deepcopy(pattern)
        par = docx.text.paragraph.Paragraph(el, d)
        runs = par.runs
        if not runs:
            par.add_run(label or rest)
            if label and rest:
                par.add_run(rest)
            return el
        runs[0].text = label or rest
        for extra in runs[1:]:
            extra._element.getparent().remove(extra._element)
        if label and rest:
            r2 = copy.deepcopy(runs[0]._element)     # 继承字体与字号
            par._p.append(r2)
            runs2 = docx.text.paragraph.Paragraph(el, d).runs
            runs2[-1].text = rest
            runs2[-1].font.bold = None              # 只有标签部分加粗
        return el

    def clone_heading(pattern, label, rest):
        """一级/二级标题：标题部分沿用标题格式，其后同段的正文用正文格式（仿宋小四不加粗）。"""
        el = copy.deepcopy(pattern)
        par = docx.text.paragraph.Paragraph(el, d)
        set_text(par, label)
        if rest:
            tpl_par = docx.text.paragraph.Paragraph(pat_body, d)
            tpl_rpr = tpl_par.runs[0]._element.find(qn("w:rPr")) if tpl_par.runs else None
            r2 = OxmlElement("w:r")
            if tpl_rpr is not None:
                r2.append(copy.deepcopy(tpl_rpr))     # 采用正文样板的字体/字号/加粗
            t = OxmlElement("w:t")
            t.set(qn("xml:space"), "preserve")
            t.text = rest
            r2.append(t)
            par._p.append(r2)
        return el

    # ---- 定位分节符 ----
    breaks = [p for p in paras
              if p._p.pPr is not None and p._p.pPr.find(qn("w:sectPr")) is not None]
    body = d.element.body
    body_sect = body.find(qn("w:sectPr"))
    print("分节符段落数:", len(breaks))
    assert len(breaks) == 3, f"模板结构异常：分节符段落应为 3 个（三栏目），实际 {len(breaks)}"

    # ---- 清空三个栏目节并填入条目 ----
    sec_bounds = [(breaks[0]._p, breaks[1]._p), (breaks[1]._p, breaks[2]._p),
                  (breaks[2]._p, body_sect)]
    for bi, board in enumerate(BOARDS):
        start, end = sec_bounds[bi]
        # 删除本节原有样例内容（保留终止分节符所在段落）
        el = start.getnext()
        while el is not None and el is not end:
            nxt = el.getnext()
            el.getparent().remove(el)
            el = nxt
        # 生成条目
        block = [s for s in items if s["board"] == board]
        cursor = end
        newelems = []
        first = True
        for s in block:
            title = s["title"]
            prov = s.get("province") or s.get("level") or ""
            prefix = f"【{prov}】" if prov else ""
            if not first:
                newelems.append(clone(pat_body, ""))          # 条间空行
            first = False
            newelems.append(clone_keep(pat_title, f"{prefix}{title}"))
            src = (f"来源：{s.get('unit','')}｜{s.get('source_type','')}｜{s.get('date_override','')}"
                   f"｜业务条线：{s.get('business','')}｜优先级 {s.get('priority','')}")
            src = f"来源：{s.get('unit','')}"      # 只写来源单位，其余信息不入正文
            newelems.append(clone_keep(pat_source, src))
            text = s.get("原文正文") or s.get("摘要") or ""
            truncated = bool(CAP) and len(text) > CAP
            for seg in body_paragraphs(text[:CAP] if truncated else text):
                lvl = level_of(seg)
                if lvl == "h1" and pat_h1:
                    label, rest = split_heading(seg)
                    newelems.append(clone_heading(pat_h1, label, rest))
                elif lvl == "h2" and pat_h2:
                    label, rest = split_heading(seg)
                    newelems.append(clone_heading(pat_h2, label, rest))
                elif lvl == "h3" and pat_h3:
                    label, rest = split_h3(seg)
                    newelems.append(clone_h3(pat_h3, label, rest))
                else:
                    newelems.append(clone(pat_body, seg))
            if truncated:
                newelems.append(clone(pat_body,
                                      f"（节选，全文 {len(text)} 字，见来源链接：{s.get('source_url_checked','')}）"))
            # 文末附原文链接
            link = s.get("source_url_checked") or ""
            if link:
                link_el = clone(pat_source, f"原文链接：{link}")
                docx.text.paragraph.Paragraph(link_el, d).paragraph_format.alignment = \
                    WD_ALIGN_PARAGRAPH.LEFT
                newelems.append(link_el)
        for el in newelems:
            cursor.addprevious(el)
        print(f"  {board}: {len(block)} 条")

    # ---- 目录页：封面红字刊名（模板文本框）+ 期号行 + 三栏目 + 全部条目 ----
    p = d.paragraphs
    # 刊名由模板封面的红字文本框承载（沿用《政策要情》版式），这里只写日期/期号/编制单位行；
    # keep_drawing=True 保证不删掉期号行里的刊名文本框。
    set_text(p[0], P.cover_line(), keep_drawing=True)
    # 清掉模板里的目录占位块
    head_idx = [i for i, par in enumerate(d.paragraphs) if is_heading(par)][:3]
    keep_from = head_idx[0]
    first_break = next(i for i, par in enumerate(d.paragraphs) if has_sectPr(par._p))
    for i in range(first_break - 1, keep_from - 1, -1):      # 只清理第 1 节内的占位目录
        el = d.paragraphs[i]._p
        if el.getparent() is not None and not has_sectPr(el):
            el.getparent().remove(el)
    # 重新生成目录
    cursor = d.paragraphs[keep_from - 1]._p
    for bi, board in enumerate(BOARDS):
        head_el = clone(pat_head, f"{'一二三'[bi]}、{board}")
        cursor.addnext(head_el)
        cursor = head_el
        for n, s in enumerate([s for s in items if s["board"] == board], 1):
            page = toc_pages.get(s["title"], "")
            prov = s.get("province") or s.get("level") or ""
            entry = toc_entry(pat_toc, d, f"{n}.{prov}：{s['title']}", page)
            cursor.addnext(entry)
            cursor = entry

    d.save(OUT)
    print("已生成:", OUT, "| 段落数:", len(docx.Document(OUT).paragraphs))


def has_sectPr(el):
    pPr = el.find(qn("w:pPr"))
    return pPr is not None and pPr.find(qn("w:sectPr")) is not None


def is_heading(par):
    return bool(par.runs) and east_font(par).startswith("黑体") \
        and "、" in (par.text or "")[:3]


def set_toc_page(el, page):
    """目录条目的页码写进最后一个 run（保留制表位）。"""
    par = docx.text.paragraph.Paragraph(el, None)
    runs = par.runs
    if not runs:
        return el
    runs[-1].text = f"\t{page}"
    return el


def toc_entry(pattern_el, doc, text, page):
    """目录条目：首个 run 放"序号.省份：标题"，末个 run 保留制表位并写页码。"""
    el = copy.deepcopy(pattern_el)
    par = docx.text.paragraph.Paragraph(el, doc)
    runs = par.runs
    if not runs:
        par.add_run(text)
        par.add_run(f"\t{page}")
        return el
    runs[0].text = text
    for r in runs[1:-1]:
        r.text = ""
    runs[-1].text = f"\t{page}"
    return el


if __name__ == "__main__":
    main()
