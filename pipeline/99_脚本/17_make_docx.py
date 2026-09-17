# -*- coding: utf-8 -*-
"""生成 Word 版交付件（阅读说明 + 目录 + 参考文档）。

设计基准：
- 阅读说明用 design preset `standard_business_brief`
- 目录与参考资料用 design preset `compact_reference_guide`
- 中文字体为命名覆盖：正文 eastAsia=宋体，标题 eastAsia=微软雅黑（ascii 仍为 Calibri）
- 页面 Letter 纵向 1 英寸页边距；《核实记录》因宽表改用横向（命名覆盖）
"""
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_utils import ROOT  # noqa: E402
from period_config import P  # noqa: E402

import openpyxl  # noqa: E402
from docx import Document  # noqa: E402
from docx.enum.section import WD_ORIENT  # noqa: E402
from docx.enum.table import WD_TABLE_ALIGNMENT  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.oxml import OxmlElement  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Inches, Pt, RGBColor  # noqa: E402

OUT_DIR = os.path.join(ROOT, "Word版")
XLSX = os.path.join(ROOT, "00_资讯目录.xlsx")
# 生成时间：优先取环境变量，与 07 号脚本写的 Markdown 目录保持一致
BUILD_TIME = os.environ.get("CATALOG_BUILD_TIME")
CONTENT_W = 9360  # DXA, 6.5in
BLUE = RGBColor(0x2E, 0x74, 0xB5)
DARK_BLUE = RGBColor(0x1F, 0x4D, 0x78)
INK = RGBColor(0x1F, 0x25, 0x2B)
HEAD_FILL = "E8EEF5"

PRESETS = {
    "brief": {"body": (11, 0, 6, 1.10), "h1": (16, 16, 8), "h2": (13, 12, 6), "h3": (12, 8, 4),
              "bullet": (0.25, 0.5, 8)},
    "guide": {"body": (11, 0, 6, 1.25), "h1": (16, 18, 10), "h2": (13, 14, 7), "h3": (12, 10, 5),
              "bullet": (0.187, 0.375, 4)},
}


def set_cjk(obj, ascii_font="Calibri", east="宋体"):
    rpr = obj._element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.append(fonts)
    fonts.set(qn("w:ascii"), ascii_font)
    fonts.set(qn("w:hAnsi"), ascii_font)
    fonts.set(qn("w:eastAsia"), east)


def style_font(style, ascii_font="Calibri", east="宋体"):
    rpr = style.element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.append(fonts)
    fonts.set(qn("w:ascii"), ascii_font)
    fonts.set(qn("w:hAnsi"), ascii_font)
    fonts.set(qn("w:eastAsia"), east)


def setup_styles(doc, preset):
    p = PRESETS[preset]
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(p["body"][0])
    normal.font.color.rgb = INK
    style_font(normal)
    pf = normal.paragraph_format
    pf.space_before = Pt(p["body"][1])
    pf.space_after = Pt(p["body"][2])
    pf.line_spacing = p["body"][3]
    for name, key, color in (("Heading 1", "h1", BLUE), ("Heading 2", "h2", BLUE),
                             ("Heading 3", "h3", DARK_BLUE)):
        st = doc.styles[name]
        size, before, after = p[key]
        st.font.name = "Calibri"
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = color
        st.font.italic = False
        style_font(st, east="微软雅黑")
        st.paragraph_format.space_before = Pt(before)
        st.paragraph_format.space_after = Pt(after)
        st.paragraph_format.line_spacing = p["body"][3]
        st.paragraph_format.keep_with_next = True
    for name in ("List Bullet", "List Number"):
        st = doc.styles[name]
        st.font.name = "Calibri"
        st.font.size = Pt(p["body"][0])
        style_font(st)
        marker, text_indent, after = p["bullet"]
        st.paragraph_format.left_indent = Inches(text_indent)
        st.paragraph_format.first_line_indent = Inches(-(text_indent - marker))
        st.paragraph_format.space_after = Pt(after)
        st.paragraph_format.line_spacing = p["body"][3]
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(8.5), Inches(11)
    for attr in ("top_margin", "bottom_margin", "left_margin", "right_margin"):
        setattr(sec, attr, Inches(1))
    return doc


def add_hyperlink(paragraph, url, text, size=11):
    part = paragraph.part
    r_id = part.relate_to(url,
                          "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
                          is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), r_id)
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "1F4D78")
    rpr.append(color)
    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")
    rpr.append(u)
    fonts = OxmlElement("w:rFonts")
    fonts.set(qn("w:ascii"), "Calibri")
    fonts.set(qn("w:eastAsia"), "宋体")
    rpr.append(fonts)
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), str(int(size * 2)))
    rpr.append(sz)
    run.append(rpr)
    t = OxmlElement("w:t")
    t.text = text
    run.append(t)
    link.append(run)
    paragraph._p.append(link)
    return paragraph


TOKEN = re.compile(r"(\*\*.+?\*\*|\[[^\]]+\]\([^)]+\)|`[^`]+`)")


def add_runs(paragraph, text, size=11, bold=False):
    for piece in TOKEN.split(text):
        if not piece:
            continue
        if piece.startswith("**") and piece.endswith("**"):
            run = paragraph.add_run(piece[2:-2])
            run.bold = True
        elif piece.startswith("`") and piece.endswith("`"):
            run = paragraph.add_run(piece[1:-1])
            run.font.name = "Consolas"
            set_cjk(run, "Consolas", "宋体")
        elif piece.startswith("[") and "](" in piece:
            label, url = piece[1:-1].split("](", 1)
            add_hyperlink(paragraph, url, label, size=size)
            continue
        else:
            run = paragraph.add_run(piece)
        run.font.size = Pt(size)
        if bold:
            run.bold = True
        set_cjk(run)
    return paragraph


def set_table_geometry(table, widths, indent=120):
    tbl = table._tbl
    tblPr = tbl.tblPr
    for tag in ("w:tblW", "w:tblInd", "w:tblLayout", "w:tblCellMar"):
        el = tblPr.find(qn(tag))
        if el is not None:
            tblPr.remove(el)
    width = OxmlElement("w:tblW")
    width.set(qn("w:w"), str(sum(widths)))
    width.set(qn("w:type"), "dxa")
    tblPr.append(width)
    ind = OxmlElement("w:tblInd")
    ind.set(qn("w:w"), str(indent))
    ind.set(qn("w:type"), "dxa")
    tblPr.append(ind)
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblPr.append(layout)
    mar = OxmlElement("w:tblCellMar")
    for side, val in (("top", 80), ("start", 120), ("bottom", 80), ("end", 120)):
        e = OxmlElement(f"w:{side}")
        e.set(qn("w:w"), str(val))
        e.set(qn("w:type"), "dxa")
        mar.append(e)
    tblPr.append(mar)
    grid = tbl.find(qn("w:tblGrid"))
    if grid is not None:
        tbl.remove(grid)
    grid = OxmlElement("w:tblGrid")
    for w in widths:
        gc = OxmlElement("w:gridCol")
        gc.set(qn("w:w"), str(w))
        grid.append(gc)
    tbl.insert(list(tbl).index(tblPr) + 1, grid)
    for row in table.rows:
        for cell, w in zip(row.cells, widths):
            cell.width = Pt(w / 20.0)
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.LEFT


def shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def repeat_header(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trPr.append(el)


def add_table(doc, headers, rows, widths, size=9.5):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    for i, text in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = ""
        par = cell.paragraphs[0]
        par.paragraph_format.space_after = Pt(2)
        par.paragraph_format.line_spacing = 1.05
        run = par.add_run(text)
        run.bold = True
        run.font.size = Pt(size)
        set_cjk(run, east="微软雅黑")
        shade(cell, HEAD_FILL)
    repeat_header(table.rows[0])
    for row in rows:
        cells = table.add_row().cells
        for i, text in enumerate(row):
            if i >= len(cells):
                break
            cells[i].text = ""
            par = cells[i].paragraphs[0]
            par.paragraph_format.space_after = Pt(2)
            par.paragraph_format.line_spacing = 1.05
            add_runs(par, str(text), size=size)
    set_table_geometry(table, widths)
    return table


def h(doc, text, level=1):
    return doc.add_paragraph(text, style=f"Heading {level}")


def para(doc, text, size=11, after=None):
    p = doc.add_paragraph()
    add_runs(p, text, size=size)
    if after is not None:
        p.paragraph_format.space_after = Pt(after)
    return p


def meta_line(doc, text):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size = Pt(9.5)
    run.font.color.rgb = RGBColor(0x59, 0x59, 0x59)
    set_cjk(run)
    p.paragraph_format.space_after = Pt(10)
    return p


# ---------------- 数据 ----------------

def load_catalog():
    wb = openpyxl.load_workbook(XLSX)
    ws = wb["资讯目录"]
    header = [c.value for c in ws[1]]
    rows = [dict(zip(header, r)) for r in ws.iter_rows(min_row=2, values_only=True)]
    return rows


def stats(rows):
    from collections import Counter
    return {
        "total": len(rows),
        "level": Counter(r["属地层级"] for r in rows),
        "module": Counter(r["板块"] for r in rows),
        "business": Counter(r.get("业务条线") or "未标注" for r in rows),
        "source_type": Counter(r.get("来源类型") for r in rows),
        "province": Counter(r["省份"] for r in rows if r["属地层级"] == "外省"),
        "priority": Counter(r["建议优先级"] for r in rows),
        "verify": Counter(r["核实状态"] for r in rows),
        "sub": Counter(r["子栏"] for r in rows if r["板块"] == "技术应用类"),
        "weekly": sum(1 for r in rows if r["来源载体"] == "周讯转载"),
    }


MODULE_ORDER = ["政策类", "技术应用类", "科技前沿类"]      # 2026-09-17 起取消“媒体动态类”


# ---------------- Word 1：阅读说明 ----------------

def build_reading_guide(rows, st, path):
    doc = Document()
    setup_styles(doc, "brief")
    title = doc.add_paragraph()
    run = title.add_run("《测绘动态资讯目录》阅读说明")
    run.font.size = Pt(20)
    run.font.bold = True
    run.font.color.rgb = INK
    set_cjk(run, east="微软雅黑")
    title.paragraph_format.space_after = Pt(2)
    meta_line(doc, f"{P.title_range} ｜ 共 {st['total']} 条 ｜ "
                   "说明范围：目录 Word 版（01_测绘动态资讯目录.docx）与表格（00_资讯目录.xlsx）")
    para(doc, "本说明只回答两个问题：Word 版目录怎么读、Excel 表格怎么读。两份内容同源，"
              "Word 版适合通读，表格适合筛选与统计，可按场景选用。")

    h(doc, "一、Word 版目录怎么读", 1)
    para(doc, f"目录按 3 个板块顺序排列（政策类、技术应用类、科技前沿类），每个板块标出条数；"
              f"其中“技术应用类”最多（{st['module'].get('技术应用类', 0)} 条），"
              "再按主题分成 6 个子栏，同类内容集中在一起，便于按需跳读。")
    matrix = [[m] + [str(sum(1 for r in rows if r["板块"] == m and r["属地层级"] == lv))
                     for lv in ("部级", "行业与官媒", "外省")]
              + [str(sum(1 for r in rows if r["板块"] == m))] for m in MODULE_ORDER]
    matrix.append(["合计", str(st["level"]["部级"]), str(st["level"]["行业与官媒"]),
                   str(st["level"]["外省"]), str(st["total"])])
    add_table(doc, ["板块", "部级", "行业与官媒", "外省", "合计"], matrix,
              [2600, 1200, 1600, 1200, 1400])
    para(doc, "每条资讯固定三段，读法一致：")
    sample = doc.add_paragraph()
    sample.paragraph_format.space_after = Pt(4)
    run = sample.add_run("12. 【陕西】 陕西测绘地理信息局开展北斗基准站系统巡检")
    run.bold = True
    run.font.size = Pt(11)
    set_cjk(run)
    sample2 = doc.add_paragraph()
    sample2.paragraph_format.space_after = Pt(4)
    run = sample2.add_run("来源：陕西测绘地理信息局")
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0x59, 0x59, 0x59)
    set_cjk(run)
    sample3 = doc.add_paragraph()
    run = sample3.add_run("摘要：数据中心完成2026年度陕西省北斗卫星导航定位基准站系统巡检，"
                          "对基准站设备、网络与数据链路逐项核查，保障全省卫星导航定位服务稳定运行……")
    run.font.size = Pt(10)
    set_cjk(run)
    para(doc, "上例中的标记含义如下：")
    add_table(doc, ["标记", "含义"], [
        ["【省份】", "资讯所属省份；全国性条目标“全国”，外省条目标具体省份"],
        ["来源", "发布单位与载体（主管部门官网／学会协会官网／原发媒体官网／单位官网／白名单公众号）"],
        ["业务条线", "对应本单位 10 条业务线之一，便于按业务汇总"],
        ["正文来源", "官网原文／公众号原文；标“待补”的表示正文不足，汇编成册前需补齐"],
        ["日期", "原文发布日期，用于判断时效"],
        ["层级", "外省／部级／行业与官媒，便于快速判断分量"],
        ["优先级", "A 建议必看（国家层面成果、全国性会议、权威学术与官媒），B 建议看，C 备选"],
        ["山东周讯收录", "是否出现在山东周讯中，可作选题价值的旁证（周讯只作线索，不作来源）"],
        ["核实", "该条通过了几种相互独立的方式核实，三重通过为最高"],
    ], [1500, 7860])
    for text in ("通读时先看模块标题和条目标题，摘要按需再看，不必逐字读完整本；",
                 f"重点关注 A 类条目，本期共 {st['priority']['A']} 条，多为全国性成果与会议；",
                 "需要引用原文时，直接点条目下方链接即可打开。"):
        p = doc.add_paragraph(style="List Bullet")
        add_runs(p, text)

    h(doc, "二、Excel 表格怎么读", 1)
    para(doc, "表格与目录同源，优势是可筛选、可排序、可统计。工作簿含三张工作表：")
    add_table(doc, ["工作表", "内容", "怎么用"], [
        ["资讯目录", f"{st['total']} 条明细，24 个字段，已冻结首行并开启自动筛选",
         "按条件筛出想看的条目，或直接浏览明细"],
        ["统计", "按板块×层级、来源单位、业务条线、来源类型、优先级、省份六个维度统计",
         "想快速看全貌，先看这张表"],
        ["周讯线索池", "山东周讯第82—87期全部 86 条，标注回溯结果",
         "作为下月备选池，也可对照山东的选题眼光"],
    ], [1200, 3960, 4200])
    para(doc, "主表 24 个字段按用途分三类，看的时候不必逐列关注：")
    add_table(doc, ["字段类别", "包含字段", "看什么"], [
        ["定位类", "序号、板块、业务条线、子栏、属地层级、省份", "这篇资讯属于哪个板块、对应哪条业务、哪个省份"],
        ["内容类", "标题、发布单位、来源类型、来源链接、发布日期、版次/公众号发布时间、关键词、摘要、建议优先级", "这篇讲了什么、值不值得看"],
        ["质检类", "是否已被山东周讯收录、核实状态、核实方式、交叉来源链接、备注", "出处是否可靠、能否追溯到原始来源"],
    ], [1200, 4800, 3360])
    para(doc, "四个常用筛选动作：")
    for text in ("按板块看：筛选“板块”列，例如只看“政策类”或“技术应用类”；",
                 "按业务看：筛选“业务条线”列，10 条业务线可直接汇总，例如只看“应急测绘保障”；",
                 "按主题看：筛选“子栏”列，例如“实景三维”可把技术应用类与科技前沿类中的同类内容一次看全；",
                 "按省份看：先筛“属地层级 = 外省”，再看“省份”列，例如只看山东、江苏、浙江；",
                 "按分量看：筛选“建议优先级 = A”，直接看最值得关注的条目。"):
        p = doc.add_paragraph(style="List Bullet")
        add_runs(p, text)
    para(doc, "两份文件内容一致：目录 Word 版用于通读和汇报，表格用于筛选、统计与取用原文链接。")

    doc.save(path)
    return path


# ---------------- Word 2：资讯目录 ----------------

def build_catalog_doc(rows, st, path):
    doc = Document()
    setup_styles(doc, "guide")
    title = doc.add_paragraph()
    run = title.add_run("测绘动态工作（测绘地理信息月刊）")
    run.font.size = Pt(20)
    run.font.bold = True
    run.font.color.rgb = INK
    set_cjk(run, east="微软雅黑")
    title.paragraph_format.space_after = Pt(2)
    # 抬头只保留三条（采集范围／条目总数／生成时间），其余说明见表内字段与阅读说明
    meta_line(doc, f"采集范围：{P.window_text()}")
    meta_line(doc, f"条目总数：{st['total']}")
    meta_line(doc, f"生成时间：{BUILD_TIME or datetime.now().strftime('%Y-%m-%d %H:%M')}")

    for module in MODULE_ORDER:
        sub = [r for r in rows if r["板块"] == module]
        if not sub:
            continue
        h(doc, f"{module}（{len(sub)} 条）", 1)
        # Word 目录同样只按三个板块编排，不设二级分类
        for r in sub:
            add_catalog_item(doc, r)

    doc.save(path)
    return path


def add_catalog_item(doc, r):
    tag = f"【{r.get('省份') or r['属地层级']}】"
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(1)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(f"{r['序号']}. {tag} {r['标题']}")
    run.bold = True
    run.font.size = Pt(11)
    set_cjk(run)
    info = doc.add_paragraph()
    info.paragraph_format.space_after = Pt(1)
    info.paragraph_format.keep_with_next = True
    # 来源行只写来源单位，其余属性保留在 xlsx 字段与统计表中
    add_runs(info, f"来源：{r['发布单位']}", size=9)
    link = doc.add_paragraph()
    link.paragraph_format.space_after = Pt(1)
    link.paragraph_format.keep_with_next = True
    add_hyperlink(link, r["来源链接"], r["来源链接"], size=8.5)
    body = doc.add_paragraph()
    add_runs(body, r.get("摘要") or "", size=10)
    body.paragraph_format.space_after = Pt(4)


def appendix_titles():
    path = os.path.join(ROOT, "06_国家政策文件附录.md")
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path, encoding="utf-8"):
        m = re.match(r"^- \*\*(.+?)\*\*", line.strip())
        if m:
            out.append(m.group(1))
    return out


# ---------------- Markdown → Word（参考资料） ----------------

def abstract_num_for_style(doc, style_name):
    style = doc.styles[style_name]
    numpr = style.element.find(qn("w:pPr"))
    if numpr is None:
        return None
    numpr = numpr.find(qn("w:numPr"))
    if numpr is None:
        return None
    num_id = numpr.find(qn("w:numId")).get(qn("w:val"))
    numbering = doc.part.numbering_part.element
    for num in numbering.findall(qn("w:num")):
        if num.get(qn("w:numId")) == num_id:
            return num.find(qn("w:abstractNumId")).get(qn("w:val"))
    return None


def restart_numbering(doc, style_name="List Number"):
    abstract = abstract_num_for_style(doc, style_name)
    if abstract is None:
        return None
    numbering = doc.part.numbering_part.element
    ids = [int(n.get(qn("w:numId"))) for n in numbering.findall(qn("w:num"))]
    new_id = max(ids) + 1
    num = OxmlElement("w:num")
    num.set(qn("w:numId"), str(new_id))
    num.set(qn("w:abstractNumId"), str(abstract))
    override = OxmlElement("w:lvlOverride")
    override.set(qn("w:ilvl"), "0")
    start = OxmlElement("w:startOverride")
    start.set(qn("w:val"), "1")
    override.append(start)
    num.append(override)
    numbering.append(num)
    return new_id


def apply_num_id(paragraph, num_id):
    pPr = paragraph._p.get_or_add_pPr()
    numPr = OxmlElement("w:numPr")
    ilvl = OxmlElement("w:ilvl")
    ilvl.set(qn("w:val"), "0")
    numPr.append(ilvl)
    numId = OxmlElement("w:numId")
    numId.set(qn("w:val"), str(num_id))
    numPr.append(numId)
    pPr.append(numPr)


def column_widths(header, rows, total_dxa, min_in=0.62, max_weight=34.0):
    """按各列内容平均长度分配列宽，避免等宽导致长文本列挤压、短列浪费。"""
    weights = []
    for idx, name in enumerate(header):
        lengths = [len(name)]
        for row in rows:
            if idx < len(row):
                lengths.append(len(str(row[idx])))
        avg = sum(lengths) / max(1, len(lengths))
        weights.append(max(3.0, min(max_weight, avg)))
    total = sum(weights)
    widths = [max(int(total_dxa * w / total), int(min_in * 1440)) for w in weights]
    scale = total_dxa / sum(widths)
    widths = [int(w * scale) for w in widths]
    widths[-1] = total_dxa - sum(widths[:-1])
    return widths


def md_to_docx(md_path, docx_path, preset="guide", title=None, landscape=False):
    lines = open(md_path, encoding="utf-8").read().split("\n")
    doc = Document()
    setup_styles(doc, preset)
    if landscape:
        sec = doc.sections[0]
        sec.orientation = WD_ORIENT.LANDSCAPE
        sec.page_width, sec.page_height = Inches(11), Inches(8.5)
        sec.left_margin = sec.right_margin = Inches(0.7)
    first = True
    i = 0
    in_code = False
    code_buf = []
    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()
        if line.startswith("```"):
            if in_code:
                for cl in code_buf:
                    p = doc.add_paragraph()
                    run = p.add_run(cl if cl else " ")
                    run.font.name = "Consolas"
                    run.font.size = Pt(9)
                    set_cjk(run, "Consolas", "宋体")
                    p.paragraph_format.space_after = Pt(0)
                    p.paragraph_format.line_spacing = 1.0
                code_buf = []
                in_code = False
            else:
                in_code = True
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue
        if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            header = [c.strip() for c in line.strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            cols = len(header)
            width = (int(6.5 * 1440) if not landscape else int(9.6 * 1440))
            widths = column_widths(header, rows, width)
            add_table(doc, header, rows, widths, size=9 if cols > 4 else 9.5)
            doc.add_paragraph().paragraph_format.space_after = Pt(2)
            continue
        if not line.strip():
            i += 1
            continue
        if line.startswith("# "):
            text = line[2:].strip()
            if first and title is None:
                p = doc.add_paragraph()
                run = p.add_run(text)
                run.font.size = Pt(19)
                run.bold = True
                run.font.color.rgb = INK
                set_cjk(run, east="微软雅黑")
                p.paragraph_format.space_after = Pt(6)
            else:
                h(doc, text, 1)
        elif line.startswith("## "):
            h(doc, line[3:].strip(), 1)
        elif line.startswith("### "):
            h(doc, line[4:].strip(), 2)
        elif line.startswith(">"):
            p = doc.add_paragraph()
            run = p.add_run(line.lstrip("> ").strip())
            run.italic = True
            run.font.size = Pt(9.5)
            run.font.color.rgb = RGBColor(0x59, 0x59, 0x59)
            set_cjk(run)
        elif re.match(r"^\d+\.\s", line):
            if not doc.paragraphs or not getattr(doc, "_num_id", None) or doc._last_was_number is False:
                doc._num_id = restart_numbering(doc)
            p = doc.add_paragraph(style="List Number")
            add_runs(p, re.sub(r"^\d+\.\s", "", line))
            apply_num_id(p, doc._num_id)
            doc._last_was_number = True
        elif line.startswith("- "):
            p = doc.add_paragraph(style="List Bullet")
            add_runs(p, line[2:].strip())
            doc._last_was_number = False
        else:
            p = doc.add_paragraph()
            add_runs(p, line.strip())
            doc._last_was_number = False
        first = False
        i += 1
    doc.save(docx_path)
    return docx_path


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = load_catalog()
    st = stats(rows)
    outputs = []
    jobs = [
        ("00_阅读说明.docx", lambda p: build_reading_guide(rows, st, p)),
        ("01_测绘动态资讯目录.docx", lambda p: build_catalog_doc(rows, st, p)),
        ("02_来源清单与采集方法.docx", lambda p: md_to_docx(
            os.path.join(ROOT, "01_来源清单与采集方法.md"), p)),
        ("03_核实记录.docx", lambda p: md_to_docx(
            os.path.join(ROOT, "04_核实记录.md"), p, landscape=True)),
        ("04_周讯线索池.docx", lambda p: md_to_docx(
            os.path.join(ROOT, "05_周讯线索池.md"), p, landscape=True)),
        ("05_未收录条目备查.docx", lambda p: md_to_docx(
            os.path.join(ROOT, "_备查", "未收录条目.md"), p, landscape=True)),
        ("06_采集口径.docx", lambda p: md_to_docx(
            os.path.join(os.path.dirname(ROOT), "00_测绘动态资讯采集口径.md"), p)),
        ("07_作业流程SOP.docx", lambda p: md_to_docx(
            os.path.join(os.path.dirname(ROOT), "01_作业流程（SOP）.md"), p)),
    ]
    locked = []
    for name, job in jobs:
        path = os.path.join(OUT_DIR, name)
        try:
            outputs.append(job(path))
        except PermissionError:
            locked.append(name)
            print(f"跳过（文件被占用，请关闭后重跑）：{name}")
    for p in outputs:
        print("生成", p, os.path.getsize(p), "字节")
    if locked:
        print("以下文件未更新：" + "、".join(locked))


if __name__ == "__main__":
    main()
