# -*- coding: utf-8 -*-
"""从《测绘地理信息周讯》整期 PDF 的可提取文本中还原条目、栏目与来源。

比长图 OCR 精确（PDF 内含真实文本层），用于生成
`03_参考_山东周讯/周讯条目提取.{md,json}`。
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_utils import ROOT, ensure_dir, save_json  # noqa: E402

import pdfplumber  # noqa: E402

WEEKLY_DIR = os.path.join(ROOT, "03_参考_山东周讯")
ISSUES = [82, 83, 84, 85, 86, 87]
SECTIONS = ["省情动态", "测绘天地", "数字经济·低空经济", "专家论道", "国际视野"]
DOTS = re.compile(r"[.．·]{4,}")
ITEM = re.compile(r"^(\d{1,2})[.、]\s*(.*)$")
SOURCE = re.compile(r"（来源[:：]?\s*([^）]*)）")


def parse_toc(text):
    """解析首页目录，返回 [(序号, 标题, 目录页码, 栏目)]。"""
    items = []
    section = ""
    pending = ""
    started = False
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        if not started:
            if re.match(r"^目\s*录$", line):
                started = True
            continue
        if DOTS.search(line):
            parts = DOTS.split(line)
            head = parts[0].strip()
            page = re.search(r"(\d{1,3})", parts[-1])
            page_no = int(page.group(1)) if page else 0
            m = ITEM.match(head)
            if m:
                title = (pending + m.group(2)).strip() if pending else m.group(2).strip()
                pending = ""
                items.append([int(m.group(1)), title, page_no, section])
            else:
                section = head
                pending = ""
            continue
        m = ITEM.match(line)
        pending = pending + (m.group(2).strip() if m else line)
    return items


def parse_body(pages, toc):
    """按目录序号在正文中定位各条目正文，并抽取“（来源：…）”。"""
    lines = []
    for idx, page in enumerate(pages[1:], start=2):
        for raw in page.split("\n"):
            line = raw.strip()
            if not line or re.fullmatch(r"\d{1,3}", line):
                continue
            lines.append((idx, line))

    section = SECTIONS[0]
    found = {}
    current = None
    expected = [it[0] for it in toc]
    cursor = 0
    for page_no, line in lines:
        if line in SECTIONS:
            section = line
            continue
        m = ITEM.match(line)
        if m and cursor < len(expected) and int(m.group(1)) == expected[cursor]:
            if current:
                found[current[0]] = current[1]
            current = [int(m.group(1)), {"section": section, "page": page_no, "text": [m.group(2).strip()]}]
            cursor += 1
            continue
        if current:
            current[1]["text"].append(line)
    if current:
        found[current[0]] = current[1]
    return found


def build_issue(issue):
    folder = os.path.join(WEEKLY_DIR, f"第{issue:03d}期")
    pdf_path = os.path.join(folder, f"测绘地理信息周讯第{issue:03d}期.pdf")
    with pdfplumber.open(pdf_path) as pdf:
        pages = [(p.extract_text() or "") for p in pdf.pages]
    with open(os.path.join(folder, "全文_pdf.txt"), "w", encoding="utf-8") as fh:
        for i, text in enumerate(pages, start=1):
            fh.write(f"\n===== 第{i}页 =====\n{text.strip()}\n")

    toc = parse_toc(pages[0])
    body = parse_body(pages, toc)
    rows = []
    for no, title, page_no, section in toc:
        info = body.get(no, {})
        text = "\n".join(info.get("text") or [])
        srcs = SOURCE.findall(text)
        rows.append({
            "issue": issue,
            "no": no,
            "section": section or info.get("section", ""),
            "title": title,
            "page": page_no,
            "source": srcs[-1].strip() if srcs else "",
            "body": text,
        })
    return rows, len(pages)


def main():
    all_rows = []
    page_counts = {}
    for issue in ISSUES:
        rows, npages = build_issue(issue)
        page_counts[issue] = npages
        all_rows.extend(rows)
        print(f"第{issue}期：{npages} 页，条目 {len(rows)} 条，其中有来源标注 "
              f"{sum(1 for r in rows if r['source'])} 条")

    save_json(os.path.join(WEEKLY_DIR, "周讯条目提取.json"), all_rows)

    lines = ["# 山东《测绘地理信息周讯》82-87 期条目提取", "",
             "> 由各期整期 PDF 的文本层直接提取（较长图 OCR 精确），个别排版符号已规范化。", ""]
    for issue in ISSUES:
        rows = [r for r in all_rows if r["issue"] == issue]
        lines += [f"## 第{issue}期（PDF {page_counts[issue]} 页，条目 {len(rows)} 条）", "",
                  "| # | 栏目 | 标题 | 来源标注 | 目录页码 |", "| --- | --- | --- | --- | --- |"]
        for r in rows:
            lines.append(f"| {r['no']} | {r['section']} | {r['title']} | "
                         f"{r['source'] or '未标注'} | p{r['page']} |")
        lines.append("")
    with open(os.path.join(WEEKLY_DIR, "周讯条目提取.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"合计条目 {len(all_rows)} 条")


if __name__ == "__main__":
    main()
