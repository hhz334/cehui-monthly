# -*- coding: utf-8 -*-
"""按来源配置抓取本期窗口内的测绘地理信息资讯，落 _raw/<source>.json（窗口取自 period.json）。"""
import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_utils import RAW, absolute, ensure_dir, get_text, http_get, norm_date, save_json, strip_html  # noqa: E402
from period_config import P  # noqa: E402

FROM, TO = P.window_from, P.window_to

SOURCES = [
    # ---------- 福建（第一优先） ----------
    {
        "id": "fjt_was5", "name": "福建省自然资源厅", "level": "福建", "carrier": "官网",
        "kind": "was5", "base": "https://zrzyt.fujian.gov.cn/",
        "channel": "267424", "classsql": "chnlid=19805", "max_pages": 12, "prepage": 50,
    },
    {
        "id": "fjch_ywdt", "name": "福建省测绘地理信息发展中心", "level": "福建", "carrier": "官网",
        "kind": "list", "base": "https://www.fjch.org.cn/xwdt/ywdt/",
        "pages": ["https://www.fjch.org.cn/xwdt/ywdt/",
                  "https://www.fjch.org.cn/xwdt/ywdt/index_{n}.htm"], "max_pages": 5,
        "article_re": r"/20\d{4}/t\d{8}_\d+\.htm",
    },
    {
        "id": "fjchxh", "name": "福建省测绘地理信息学会", "level": "福建", "carrier": "官网",
        "kind": "list", "base": "https://www.fjchxh.cn/",
        "pages": ["https://www.fjchxh.cn/xhyw"], "max_pages": 1,
        "article_re": r"/newsinfo/\d+\.html",
    },
    # ---------- 部级 / 国家级 ----------
    {
        "id": "mnr_ch", "name": "自然资源部（测绘）", "level": "部级", "carrier": "官网",
        "kind": "list", "base": "https://www.mnr.gov.cn/dt/ch/",
        "pages": ["https://www.mnr.gov.cn/dt/ch/", "https://www.mnr.gov.cn/dt/ch/index_{n}.html"],
        "max_pages": 6, "article_re": r"t\d{8}_\d+\.html",
    },
    {
        "id": "mnr_ywbb", "name": "自然资源部（要闻播报）", "level": "部级", "carrier": "官网",
        "kind": "list", "base": "https://www.mnr.gov.cn/dt/ywbb/",
        "pages": ["https://www.mnr.gov.cn/dt/ywbb/", "https://www.mnr.gov.cn/dt/ywbb/index_{n}.html"],
        "max_pages": 4, "article_re": r"t\d{8}_\d+\.html",
    },
    {
        "id": "mnr_dfdt", "name": "自然资源部（地方动态）", "level": "外省", "carrier": "官网",
        "kind": "list", "base": "https://www.mnr.gov.cn/dt/dfdt/",
        "pages": ["https://www.mnr.gov.cn/dt/dfdt/", "https://www.mnr.gov.cn/dt/dfdt/index_{n}.html"],
        "max_pages": 4, "article_re": r"t\d{8}_\d+\.html",
    },
    {
        "id": "csgpc_xhdt", "name": "中国测绘学会（学会动态）", "level": "部级", "carrier": "官网",
        "kind": "list", "base": "https://www.csgpc.org/list/107.html",
        "pages": ["https://www.csgpc.org/list/107.html"], "max_pages": 1,
        "article_re": r"/detail/\d+\.html",
    },
    {
        # 中国测绘学会“论文摘选”：2026-09-17 起停用（前沿论文例外取消），保留配置仅作留档，
        # 采集到的条目在 31 号选目阶段按 source_id 排除，不参与候选。
        "id": "csgpc_lwzx", "name": "中国测绘学会（论文摘选）", "level": "行业与官媒", "carrier": "官网",
        "kind": "list", "base": "https://www.csgpc.org/list/2902.html",
        "pages": ["https://www.csgpc.org/list/2902.html"], "max_pages": 1,
        "article_re": r"/detail/\d+\.html",
    },
    {
        "id": "cagis_cyyw", "name": "中国地理信息产业协会（产业要闻）", "level": "部级", "carrier": "官网",
        "kind": "list", "base": "https://www.cagis.org.cn/Lists/index/cid/8.html",
        "pages": ["https://www.cagis.org.cn/Lists/index/cid/8.html",
                  "https://www.cagis.org.cn/Lists/index/cid/8/p/{n}.html"],
        "max_pages": 3, "article_re": r"/Lists/content/id/\d+\.html",
    },
    {
        "id": "ngcc_ywcg", "name": "国家基础地理信息中心（业务成果）", "level": "部级", "carrier": "官网",
        "kind": "list", "base": "https://www.ngcc.cn/xwzx/ywcg/",
        "pages": ["https://www.ngcc.cn/xwzx/ywcg/", "https://www.ngcc.cn/xwzx/ywcg/index_{n}.html"],
        "max_pages": 4, "article_re": r"t\d{8}_\d+\.html",
    },
    {
        "id": "casm_tzgg", "name": "中国测绘科学研究院（通知公告）", "level": "部级", "carrier": "官网",
        "kind": "list", "base": "http://www.casm.ac.cn/",
        "pages": ["http://www.casm.ac.cn/xxgk/tzgg/", "http://www.casm.ac.cn/xxgk/tzgg/index_{n}.html"],
        "max_pages": 3, "article_re": r"/20\d{6}/t\d{8}_\d+\.html|/\d{6}/\d{1,2}/\d+\.html",
    },
    # ---------- 重点外省 ----------
    {
        "id": "sd_dnr", "name": "山东省自然资源厅", "level": "外省", "carrier": "官网",
        "kind": "list", "base": "http://dnr.shandong.gov.cn/xwdt_324/xtyw_29240/",
        "pages": ["http://dnr.shandong.gov.cn/xwdt_324/xtyw_29240/",
                  "http://dnr.shandong.gov.cn/xwdt_324/xtyw_29240/index_{n}.html"],
        "max_pages": 4, "article_re": r"t\d{8}_\d+\.html",
    },
    {
        "id": "sd_cehui", "name": "山东省国土测绘院", "level": "外省", "carrier": "官网",
        "kind": "list", "base": "http://www.shandongcehui.cn/",
        "pages": ["http://www.shandongcehui.cn/"], "max_pages": 2,
        "article_re": r"\.html?$|\.htm$",
    },
    {
        "id": "js_dnr", "name": "江苏省自然资源厅", "level": "外省", "carrier": "官网",
        "kind": "list", "base": "http://zrzy.jiangsu.gov.cn/xwzx/xwbb/",
        "pages": ["http://zrzy.jiangsu.gov.cn/xwzx/xwbb/"], "max_pages": 3,
        "article_re": r"/xwzx/\w+/\d{4}/\d{2}/\d+\.html",
    },
    {
        "id": "zj_dnr", "name": "浙江省自然资源厅（测绘地理信息）", "level": "外省", "carrier": "官网",
        "kind": "list", "base": "https://zrzyt.zj.gov.cn/col/col1633746/index.html",
        "pages": ["https://zrzyt.zj.gov.cn/col/col1633746/index.html",
                  "https://zrzyt.zj.gov.cn/col/col1633746/index_{n}.html"], "max_pages": 3,
        "article_re": r"/art/\d{4}/\d{1,2}/\d{1,2}/art_\d+_\d+\.html",
    },
    {
        "id": "gd_dnr", "name": "广东省自然资源厅（政务动态）", "level": "外省", "carrier": "官网",
        "kind": "list", "base": "https://nr.gd.gov.cn/xwdtnew/zwdt/index.html",
        "pages": ["https://nr.gd.gov.cn/xwdtnew/zwdt/index.html"], "max_pages": 3,
        "article_re": r"/content/post_\d+\.html",
    },
    {
        "id": "ah_dnr", "name": "安徽省自然资源厅（要闻联播）", "level": "外省", "carrier": "官网",
        "kind": "list", "base": "https://zrzyt.ah.gov.cn/xwdt/ywlb/index.html",
        "pages": ["https://zrzyt.ah.gov.cn/xwdt/ywlb/index.html"], "max_pages": 3,
        "article_re": r"/xwdt/\w+/\d+\.html",
    },
    {
        "id": "hubei_dnr", "name": "湖北省自然资源厅（自然资源要闻）", "level": "外省", "carrier": "官网",
        "kind": "list", "base": "https://zrzyt.hubei.gov.cn/bmdt/zrzyyw/",
        "pages": ["https://zrzyt.hubei.gov.cn/bmdt/zrzyyw/",
                  "https://zrzyt.hubei.gov.cn/bmdt/zrzyyw/index_{n}.shtml"],
        "max_pages": 3, "article_re": r"/bmdt/\w+/\d+/\w+\.shtml",
    },
    {
        "id": "snsm_sjyw", "name": "陕西测绘地理信息局（省局要闻）", "level": "外省", "carrier": "官网",
        "kind": "list", "base": "http://snsm.mnr.gov.cn/Information/Section/1014",
        "pages": ["http://snsm.mnr.gov.cn/Information/Section/1014",
                  "http://snsm.mnr.gov.cn/Information/Section/1014/{n}"],
        "max_pages": 3, "article_re": r"/Information/news/\d+",
    },
    {
        "id": "snsm_hydt", "name": "陕西测绘地理信息局（行业动态）", "level": "外省", "carrier": "官网",
        "kind": "list", "base": "http://snsm.mnr.gov.cn/Information/Section/1015",
        "pages": ["http://snsm.mnr.gov.cn/Information/Section/1015",
                  "http://snsm.mnr.gov.cn/Information/Section/1015/{n}"],
        "max_pages": 3, "article_re": r"/Information/news/\d+",
    },
    {
        "id": "scsm_sjyw", "name": "四川测绘地理信息局（省局要闻）", "level": "外省", "carrier": "官网",
        "kind": "list", "base": "http://scsm.mnr.gov.cn/info/iList.jsp?cat_id=25295",
        "pages": ["http://scsm.mnr.gov.cn/info/iList.jsp?cat_id=25295"], "max_pages": 2,
        "article_re": r"/(dt|zsdw)/\w+/\d+\.htm",
    },
    {
        "id": "scsm_hydt", "name": "四川测绘地理信息局（行业动态）", "level": "外省", "carrier": "官网",
        "kind": "list", "base": "http://scsm.mnr.gov.cn/info/iList.jsp?cat_id=25296",
        "pages": ["http://scsm.mnr.gov.cn/info/iList.jsp?cat_id=25296"], "max_pages": 2,
        "article_re": r"/(dt|zsdw)/\w+/\d+\.htm",
    },
    # ---------- 自然资源部测绘发展研究中心 ----------
    {
        "id": "drcmnr_zxxw", "name": "自然资源部测绘发展研究中心（中心新闻）", "level": "部级", "carrier": "官网",
        "kind": "list", "base": "https://www.drcmnr.cn/zxxw/index.jhtml",
        "pages": ["https://www.drcmnr.cn/zxxw/index.jhtml",
                  "https://www.drcmnr.cn/zxxw/index_{n}.jhtml"],
        "max_pages": 4, "article_re": r"/zxxw/\d+\.jhtml",
    },
    {
        "id": "drcmnr_xyxw", "name": "自然资源部测绘发展研究中心（行业新闻）", "level": "部级", "carrier": "官网",
        "kind": "list", "base": "https://www.drcmnr.cn/xyxw/index.jhtml",
        "pages": ["https://www.drcmnr.cn/xyxw/index.jhtml",
                  "https://www.drcmnr.cn/xyxw/index_{n}.jhtml"],
        "max_pages": 4,
        # 该栏目为转载汇编，条目多指向部官网与视频站；公众号链接不作来源
        "article_re": r"/xyxw/\d+\.jhtml|t\d{8}_\d+\.html?$",
    },
    {
        "id": "drcmnr_tzgg", "name": "自然资源部测绘发展研究中心（通知公告）", "level": "部级", "carrier": "官网",
        "kind": "list", "base": "https://www.drcmnr.cn/tzgg/index.jhtml",
        "pages": ["https://www.drcmnr.cn/tzgg/index.jhtml",
                  "https://www.drcmnr.cn/tzgg/index_{n}.jhtml"],
        "max_pages": 3, "article_re": r"/tzgg/\d+\.jhtml",
    },
    {
        "id": "drcmnr_yjbg", "name": "自然资源部测绘发展研究中心（研究报告）", "level": "部级", "carrier": "官网",
        "kind": "list", "base": "https://www.drcmnr.cn/yjbg/index.jhtml",
        "pages": ["https://www.drcmnr.cn/yjbg/index.jhtml"], "max_pages": 2,
        "article_re": r"/yjbg/\d+\.jhtml",
    },
    {
        "id": "drcmnr_fzyjdt", "name": "自然资源部测绘发展研究中心（发展研究动态）", "level": "部级", "carrier": "官网",
        "kind": "list", "base": "https://www.drcmnr.cn/fzyjdt/index.jhtml",
        "pages": ["https://www.drcmnr.cn/fzyjdt/index.jhtml",
                  "https://www.drcmnr.cn/fzyjdt/index_{n}.jhtml"],
        "max_pages": 3, "article_re": r"/fzyjdt/\d+\.jhtml",
    },
    {
        "id": "drcmnr_zcfg", "name": "自然资源部测绘发展研究中心（政策法规）", "level": "部级", "carrier": "官网",
        "kind": "list", "base": "https://www.drcmnr.cn/zcfg/index.jhtml",
        "pages": ["https://www.drcmnr.cn/zcfg/index.jhtml",
                  "https://www.drcmnr.cn/zcfg/index_{n}.jhtml"],
        "max_pages": 2, "article_re": r"/zcfg/\d+\.jhtml",
    },
    {
        "id": "drcmnr_zcjd", "name": "自然资源部测绘发展研究中心（政策解读）", "level": "部级", "carrier": "官网",
        "kind": "list", "base": "https://www.drcmnr.cn/zcjd/index.jhtml",
        "pages": ["https://www.drcmnr.cn/zcjd/index.jhtml"], "max_pages": 2,
        "article_re": r"/zcjd/\d+\.jhtml",
    },
    {
        "id": "drcmnr_zktz", "name": "自然资源部测绘发展研究中心（智库通知）", "level": "部级", "carrier": "官网",
        "kind": "list", "base": "https://www.drcmnr.cn/zktz/index.jhtml",
        "pages": ["https://www.drcmnr.cn/zktz/index.jhtml"], "max_pages": 2,
        "article_re": r"/zktz/\d+\.jhtml",
    },
    # ---------- 部级专题：测绘法宣传日暨国家版图意识宣传周 ----------
    {
        "id": "mnr_zt_chfxcr", "name": "自然资源部（2026年测绘法宣传日暨国家版图意识宣传周专题）",
        "level": "部级", "carrier": "官网站",
        "kind": "list", "base": "https://www.mnr.gov.cn/zt/hd/chfxcr/2026chfxcr/",
        "pages": ["https://www.mnr.gov.cn/zt/hd/chfxcr/2026chfxcr/",
                  "https://www.mnr.gov.cn/zt/hd/chfxcr/2026chfxcr/tpsp/",
                  "https://www.mnr.gov.cn/zt/hd/chfxcr/2026chfxcr/gdhd/"],
        "max_pages": 1, "article_re": r"t\d{8}_\d+\.html",
    },
    # ---------- 国际 ----------
    {
        "id": "fig_news", "name": "FIG（国际测量师联合会）", "level": "国际", "carrier": "官网",
        "kind": "list", "base": "https://www.fig.net/news/",
        "pages": ["https://www.fig.net/news/"], "max_pages": 1,
        "article_re": r"/news/|/newsroom/",
    },
    {
        "id": "isprs_news", "name": "ISPRS（国际摄影测量与遥感学会）", "level": "国际", "carrier": "官网",
        "kind": "list", "base": "https://www.isprs.org/news/",
        "pages": ["https://www.isprs.org/news/"], "max_pages": 1,
        "article_re": r"/news/|/newsletter/",
    },
]


def date_from_href(href):
    m = re.search(r"t(20\d{2})(\d{2})(\d{2})_", href)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"/(20\d{2})/(\d{1,2})/", href)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-01"
    return ""


def page_urls_of(src):
    if "{n}" in src["pages"][0]:
        return [src["pages"][0].format(n=n) for n in range(1, src["max_pages"] + 1)]
    urls = [src["pages"][0]]
    if len(src["pages"]) > 1:
        urls += [src["pages"][1].format(n=n) for n in range(1, src["max_pages"])]
    return urls


def harvest_list(src):
    """通用列表页抓取：标题 + 链接 + 列表页可见日期。"""
    from lxml import html as LH
    items, seen = [], set()
    for page_url in page_urls_of(src):
        try:
            final, page = get_text(page_url)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! 列表失败 {page_url} :: {exc}")
            continue
        doc = LH.fromstring(page)
        page_hits = 0
        for a in doc.iter("a"):
            href = a.get("href") or ""
            if not href or href.startswith(("javascript", "#")):
                continue
            full = absolute(final, href)
            if not re.search(src["article_re"], full):
                continue
            title = re.sub(r"\s+", " ", a.text_content() or "").strip()
            title = re.sub(r"^[·•\s]*(?:\d{1,3})[\s.、]+(?=[^\d])", "", title)   # 去掉列表序号
            title = re.sub(r"\s*20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}(\s+\d{1,2}:\d{2}(:\d{2})?)?\s*$", "", title)
            title = title.strip()
            if len(title) < 8:
                continue
            node, ctx = a, ""
            for _ in range(4):
                node = node.getparent()
                if node is None:
                    break
                if node.tag in ("li", "tr", "dd", "dl", "p", "div"):
                    ctx = re.sub(r"\s+", " ", node.text_content() or "")[:200]
                    break
            ctx_dates = set(re.findall(r"20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}", ctx))
            ctx_date = norm_date(ctx) if len(ctx_dates) <= 1 else ""
            date = norm_date(title) or norm_date(href) or ctx_date or date_from_href(full)
            key = full.split("?")[0]
            if key in seen:
                continue
            seen.add(key)
            if date and (date < FROM or date > TO):
                continue
            page_hits += 1
            items.append({"title": title, "url": full, "date_list": date, "source_id": src["id"],
                          "source_name": src["name"], "level": src["level"], "carrier": src["carrier"]})
        print(f"  {page_url} -> {page_hits} 条")
    return items


def harvest_was5(src):
    """福建省自然资源厅站内检索接口，直接返回结构化 JSON。"""
    items, seen = [], set()
    base = src["base"] + "was5/web/search"
    for page in range(1, src["max_pages"] + 1):
        params = {
            "channelid": src["channel"], "templet": "advsch.jsp",
            "sortfield": "-docorderpri,-docreltime", "classsql": src["classsql"],
            "prepage": str(src["prepage"]), "page": str(page), "searchWord": "", "years": "",
        }
        url = base + "?" + urllib.parse.urlencode(params)
        try:
            _, raw = http_get(url, referer=src["base"], timeout=60)
            data = json.loads(raw.decode("utf-8", "ignore"), strict=False)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! 检索失败 page={page} :: {exc}")
            continue
        docs = data.get("docs", [])
        if not docs:
            break
        oldest = ""
        for doc in docs:
            date = norm_date(doc.get("time") or "")
            title = (doc.get("title") or "").strip()
            link = (doc.get("url") or "").strip()
            if not title or not link:
                continue
            if date and (not oldest or date < oldest):
                oldest = date
            key = link.split("?")[0]
            if key in seen:
                continue
            seen.add(key)
            if date and (date < FROM or date > TO):
                continue
            items.append({
                "title": title, "url": link, "date_list": date,
                "source_name": src["name"], "source_id": src["id"],
                "level": src["level"], "carrier": src["carrier"],
                "origin": (doc.get("src") or "").strip(),
                "content": strip_html(doc.get("content") or ""),
                "pubtime": doc.get("pubtime") or "",
            })
        print(f"  page {page} -> 累计 {len(items)} 条（本页最早 {oldest or '未知'}）")
        if oldest and oldest < FROM:
            break
    return items


def main():
    ensure_dir(RAW)
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    for src in SOURCES:
        if only and src["id"] not in only:
            continue
        print(f"### {src['name']} ({src['id']})")
        items = harvest_was5(src) if src["kind"] == "was5" else harvest_list(src)
        save_json(os.path.join(RAW, f"{src['id']}.json"), items)
        print(f"  => 保存 {len(items)} 条")


if __name__ == "__main__":
    main()
