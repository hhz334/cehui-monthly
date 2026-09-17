# -*- coding: utf-8 -*-
"""人工指定采纳入口：把指定链接（含部专题、中央媒体地方频道等）纳入本期选目。

用途：遇到"必须采纳但不在自动采集范围"的稿件时使用。
做三件事：
1. 抓取链接标题、发布日期与原文正文；
2. 写入语料 `_raw/manual_detail.json`（供 07 匹配、25 复核）；
3. 写入选目补丁 `_raw/manual_includes.json`（供 23 合并进四板块选目）。

每期如需新增人工采纳条目，编辑下方 MANUAL 列表后重新运行本脚本即可。
"""
import importlib.util
import os
import re
import ssl
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_utils import RAW, load_json, norm_date, save_json, strip_html  # noqa: E402
import sources_whitelist as WL  # noqa: E402

ssl._create_default_https_context = ssl._create_unverified_context
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0",
      "Accept-Language": "zh-CN,zh;q=0.9"}

# ---------------------------------------------------------------- 人工采纳清单
MANUAL = [
    {
        "url": "https://www.mnr.gov.cn/zt/hd/chfxcr/2026chfxcr/tpsp/202608/t20260829_2937307.html",
        "board": "技术应用类", "business": "测绘行业管理与技术服务",
        "level": "部级", "province": "全国",
        "unit": "自然资源部（2026年测绘法宣传日专题）", "priority": "B",
        "keywords": "测绘法宣传日;国家版图意识;地图审查;问题地图",
        "note": "2026年测绘法宣传日专题（图片视频栏目）；收录例外：部级宣传周稿件可收",
    },
    {
        "url": "http://nx.people.com.cn/GB/n2/2026/0829/c410805-41681345.html",
        "board": "技术应用类", "business": "测绘地理信息公共服务",
        "level": "外省", "province": "宁夏",
        "unit": "人民网宁夏频道", "priority": "B",
        "keywords": "测绘法宣传日;国家版图意识;技能竞赛;学术研讨",
        "note": "人民网宁夏频道报道；收录例外：省级宣传周做法成效报道可收，含\"宁聚智绘\"学术研讨与全区自然资源调查监测劳动技能竞赛",
    },
    # —— 以下为部级专题内符合"收录例外"的条目（省级做法、部级深度稿）——
    {
        "url": "https://www.mnr.gov.cn/dt/ch/202609/t20260901_2937359.html",
        "board": "技术应用类", "business": "测绘地理信息公共服务",
        "level": "部级", "province": "全国",
        "unit": "自然资源部（2026年测绘法宣传日专题）", "priority": "B",
        "keywords": "测绘法宣传日;国家版图意识;地理信息安全",
        "note": "部级专题深度稿（宣传周）",
    },
    {
        "url": "https://www.mnr.gov.cn/zt/hd/chfxcr/2026chfxcr/tpsp/202608/t20260828_2937222.html",
        "board": "技术应用类", "business": "测绘基准服务",
        "level": "部级", "province": "全国",
        "unit": "自然资源部（2026年测绘法宣传日专题）", "priority": "B",
        "keywords": "全国几何基准影像;测绘基准;科普解读",
        "note": "部级专题科普解读：一图读懂全国几何基准影像",
    },
    {
        "url": "https://www.mnr.gov.cn/dt/mtsy/202609/t20260901_2937371.html",
        "board": "技术应用类", "business": "测绘地理信息公共服务",
        "level": "外省", "province": "青海",
        "unit": "自然资源部（2026年测绘法宣传日专题·各地活动）", "priority": "B",
        "keywords": "测绘法宣传日;青海;国家版图意识",
        "note": "省级宣传周活动报道（收录例外）",
    },
    {
        "url": "https://www.mnr.gov.cn/zt/hd/chfxcr/2026chfxcr/gdhd/202609/t20260901_2937369.html",
        "board": "技术应用类", "business": "测绘地理信息公共服务",
        "level": "外省", "province": "甘肃",
        "unit": "自然资源部（2026年测绘法宣传日专题·各地活动）", "priority": "B",
        "keywords": "测绘法宣传日;甘肃;主场活动",
        "note": "省级宣传周主场活动报道（收录例外）",
    },
]


def best_block():
    spec = importlib.util.spec_from_file_location(
        "detail", os.path.join(os.path.dirname(os.path.abspath(__file__)), "04_fetch_details.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.best_block


def fetch(url, block):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        if (resp.headers.get("Content-Encoding") or "").lower() == "gzip":
            import gzip
            raw = gzip.decompress(raw)
    for enc in ("utf-8", "gb18030"):
        try:
            page = raw.decode(enc)
            break
        except UnicodeDecodeError:
            page = raw.decode("utf-8", "ignore")
    title = ""
    for pat in (r"(?is)<h1[^>]*>(.*?)</h1>", r"(?is)<title[^>]*>(.*?)</title>"):
        m = re.search(pat, page)
        if m:
            t = re.sub(r"\s+", " ", strip_html(m.group(1))).strip()
            t = re.sub(r"[-—|]{1,2}(?:宁夏频道|人民网|中国.*网).*$", "", t).strip()
            if t:
                title = t
                break
    if not title:                      # 兜底：取正文首行
        title = (block(page) or "").strip().split("\n")[0][:60]
    text = block(page) or ""
    plain = strip_html(page)
    date = norm_date(text[:400]) or norm_date(plain[:1500])
    return title, date, text or plain


def main():
    block = best_block()
    details, includes = [], []
    for item in MANUAL:
        title, date, text = fetch(item["url"], block)
        print(f"[{item['unit']}] {title[:50]} | {date} | 正文 {len(text)} 字")
        details.append({
            "url": item["url"], "final_url": item["url"], "title": title, "title_page": title,
            "date_page": date, "date_list": date, "source_id": "manual",
            "source_name": item["unit"], "level": item["level"],
            "carrier": WL.site_type(item["url"]) or "官网", "text": text, "text_len": len(text),
            "http_ok": bool(text),
        })
        sel = dict(item)
        sel.update({
            "module": "跨界融合与产业", "title": title, "source_name": item["unit"],
            "source_type": WL.site_type(item["url"]) or "主管部门官网",
            "source_url_checked": item["url"], "date_override": date,
            "match": item["url"].split("?")[0],
            "summary": re.sub(r"\s+", " ", text)[:180],
            "manual": True,
        })
        includes.append(sel)
    save_json(os.path.join(RAW, "manual_detail.json"), details)
    save_json(os.path.join(RAW, "manual_includes.json"), includes)
    print(f"已写入语料 {len(details)} 条、选目补丁 {len(includes)} 条")


if __name__ == "__main__":
    main()
