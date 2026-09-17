# -*- coding: utf-8 -*-
"""按人工精选清单生成 xlsx 目录、Markdown 目录与原文归档。"""
import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_utils import RAW, ROOT, ensure_dir, load_json  # noqa: E402
from period_config import P  # noqa: E402

CATALOG_DIR = os.path.join(ROOT, "02_原文")
MODULES = ["政策法规", "技术应用类", "科技前沿类"]      # 2026-09-17 起取消“媒体动态类”
LEVEL_ORDER = {"部级": 0, "行业与官媒": 1, "外省": 2}
SUB_ORDER = ["实景三维", "遥感与影像", "一张图与时空数据", "低空经济与无人机",
             "应急测绘", "调查监测与基础测绘", "北斗与时空基准"]
COLLECT_DATE = P.collect_date
PUBLICATION = "测绘动态工作（测绘地理信息月刊）"
# 生成时间：优先取环境变量，便于 md／xlsx／Word 三处写成同一时间
BUILD_TIME = os.environ.get("CATALOG_BUILD_TIME") or datetime.now().strftime("%Y-%m-%d %H:%M")
_HERE = P.sel_dir        # 该期选目数据目录（期次目录/99_脚本）
# 优先级：来源实体复检后的定稿 → 四板块重建结果 → 旧版人工选目
SEL_FILE = next((p for p in (
    os.path.join(_HERE, "catalog_selection_final.json"),
    os.path.join(_HERE, "catalog_selection_boards.json"),
    os.path.join(_HERE, "catalog_selection.json")) if os.path.exists(p)), "")


def norm(text):
    return re.sub(r"[\s\W_]+", "", text or "").lower()


def similarity(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return sum(1 for ch in set(shorter) if ch in longer) / len(set(shorter))


def load_corpus():
    items = []
    for name in sorted(f for f in os.listdir(RAW) if f.endswith("_detail.json")):
        for it in load_json(os.path.join(RAW, name)):
            items.append(it)
    return items


def pick(corpus, sel):
    """用 URL 子串 / 标题包含关系定位采集到的条目，可用 source_name 消歧。"""
    key = sel.get("match") or ""
    title_key = sel.get("title") or key
    pool = corpus
    if sel.get("source_name"):
        narrowed = [it for it in corpus if sel["source_name"] in (it.get("source_name") or "")]
        if narrowed:
            pool = narrowed

    def search(pool_):
        if key:
            by_url = [it for it in pool_ if key in (it.get("final_url") or it.get("url") or "")]
            if by_url:
                return by_url
        nk = norm(title_key)
        exact = [it for it in pool_ if norm(it.get("title")) == nk]
        if exact:
            return exact
        contains = [it for it in pool_ if nk and nk in norm(it.get("title"))]
        if contains:
            return sorted(contains, key=lambda x: len(norm(x.get("title"))))
        fuzzy = [it for it in pool_ if similarity(it.get("title"), title_key) >= 0.85]
        return sorted(fuzzy, key=lambda x: -similarity(x.get("title"), title_key))

    hits = search(pool)
    if not hits and pool is not corpus:
        hits = search(corpus)
    if not hits:
        raise SystemExit(f"未匹配到条目: {key} / {title_key}")
    hits.sort(key=lambda x: -len((x.get("text") or "")))
    return hits[0]


def weekly_lookup():
    path = os.path.join(ROOT, "03_参考_山东周讯", "周讯条目提取.json")
    weekly = load_json(path) if os.path.exists(path) else []
    return weekly


def main():
    sel_path = SEL_FILE if os.path.exists(SEL_FILE) else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "catalog_selection.json")
    selection = json.load(open(sel_path, encoding="utf-8"))
    corpus = load_corpus()
    weekly = weekly_lookup()
    verify_path = os.path.join(RAW, "核实结果.json")
    verify = load_json(verify_path) if os.path.exists(verify_path) else {}
    rows = []
    for sel in selection:
        item = pick(corpus, sel)
        title = sel.get("title") or item.get("title")
        date = sel.get("date_override") or item.get("date_page") or item.get("date_list") or ""
        src_name = sel.get("unit") or item.get("source_name") or ""
        level = sel.get("level") or item.get("level") or ""
        carrier = sel.get("carrier") or item.get("carrier") or "官网"
        url = item.get("final_url") or item.get("url")
        # 正文优先用来源实体复检时抓到的"原文正文"（确保是原发布方原文，而非周讯转载文本）
        text = sel.get("原文正文") or item.get("text") or ""
        # 周讯转载条目同一期共用同一篇文章链接，核实记录按“链接#标题”存放
        verify_key = url if item.get("source_id") != "weekly" else f"{url}#{title}"
        best_score, best_hit = 0.0, None
        for w in weekly:
            score = similarity(title, w["title"])
            if score > best_score:
                best_score, best_hit = score, w
        weekly_flag = f"是（第{best_hit['issue']}期）" if best_hit and best_score >= 0.75 else "否"
        rows.append({
            "板块": sel.get("board") or sel["module"], "子栏": sel.get("sub", ""),
            "业务条线": sel.get("business", ""),
            "来源类型": sel.get("source_type") or {"官网": "主管部门官网"}.get(carrier, carrier),
            "版次/公众号发布时间": sel.get("edition", ""),
            "正文来源": sel.get("正文来源", ""),
            "正文长度": sel.get("正文长度", ""),
            "属地层级": level, "省份": sel.get("province", ""),
            "标题": title, "发布单位": src_name,
            "来源载体": carrier, "来源链接": url, "发布日期": date, "采集日期": COLLECT_DATE,
            "关键词": sel.get("keywords", ""),
            "摘要": sel.get("summary") or re.sub(r"\s+", " ", text)[:180] or "（原文附后）",
            "建议优先级": sel.get("priority", "B"),
            "是否已被山东周讯收录": weekly_flag, "备注": sel.get("note", ""),
            "核实状态": verify.get(verify_key, {}).get("核实状态", "未核实"),
            "核实方式": verify.get(verify_key, {}).get("核实方式", ""),
            "交叉来源": "；".join(f"{c['source']}：{c['url']}" for c in
                                 (verify.get(url, {}).get("交叉来源") or []))[:400],
            "text": text,
        })

    # R4：类内顺序由 31 号脚本按“层级 → 业务中心度 → 日期倒序”排定；
    # 这里只按板块分组并保持组内既有顺序（稳定排序），不再按子栏／层级／日期重排。
    rows.sort(key=lambda r: MODULES.index(r["板块"]) if r["板块"] in MODULES else 9)
    for i, r in enumerate(rows, 1):
        r["序号"] = i

    # ---- 原文归档 ----
    written = set()
    for r in rows:
        folder = ensure_dir(os.path.join(CATALOG_DIR, r["板块"]))
        safe = re.sub(r'[\\/:*?"<>|\s]+', "", r["标题"])[:40]
        path = os.path.join(folder, f"{r['发布日期']}_{r['发布单位'][:12]}_{safe}.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"# {r['标题']}\n\n")
            fh.write(f"- 板块：{r['板块']}\n- 业务条线：{r['业务条线'] or '未标注'}\n")
            fh.write(f"- 属地层级：{r['属地层级']}\n- 发布单位：{r['发布单位']}\n")
            fh.write(f"- 来源类型：{r['来源类型']}\n")
            fh.write(f"- 正文来源：{r.get('正文来源') or '未核验'}（{r.get('正文长度') or 0} 字）\n")
            if r.get("原文核验"):
                fh.write(f"- 来源核验：{r['原文核验']}\n")
            if r.get("版次/公众号发布时间"):
                fh.write(f"- 版次/公众号发布时间：{r['版次/公众号发布时间']}\n")
            if r.get("子栏"):
                fh.write(f"- 子栏：{r['子栏']}\n")
            fh.write(f"- 发布日期：{r['发布日期']}\n- 原文链接：{r['来源链接']}\n")
            fh.write(f"- 采集日期：{COLLECT_DATE}\n- 建议优先级：{r['建议优先级']}\n")
            fh.write(f"- 是否已被山东周讯收录：{r['是否已被山东周讯收录']}\n")
            fh.write(f"- 核实状态：{r['核实状态']}（{r['核实方式']}）\n")
            if r.get("交叉来源"):
                fh.write(f"- 交叉来源：{r['交叉来源']}\n")
            if r.get("备注"):
                fh.write(f"- 备注：{r['备注']}\n")
            fh.write(f"\n## 摘要\n\n{r['摘要']}\n\n## 原文\n\n")
            fh.write((r["text"] or "（未抓取到正文，请通过原文链接查看）").strip() + "\n")
        written.add(os.path.abspath(path))

    # 归档只保留本期条目（份数 = 目录条数）；上一版内容见《_备查/全量底稿（<采集范围>）.md》
    removed = 0
    # 连同已取消／改名的板块目录（媒体动态类、旧名“政策类”）一起清理
    for board in MODULES + ["媒体动态类", "政策类"]:
        folder = os.path.join(CATALOG_DIR, board)
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            full = os.path.abspath(os.path.join(folder, name))
            if os.path.isfile(full) and full not in written:
                os.remove(full)
                removed += 1
        if board not in MODULES and os.path.isdir(folder) and not os.listdir(folder):
            os.rmdir(folder)          # 已取消板块的空目录一并移除
    if removed:
        print(f"  已清理往期归档 {removed} 份（归档现为 {len(written)} 份）")

    # ---- Markdown 目录 ----
    lines = [f"# {PUBLICATION}", "",
             f"## 测绘动态资讯目录（{P.title_range}）", "",
             f"- 采集范围：{P.window_text()}",
             f"- 条目总数：{len(rows)}",
             f"- 生成时间：{BUILD_TIME}", ""]
    for module in MODULES:
        sub = [r for r in rows if r["板块"] == module]
        if not sub:
            continue
        lines += [f"## {module}（{len(sub)} 条）", ""]
        # 目录只按四个板块编排，不设二级分类（子栏仅作数据字段）
        groups = [None]
        for group in groups:
            members = sub if group is None else [r for r in sub if r["子栏"] == group]
            if group is not None:
                label = group or "其他"
                lines += [f"### {label}（{len(members)} 条）", ""]
            for r in members:
                tag = f"【{r.get('省份','') or r['属地层级']}】"
                lines.append(f"**{r['序号']}. {tag}{r['标题']}**")
                # 来源行只写来源单位，其余属性保留在 xlsx 字段与统计表中
                lines.append(f"- 来源：{r['发布单位']}")
                lines.append(f"- 链接：{r['来源链接']}")
                if r.get("备注"):
                    lines.append(f"- 备注：{r['备注']}")
                lines.append(f"- 摘要：{r['摘要']}")
                lines.append("")
    with open(os.path.join(ROOT, "00_资讯目录.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    # ---- xlsx ----
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "资讯目录"
    cols = ["序号", "板块", "业务条线", "子栏", "属地层级", "省份", "标题", "发布单位", "来源类型",
            "来源载体", "正文来源", "正文长度",
            "来源链接", "发布日期", "版次/公众号发布时间", "采集日期", "关键词", "摘要",
            "建议优先级", "是否已被山东周讯收录", "核实状态", "核实方式", "交叉来源链接", "备注"]
    ws.append(cols)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="2F5597")
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for r in rows:
        ws.append([r["序号"], r["板块"], r["业务条线"], r.get("子栏", ""), r["属地层级"],
                   r.get("省份", ""), r["标题"], r["发布单位"], r["来源类型"], r["来源载体"],
                   r.get("正文来源", ""), r.get("正文长度", ""),
                   r["来源链接"], r["发布日期"], r.get("版次/公众号发布时间", ""), r["采集日期"],
                   r["关键词"], r["摘要"], r["建议优先级"], r["是否已被山东周讯收录"],
                   r.get("核实状态", ""), r.get("核实方式", ""), r.get("交叉来源", ""), r["备注"]])
    widths = {"A": 6, "B": 12, "C": 24, "D": 14, "E": 10, "F": 8, "G": 56, "H": 22, "I": 14,
              "J": 10, "K": 14, "L": 9, "M": 52, "N": 12, "O": 16, "P": 12, "Q": 18, "R": 62,
              "S": 10, "T": 18, "U": 14, "V": 30, "W": 40, "X": 24}
    for col, width in widths.items():
        ws.column_dimensions[col].width = width
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=cell.column_letter in "FLPRS")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    stat = wb.create_sheet("统计")
    stat.append(["按板块 × 属地层级统计", "", "", "", ""])
    stat["A1"].font = Font(bold=True)
    stat.append(["板块"] + list(LEVEL_ORDER) + ["合计"])
    for cell in stat[2]:
        cell.font = Font(bold=True)
    for module in MODULES:
        sub = [r for r in rows if r["板块"] == module]
        stat.append([module] + [sum(1 for r in sub if r["属地层级"] == lv) for lv in LEVEL_ORDER]
                    + [len(sub)])
    stat.append(["合计"] + [sum(1 for r in rows if r["属地层级"] == lv) for lv in LEVEL_ORDER]
                + [len(rows)])
    stat.append([])
    stat.append(["按来源单位统计", "", ""])
    stat.append(["发布单位", "条数", ""])
    from collections import Counter
    for name, num in Counter(r["发布单位"] for r in rows).most_common():
        stat.append([name, num, ""])
    stat.append([])
    stat.append(["优先级", "条数", ""])
    for name, num in sorted(Counter(r["建议优先级"] for r in rows).items()):
        stat.append([name, num, ""])
    stat.append([])
    stat.append(["按省份统计（外省动态）", "", ""])
    stat.append(["省份", "条数", ""])
    for name, num in Counter(r.get("省份", "") for r in rows if r["属地层级"] == "外省").most_common():
        stat.append([name, num, ""])
    stat.append([])
    stat.append(["按业务条线统计（10 条）", "", ""])
    stat.append(["业务条线", "条数", ""])
    from collections import Counter as _C
    for name, num in _C(r["业务条线"] or "未标注" for r in rows).most_common():
        stat.append([name, num, ""])
    stat.append([])
    stat.append(["按来源类型统计", "", ""])
    stat.append(["来源类型", "条数", ""])
    for name, num in _C(r["来源类型"] for r in rows).most_common():
        stat.append([name, num, ""])
    stat.append([])
    stat.append(["按子栏统计（技术应用类细分，其余为主题标签）", "", "", ""])
    stat.append(["子栏", "技术应用", "其他模块", ""])
    for name in SUB_ORDER:
        tech = sum(1 for r in rows if r["板块"] == "技术应用类" and r.get("子栏") == name)
        other = sum(1 for r in rows if r["板块"] != "技术应用类" and r.get("子栏") == name)
        if tech or other:
            stat.append([name, tech, other, ""])
    stat.append(["（技术应用类中未细分）",
                 sum(1 for r in rows if r["板块"] == "技术应用类" and not r.get("子栏")), 0, ""])
    for col, width in {"A": 34, "B": 12, "C": 12, "D": 12, "E": 12}.items():
        stat.column_dimensions[col].width = width
    wb.save(os.path.join(ROOT, "00_资讯目录.xlsx"))
    print(f"生成完成：{len(rows)} 条")
    for board in MODULES:
        print(f"  {board}: {sum(1 for r in rows if r['板块'] == board)} 条")


if __name__ == "__main__":
    main()
