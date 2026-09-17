# -*- coding: utf-8 -*-
"""把周讯 OCR 文本整理成条目表：栏目 / 条目标题 / 来源。"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_utils import ROOT, ensure_dir, load_json, save_json  # noqa: E402

WEEKLY_DIR = os.path.join(ROOT, "03_参考_山东周讯")
SECTIONS = ["省情动态", "测绘天地", "国际视野", "专家论坛", "专家论首", "政策法规",
            "他山之石", "科技前沿", "技术应用"]


def clean(line):
    line = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", line)
    return re.sub(r"\s+", " ", line).strip()


def fix_text(text):
    """修正常见 OCR 误识。"""
    rep = {
        "计自然网站": "i自然网站", "站自然网站": "i自然网站", "1 自然网站": "i自然网站",
        "《来源": "来源", "《 来源": "来源", "来源 :": "来源:", "来源；": "来源:",
        "白然资源部": "自然资源部", "于感": "遥感", "咏控": "防控", "局动": "启动",
        "寺感": "遥感", "知能网联": "智能网联", "机明": "机遇", "收宦": "收官",
        "湖水的安全线": "防溺水安全线", "亮权人企": "亮码入企", "桥盖": "覆盖",
        "爹面推进": "全面推进", "癸究院": "研究院", "解详": "解译", "贾及": "贾丹",
        "囊荣才": "龚荣才", "雇眼": "慧眼", "涅源县": "湟源县", "下感学会": "遥感学会",
        "1S 条": "15条",
    }
    for k, v in rep.items():
        text = text.replace(k, v)
    text = re.sub(r"\s*[.…]{2,}\s*$", "", text)
    text = re.sub(r"\s*[a-zA-Z]{2,}\s*$", "", text)
    text = re.sub(r"\s*\d{1,2}\s*$", "", text)
    return text.strip(" .·…")


def parse_issue(issue_dir):
    pages = sorted(f for f in os.listdir(issue_dir) if f.endswith(".txt"))
    section, items, cur = "", [], None
    for idx, name in enumerate(pages, 1):
        text = open(os.path.join(issue_dir, name), encoding="utf-8").read()
        for raw in text.split("\n"):
            line = clean(raw)
            if not line:
                continue
            for sec in SECTIONS:
                if line.replace(" ", "") == sec:
                    section = sec
            m = re.match(r"^(\d{1,2})[.、]\s*(.{6,80})$", line)
            if m and not re.match(r"^\d+[.、]\s*\d", line):
                if cur:
                    items.append(cur)
                title = fix_text(m.group(2))
                cur = {"no": int(m.group(1)), "title": title, "source": "", "section": section,
                       "page": idx}
                continue
            if cur and ("来源" in line):
                src = re.sub(r"^[（(]?\s*来源\s*[:：;，,]?\s*", "", line).strip("（）() ")
                src = re.sub(r"[）)]$", "", src).strip()
                if src and not cur["source"]:
                    cur["source"] = fix_text(src)
    if cur:
        items.append(cur)
    # 只保留正文条目（有栏目或有来源），并按标题去重
    keep, seen, seen_no = [], set(), set()
    for it in items:
        if not (it["section"] or it["source"]):
            continue
        key = re.sub(r"[\s\W_]+", "", it["title"])[:20]
        if key in seen or it["no"] in seen_no:
            continue
        seen.add(key)
        seen_no.add(it["no"])
        keep.append(it)
    return keep


def main():
    all_items, lines = [], ["# 山东《测绘地理信息周讯》82-87 期条目提取", "",
                            "> 由整期长图中文 OCR 提取，个别字词可能存在识别误差，已尽量按上下文校正。", ""]
    metas = {m["issue"]: m for m in load_json(os.path.join(WEEKLY_DIR, "周讯元数据.json"))}
    for issue in sorted(metas):
        issue_dir = os.path.join(WEEKLY_DIR, f"第{issue:03d}期")
        if not os.path.isdir(issue_dir):
            continue
        items = parse_issue(issue_dir)
        for it in items:
            it["issue"] = issue
            all_items.append(it)
        meta = metas[issue]
        lines += [f"## 第{issue}期（发布 {meta['publish']}）", "",
                  f"- 原文：{meta['url']}",
                  f"- 整期长图：{len(meta['images'])} 页", "",
                  "| # | 栏目 | 标题 | 来源标注 | 页码 |", "| --- | --- | --- | --- | --- |"]
        for it in items:
            lines.append(f"| {it['no']} | {it['section'] or '—'} | {it['title']} | "
                         f"{it['source'] or 'OCR未识别'} | p{it['page']} |")
        lines.append("")
    save_json(os.path.join(WEEKLY_DIR, "周讯条目提取.json"), all_items)
    with open(os.path.join(WEEKLY_DIR, "周讯条目提取.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("条目数：", len(all_items))
    for it in all_items:
        print(f"{it['issue']}\t{it['no']}\t{it['section']}\t{it['title'][:44]}\t{it['source'][:24]}")


if __name__ == "__main__":
    main()
