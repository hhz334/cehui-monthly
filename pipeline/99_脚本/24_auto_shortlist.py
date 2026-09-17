# -*- coding: utf-8 -*-
"""从新采集来源里自动初筛候选条目（四板块 + 业务条线），供 23 合并进选目。

规则：
- 必须命中测绘地理信息相关性关键词；
- 排除党建、巡视、宣传科普、招聘公示、培训、走访座谈、表彰活动等非业务内容；
- 每条来源最多取 MAX_PER_SOURCE 条，输出 _raw/auto_shortlist.json。
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_utils import RAW, load_json, save_json  # noqa: E402
from period_config import P  # noqa: E402
import sources_whitelist as WL  # noqa: E402

FROM, TO = P.window_from, P.window_to
MAX_PER_SOURCE = 6

# 只对这些来源做自动初筛（本期新补的通道与省厅）
SCOPE_IDS = {
    "hubei_dnr", "snsm_sjyw", "snsm_hydt", "scsm_sjyw", "scsm_hydt",
    "gd_dnr", "js_dnr", "sd_dnr",
    "drcmnr_zxxw", "drcmnr_xyxw", "drcmnr_tzgg", "drcmnr_fzyjdt", "drcmnr_yjbg",
    "drcmnr_zcfg", "drcmnr_zcjd", "drcmnr_zktz",
}

RELEVANT = [r"测绘", r"实景三维", r"遥感", r"影像", r"基准站", r"北斗", r"导航定位",
            r"地图", r"地理信息", r"时空", r"三维", r"无人机", r"航摄", r"地理空间",
            r"GNSS", r"质检", r"调查监测", r"变更调查", r"确权", r"地籍", r"耕地保护",
            r"应急测绘", r"测绘资质", r"版图", r"标准地图",
            # 科技创新方向（按业务补充说明新增）
            r"实景三维数据更新", r"地理实体", r"语义化", r"大数据", r"挖掘分析", r"众源",
            r"人工智能", r"低空经济", r"感知", r"智能解译",
            # 基准服务与公共服务方向
            r"测量标志", r"陆海一体化", r"似大地水准面", r"天地图", r"公众版",
            r"公益性地图", r"政务用图", r"一张图",
            # 数据安全方向
            r"保密", r"涉密", r"数据安全", r"重要数据"]

# 排除：非业务内容
EXCLUDE_TITLE = [r"巡视", r"巡察", r"党建", r"党支部", r"主题党日", r"党课", r"廉政",
                 r"纪检", r"团委", r"青年", r"工会", r"妇联", r"宣讲", r"运动会",
                 r"越野赛", r"文化活动", r"健步", r"招聘", r"拟聘", r"公示",
                 r"培训班", r"培训会",
                 r"揭牌", r"签约", r"会见", r"座谈", r"调研交流", r"总结大会",
                 r"表彰", r"专访", r"慰问", r"离退休", r"观影", r"文艺",
                 r"保密宣传月", r"保密宣传"]

LEVEL_OF = {"drcmnr": "部级", "hubei_dnr": "外省", "snsm": "外省", "scsm": "外省",
            "gd_dnr": "外省", "js_dnr": "外省", "sd_dnr": "外省"}
PROVINCE_OF = {"hubei_dnr": "湖北", "snsm_sjyw": "陕西", "snsm_hydt": "陕西",
               "scsm_sjyw": "四川", "scsm_hydt": "四川",
               "gd_dnr": "广东", "js_dnr": "江苏", "sd_dnr": "山东"}
UNIT_OF = {
    "hubei_dnr": "湖北省自然资源厅",
    "snsm_sjyw": "陕西测绘地理信息局", "snsm_hydt": "陕西测绘地理信息局",
    "scsm_sjyw": "四川测绘地理信息局", "scsm_hydt": "四川测绘地理信息局",
    "gd_dnr": "广东省自然资源厅", "js_dnr": "江苏省自然资源厅", "sd_dnr": "山东省自然资源厅",
    "drcmnr_zxxw": "自然资源部测绘发展研究中心",
    "drcmnr_xyxw": "自然资源部测绘发展研究中心",
    "drcmnr_tzgg": "自然资源部测绘发展研究中心",
    "drcmnr_fzyjdt": "自然资源部测绘发展研究中心",
    "drcmnr_yjbg": "自然资源部测绘发展研究中心",
    "drcmnr_zcfg": "自然资源部测绘发展研究中心",
    "drcmnr_zcjd": "自然资源部测绘发展研究中心",
    "drcmnr_zktz": "自然资源部测绘发展研究中心",
}


PROVINCES = ["北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江", "上海", "江苏",
             "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "广西",
             "海南", "重庆", "四川", "贵州", "云南", "西藏", "陕西", "甘肃", "青海", "宁夏",
             "新疆"]
KEY_PROVINCES = ["山东", "陕西", "四川", "广东", "湖南", "江苏"]

# 经验做法稿特征（外省单位的实践报道 → 技术应用类；2026-09-17 起取消“媒体动态类”）
EXPERIENCE = [r"经验", r"做法", r"探索", r"实践", r"模式", r"样板", r"新范式", r"新路径",
              r"织密", r"打造", r"纪实", r"担当", r"亮点", r"观察", r"蹲点", r"一线"]
EXPERIENCE_BLOCK = [r"党组", r"理论学习", r"学习贯彻", r"党课", r"巡视"]


def province_of(title):
    title = clean_title(title)
    for p in PROVINCES:
        if title.startswith(p) or f"{p}" in title[:12]:
            return p
    return ""


def clean_title(title):
    """去掉列表页残留：前缀序号/项目符号、尾部"时间：… 来源：…"等元信息。"""
    t = (title or "").strip()
    t = re.sub(r"^[·•∙・\-\u2022\s]+", "", t)
    t = re.sub(r"^\d{1,3}[\s.、]+(?=[^\d])", "", t)
    t = t.split("|")[0]                     # 列表页用 ASCII 竖线拼接的同条多标题，取前一段
    t = re.split(r"\s*(?:时间|来源|发布(?:时间|日期)|日期)\s*[:：]", t)[0]
    t = re.sub(r"\s*\[\s*20\d{2}-\d{2}-\d{2}\s*\]\s*$", "", t)
    return re.sub(r"\s+", " ", t).strip()


def is_experience(title):
    title = clean_title(title)
    if any(re.search(p, title) for p in EXPERIENCE_BLOCK):
        return False
    return any(re.search(p, title) for p in EXPERIENCE)


def level_of(sid):
    for key, lv in LEVEL_OF.items():
        if sid.startswith(key):
            return lv
    return "外省"


def fetch_iziran_article(aid):
    """取 i 自然官网单篇正文（公开接口，无需登录）。"""
    import urllib.request
    from fetch_utils import strip_html
    url = f"https://api.iziran.net/api/getArticle?aid={aid}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0",
            "Referer": "https://www.iziran.net/"})
        raw = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")
        data = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        print(f"    ! 正文抓取失败 aid={aid} :: {exc}")
        return ""
    content = ""
    if isinstance(data, dict):
        content = (data.get("data") or {}).get("content") or data.get("content") or ""
    return strip_html(content)


def main():
    out = []
    # ---- A. 新补省厅 / 部属单位官网 ----
    for name in sorted(os.listdir(RAW)):
        if not name.endswith("_detail.json"):
            continue
        sid = name[:-len("_detail.json")]
        if sid not in SCOPE_IDS:
            continue
        picked = 0
        for it in load_json(os.path.join(RAW, name)):
            if picked >= MAX_PER_SOURCE:
                break
            title = clean_title(it.get("title"))
            text = it.get("text") or ""
            date = it.get("date_page") or it.get("date_list") or ""
            url = it.get("final_url") or it.get("url") or ""
            if not title or not url:
                continue
            if date and not (FROM <= date <= TO):
                continue
            if not any(re.search(p, title) for p in RELEVANT):
                continue
            if any(re.search(p, title) for p in EXCLUDE_TITLE) or WL.promo_excluded(title):
                continue
            if WL.site_type(url) in ("", "公众号"):
                continue
            board = WL.board_of("", title, text[:400])
            hits = WL.business_of(title, text[:400], "")
            if not hits:
                continue
            summary = re.sub(r"\s+", " ", text).strip()[:180]
            out.append({
                "module": {"政策类": "政策措施", "技术应用类": "技术应用",
                           "科技前沿类": "科技前沿"}[board],
                "board": board,
                "business": hits[0][0],
                "business_all": [h[0] for h in hits],
                "level": level_of(sid),
                "province": PROVINCE_OF.get(sid, "全国"),
                "title": title,
                "unit": UNIT_OF.get(sid, it.get("source_name") or ""),
                "source_name": it.get("source_name") or "",
                "source_type": WL.site_type(url) or "主管部门官网",
                "source_url_checked": url,
                "match": url.split("?")[0][-60:],
                "date_override": date,
                "priority": "A" if level_of(sid) == "部级" else "B",
                "keywords": "；".join(sorted({h[0] for h in hits})),
                "summary": summary or "（自动初筛条目，摘要取自原文首段，待人工润色）",
                "note": f"自动初筛：来源 {it.get('source_name') or sid}",
                "auto": True,
            })
            picked += 1
        if picked:
            print(f"  {sid}: 初筛 {picked} 条")

    # ---- B. 部「地方动态」重点省份补充（覆盖广东、湖南等未自建来源的省份）----
    dfdt = os.path.join(RAW, "mnr_dfdt_detail.json")
    if os.path.exists(dfdt):
        seen = {x["title"] for x in out}
        per_prov = {}
        for it in load_json(dfdt):
            title = clean_title(it.get("title"))
            text = it.get("text") or ""
            date = it.get("date_page") or it.get("date_list") or ""
            url = it.get("final_url") or it.get("url") or ""
            if not title or not url or title in seen:
                continue
            prov = province_of(title)
            if prov not in KEY_PROVINCES or per_prov.get(prov, 0) >= 3:
                continue
            if date and not (FROM <= date <= TO):
                continue
            if not any(re.search(p, text[:400]) for p in RELEVANT):
                continue
            if any(re.search(p, f"{title} {text[:200]}") for p in EXCLUDE_TITLE) \
                    or WL.promo_excluded(title, text[:200]):
                continue
            # 经验做法稿不再单列，统一归技术应用类
            board = "技术应用类" if is_experience(title) else WL.board_of("", title, text[:400])
            hits = WL.business_of(title, text[:400], "")
            if not hits:
                continue
            out.append({
                "module": {"政策类": "政策措施", "技术应用类": "技术应用",
                           "科技前沿类": "科技前沿"}[board],
                "board": board,
                "business": hits[0][0],
                "business_all": [h[0] for h in hits],
                "level": "外省",
                "province": prov,
                "title": title,
                "unit": "自然资源部（地方动态）",
                "source_name": it.get("source_name") or "自然资源部（地方动态）",
                "source_type": WL.site_type(url) or "主管部门官网",
                "source_url_checked": url,
                "match": url.split("?")[0][-60:],
                "date_override": date,
                "priority": "B",
                "keywords": "；".join(sorted({h[0] for h in hits})),
                "summary": f"自然资源部网站地方动态：{title}。{re.sub(r'[ \\t\\r\\n]+', ' ', text)[:150]}",
                "note": f"部地方动态（{prov}）",
                "auto": True,
            })
            per_prov[prov] = per_prov.get(prov, 0) + 1
            seen.add(title)
        if per_prov:
            print(f"  部地方动态重点省份补充: {per_prov}")

    # ---- C. 中国自然资源报（i自然官网）测绘栏目 ----
    zdir = os.path.join(RAW, "zrzyb")
    if os.path.isdir(zdir):
        news = []
        for fn in sorted(os.listdir(zdir)):
            if not fn.startswith("iziran_cid") or not fn.endswith(".json"):
                continue
            data = load_json(os.path.join(zdir, fn))
            news.extend(data.get("articles", []) if isinstance(data, dict) else [])
        seen_titles = {x["title"] for x in out}
        picked = 0
        details = []
        for art in news:
            title = clean_title(art.get("title"))
            date = (art.get("publishTime") or "")[:10]
            url = art.get("url") or ""
            if not title or not url or title in seen_titles:
                continue
            if not (FROM <= date <= TO):
                continue
            if not any(re.search(p, title) for p in RELEVANT):
                continue
            if any(re.search(p, title) for p in EXCLUDE_TITLE) or WL.promo_excluded(title):
                continue
            prov = province_of(title)
            # 经验做法稿不再单列，统一归技术应用类
            board = "技术应用类" if is_experience(title) else WL.board_of("", title, "")
            hits = WL.business_of(title, "", "")
            if not hits:
                continue
            out.append({
                "module": {"政策类": "政策措施", "技术应用类": "技术应用",
                           "科技前沿类": "科技前沿"}[board],
                "board": board,
                "business": hits[0][0],
                "business_all": [h[0] for h in hits],
                "level": "外省" if prov else "行业与官媒",
                "province": prov or "全国",
                "title": title,
                "unit": "中国自然资源报（i自然）",
                "source_name": "中国自然资源报（i自然）",
                "source_type": "原发媒体官网",
                "source_url_checked": url,
                "match": f"aid={art.get('fileID')}",
                "date_override": date,
                "priority": "B",
                "keywords": "；".join(sorted({h[0] for h in hits})),
                "summary": f"中国自然资源报（i自然）报道：{title}。摘自原发媒体官网，正文见源链接。",
                "note": f"中国自然资源报 i自然官网 {date}（栏目：{art.get('columnName') or ''}）",
                "auto": True,
            })
            picked += 1
            seen_titles.add(title)
        if picked:
            print(f"  zrzyb(测绘栏目): 初筛 {picked} 条")
        if picked:
            for rec in out:
                if rec.get("auto") and rec.get("source_name") == "中国自然资源报（i自然）":
                    aid = (rec.get("match") or "").split("=")[-1]
                    text = fetch_iziran_article(aid)
                    # 摘要用真实正文首段，避免"摘自原发媒体官网"这类模板句
                    if text:
                        lead = re.sub(r"\s+", " ", text).strip()
                        rec["summary"] = lead[:170] + ("……" if len(lead) > 170 else "")
                    details.append({
                        "url": rec["source_url_checked"],
                        "final_url": rec["source_url_checked"],
                        "title": rec["title"],
                        "title_page": rec["title"],
                        "date_page": rec["date_override"],
                        "date_list": rec["date_override"],
                        "origin_page": "中国自然资源报",
                        "source_id": "zrzyb",
                        "source_name": "中国自然资源报（i自然）",
                        "level": rec["level"],
                        "carrier": "原发媒体官网",
                        "text": text,
                        "text_len": len(text),
                        "http_ok": bool(text),
                    })
            save_json(os.path.join(RAW, "zrzyb_detail.json"), details)
            print(f"  已写入语料 _raw/zrzyb_detail.json：{len(details)} 条")
    save_json(os.path.join(RAW, "auto_shortlist.json"), out)
    import collections
    print(f"合计初筛 {len(out)} 条；板块 {dict(collections.Counter(x['board'] for x in out))}")


if __name__ == "__main__":
    main()
