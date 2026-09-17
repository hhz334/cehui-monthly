# -*- coding: utf-8 -*-
"""迭代生成月刊：构建 → 渲染 → 读回页码 → 重写目录，直到页码收敛。"""
import json
import os
import re
import subprocess
import sys

import pdfplumber

BASE = os.path.dirname(os.path.abspath(__file__))          # 编制排版目录
PY = os.environ.get("CEHUI_PYTHON") or sys.executable
# 渲染器（documents 技能自带 render_docx.py）；可用 CEHUI_DOCS_SKILL 覆盖
def _find_render_docx():
    import glob
    root = os.environ.get("CEHUI_DOCS_SKILL") or os.path.join(
        os.path.expanduser("~"), ".codex", "plugins", "cache", "openai-primary-runtime", "documents")
    hits = sorted(glob.glob(os.path.join(root, "*", "skills", "documents", "render_docx.py")))
    return hits[-1] if hits else os.path.join(root, "render_docx.py")
TOOL_ROOT = os.environ.get("CEHUI_TOOL_ROOT") or os.path.dirname(BASE)
sys.path.insert(0, os.path.join(TOOL_ROOT, "99_脚本"))
from period_config import P  # noqa: E402

BUILDER = os.path.join(BASE, "_build_monthly_issue.py")
WORK_DOCX = os.path.join(BASE, "_tmpl_tmp", "issue_work.docx")      # 迭代期间的工作副本
# 正式文件名按期号生成；-Forward 干跑时用 ISSUE_FINAL 指定临时路径
FINAL_DOCX = os.environ.get("ISSUE_FINAL") or os.path.join(BASE, P.issue_file_stem + ".docx")
DOCX = WORK_DOCX
TOC = os.path.join(BASE, "_tmpl_tmp", "toc_pages.json")
WORK = os.path.join(BASE, "_tmpl_tmp", "issue-iter")
SEL = os.path.join(P.sel_dir, "catalog_selection_final.json")
ITEMS = json.load(open(SEL, encoding="utf-8"))
os.makedirs(os.path.dirname(WORK_DOCX), exist_ok=True)     # _tmpl_tmp
os.makedirs(WORK, exist_ok=True)


def build():
    env = dict(os.environ)
    env["ISSUE_OUT"] = WORK_DOCX
    subprocess.run([PY, BUILDER], check=True, capture_output=True, env=env)


def render(tag):
    out = os.path.join(WORK, tag)
    os.makedirs(out, exist_ok=True)
    env = dict(os.environ)
    env["PATH"] = os.environ.get("CEHUI_SOFFICE_DIR", r"C:\Program Files\LibreOffice\program") + ";" + env.get("PATH", "")
    subprocess.run([PY, _find_render_docx(), DOCX,
                    "--output_dir", out, "--emit_pdf"],
                   check=True, capture_output=True, env=env)
    return os.path.join(out, os.path.basename(DOCX).replace(".docx", ".pdf"))


def mapping(pdf):
    with pdfplumber.open(pdf) as doc:
        pages = [re.sub(r"\s+", "", pg.extract_text() or "") for pg in doc.pages]
    first_body = next((i for i, t in enumerate(pages, 1) if "来源：" in t), 1)
    m = {}
    for s in ITEMS:
        key = re.sub(r"\s+", "", s["title"])[:16]
        for pi in range(first_body, len(pages) + 1):
            if key and key in pages[pi - 1]:
                m[s["title"]] = pi
                break
    return m, len(pages), first_body - 1


def main():
    prev = json.load(open(TOC, encoding="utf-8")) if os.path.exists(TOC) else {}
    for it in range(1, 6):
        build()
        pdf = render("iter%d" % it)
        m, total, toc_pages = mapping(pdf)
        same = (m == prev)
        print("第%d轮：总页数 %d｜目录 %d 页｜定位 %d/%d｜与上轮页码%s"
              % (it, total, toc_pages, len(m), len(ITEMS), "一致" if same else "不一致"))
        json.dump(m, open(TOC, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if same:
            print("页码已收敛")
            return deliver()
        prev = m
    print("未在 5 轮内收敛")
    return 1


def deliver():
    """把工作副本落到正式文件名；若被 Word/WPS 占用则另存为"全文版"。"""
    import shutil
    try:
        shutil.copyfile(WORK_DOCX, FINAL_DOCX)
        print("正式文件已更新：", FINAL_DOCX)
    except PermissionError:
        alt = os.path.join(os.path.dirname(FINAL_DOCX), P.issue_file_stem + "_全文版.docx")
        shutil.copyfile(WORK_DOCX, alt)
        print("正式文件被占用（正打开），已另存：", alt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
