# -*- coding: utf-8 -*-
"""以《政策要情》第一百期为版式基准，生成《测绘动态工作》月刊模板（三栏目 + docx/dotx）。

三栏目：政策法规 / 技术应用类 / 科技前沿类（2026-09-17 起取消“媒体动态类”）。
做法与政策要情模板一致：复制参考件就地改字，不新建样式、不动页面设置。
文章样例：政策法规用公文式，技术应用类用报道式，科技前沿类用案例式（均为参考件自带版式）。
"""
import copy
import os
import shutil
import zipfile

import docx
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BASE = os.path.dirname(os.path.abspath(__file__))          # 编制排版目录
# 参考件：默认取同目录的《政策要情》出版物；可用 CEHUI_TEMPLATE_REF 指定其它参考件
REF = os.environ.get("CEHUI_TEMPLATE_REF") or os.path.join(BASE, "政策要情第一百期8月30日.docx")
OUT_DOCX = os.path.join(BASE, "测绘动态月刊_模板.docx")
OUT_DOTX = os.path.join(BASE, "测绘动态月刊_模板.dotx")
# 允许外部指定输出（正式文件被 WPS/Word 占用时可先写到临时文件）
OUT_DOCX = os.environ.get("CEHUI_TEMPLATE_OUT") or OUT_DOCX
OUT_DOTX = os.environ.get("CEHUI_TEMPLATE_DOTX") or OUT_DOTX

BOARDS = ["政策法规", "技术应用类", "科技前沿类"]
# 封面红字刊名（沿用《政策要情》版式：方正小标宋简体、36pt、C00000）
COVER_TITLE = "测绘地理信息月刊"


def is_drawing_run(run):
    """判断 run 里是否带图形（文本框/线条等）——替换文字时不能删掉它。"""
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


def set_cover_title(doc, text):
    """把封面刊名文本框的文字换成刊名（保留《政策要情》原有的红字文本框版式）。"""
    for txbx in doc.element.body.iter(qn("w:txbxContent")):
        for par in txbx.iter(qn("w:p")):
            runs = par.findall(qn("w:r"))
            if not runs:
                continue
            for extra in runs[1:]:
                par.remove(extra)
            for t in runs[0].iter(qn("w:t")):
                t.text = text
                return True
    return False


def set_catalog_entry(par, no, title="【条目标题】", page="【页码】"):
    runs = par.runs
    if not runs:
        par.add_run(f"{no}.{title}\t{page}")
        return
    runs[0].text = f"{no}.{title}"
    for r in runs[1:-1]:
        r.text = ""
    runs[-1].text = f"\t{page}"


def is_centered(par):
    return par.alignment is not None and int(par.alignment) == 1


# ---------------- 正文三级格式（与《政策要情》第 100 期一致） ----------------
# 一级标题：黑体 小四（12pt）不加粗；二级标题：楷体_GB2312 小四 加粗；
# 正文小标题：仿宋_GB2312 小四 加粗（仅“标签：”部分加粗）；正文：仿宋_GB2312 小四。
LEVEL_FORMATS = {
    "h1": ("黑体", 12, False, 304800),
    "h2": ("楷体_GB2312", 12, True, 306070),
    "h3": ("仿宋_GB2312", 12, True, 306070),
    "body": ("仿宋_GB2312", 12, False, 304800),
    "source": ("楷体_GB2312", 12, False, None),      # 来源行／原文链接行
}


def set_level_format(par, level, label=None, rest=None):
    """把段落设置成指定级别的字体/字号/加粗与首行缩进；h3 可拆成“加粗标签＋正文”。"""
    east, size_pt, bold, indent = LEVEL_FORMATS[level]
    if label is None:
        set_text(par, par.text)
        style_run(par.runs[0], east, size_pt, bold)
    else:
        set_text(par, label)
        style_run(par.runs[0], east, size_pt, True)
        if rest:
            style_run(par.add_run(rest), east, size_pt, None)
    if indent:
        par.paragraph_format.first_line_indent = indent
    else:
        par.paragraph_format.first_line_indent = None
    # 段落标记的字体也同步，避免段落属性与本段字体不一致（WPS 里看段落字体时更直观）
    pPr = par._p.get_or_add_pPr()
    p_rPr = pPr.find(qn("w:rPr"))
    if p_rPr is None:
        p_rPr = OxmlElement("w:rPr")
        pPr.append(p_rPr)
    p_fonts = p_rPr.find(qn("w:rFonts"))
    if p_fonts is None:
        p_fonts = OxmlElement("w:rFonts")
        p_rPr.insert(0, p_fonts)
    p_fonts.set(qn("w:eastAsia"), east)
    return par


def style_run(run, east, size_pt=12, bold=None):
    """设置 run 的中文字体（ascii 交给 _set_latin_font 统一成 Times New Roman）。"""
    from docx.shared import Pt
    rpr = run._element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.insert(0, fonts)
    fonts.set(qn("w:eastAsia"), east)
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    return run


def is_hei(par):
    return bool(par.runs) and (par.runs[0].font.name or "").startswith("黑体")


def make_dotx(docx_path, dotx_path):
    """把 docx 转成 Word 模板格式：仅改主文档部件的内容类型声明。"""
    CT = "[Content_Types].xml"
    OLD = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
    NEW = "application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml"
    with zipfile.ZipFile(docx_path) as zin, zipfile.ZipFile(dotx_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == CT:
                data = data.decode("utf-8").replace(OLD, NEW).encode("utf-8")
            zout.writestr(item, data)


def main():
    shutil.copyfile(REF, OUT_DOCX)
    d = docx.Document(OUT_DOCX)
    P = d.paragraphs

    # ---------- 节1：刊头（红字刊名文本框 + 期号行）+ 三栏目目录 ----------
    # keep_drawing=True：不能删掉期号行里的刊名文本框（原《政策要情》红字刊名）
    set_text(P[0], "【20XX年X月X日】　　　【第XXX期】　　　【编制单位】", keep_drawing=True)
    if not set_cover_title(d, COVER_TITLE):
        print("  ! 未找到封面刊名文本框，请检查参考件版式")
    blocks = [(2, 3), (9, 10), (16, 17)]          # (栏目名段落, 首条目录段落)
    for idx, (name_i, first_i) in enumerate(blocks):
        set_text(P[name_i], f"{'一二三四五六七八九十'[idx]}、{BOARDS[idx]}")
        for k in range(5):
            set_catalog_entry(P[first_i + k], k + 1)
    # 三栏目：不再克隆第 4 个栏目块（原“媒体动态类”已取消）
    # ---------- 节2：政策法规（样例与成刊结构一致：标题→来源行→正文→三级标题→原文链接）----------
    set_text(P[24], "【省份】XX省印发《XX省基础测绘管理办法》")
    set_text(P[26], "来源：XX省自然资源厅")
    set_level_format(P[26], "source")
    set_text(P[28], "为规范基础测绘活动、健全测绘基准服务，XX省人民政府近日印发本省基础测绘管理办法，"
                    "自 20XX 年 X 月 X 日起施行。")
    set_level_format(P[28], "body")
    set_text(P[29], "一、总体要求")
    set_level_format(P[29], "h1")
    set_text(P[30], "明确基础测绘为经济建设、国防建设、社会发展和生态文明建设服务，落实测绘基准统一监管。")
    set_level_format(P[30], "body")
    set_text(P[31], "（一）主要任务")
    set_level_format(P[31], "h2")
    # 正文小标题示例：仅“标签：”部分加粗（与《政策要情》一致）
    set_level_format(P[32], "h3", label="1.建设要求：",
                     rest="统筹全省测绘基准建设与维护，推进卫星导航定位基准站“一张网”服务。")
    set_text(P[33], "原文链接：https://example.com/gnss-act")
    set_level_format(P[33], "source")

    # ---------- 节3：技术应用类（报道式样例）----------
    set_text(P[379], "【省份】XX省以实景三维赋能城市治理")
    set_text(P[380], "来源：XX省自然资源厅")
    set_level_format(P[380], "source")
    set_text(P[382], "XX省依托实景三维数据底座搭建城市运行“一张图”，项目审批、耕地保护等场景实现在线协同。")
    set_level_format(P[382], "body")
    set_text(P[383], "一、应用场景")
    set_level_format(P[383], "h1")
    set_text(P[384], "（一）项目审批")
    set_level_format(P[384], "h2")
    set_level_format(P[385], "h3", label="1.办理成效：",
                     rest="审批环节压减 8 个、申报材料减少 5 项，办理时限缩短三成。")
    set_text(P[386], "原文链接：https://example.com/real-3d")
    set_level_format(P[386], "source")
    for i in range(387, 392):            # 其余留作空行（与成刊“条间空行”一致）
        set_text(P[i], "")

    # ---------- 节4：科技前沿类（案例式样例）----------
    set_text(P[577], "【省份】XX省发布遥感影像智能解译大模型")
    style_run(P[577].runs[0], "方正小标宋简体", 16)      # 与其它栏目标题同号（成刊统一 16pt）
    set_text(P[578], "来源：XX省测绘科学技术研究院")
    set_level_format(P[578], "source")
    set_text(P[579], "一、技术路径")
    set_level_format(P[579], "h1")
    set_text(P[580], "大模型面向耕地“非农化”“非粮化”监测，实现卫星影像自动解译与问题线索提取。")
    set_level_format(P[580], "body")
    set_text(P[581], "（一）模型训练")
    set_level_format(P[581], "h2")
    set_level_format(P[582], "h3", label="1.样本库：",
                     rest="构建 10 万级遥感样本库，主要地物解译准确率达 92%。")
    set_text(P[583], "原文链接：https://example.com/ai-model")
    set_level_format(P[583], "source")
    for i in range(584, 592):
        set_text(P[i], "")

    # ---------- 删除多余内容 ----------
    def drop(start, end, protect=()):
        for i in range(end, start - 1, -1):
            if i in protect:
                continue
            el = P[i]._p
            if el.getparent() is not None:
                el.getparent().remove(el)

    drop(34, 376, protect=(377,))        # 政策法规：第 2 篇起（保留分节符段落）
    drop(25, 25)                         # 样例标题第二行
    drop(8, 8)                           # 目录：栏目一第 6 条
    drop(15, 15)                         # 目录：栏目二第 6 条
    drop(392, 574, protect=(575,))       # 技术应用类：样例之后（保留分节符段落）
    drop(589, 662)                       # 科技前沿类：样例之后

    # ---------- 页眉改为三个板块（栏名 + 上移一空行；字体统一黑体） ----------
    d2 = d
    for si, sec in enumerate(d2.sections):
        if si == 0:
            continue
        hdr = sec.header
        try:
            hdr.is_linked_to_previous = False
        except Exception:
            pass
        if hdr.paragraphs:
            name_par = hdr.paragraphs[0]
            set_text(name_par, BOARDS[si - 1], keep_drawing=True)
            for run in name_par.runs:                      # 页眉中英文统一黑体
                rpr = run._element.get_or_add_rPr()
                fonts = rpr.find(qn("w:rFonts"))
                if fonts is None:
                    fonts = OxmlElement("w:rFonts")
                    rpr.append(fonts)
                for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
                    fonts.set(qn(attr), "黑体")
            # 栏名前加一个同为“底边框+居中”的空段落，使页眉整体下移一行（与领导确认版一致）
            blank_el = copy.deepcopy(name_par._p)
            set_text(docx.text.paragraph.Paragraph(blank_el, name_par._parent), "")
            name_par._p.addprevious(blank_el)

    d2.save(OUT_DOCX)
    make_dotx(OUT_DOCX, OUT_DOTX)
    # 西文与数字统一 Times New Roman（中文东亚字体不变）
    from _set_latin_font import convert_many
    convert_many([OUT_DOCX, OUT_DOTX])
    print("docx:", OUT_DOCX)
    print("dotx:", OUT_DOTX)
    chk = docx.Document(OUT_DOCX)
    print("段落数:", len(chk.paragraphs), "| 节数:", len(chk.sections))
    for si, s in enumerate(chk.sections):
        head = " / ".join(x.text.strip() for x in s.header.paragraphs if x.text.strip())
        print(f"  节{si+1}: 页眉='{head}'")


if __name__ == "__main__":
    main()
