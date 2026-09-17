# -*- coding: utf-8 -*-
"""成稿后的文本核校：清掉全文的多余空格与特殊空白字符（不动版式）。

处理对象：document.xml 与各 header/footer 里的全部 `w:t` 文本节点（用 lxml 解析，避免改坏 XML）。
处理规则（与 sources_whitelist.normalize_text 同一口径）：

1. 特殊空白字符（\\u200a \\u200b \\u2009 \\u2004–\\u2008 \\ufeff）一律清除；
2. 汉字 ↔ 字母/数字之间的空格清除（“自 2023 年”→“自2023年”、“将 AI深度嵌入”→“将AI深度嵌入”）；
3. 中文标点前后的空格清除（“‘横向到边’ 的”→“‘横向到边’的”）；
4. 不动：行首行尾空格、页脚“— 1 —”的装饰空格、目录行的制表位、
   法条标题（第X章/第X条）、引号内标语（“维护地理信息安全 激发时空数据潜能”）。

用法：
    python 33_fix_docx_text.py <输入.docx> [-o <输出.docx>] [--report x.md] [--dry-run]
"""
import argparse
import os
import re
import sys
import zipfile

from lxml import etree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sources_whitelist as WL  # noqa: E402

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
XMLSPACE = "{http://www.w3.org/XML/1998/namespace}space"
PARTS = re.compile(r"^word/(?:document|header\d*|footer\d*)\.xml$")
SPECIAL = "\u200a\u200b\u200c\u200d\u2009\u2004\u2005\u2006\u2007\u2008\ufeff"


def fix_text(t, is_heading):
    """核对单个文本节点；返回 (新文本, 改动数, [改动说明])。"""
    if not t:
        return t, 0, []
    hits, notes = 0, []
    for ch in SPECIAL:
        if ch in t:
            hits += t.count(ch)
            notes.append("特殊空白 U+%04X" % ord(ch))
            t = t.replace(ch, "")
    if "\xa0" in t:
        hits += t.count("\xa0")
        notes.append("不间断空格 U+00A0→普通空格")
        t = t.replace("\xa0", " ")
    if not is_heading:
        pats = [("汉字与字母/数字之间有空格", r"(?<=[%s])[ \t]+(?=[A-Za-z0-9])" % WL.CJK),
                ("字母/数字与汉字之间有空格", r"(?<=[A-Za-z0-9])[ \t]+(?=[%s])" % WL.CJK),
                ("中文标点前有空格", r"[ \t]+(?=[%s])" % WL.CN_PUNCT_OPEN),
                ("中文标点后有空格", r"(?<=[%s])[ \t]+" % WL.CN_PUNCT_CLOSE)]
        for label, pat in pats:
            t2 = re.sub(pat, "", t)
            if t2 != t:
                hits += 1
                notes.append(label)
                t = t2
        for half, full in ((",", "，"), (";", "；"), ("!", "！"), ("?", "？")):
            t2 = re.sub(r"(?<=[%s])%s(?=[%s])" % (WL.CJK, re.escape(half), WL.CJK), full, t)
            if t2 != t:
                hits += 1
                notes.append("汉字间半角标点 %s→%s" % (half, full))
                t = t2
    return t, hits, notes


def clean_part(xml_bytes, path, changes):
    root = etree.fromstring(xml_bytes)
    total = 0
    for par in root.iter(W + "p"):
        ts = list(par.iter(W + "t"))
        if not ts:
            continue
        is_heading = bool(WL.HEADING_LINE.match("".join(t.text or "" for t in ts).strip()))
        for t in ts:
            old = t.text or ""
            new, k, notes = fix_text(old, is_heading)
            if k and new != old:
                changes.append((path, notes, old, new))
                total += k
                t.text = new
                if new != new.strip():
                    t.set(XMLSPACE, "preserve")
    return (etree.tostring(root, xml_declaration=True, encoding="UTF-8",
                           standalone=True), total)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("-o", "--out", default="")
    ap.add_argument("--report", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    out = a.out or os.path.splitext(a.src)[0] + "_核校版.docx"
    zin = zipfile.ZipFile(a.src)
    changes, total = [], {}
    parts = []
    for it in zin.infolist():
        data = zin.read(it.filename)
        if PARTS.match(it.filename):
            data, k = clean_part(data, it.filename, changes)
            if k:
                total[it.filename] = k
        parts.append((it, data))
    # 只有确实改动了才落盘，避免生成一份内容完全相同的“核校版”副本
    if not a.dry_run and total:
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
            for it, data in parts:
                zout.writestr(it, data)
    for p, notes, old, new in changes:
        print("[%s] %s\n    旧：%s\n    新：%s"
              % (p, "、".join(sorted(set(notes))), old[:80], new[:80]))
    print("命中：" + (", ".join("%s=%d" % kv for kv in total.items()) or "无"))
    if not a.dry_run and total:
        print("输出：%s" % out)
    elif not a.dry_run:
        print("无需核校：未发现多余空格／半角标点，未生成副本")
    if a.report:
        with open(a.report, "w", encoding="utf-8") as f:
            f.write("# 成稿空格核校\n\n")
            f.write("- 输入：`%s`\n- 输出：`%s`\n"
                    % (a.src, "（dry-run）" if a.dry_run else out))
            f.write("- 命中：%s\n\n"
                    % (", ".join("%s=%d" % kv for kv in total.items()) or "无"))
            for p, notes, old, new in changes:
                f.write("- `%s`｜%s\n    - 旧：%s\n    - 新：%s\n"
                        % (p, "、".join(sorted(set(notes))), old[:120], new[:120]))


if __name__ == "__main__":
    main()
