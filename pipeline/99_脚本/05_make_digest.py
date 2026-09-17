# -*- coding: utf-8 -*-
"""合并详情结果：清洗标题、校正日期、做测绘地信相关性预筛，输出候选清单。"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_utils import RAW, load_json  # noqa: E402
from period_config import P  # noqa: E402

FROM, TO = P.window_from, P.window_to
SANE_FROM, SANE_TO = "2026-07-15", "2026-09-14"

CORE = ["测绘", "地理信息", "地理空间", "实景三维", "三维", "遥感", "卫星", "北斗",
        "导航定位", "基准站", "时空", "一张图", "地图", "版图", "基础测绘", "测绘资质",
        "摄影测量", "无人机", "低空", "数字孪生", "GIS", "地理实体", "调查监测",
        "国土空间监测", "数据要素", "智能审图", "地形", "影像", "人工智能", "大模型", "地信"]
WEAK = ["土地", "矿产", "耕地", "不动产", "生态修复", "规划", "海洋", "林业", "地质"]
EXCLUDE = ["每日晨读", "党纪", "巡视", "廉政", "党史", "招聘", "考试", "决算", "预算",
           "党日", "党课", "读书班", "运动会", "演出", "群团", "工会"]


def clean_title(title):
    t = re.sub(r"\s+", " ", title or "").strip()
    t = re.sub(r"^[\s·•]*(?:\d{1,3})[\s.、]+(?=[^\d])", "", t)          # 去掉列表序号
    t = re.sub(r"\s*20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}(\s+\d{1,2}:\d{2}(:\d{2})?)?\s*$", "", t)
    t = re.sub(r"^[·•\s]+", "", t)
    return t.strip()


def pick_date(item):
    for key in ("date_page", "date_list"):
        d = item.get(key) or ""
        if d and SANE_FROM <= d <= SANE_TO:
            return d
    return ""


def main():
    rows = []
    for name in sorted(f for f in os.listdir(RAW) if f.endswith("_detail.json")):
        for item in load_json(os.path.join(RAW, name)):
            title = clean_title(item.get("title") or item.get("title_page") or "")
            if not title:
                continue
            date = pick_date(item)
            text = item.get("text") or ""
            blob = title + " " + text[:2000]
            core = sum(1 for k in CORE if k in blob)
            title_core = sum(1 for k in CORE if k in title)
            rows.append({
                **{k: v for k, v in item.items() if k != "text"},
                "title": title, "date": date, "text": text,
                "core": core, "title_core": title_core,
                "in_window": bool(date and FROM <= date <= TO),
                "excluded": any(k in title for k in EXCLUDE),
            })

    for r in rows:
        if not r["in_window"]:
            r["relevance"] = "窗外"
        elif r["excluded"]:
            r["relevance"] = "剔除"
        elif r["title_core"] >= 1:
            r["relevance"] = "高"
        elif r["core"] >= 5:
            r["relevance"] = "中"
        else:
            r["relevance"] = "低"

    def dump(path, subset, with_text=False):
        lines = ["| # | 相关度 | 属地 | 来源 | 日期 | 标题 |", "| --- | --- | --- | --- | --- | --- |"]
        for i, r in enumerate(subset, 1):
            lines.append(f"| {i} | {r['relevance']} | {r['level']} | {r['source_name']} | "
                         f"{r['date'] or '—'} | [{r['title']}]({r.get('final_url') or r.get('url')}) |")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

    keep = [r for r in rows if r["in_window"] and r["relevance"] in ("高", "中")]
    keep.sort(key=lambda x: (x["level"] != "福建", {"高": 0, "中": 1}[x["relevance"]], x["date"]))
    dump(os.path.join(RAW, "候选清单.md"), keep)
    fujian = [r for r in rows if r["level"] == "福建"]
    fujian.sort(key=lambda x: (x["relevance"], x["date"]))
    dump(os.path.join(RAW, "福建全量清单.md"), fujian)
    allrows = sorted(rows, key=lambda x: (x["level"] != "福建", x["date"]))
    dump(os.path.join(RAW, "全量清单.md"), allrows)

    print("总条目", len(rows), "| 窗口内", sum(1 for r in rows if r["in_window"]),
          "| 候选", len(keep), "| 福建窗口内", sum(1 for r in fujian if r["in_window"]))
    print("=== 候选（相关度 高/中，窗口内）===")
    for i, r in enumerate(keep, 1):
        print(f"{i}\t{r['relevance']}\t{r['level']}\t{r['source_name'][:14]}\t{r['date']}\t{r['title'][:62]}")


if __name__ == "__main__":
    main()
