# -*- coding: utf-8 -*-
"""为目录增加“子栏”：技术应用按主题细分，其余模块给同类主题打标签便于筛选。

技术应用子栏顺序：实景三维 → 遥感与影像 → 一张图与时空数据 → 低空经济与无人机
                → 应急测绘 → 调查监测与基础测绘
其他模块中属于这些主题的条目同样打标签（跨模块可按“子栏”筛选，例如汇总全部实景三维动态）。
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_utils import RAW, load_json, save_json  # noqa: E402

SEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalog_selection.json")
SNAPSHOT = os.path.join(RAW, "catalog_selection_base_v3.json")

SUB_ORDER = ["实景三维", "遥感与影像", "一张图与时空数据", "低空经济与无人机",
             "应急测绘", "调查监测与基础测绘", "北斗与时空基准"]

# 标题关键字 → 子栏（技术应用逐条明确归类）
SUB = {
    # —— 实景三维 ——
    "实景三维“复刻”八闽大地": "实景三维",
    "扫一扫就能“看透”地下": "实景三维",
    "连云港市局依托BIM实景三维技术": "实景三维",
    "广西研发便携测绘系统让三维建模提速增效": "实景三维",
    "四川测绘产品质量监督检验站自研系统赋能实景三维质检": "实景三维",
    "“测绘+AI”助力地震防控": "实景三维",
    # —— 遥感与影像 ——
    "辽宁省遥感影像数据统筹": "遥感与影像",
    "山西实现0.2米航空影像全省域覆盖": "遥感与影像",
    "湖北全面推进天空地网一体化监测网建设": "遥感与影像",
    "广西自研多源遥感数据自动化处理系统通过验收": "遥感与影像",
    "聊城建成一体化遥感时空影像数据库": "遥感与影像",
    "我国首版全国几何基准影像成果正式发布": "遥感与影像",
    "武汉大学东方慧眼星座高光谱": "遥感与影像",
    "重庆山地遥感影像智能解译样本库发布": "遥感与影像",
    # —— 一张图与时空数据 ——
    "全国首个！福建自然资源“大管家”": "一张图与时空数据",
    "自然资源“一张图”建设扎实推进": "一张图与时空数据",
    "我国加快自然资源“一张图”平台建设": "一张图与时空数据",
    "山东日照：“一张图”场景应用驱动数智治理": "一张图与时空数据",
    "大连市自然资源局实现“一图管陆海”": "一张图与时空数据",
    "德州“一码”通管自然资源“一本账”": "一张图与时空数据",
    # —— 低空经济与无人机 ——
    "武汉搭建超大城市全域低空无人机监测网络": "低空经济与无人机",
    "上海低空测绘技术成果集中亮相": "低空经济与无人机",
    # —— 应急测绘 ——
    "自然资源部工作组在吉隆灾区": "应急测绘",
    "地信中心全力做好西藏吉隆泥石流灾害应急测绘保障": "应急测绘",
    "山东省2026年度应急测绘保障实战演练顺利完成": "应急测绘",
    "“电建一号”卫星获取西藏吉隆口岸首批灾后卫星影像": "应急测绘",
    # —— 调查监测与基础测绘 ——
    "地信中心实现馆藏古地图": "调查监测与基础测绘",
    "浙江以“人工智能+地图监管”": "调查监测与基础测绘",
    "湖南省第二测绘院支撑全省生态产品总值首次试算圆满收官": "调查监测与基础测绘",
    "青海省地质测绘地理信息院精准航测支撑湟源县林权改革": "调查监测与基础测绘",
    "黑龙江第二测绘工程院开展矿山超层越界测量": "调查监测与基础测绘",
    # —— 北斗与时空基准（跨模块标签） ——
    "全国卫星导航定位基准站网服务数据授权运营落地": "北斗与时空基准",
    "山东举办卫星导航定位与大地测量技术及北斗应用研讨会": "北斗与时空基准",
}


def norm(text):
    return re.sub(r"[\s\W_]+", "", text or "")


def main():
    base_path = SNAPSHOT if os.path.exists(SNAPSHOT) else SEL_PATH
    selection = json.load(open(base_path, encoding="utf-8"))
    if not os.path.exists(SNAPSHOT):
        save_json(SNAPSHOT, selection)
    for sel in selection:
        sel["sub"] = ""
        for key, sub in SUB.items():
            if norm(key) in norm(sel["title"]):
                sel["sub"] = sub
                break
    with open(SEL_PATH, "w", encoding="utf-8") as fh:
        json.dump(selection, fh, ensure_ascii=False, indent=1)

    from collections import Counter
    tech = [s for s in selection if s["module"] == "技术应用"]
    untagged = [s["title"] for s in tech if not s["sub"]]
    print("技术应用", len(tech), "条：", dict(Counter(s["sub"] for s in tech)))
    if untagged:
        print("  未归类（技术应用）：", untagged)
    cross = [s for s in selection if s["module"] != "技术应用" and s["sub"]]
    print("跨模块主题标签", len(cross), "条：", dict(Counter(s["sub"] for s in cross)))


if __name__ == "__main__":
    main()
