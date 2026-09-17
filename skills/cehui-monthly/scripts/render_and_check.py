#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导出月刊 PDF/预览并做版式体检（阶段B 第 3、4 步）。

用法：
    python render_and_check.py "<期次目录>" [--docx <docx路径>] [--outdir <预览目录>] [--no-png]

体检项：条数＝来源行＝原文链接；三栏目；封面红字刊名；页眉位置；无“媒体动态类”；PDF 页数。
任一项不通过时退出码为 1。
"""
import argparse
import glob
import os
import re
import shutil
import subprocess
import sys

TOOL_ROOT = os.environ.get("CEHUI_TOOL_ROOT") or r"<工作根 ToolRoot>"
sys.path.insert(0, os.path.join(TOOL_ROOT, "99_脚本"))
from period_config import P  # noqa: E402

BASE = os.path.join(TOOL_ROOT, "编制排版")
MEDIA_SKILL = r"C:\Users\admin\.codex\plugins\cache\openai-primary-runtime\documents"
BOARDS = ["政策法规", "技术应用类", "科技前沿类"]


def find_render_docx():
    hits = glob.glob(os.path.join(MEDIA_SKILL, "*", "skills", "documents", "render_docx.py"))
    return sorted(hits)[-1] if hits else ""


def find_soffice():
    """定位 LibreOffice：优先常见安装路径，其次 PATH。"""
    for cand in (r"C:\Program Files\LibreOffice\program\soffice.exe",
                 r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
                 "/Applications/LibreOffice.app/Contents/MacOS/soffice",
                 "/usr/bin/soffice", "/usr/local/bin/soffice"):
        if os.path.exists(cand):
            return cand
    return shutil.which("soffice") or ""


def render(docx_path, outdir, want_png=True):
    os.makedirs(outdir, exist_ok=True)
    renderer = find_render_docx()
    env = dict(os.environ)
    soffice = find_soffice()
    env["PATH"] = (os.path.dirname(soffice) + os.pathsep + env.get("PATH", "")) if soffice else env.get("PATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    # 版式体检用“标点压缩”口径渲染（与 Word/WPS 分页一致），否则页数/分页会与成刊 PDF 不同
    try:
        from render_compressed import compressed_pdf
        pdf = compressed_pdf(docx_path, os.path.join(outdir, "_compressed"))
        if pdf:
            target = os.path.join(outdir, os.path.splitext(os.path.basename(docx_path))[0] + ".pdf")
            shutil.copyfile(pdf, target)
            if want_png and renderer:
                subprocess.run([sys.executable, renderer, docx_path, "--output_dir", outdir, "--emit_pdf"],
                               env=env, check=False, capture_output=True)
            return target
    except Exception:  # noqa: BLE001
        pass
    if renderer and want_png:
        # documents 技能渲染器：同时产出 PDF 与逐页 PNG 预览
        subprocess.run([sys.executable, renderer, docx_path, "--output_dir", outdir, "--emit_pdf"],
                       env=env, check=False, capture_output=True)
    else:
        # 只要 PDF（--no-png）或未找到渲染器：直接用 LibreOffice 转换
        if not soffice:
            print("  ! 未找到 LibreOffice（soffice），无法导出 PDF；请安装或把 soffice 加入 PATH")
        else:
            subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", outdir, docx_path],
                           env=env, check=False, capture_output=True)
    pdfs = [p for p in glob.glob(os.path.join(outdir, "*.pdf"))]
    return max(pdfs, key=os.path.getmtime) if pdfs else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("period_dir", nargs="?", default=P.issue_dir)
    ap.add_argument("--docx", default="")
    ap.add_argument("--outdir", default="")
    ap.add_argument("--expect-items", type=int, default=0)
    ap.add_argument("--no-png", action="store_true")
    args = ap.parse_args()

    docx_path = args.docx or os.path.join(BASE, P.issue_file_stem + ".docx")
    outdir = args.outdir or os.path.join(BASE, "月刊预览")
    if not os.path.exists(docx_path):
        print("[FAIL] 找不到成刊文件：%s" % docx_path)
        return 1

    pdf = render(docx_path, outdir, want_png=not args.no_png)
    if not pdf:
        print("[FAIL] 渲染 PDF 失败（检查 LibreOffice 是否可用）")
        return 1
    print("[OK] PDF：%s" % pdf)

    try:
        import pdfplumber
    except ImportError:
        print("[WARN] 未安装 pdfplumber，跳过版式体检")
        return 0

    with pdfplumber.open(pdf) as doc:
        pages = [pg.extract_text() or "" for pg in doc.pages]
        first = doc.pages[0]
        body_page = doc.pages[min(2, len(doc.pages) - 1)]
        red_title = "".join(c["text"] for c in first.chars if (c.get("size") or 0) > 30)
        header = [(round(c["top"]), c["text"]) for c in body_page.chars if c["top"] < 80]
        header_line = [round(l["top"], 1) for l in body_page.lines if l["top"] < 95]
        page_count = len(doc.pages)
        # 空白页：去掉页眉（栏目名）与页脚（— N —）后页面没有内容
        blank_pages = []
        for i, pg in enumerate(doc.pages, 1):
            t = re.sub(r"\s+", "", pg.extract_text() or "")
            t = re.sub(r"—\d+—", "", t)
            for b in BOARDS:
                if t.startswith(b):
                    t = t[len(b):]
                    break
            if not t:
                blank_pages.append(i)

    text = re.sub(r"\s+", "", "".join(pages))
    n_src = text.count("来源：")
    n_link = text.count("原文链接：")
    want_link = 1 if os.environ.get("CEHUI_SOURCE_LINK", "").strip().lower() in ("1", "true", "yes", "on") else 0
    checks = []
    checks.append(("页数>0", page_count > 0, "%d 页" % page_count))
    checks.append(("三栏目齐全", all(b in text for b in BOARDS), "、".join(b for b in BOARDS if b in text)))
    checks.append(("无“媒体动态类”", "媒体动态类" not in text, "0 处" if "媒体动态类" not in text else "仍出现"))
    if want_link:
        checks.append(("来源行＝原文链接", n_src == n_link and n_src > 0, "%d / %d" % (n_src, n_link)))
    else:
        checks.append(("正文不排原文链接（固定规则）", n_link == 0,
                       "原文链接 %d 行（设 CEHUI_SOURCE_LINK=1 可改回排印）" % n_link))
    if args.expect_items:
        checks.append(("条数符合预期", n_src == args.expect_items,
                       "期望 %d，实际 %d" % (args.expect_items, n_src)))
    checks.append(("封面红字刊名", "测绘地理信息月刊" in red_title, red_title or "未见大字号刊名"))
    checks.append(("正文页眉就位", bool(header) and bool(header_line),
                   "栏名 top=%s｜线 %s" % (header[0][0] if header else "-", header_line[:2])))
    checks.append(("无空白页", not blank_pages,
                   "空白页 %s" % (blank_pages if blank_pages else "0 个")))

    ok = True
    for name, passed, detail in checks:
        print("  %s %s（%s）" % ("✓" if passed else "✗", name, detail))
        ok = ok and passed
    print("[%s] 版式体检：%d 项，%d 项不通过" % ("PASS" if ok else "FAIL", len(checks), sum(1 for _, p, _ in checks if not p)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
