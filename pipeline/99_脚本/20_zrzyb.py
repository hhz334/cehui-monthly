# -*- coding: utf-8 -*-
"""《中国自然资源报》取文工具（i自然官网 + 数字报 + 公众号单篇）。

三条通道：
  A. i自然官网 api.iziran.net —— 栏目文章列表 + 单篇全文（JSON，无需登录）
  B. 数字报 szb.iziran.net —— 版面/文章全文检索（ES），可查版面 PDF、图片直链
  C. 公众号 mp.weixin.qq.com —— 给定文章 URL 抽取标题/正文（无需登录）

用法：
  python 20_zrzyb.py a-list    --cid 29214 --pages 2
  python 20_zrzyb.py a-article --aid 5494600
  python 20_zrzyb.py b-pages   --date 2026-09-15
  python 20_zrzyb.py b-search  --kw 实景三维 --start <期次起始日> --end <期次截止日> --size 20
  python 20_zrzyb.py b-article --id <esId>
  python 20_zrzyb.py c-wechat  --url "https://mp.weixin.qq.com/s?__biz=..."
"""
import argparse
import datetime as _dt
import gzip
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import uuid

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "_raw", "zrzyb")

IZIRAN_API = "https://api.iziran.net"
IZIRAN_WEB = "https://www.iziran.net"
SZB = "https://szb.iziran.net"
DATA_FILE = SZB + "/dataFile"

# i自然官网栏目 cid（摘自 www.iziran.net/js/index.js 与首页导航）
COLUMNS = {
    "要闻": 29137,
    "自然头条": 29067,
    "测绘": 29214,
    "科技": 29167,
    "基层": 29177,
    "不动产": 29184,
    "用地": 29190,
    "耕保": 29197,
    "地调": 29204,
    "矿产": 29209,
    "海洋": 29219,
    "生态": 29225,
    "法治": 29231,
    "评论": 29243,
    "文化": 29236,
    "时事评论": 29552,
}

# 数字报 site 内的报纸 column id
PAPERS = {"中国自然资源报": 1}


# --------------------------------------------------------------------------
# HTTP 基础（仅标准库）
# --------------------------------------------------------------------------
class Session:
    """带 cookie 的极简会话。"""

    def __init__(self):
        self.jar = {}
        self.extra_headers = {}

    def header(self, key, value):
        self.extra_headers[key] = value

    def _cookie_header(self):
        if not self.jar:
            return None
        return "; ".join("%s=%s" % (k, v) for k, v in self.jar.items())

    def request(self, url, method="GET", data=None, referer=None,
                timeout=40, retries=3, sleep=1.5):
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
                ck = self._cookie_header()
                if ck:
                    req.add_header("Cookie", ck)
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

    def post_form(self, url, data, referer=None, timeout=40, retries=3):
        _, raw = self.request(url, method="POST", data=data, referer=referer,
                              timeout=timeout, retries=retries)
        return json.loads(raw.decode("utf-8", "ignore"))


def strip_html(fragment, keep_breaks=True):
    if not fragment:
        return ""
    txt = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", fragment)
    if keep_breaks:
        txt = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h[1-6]>", "\n", txt)
    txt = re.sub(r"(?s)<[^>]+>", "", txt)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&quot;", '"'),
                 ("&#39;", "'"), ("&lt;", "<"), ("&gt;", ">")):
        txt = txt.replace(a, b)
    txt = re.sub(r"[ \t\u3000]+", " ", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt.strip()


# --------------------------------------------------------------------------
# A. i自然官网（api.iziran.net）
# --------------------------------------------------------------------------
def a_list(cid, pages=1, page_size=20, orderby="", need_fulltext=False):
    """按栏目取文章列表。"""
    s = Session()
    s.header("Referer", IZIRAN_WEB + "/")
    out, last_id, col = [], 0, None
    for page in range(1, pages + 1):
        url = ("%s/api/getArticles?cid=%s&rowNumber=0&lastFileID=%s"
               "&pageNumber=%d&pageSize=%d&imgTop=0&orderby=%s&excids=1,2,3"
               % (IZIRAN_API, cid, last_id, page, page_size, orderby))
        data = s.get_json(url)
        col = data.get("column") or col
        items = data.get("list") or []
        if not items:
            break
        for it in items:
            out.append({
                "fileID": it.get("fileID"),
                "title": it.get("title"),
                "publishTime": it.get("publishTime"),
                "author": it.get("author"),
                "source": it.get("source"),
                "columnName": it.get("columnName"),
                "columnID": it.get("columnID"),
                "url": "%s/news.html?aid=%s" % (IZIRAN_WEB, it.get("fileID")),
                "total": data.get("total"),
            })
        last_id = items[-1].get("fileID") or last_id
    if need_fulltext:
        for rec in out:
            try:
                art = a_article(rec["fileID"])
                rec["content"] = art.get("content", "")
                rec["contentText"] = art.get("contentText", "")
                rec["editor"] = art.get("editor")
            except Exception as exc:  # noqa: BLE001
                rec["error"] = str(exc)
    return {"column": col, "cid": cid, "count": len(out), "articles": out}


def a_article(aid):
    """取单篇全文（含 HTML 正文，公开无需登录）。"""
    s = Session()
    s.header("Referer", "%s/news.html?aid=%s" % (IZIRAN_WEB, aid))
    data = s.get_json("%s/api/getArticle?aid=%s" % (IZIRAN_API, aid))
    data["contentText"] = strip_html(data.get("content", ""))
    return data


# --------------------------------------------------------------------------
# B. 数字报（szb.iziran.net）
# --------------------------------------------------------------------------
class Epaper:
    """数字报刊会话：先 ipLogin 拿匿名会话，再调 /data/query 做全文检索。"""

    def __init__(self, site="iziran"):
        self.s = Session()
        self.identity = str(uuid.uuid4())
        self.s.header("Referer", SZB + "/bz/html/index.html")
        self.s.header("X-Requested-With", "XMLHttpRequest")
        self.s.header("myIdentity", self.identity)
        self.s.header("SITE", site)
        self.s.jar["identity"] = self.identity
        self.login()

    def login(self):
        rd = int(time.time() * 1000)
        return self.s.get_json(
            "%s/user/ipLogin?rd=%d&identity=%s" % (SZB, rd, self.identity),
            referer=SZB + "/bz/html/index.html")

    def query(self, index, query_body):
        return self.s.post_form(
            SZB + "/data/query",
            {"index": index, "query": json.dumps(query_body, ensure_ascii=False)},
            referer=SZB + "/bz/html/index.html")

    @staticmethod
    def _source(hit):
        return hit.get("_source", {}) if isinstance(hit, dict) else {}

    def pages_by_date(self, date, paper_cid=1):
        """某日各版面：含版名、版面大图、PDF 直链。"""
        qb = {
            "from": 0, "size": 999,
            "query": {"bool": {"must": [
                {"term": {"columns.id": paper_cid}},
                {"term": {"bzDate_date_sore": date}},
            ]}},
            "sort": [{"pageIndex_int_sore": {"order": "asc"}}],
        }
        res = self.query("bz_page", qb)
        rows = []
        for hit in res.get("hits", {}).get("hits", []):
            src = self._source(hit)
            rows.append({
                "pageId": hit.get("_id"),
                "bzId": src.get("bzId_no_analyzer_sore"),
                "date": src.get("bzDate_date_sore"),
                "pageNumber": src.get("pageNumber_sore"),
                "pageName": src.get("pageName_sore"),
                "pageIndex": src.get("pageIndex_int_sore"),
                "size": "%sx%s" % (src.get("width_sore"), src.get("height_sore")),
                "pdfUrl": self.file_url(src.get("pdfFilePath_sore")),
                "imageUrl": self.file_url(src.get("imgLFilePath_sore")),
                "thumbUrl": self.file_url(src.get("imgSFilePath_sore")),
            })
        return {"date": date, "paperCid": paper_cid,
                "total": len(rows), "pages": rows}

    def search(self, keyword, start=None, end=None, size=20, frm=0,
               paper_cid=1, field="all"):
        """全文检索。field: all=全文+标题+作者+栏目，title/author/column 用字段精确。"""
        must = [{"term": {"columns.id": paper_cid}}]
        if start or end:
            rng = {}
            if start:
                rng["gte"] = start
            if end:
                rng["lte"] = end
            must.append({"range": {"bzDate_date_sore": rng}})

        if field == "title":
            must.append({"term": {"title_ngram_sore": keyword}})
        elif field == "author":
            must.append({"term": {"author_ngram_sore": keyword}})
        elif field == "column":
            must.append({"term": {"column_ngram_sore": keyword}})
        else:
            script = ("if(doc['split_text_int_sore'].empty){return false;}"
                      "int n=(int)doc['split_text_int_sore'].value;"
                      "StringBuffer b=new StringBuffer();"
                      "for(int x=1;x<=n;x++){String t='text'.concat(String.valueOf(x))"
                      ".concat('_fielddata');if(null!=doc[t]){b.append(doc[t].value);}}"
                      "return b.indexOf(params.a)!=-1;")
            must.append({"bool": {"should": [
                {"term": {"title_ngram_sore": keyword}},
                {"term": {"subtitle_ngram_sore": keyword}},
                {"term": {"author_ngram_sore": keyword}},
                {"term": {"column_ngram_sore": keyword}},
                {"script": {"script": {"inline": script, "lang": "painless",
                                       "params": {"a": keyword}}}},
            ]}})

        qb = {"from": frm, "size": size,
              "query": {"bool": {"must": must}},
              "sort": [{"bzDate_date_sore": {"order": "desc"}}]}
        res = self.query("bz_article", qb)
        hits = res.get("hits", {})
        rows = []
        for hit in hits.get("hits", []):
            src = self._source(hit)
            text = self._full_text(src)
            rows.append({
                "esId": hit.get("_id"),
                "date": src.get("bzDate_date_sore"),
                "pageNumber": src.get("pageNumber_sore"),
                "title": src.get("title_ngram_sore"),
                "subtitle": src.get("subtitle_ngram_sore"),
                "author": src.get("author_ngram_sore"),
                "column": src.get("column_ngram_sore"),
                "pageId": src.get("pageId_no_analyzer_sore"),
                "bzId": src.get("bzId_no_analyzer_sore"),
                "textLength": len(text),
                "contentText": text,
            })
        return {"keyword": keyword, "start": start, "end": end,
                "total": hits.get("total", {}).get("value"), "articles": rows}

    @staticmethod
    def _full_text(src):
        n = src.get("split_text_int_sore") or 0
        try:
            n = int(n)
        except (TypeError, ValueError):
            n = 0
        if n <= 0:
            return src.get("text1_fielddata") or ""
        return "".join(src.get("text%d_fielddata" % x) or ""
                       for x in range(1, n + 1))

    def article_by_id(self, es_id):
        """按 ES _id 取单篇（含全文 text1_fielddata）。"""
        qb = {"from": 0, "size": 1, "query": {"ids": {"values": [es_id]}}}
        res = self.query("bz_article", qb)
        hits = res.get("hits", {}).get("hits", [])
        if not hits:
            return None
        src = self._source(hits[0])
        return {"esId": hits[0].get("_id"),
                "date": src.get("bzDate_date_sore"),
                "title": src.get("title_ngram_sore"),
                "author": src.get("author_ngram_sore"),
                "pageNumber": src.get("pageNumber_sore"),
                "pageId": src.get("pageId_no_analyzer_sore"),
                "contentText": self._full_text(src)}

    @staticmethod
    def file_url(path):
        if not path:
            return None
        return DATA_FILE + urllib.parse.quote(path, safe="/")


# --------------------------------------------------------------------------
# C. 微信公众号单篇
# --------------------------------------------------------------------------
def c_wechat(url):
    """给定 mp.weixin.qq.com 文章链接，抽取标题/公众号名/正文（公开可读）。"""
    s = Session()
    html = s.get_text(url, referer="https://mp.weixin.qq.com/")
    title = ""
    m = re.search(r"var\s+msg_title\s*=\s*'([^']*)'", html)
    if m:
        title = m.group(1)
    if not title:
        m = re.search(r'<meta property="og:title" content="([^"]*)"', html)
        title = m.group(1) if m else ""
    nick = ""
    m = re.search(r'id="js_name"[^>]*>([^<]+)<', html)
    if m:
        nick = m.group(1).strip()
    biz = ""
    m = re.search(r'var\s+biz\s*=\s*"([^"]*)"', html)
    if m:
        biz = m.group(1)
    body = ""
    m = re.search(r'id="js_content"[^>]*>(.*?)</div>\s*<script', html, re.S)
    if not m:
        m = re.search(r'id="js_content"[^>]*>(.*?)</div>', html, re.S)
    if m:
        body = strip_html(m.group(1))
    return {"url": url, "title": title, "account": nick, "biz": biz,
            "contentText": body, "contentLength": len(body)}


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
    ap = argparse.ArgumentParser(description="《中国自然资源报》取文工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("a-list", help="i自然官网：按栏目取列表")
    p.add_argument("--cid", default="29214", help="栏目 id 或名称（测绘/要闻/科技…）")
    p.add_argument("--pages", type=int, default=1)
    p.add_argument("--page-size", type=int, default=20)
    p.add_argument("--fulltext", action="store_true", help="同时抓正文")

    p = sub.add_parser("a-article", help="i自然官网：单篇全文")
    p.add_argument("--aid", required=True)

    p = sub.add_parser("b-pages", help="数字报：某日版面+PDF直链")
    p.add_argument("--date", default=_dt.date.today().isoformat())
    p.add_argument("--paper-cid", type=int, default=1)

    p = sub.add_parser("b-search", help="数字报：全文检索")
    p.add_argument("--kw", required=True)
    p.add_argument("--start")
    p.add_argument("--end")
    p.add_argument("--size", type=int, default=20)
    p.add_argument("--from", dest="frm", type=int, default=0)
    p.add_argument("--field", default="all",
                   choices=["all", "title", "author", "column"])
    p.add_argument("--paper-cid", type=int, default=1)

    p = sub.add_parser("b-article", help="数字报：按 ES _id 取单篇")
    p.add_argument("--id", required=True)

    p = sub.add_parser("c-wechat", help="公众号：单篇抽取")
    p.add_argument("--url", required=True)

    args = ap.parse_args(argv)

    if args.cmd == "a-list":
        cid = COLUMNS.get(args.cid, args.cid)
        res = a_list(cid, args.pages, args.page_size, need_fulltext=args.fulltext)
        name = _dump(res, "iziran_cid%s.json" % cid)
        col = (res["column"] or {}).get("columnName") if res["column"] else cid
        print("栏目=%s 共%d条 -> %s" % (col, res["count"], name))
        for a in res["articles"]:
            print("  %s\t%s\t%s" % (a["publishTime"], a["title"], a["url"]))
        return 0

    if args.cmd == "a-article":
        res = a_article(args.aid)
        name = _dump(res, "iziran_aid%s.json" % args.aid)
        print("%s\t%s\t作者=%s\t正文%d字 -> %s"
              % (res.get("publishTime"), res.get("title"), res.get("author"),
                 len(res.get("contentText") or ""), name))
        return 0

    if args.cmd == "b-pages":
        res = Epaper().pages_by_date(args.date, args.paper_cid)
        name = _dump(res, "epaper_pages_%s.json" % args.date)
        print("%s 共%d版 -> %s" % (args.date, res["total"], name))
        for pg in res["pages"]:
            print("  第%s版 %s PDF=%s" % (pg["pageNumber"], pg["pageName"], pg["pdfUrl"]))
        return 0

    if args.cmd == "b-search":
        res = Epaper().search(args.kw, args.start, args.end, args.size,
                              args.frm, args.paper_cid, args.field)
        name = _dump(res, "epaper_search_%s.json" % args.kw)
        print("关键词“%s” 命中%s篇（本页%d） -> %s"
              % (args.kw, res["total"], len(res["articles"]), name))
        for a in res["articles"]:
            print("  %s 第%s版\t%s\t%s"
                  % (a["date"], a["pageNumber"], a["title"], a["author"]))
        return 0

    if args.cmd == "b-article":
        res = Epaper().article_by_id(args.id)
        if not res:
            print("未找到该 _id")
            return 1
        name = _dump(res, "epaper_article_%s.json" % args.id)
        print("%s 第%s版\t%s\t正文%d字 -> %s"
              % (res["date"], res["pageNumber"], res["title"],
                 len(res["contentText"]), name))
        return 0

    if args.cmd == "c-wechat":
        res = c_wechat(args.url)
        name = _dump(res, "wechat_article.json")
        print("%s\t%s\t正文%d字 -> %s"
              % (res["account"], res["title"], res["contentLength"], name))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
