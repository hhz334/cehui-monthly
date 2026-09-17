# -*- coding: utf-8 -*-
"""浙江省自然资源厅（测绘栏目）+ 浙江省测绘科学技术研究院公众号 取文工具。

四条通道：
  A. 浙江政务统一检索（search.zj.gov.cn）—— 全站全文检索，返回 JSON，含正文
  B. 浙江厅栏目列表（jpaas build/unit）—— 按栏目取完整列表（JS 动态列表的破解点）
  C. 浙江厅文章页 —— 静态 HTML，取标题/发布日期/来源/正文
  D. 公众号「浙江省测绘科学技术研究院」—— 搜狗微信检索 → 还原链接 → 抽正文

用法：
  python 22_zhejiang.py a-search   --q 测绘 --cate 动态信息 --pages 2
  python 22_zhejiang.py b-column   --col 测绘成果使用审批 --pages 2
  python 22_zhejiang.py b-columns
  python 22_zhejiang.py c-article  --url "https://zrzyt.zj.gov.cn/col/.../art_xxx.html"
  python 22_zhejiang.py d-search   --q 浙江省测绘科学技术研究院 --pages 2
  python 22_zhejiang.py d-resolve  --link "/link?url=dn9a_..."
  python 22_zhejiang.py d-article  --url "https://mp.weixin.qq.com/s?src=11&..."
"""
import argparse
import gzip
import importlib.util
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "_raw", "zhejiang")

ZRZYT = "https://zrzyt.zj.gov.cn"
SEARCH = "https://search.zj.gov.cn"

SEARCH_API = SEARCH + "/api-gateway/jpaas-jsearch-web-server/interface/search/app/info"
SERVICE_ID = "YcTOd1ftgC5dxzJ8RhCBN"
SITE = {"websiteid": "330000000000", "webid": "1568"}

CATEGORIES = {
    "全部": "6N89tbnrVTYIQK5jt7q3T",
    "政务服务": "ShhDNU0SGB3DPrgh3GxyA",
    "法规文件": "RD2hFhHjNN8CSHjKEtSUx",
    "动态信息": "VYyQDa265Tnj5A7jf9q6k",
    "机构人事": "JcWYdyk9h9TDZMUT63ts9",
    "政务专题": "26B9ATqNIxOTdzUrTLfPg",
    "公告公示": "E6OnRo9SrojDOf5JGpc7x",
    "信息公开": "pxqXRJ8GOBibTdpvrmvYz",
    "政民互动": "CnN4JKUa9mrCbdJzLAXLt",
    "数据开放": "jPP8PPL77kmFDxqlxYNY1",
    "其他": "ROJC4StewZSmYa3mLLPYs",
}

COLUMNS = {
    "工作动态": 1289955,
    "市县动态": 1070717,
    "行业动态": 1289957,
    "通知公告": 1289924,
    "测绘地理信息(服务页)": 1633746,
    "地理信息管理": 1229767835,
    "测绘成果使用审批": 1229767838,
    "地图审批": 1229768878,
    "测量标志拆迁审批": 1229780615,
    "资质审批": 1229536899,
    "资质审批结果": 1229536892,
}

WX_ACCOUNT = "浙江省测绘科学技术研究院"
WX_BIZ = "MzkzMTAxOTQyMg=="


class Session:
    """带 cookie 的极简会话（仅标准库）。"""

    def __init__(self):
        self.jar = {}
        self.extra_headers = {}

    def header(self, key, value):
        self.extra_headers[key] = value

    def request(self, url, method="GET", data=None, referer=None,
                timeout=40, retries=3, sleep=2.0):
        url = urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=%~")
        body = None
        if data is not None:
            body = urllib.parse.urlencode(data, doseq=True).encode("utf-8")
        last_err = None
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, data=body, method=method)
                req.add_header("User-Agent", UA)
                req.add_header("Accept", "application/json,text/html,*/*;q=0.8")
                req.add_header("Accept-Encoding", "gzip, deflate")
                req.add_header("Accept-Language", "zh-CN,zh;q=0.9")
                if body is not None:
                    req.add_header("Content-Type",
                                   "application/x-www-form-urlencoded;charset=UTF-8")
                if referer:
                    req.add_header("Referer", referer)
                for k, v in self.extra_headers.items():
                    req.add_header(k, v)
                if self.jar:
                    req.add_header("Cookie", "; ".join(
                        "%s=%s" % (k, v) for k, v in self.jar.items()))
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw = resp.read()
                    enc = (resp.headers.get("Content-Encoding") or "").lower()
                    if "gzip" in enc:
                        raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
                    for sc in resp.headers.get_all("Set-Cookie") or []:
                        kv = sc.split(";", 1)[0]
                        if "=" in kv:
                            k, v = kv.split("=", 1)
                            self.jar[k.strip()] = v.strip()
                    return resp.geturl(), raw
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                time.sleep(sleep * (attempt + 1))
        raise RuntimeError("请求失败: %s :: %s" % (url, last_err))

    def get_text(self, url, referer=None, timeout=40, retries=3):
        _, raw = self.request(url, referer=referer, timeout=timeout, retries=retries)
        for enc in ("utf-8", "gb18030"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", "ignore")

    def get_json(self, url, referer=None, timeout=40, retries=3):
        return json.loads(self.get_text(url, referer=referer,
                                        timeout=timeout, retries=retries))


def strip_html(fragment, keep_breaks=True):
    if not fragment:
        return ""
    txt = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", fragment)
    if keep_breaks:
        txt = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h[1-6]>", "\n", txt)
    txt = re.sub(r"(?s)<[^>]+>", "", txt)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&quot;", '"'),
                 ("&#39;", "'"), ("&lt;", "<"), ("&gt;", ">"),
                 ("&ldquo;", "\u201c"), ("&rdquo;", "\u201d")):
        txt = txt.replace(a, b)
    txt = re.sub(r"[ \t\u3000]+", " ", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt.strip()


# --------------------------------------------------------------------------
# A. 浙江政务统一检索（search.zj.gov.cn）
# --------------------------------------------------------------------------
class ZjSearch:
    """省政务网站统一检索。返回 JSON，含标题、URL、栏目、作者、正文（vc_content）。"""

    def __init__(self, site=None):
        self.s = Session()
        self.s.header("Referer", SEARCH + "/")
        self.site = dict(site or SITE)

    def search(self, q, cate="动态信息", page=1, page_size=20, sort_type="2",
               pos="", begin=None, end=None, site=None):
        cfg = dict(site or self.site)
        params = {
            "q": q,
            "serviceId": SERVICE_ID,
            "cateid": CATEGORIES.get(cate, cate),
            "p": str(page),
            "pg": str(page_size),
            "sortType": sort_type,
            "pos": pos,
            "websiteid": cfg.get("websiteid", ""),
            "_cus_eq_webid": cfg.get("webid", ""),
        }
        if begin:
            params["begin"] = begin
            params["timetype"] = "timeqb"
        if end:
            params["end"] = end
        qs = urllib.parse.urlencode(params)
        data = self.s.get_json(SEARCH_API + "?" + qs,
                               referer=SEARCH + "/")
        blocks = (data.get("data") or {}).get("appSearchResultBeanList") or []
        if not blocks:
            return {"q": q, "cate": cate, "page": page, "total": 0, "items": []}
        block = blocks[0]
        result = block.get("mapSearchResult") or {}
        items = []
        for hit in result.get("items") or []:
            d = hit.get("data") or {}
            items.append({
                "title": strip_html(d.get("title_h") or d.get("title") or "",
                                    keep_breaks=False),
                "url": d.get("url"),
                "site": d.get("webname"),
                "channel": d.get("tag"),
                "module": d.get("module"),
                "columnId": d.get("column"),
                "author": d.get("author"),
                "keywords": d.get("keyword"),
                "publishTime": d.get("checktime") and time.strftime(
                    "%Y-%m-%d", time.localtime(int(d["checktime"]) / 1000)) or "",
                "content": d.get("vc_content") or "",
                "contentText": strip_html(d.get("vc_content") or ""),
            })
        return {"q": q, "cate": block.get("category", {}).get("categoryName", cate),
                "page": page, "total": result.get("total"), "items": items}


# --------------------------------------------------------------------------
# B. 浙江厅栏目列表（jpaas build/unit）
# --------------------------------------------------------------------------
class ZrzytColumn:
    """JS 动态列表的破解点：栏目页里的 queryData 指向 build/unit 接口。"""

    def __init__(self):
        self.s = Session()

    def meta(self, col_id):
        """从栏目页解析 queryData（含 tplSetId / tagId），这些参数因栏目而异。"""
        url = "%s/col/col%s/index.html" % (ZRZYT, col_id)
        html = self.s.get_text(url, referer=ZRZYT + "/")
        m = re.search(r'queryData="([^"]+)"', html)
        if not m:
            raise RuntimeError("栏目 col%s 没有列表单元（可能是服务导航页）" % col_id)
        return url, json.loads(m.group(1).replace("'", '"'))

    def list(self, col_id, page=1, page_size=20):
        page_url, q = self.meta(col_id)
        q = dict(q)
        q["paramJson"] = json.dumps(
            {"pageNo": page, "pageSize": page_size, "search": ""}, ensure_ascii=False)
        api = ZRZYT + "/api-gateway/jpaas-publish-server/front/page/build/unit"
        data = self.s.get_json(api + "?" + urllib.parse.urlencode(q),
                               referer=page_url)
        html = ((data.get("data") or {}).get("html")) or ""
        items = []
        for m in re.finditer(
                r'href="([^"]*art/\d{4}/art_[0-9a-f]+\.html)"[^>]*>'
                r'(?:<i></i>)?([\s\S]{0,120}?)</a>\s*<span[^>]*>([^<]*)</span>', html):
            items.append({
                "title": strip_html(m.group(2), keep_breaks=False),
                "url": m.group(1) if m.group(1).startswith("http")
                       else ZRZYT + m.group(1),
                "publishTime": m.group(3).strip(),
            })
        return {"columnId": col_id, "page": page, "count": len(items), "items": items}


# --------------------------------------------------------------------------
# C. 浙江厅文章页
# --------------------------------------------------------------------------
class ZrzytArticle:
    """文章页为静态 HTML：标题在 .wzytitle，正文在 <div id="zoom">。"""

    def __init__(self):
        self.s = Session()

    def fetch(self, url):
        html = self.s.get_text(url, referer=ZRZYT + "/")
        title = ""
        m = re.search(r'(?s)class="title wzytitle"[^>]*>(.*?)</td>', html)
        if m:
            title = strip_html(m.group(1), keep_breaks=False)
        if not title:
            title = strip_html(re.search(r"<title>([\s\S]*?)</title>", html)
                               .group(1), keep_breaks=False)
        body = ""
        m = re.search(r'(?s)<div id="zoom"[^>]*>(.*?)</div>\s*</td>', html)
        if not m:
            m = re.search(r'(?s)<div id="zoom"[^>]*>(.*?)</div>', html)
        if m:
            body = m.group(1)
        pub = ""
        m = re.search(r'<meta name="PubDate" content="([^"]*)"', html)
        if m:
            pub = m.group(1)
        source = ""
        m = re.search(r"信息来源：\s*([^\s<]{2,30})", html)
        if m:
            source = m.group(1)
        col = ""
        m = re.search(r'<meta name="ColId" content="([^"]*)"', html)
        if m:
            col = m.group(1)
        return {"url": url, "title": title, "publishTime": pub,
                "source": source, "columnId": col,
                "content": body, "contentText": strip_html(body)}


# --------------------------------------------------------------------------
# D. 公众号（搜狗微信）—— 复用 21_taibo.py 的实现
# --------------------------------------------------------------------------
def _load_sogou_class():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "21_taibo.py")
    spec = importlib.util.spec_from_file_location("taibo_helper", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.WeixinSogou


class InstituteWeChat:
    """浙江省测绘科学技术研究院 公众号。"""

    def __init__(self):
        self.wx = _load_sogou_class()()

    def search(self, q=None, page=1):
        return self.wx.search(q or WX_ACCOUNT, page)

    def resolve(self, link):
        return self.wx.resolve(link)

    def article(self, url):
        return self.wx.article(url)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def _dump(obj, name):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description="浙江厅测绘栏目 + 省测绘科研院公众号 取文工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("a-search", help="统一检索（返回 JSON，含正文）")
    p.add_argument("--q", required=True)
    p.add_argument("--cate", default="动态信息", help="分类：%s" % "/".join(CATEGORIES))
    p.add_argument("--pages", type=int, default=1)
    p.add_argument("--page-size", type=int, default=20)
    p.add_argument("--begin", help="起始日期 YYYY-MM-DD")
    p.add_argument("--end", help="结束日期 YYYY-MM-DD")
    p.add_argument("--webid", default=SITE["webid"], help="站点 webId，留空=全省")

    p = sub.add_parser("b-column", help="栏目列表（jpaas build/unit）")
    p.add_argument("--col", required=True, help="栏目名或 pageId")
    p.add_argument("--pages", type=int, default=1)
    p.add_argument("--page-size", type=int, default=20)

    sub.add_parser("b-columns", help="列出已知栏目 ID")

    p = sub.add_parser("c-article", help="浙江厅文章页正文")
    p.add_argument("--url", required=True)

    p = sub.add_parser("d-search", help="公众号：搜狗微信检索")
    p.add_argument("--q", default=WX_ACCOUNT)
    p.add_argument("--pages", type=int, default=1)
    p.add_argument("--sleep", type=float, default=6.0)

    p = sub.add_parser("d-resolve", help="公众号：还原搜狗链接")
    p.add_argument("--link", required=True)

    p = sub.add_parser("d-article", help="公众号：单篇正文")
    p.add_argument("--url", required=True)

    args = ap.parse_args(argv)

    if args.cmd == "a-search":
        site = {"websiteid": SITE["websiteid"], "webid": args.webid}
        zs, all_items, total = ZjSearch(site), [], None
        for page in range(1, args.pages + 1):
            res = zs.search(args.q, args.cate, page, args.page_size,
                            begin=args.begin, end=args.end)
            total = res["total"]
            all_items.extend(res["items"])
            if not res["items"]:
                break
            time.sleep(1.5)
        out = {"q": args.q, "cate": args.cate, "total": total,
               "count": len(all_items), "begin": args.begin, "end": args.end,
               "items": all_items}
        name = _dump(out, "zj_search_%s.json" % args.q)
        print("检索「%s」[%s] 命中%s条（取回%d） -> %s"
              % (args.q, args.cate, total, len(all_items), name))
        for it in all_items[:20]:
            print("  %s\t%s\t%s" % (it["publishTime"], it["title"], it["url"]))
        return 0

    if args.cmd == "b-column":
        col = COLUMNS.get(args.col, args.col)
        zc, all_items = ZrzytColumn(), []
        for page in range(1, args.pages + 1):
            res = zc.list(col, page, args.page_size)
            all_items.extend(res["items"])
            if not res["items"]:
                break
            time.sleep(1.5)
        out = {"columnId": col, "count": len(all_items), "items": all_items}
        name = _dump(out, "zj_col%s.json" % col)
        print("栏目 col%s 取回%d条 -> %s" % (col, len(all_items), name))
        for it in all_items[:20]:
            print("  %s\t%s\t%s" % (it["publishTime"], it["title"], it["url"]))
        return 0

    if args.cmd == "b-columns":
        for k, v in COLUMNS.items():
            print("%-24s %s" % (k, v))
        return 0

    if args.cmd == "c-article":
        res = ZrzytArticle().fetch(args.url)
        name = _dump(res, "zj_article.json")
        print("%s\t%s\t来源=%s\t正文%d字 -> %s"
              % (res["publishTime"], res["title"], res["source"],
                 len(res["contentText"]), name))
        return 0

    if args.cmd == "d-search":
        inst = InstituteWeChat()
        all_items = []
        for page in range(1, args.pages + 1):
            res = inst.search(args.q, page)
            all_items.extend(res["items"])
            print("第%d页 %d条（累计%d）" % (page, len(res["items"]), len(all_items)))
            if not res["items"]:
                break
            if page < args.pages:
                time.sleep(args.sleep)
        name = _dump({"query": args.q, "count": len(all_items), "items": all_items},
                     "wx_sogou_%s.json" % args.q)
        print("搜狗微信「%s」共%d条 -> %s" % (args.q, len(all_items), name))
        for it in all_items[:20]:
            print("  %s\t%s\t%s" % (it["date"], it["account"], it["title"]))
        return 0

    if args.cmd == "d-resolve":
        print(InstituteWeChat().resolve(args.link))
        return 0

    if args.cmd == "d-article":
        res = InstituteWeChat().article(args.url)
        name = _dump(res, "wx_article.json")
        print("%s\t%s\t正文%d字 -> %s"
              % (res["account"], res["title"], len(res["contentText"]), name))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
