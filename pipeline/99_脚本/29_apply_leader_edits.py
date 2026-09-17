# -*- coding: utf-8 -*-
"""把领导批注版（0916.doc）的修订固化成基线：_raw/leader_0916.json + 备查报告。

做四件事：
1. 把二进制 .doc 转成 docx（LibreOffice），解析修订痕迹（w:ins / w:del）；
2. 还原"领导终稿"（保留修订=接受）与"领导批注前版本"（69 条底稿）；
3. 输出终稿条目（含板块、顺序、来源、链接、摘要、是否新增、日期）、删除清单（附原因分类）、新增条目、板块迁移、链接改动；
4. 生成《_备查/领导批注规则（0916）.md》供人工确认。
"""
import json
import argparse
import os
import re
import subprocess
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_utils import RAW, ROOT, ensure_dir, save_json  # noqa: E402
import sources_whitelist as WL  # noqa: E402

from lxml import etree  # noqa: E402

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
# 默认处理 0916 版；可用命令行参数处理后续批注版（如 0917）
DOC = os.path.join(ROOT, "Word版", "01_测绘动态资讯目录0916.doc")
OUT_JSON = os.path.join(RAW, "leader_0916.json")
OUT_MD = os.path.join(ROOT, "_备查", "领导批注规则（0916）.md")
LABEL = "0916"
# 兼容历史批注版：0916 版含“媒体动态类”，0917 版起只有三个板块；
# 这里保留四个名字用于识别不同版本文件里的栏目标题。
BOARDS = ("政策法规", "技术应用类", "科技前沿类", "媒体动态类")

# 删除原因分类（与口径 R1/R2 对齐）
REASONS = [
    ("程序性文件/标准/指南", r"征求意见|申请指南|国家标准|管理办法（试行）|预算|决算"),
    ("宣传科普版图", r"宣传日|版图意识|宣传周|宣传片"),
    ("视频类", r"加速度"),
    ("地市级/县级", r"市局|县局|日照|连云港|大连|宣城|亳州|遂宁|益阳|自贡|市自然资源和规划局"),
    ("培训/讲座/讲堂/竞赛", r"培训|讲座|讲堂|竞赛|练兵|大讲堂|技能"),
    ("会议/论坛/研讨会/交流会", r"研讨会|交流会|论坛|年会|专题会|会议"),
    ("签约/合作/调研交流", r"签约|合作|调研|交流|框架协议|签署"),
    ("验收/预验收/评审", r"验收|评审|评估"),
    ("部属单位内部事务/同类重复（人工准则）", r".*"),
]


def convert_doc(path):
    tmp = os.path.join(RAW, "_doc_cache")
    ensure_dir(tmp)
    out = os.path.join(tmp, os.path.splitext(os.path.basename(path))[0] + ".docx")
    if os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(path):
        return out
    soffice = r"C:\Program Files\LibreOffice\program\soffice.exe"
    subprocess.run([soffice, "--headless", "--norestore", "--convert-to", "docx",
                    "--outdir", tmp, path], check=True, capture_output=True)
    return out


def texts_of(par):
    """(终稿文本, 批注前文本)；w:ins 内为新增，w:delText 为删除。"""
    fin, orig = [], []
    for node in par.iter():
        tag = etree.QName(node).localname
        if tag == "t" and node.text:
            anc, is_ins = node.getparent(), False
            while anc is not None:
                if etree.QName(anc).localname == "ins":
                    is_ins = True
                    break
                anc = anc.getparent()
            fin.append(node.text)
            if not is_ins:
                orig.append(node.text)
        elif tag == "delText" and node.text:
            orig.append(node.text)
    return "".join(fin).strip(), "".join(orig).strip()


def parse_items(lines):
    """解析条目：带序号（N. 【省】标题）与新增（MMDD 标题）两种。"""
    sec, out, cur = None, [], None
    for l in lines:
        if not l:
            continue
        m = re.match(r"^(%s)（\s*\d*\s*条）$" % "|".join(BOARDS + ("政策类", "媒体动态类")), l)
        if m:
            # 只归一“改名”的板块；已取消的“媒体动态类”保留原名（它是该批注版里的真实栏目）
            sec = {"政策类": "政策法规"}.get(m.group(1), m.group(1))
            continue
        m1 = re.match(r"^(\d{1,3})?\.?\s*【(.+?)】\s*(.+)$", l)
        m2 = re.match(r"^(\d{2})(\d{2})\s{1,3}(.+)$", l)
        if m1 or m2:
            if cur:
                out.append(cur)
            if m1:
                cur = {"sec": sec, "no": int(m1.group(1)) if m1.group(1) else None, "prov": m1.group(2),
                       "title": m1.group(3).strip(), "added": False,
                       "src": "", "urls": [], "summary": ""}
            else:
                cur = {"sec": sec, "no": None, "prov": None, "title": m2.group(3).strip(),
                       "added": True, "added_date": "2026-%s-%s" % (m2.group(1), m2.group(2)),
                       "src": "", "urls": [], "summary": ""}
            continue
        if cur is None:
            continue
        if l.startswith("来源："):
            cur["src"] = (cur["src"] + l).strip()
        elif l.startswith("http"):
            cur["urls"].append(l)
        elif len(l) > 20 and not cur["summary"]:
            cur["summary"] = l
    if cur:
        out.append(cur)
    return out


def reason_of(title):
    for name, pat in REASONS:
        if re.search(pat, title):
            return name
    return "其他"


def main():
    ap = argparse.ArgumentParser(description="解析领导批注版（.doc 修订痕迹）")
    ap.add_argument("--doc", default=DOC, help="批注版 .doc 路径")
    ap.add_argument("--label", default=LABEL, help="版本标签，如 0917")
    ap.add_argument("--out-json", default="", help="输出 JSON 路径")
    ap.add_argument("--out-md", default="", help="输出报告路径")
    args = ap.parse_args()
    doc_path = args.doc
    label = args.label
    out_json = args.out_json or os.path.join(RAW, f"leader_{label}.json")
    out_md = args.out_md or os.path.join(ROOT, "_备查", f"领导批注规则（{label}）.md")
    return run(doc_path, label, out_json, out_md)


def run(doc_path, label, out_json, out_md):
    DOC_ = doc_path
    OUT_JSON_ = out_json
    OUT_MD_ = out_md
    docx = convert_doc(DOC_)
    with zipfile.ZipFile(docx) as z:
        root = etree.fromstring(z.read("word/document.xml"))
    fin_lines, orig_lines = [], []
    for par in root.iter(W + "p"):
        fin, orig = texts_of(par)
        if fin:
            fin_lines.append(fin)
        if orig:
            orig_lines.append(orig)
    final = parse_items(fin_lines)
    base = parse_items(orig_lines)

    def key(t):
        return re.sub(r"[\s\W_]+", "", t or "")

    base_by = {key(x["title"]): x for x in base}
    fin_keys = {key(x["title"]) for x in final}
    removed = [dict(x, reason=reason_of(x["title"])) for x in base if key(x["title"]) not in fin_keys]
    kept = [x for x in final if not x["added"] and key(x["title"]) in base_by]
    moved = [{"title": x["title"], "from": base_by[key(x["title"])]["sec"], "to": x["sec"]}
             for x in kept if base_by[key(x["title"])]["sec"] != x["sec"]]
    added = [x for x in final if x["added"]]
    link_changed = []
    for x in kept:
        b = base_by[key(x["title"])]
        if (b["urls"] or [""])[0] != (x["urls"] or [""])[0]:
            link_changed.append({"title": x["title"], "before": b["urls"][:2], "after": x["urls"][:2]})

    # 顺序：按板块分组后的文档顺序
    order = {}
    for sec in BOARDS:
        order[sec] = [x["title"] for x in final if x["sec"] == sec]

    data = {"source": os.path.basename(DOC_), "label": label, "final_count": len(final),
            "final": final, "removed": removed, "removed_count": len(removed),
            "added": added, "board_moves": moved, "link_changes": link_changed,
            "order": order,
            "counts": {sec: sum(1 for x in final if x["sec"] == sec) for sec in BOARDS}}
    save_json(OUT_JSON_, data)

    from collections import Counter
    ensure_dir(os.path.dirname(OUT_MD_))
    lines = [f"# 领导批注规则（{label} 版）", "",
             f"- 来源文件：`{DOC_}`",
             f"- 终稿：**{len(final)} 条**｜删除 {len(removed)} 条｜新增 {len(added)} 条｜板块迁移 {len(moved)} 条｜链接改动 {len(link_changed)} 条",
             f"- 终稿板块构成：{'、'.join('%s %d' % (k, v) for k, v in data['counts'].items())}", "",
             "## 一、新增条目", "", "| # | 板块 | 日期 | 标题 | 链接 |", "| --- | --- | --- | --- | --- |"]
    for i, x in enumerate(added, 1):
        lines.append(f"| {i} | {x['sec']} | {x.get('added_date','')} | {x['title'][:44]} | {(x['urls'] or [''])[0][:60]} |")
    lines += ["", "## 二、删除条目（按原因分类）", ""]
    for name, _ in REASONS:
        group = [x for x in removed if x["reason"] == name]
        if not group:
            continue
        lines += [f"### {name}（{len(group)} 条）", "", "| 原序号 | 板块 | 标题 |", "| --- | --- | --- |"]
        for x in group:
            lines.append(f"| {x['no']} | {x['sec']} | {x['title'][:56]} |")
        lines.append("")
    lines += ["## 三、板块迁移", "", "| 标题 | 原板块 | 终稿板块 |", "| --- | --- | --- |"]
    for x in moved:
        lines.append(f"| {x['title'][:44]} | {x['from']} | {x['to']} |")
    lines += ["", "## 四、链接改动", "", "| 标题 | 原链接 | 终稿链接 |", "| --- | --- | --- |"]
    for x in link_changed:
        lines.append(f"| {x['title'][:36]} | {(x['before'] or [''])[0][:52]} | {(x['after'] or [''])[0][:52]} |")
    lines += ["", "## 五、终稿顺序（骨架）", ""]
    for sec in BOARDS:
        lines += [f"**{sec}（{len(order[sec])} 条）**", ""]
        for i, t in enumerate(order[sec], 1):
            lines.append(f"{i}. {t}")
        lines.append("")
    open(OUT_MD_, "w", encoding="utf-8").write("\n".join(lines) + "\n")

    print(f"终稿 {len(final)} 条｜删除 {len(removed)}｜新增 {len(added)}｜迁移 {len(moved)}｜链接改动 {len(link_changed)}")
    print("删除原因分布：", dict(Counter(x["reason"] for x in removed)))
    print("输出：", OUT_JSON_)
    print("报告：", OUT_MD_)


if __name__ == "__main__":
    main()
