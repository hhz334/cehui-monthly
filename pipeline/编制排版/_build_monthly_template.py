# -*- coding: utf-8 -*-
"""以《政策要情》第一百期为版式基准，生成《测绘动态工作》月刊模板（三栏目 + docx/dotx）。

三栏目：政策类 / 技术应用类 / 科技前沿类（2026-09-17 起取消“媒体动态类”）。
做法与政策要情模板一致：复制参考件就地改字，不新建样式、不动页面设置。
文章样例：政策类用公文式，技术应用类用报道式，科技前沿类用案例式（均为参考件自带版式）。
"""
import copy
import os
import shutil
import zipfile

import docx
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BASE = r"<工作根 ToolRoot>\编制排版"
REF = os.path.join(BASE, "政策要情第一百期8月30日.docx")
OUT_DOCX = os.path.join(BASE, "测绘动态月刊_模板.docx")
OUT_DOTX = os.path.join(BASE, "测绘动态月刊_模板.dotx")

BOARDS = ["政策类", "技术应用类", "科技前沿类"]
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
    # ---------- 节2：政策类（公文式样例）----------
    set_text(P[24], "【单位：文件标题】")
    set_text(P[26], "【发文字号】")
    set_text(P[28], "【主送单位：】")
    set_text(P[29], "【正文段落：说明发文背景、依据与目的。】")
    set_text(P[30], "一、【小标题】")
    set_text(P[31], "【正文段落。】")
    set_text(P[32], "二、【小标题】")
    set_text(P[33], "【正文段落。】")
    sign_unit = copy.deepcopy(P[60]._p)
    sign_date = copy.deepcopy(P[61]._p)
    P[33]._p.addnext(sign_date)
    P[33]._p.addnext(sign_unit)
    for el, text in ((sign_unit, "【发文单位】    "), (sign_date, "【20XX年X月X日】    ")):
        set_text(docx.text.paragraph.Paragraph(el, P[33]._parent), text)

    # ---------- 节3：技术应用类（报道式样例）----------
    set_text(P[379], "【报道标题】")
    sub_no, body_no, first_body = 0, 0, True
    for i in range(380, 392):
        if not (P[i].text or "").strip():
            continue
        if is_centered(P[i]) or is_hei(P[i]):
            sub_no += 1
            set_text(P[i], "【小标题】" if sub_no <= 1 else "")
        else:
            body_no += 1
            set_text(P[i], "【导语：交代事件、时间、地点与主体。】" if first_body
                     else ("【正文段落。】" if body_no <= 3 else ""))
            first_body = False
    section3_sample = [P[i]._p for i in (379, 380, 381, 382, 383)]   # 标题+小标题+导语+正文

    # ---------- 节4：科技前沿类（案例式样例）----------
    set_text(P[577], "【案例标题】")
    set_text(P[578], "【副标题（可留空）】")
    sub_no = 0
    for i in range(579, 592):
        if not (P[i].text or "").strip():
            continue
        if is_hei(P[i]):
            sub_no += 1
            set_text(P[i], f"{'一二三四五六七八九十'[sub_no - 1]}、【小标题】")
        elif not is_centered(P[i]):
            set_text(P[i], "【正文段落：做法、成效与评析。】")

    # ---------- 删除多余内容 ----------
    def drop(start, end, protect=()):
        for i in range(end, start - 1, -1):
            if i in protect:
                continue
            el = P[i]._p
            if el.getparent() is not None:
                el.getparent().remove(el)

    drop(34, 376, protect=(377,))        # 政策类：第 2 篇起（保留分节符段落）
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
