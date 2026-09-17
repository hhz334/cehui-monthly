# -*- coding: utf-8 -*-
"""把工作副本同步到 `_release/cehui-monthly`（GitHub 发布包），并做发布前的必要处理。

一次完成四件事：
1. 复制 `99_脚本`（跳过 `_` 开头的临时脚本）、`编制排版`（只收 .py/.ps1 与模板 docx/dotx）、
   技能的 `SKILL.md`／`references`／`scripts`／`agents`／`assets`、根目录两份口径与流程文档；
2. 删掉误带入的本地成品（政策要情参考件、成刊、探针文档等）；
3. 脱敏绝对路径：`<工作根 ToolRoot>` → `<工作根 ToolRoot>`，技能路径 → `~/.codex/skills/...`；
4. 给 .ps1 补 UTF-8 BOM（Windows PowerShell 5.1 按 ANSI 读无 BOM 脚本会报 ParserError）。

用法：
    python 37_sync_release.py            # 同步
    python 37_sync_release.py --check    # 只报告差异，不写盘
"""
import argparse
import filecmp
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
TOOL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REL = os.path.join(TOOL, "_release", "cehui-monthly")
SKILL_SRC = os.path.join(os.path.expanduser("~"), ".codex", "skills", "cehui-monthly")
RAW = "<工作根 ToolRoot>"
MASK = "<工作根 ToolRoot>"
SKILL_RAW = os.path.join(os.path.expanduser("~"), ".codex", "skills", "cehui-monthly")
SKILL_MASK = "~/.codex/skills/cehui-monthly"
TEXT_EXT = {".py", ".ps1", ".md", ".json", ".js", ".txt", ".yaml", ".yml"}
EXTRA = [
    r"pipeline\编制排版\_build_template.py",
    r"pipeline\编制排版\_probe_split.docx",
    r"pipeline\编制排版\政策要情_模板.docx",
    r"pipeline\编制排版\政策要情第一百期8月30日.docx",
    r"pipeline\编制排版\测绘动态工作_2026年第1期.docx",
    r"pipeline\编制排版\测绘动态月刊_模板_修改.docx",
    r"pipeline\编制排版\测绘地理信息月刊第1期2026年9月15日.docx",
    r"pipeline\编制排版\测绘地理信息月刊第1期2026年9月15日_可跳转版.docx",
    r"pipeline\编制排版\测绘地理信息月刊第1期2026年9月15日_核校版.docx",
    r"pipeline\编制排版\测绘地理信息月刊第1期2026年9月15日_可跳转版.pdf",
    r"pipeline\编制排版\测绘动态工作_2026年第1期.pdf",
]


def sanitize(path):
    if os.path.splitext(path)[1].lower() not in TEXT_EXT:
        return False
    t = open(path, encoding="utf-8").read()
    t2 = (t.replace(RAW.replace("\\", "\\\\"), MASK).replace(RAW, MASK)
           .replace(SKILL_RAW.replace("\\", "\\\\"), SKILL_MASK)
           .replace(SKILL_RAW, SKILL_MASK))
    if path.lower().endswith(".ps1") and t2 and not t2.startswith("\ufeff"):
        t2 = "\ufeff" + t2
    if t2 != t:
        open(path, "w", encoding="utf-8").write(t2)
        return True
    return False


def plan():
    """返回 [(源文件, 发布包目标路径)]。"""
    out = []
    for name in sorted(os.listdir(os.path.join(TOOL, "99_脚本"))):
        if name.startswith("_") or not name.endswith(".py"):
            continue
        out.append((os.path.join(TOOL, "99_脚本", name),
                    os.path.join(REL, "pipeline", "99_脚本", name)))
    for name in sorted(os.listdir(os.path.join(TOOL, "编制排版"))):
        if name.startswith("~$"):
            continue
        is_code = name.endswith((".py", ".ps1"))
        is_tpl = name.startswith("测绘动态月刊_模板") and name.endswith((".docx", ".dotx"))
        if not (is_code or is_tpl):          # 成刊、参考件等本地成品不进发布包
            continue
        out.append((os.path.join(TOOL, "编制排版", name),
                    os.path.join(REL, "pipeline", "编制排版", name)))
    for sub in ("", "references", "scripts", "agents", "assets"):
        src = os.path.join(SKILL_SRC, sub) if sub else SKILL_SRC
        dst = os.path.join(REL, "skills", "cehui-monthly", sub)
        if not os.path.isdir(src):
            continue
        for name in sorted(os.listdir(src)):
            p = os.path.join(src, name)
            if os.path.isfile(p) and os.path.splitext(name)[1].lower() in TEXT_EXT:
                out.append((p, os.path.join(dst, name)))
    for doc in ("00_测绘动态资讯采集口径.md", "01_作业流程（SOP）.md"):
        out.append((os.path.join(TOOL, doc), os.path.join(REL, "docs", doc)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    copied = changed = 0
    for src, dst in plan():
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        same = os.path.exists(dst) and filecmp.cmp(src, dst, shallow=False)
        if same:
            continue
        copied += 1
        print(("差异" if a.check else "同步") + " " + os.path.relpath(dst, REL))
        if not a.check:
            shutil.copy2(src, dst)
            if sanitize(dst):
                changed += 1
    for rel in EXTRA:
        p = os.path.join(REL, rel)
        if os.path.exists(p):
            print(("待删" if a.check else "删除") + " " + rel)
            if not a.check:
                os.remove(p)
    print("同步 %d 个文件（其中 %d 个做了脱敏／BOM 处理）→ %s" % (copied, changed, REL))


if __name__ == "__main__":
    main()
