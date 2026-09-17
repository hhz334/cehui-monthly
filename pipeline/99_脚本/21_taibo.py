# -*- coding: utf-8 -*-
"""泰伯网（taibo.cn / 原 3snews.net）取文工具：官网 + 微信公众号。

两条通道：
  A. 泰伯网官网 www.taibo.cn —— 资讯列表 / 站内检索 / 单篇正文（无需登录）
  B. 微信公众号“泰伯网”（微信号 news_3snews，__biz=MjM5NTg1MzcyMQ==）
     经搜狗微信（weixin.sogou.com）检索 → 还原真实 mp.weixin.qq.com 链接 → 抽正文

用法：
  python 21_taibo.py a-list    --page 2
  python 21_taibo.py a-zaobao  --page 1
  python 21_taibo.py a-search  --q 低空经济 --pages 3
  python 21_taibo.py a-article --id 99719
  python 21_taibo.py b-search  --q 泰伯网 --pages 2
  python 21_taibo.py b-resolve --link "/link?url=dn9a_..."
  python 21_taibo.py b-article --url "https://mp.weixin.qq.com/s?src=11&..."
"""
import argparse
import gzip
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
OUT = os.path.join(ROOT, "_raw", "taibo")

SITE = "https://www.taibo.cn"
SOGOU = "https://weixin.sogou.com"

# 泰伯网公众号
WX_ACCOUNT = "泰伯网"
WX_ID = "news_3snews"
WX_BIZ = "MjM5NTg1MzcyMQ=="


class Session:
    """带 cookie 的极简会话（仅标准库）。"""

    def __init__(self):
        self.jar = {}
        self.extra_headers = {}

    def header(self, key, value):
        self.extra_headers[key] = value

    def request(self, url, method="GET", data=None, referer=None,
                timeout=40, retries=3, sleep=2.0):
        # 搜狗还原出的链接里可能带未编码的空格/中文，先做安全编码
        url = urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=%~")
        body = None
        if data is not None:
            body = urllib.parse.urlencode(data, doseq=True).encode("utf-8")
        last_err = None
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, data=body, method=method)
                req.add_header("User-Agent", UA)
                req.add_header("Accept",
                               "text/html,application/xhtml+xml,application/json,*/*;q=0.8")
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
                    req.add_header("Cookie",
                                   "; ".join("%s=%s" % (k, v) for k, v in self.jar.items()))
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


def strip_html(fragment, keep_breaks=True):
    if not fragment:
        return ""
    txt = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", fragment)
    if keep_breaks:
        txt = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h[1-6]>", "\n", txt)
    txt = re.sub(r"(?s)<[^>]+>", "", txt)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&quot;", '"'),
                 ("&#39;", "'"), ("&lt;", "<"), ("&gt;", ">"),
                 ("&ldquo;", "“"), ("&rdquo;", "”")):
        txt = txt.replace(a, b)
    txt = re.sub(r"[ \t\u3000]+", " ", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt.strip()


# --------------------------------------------------------------------------
# A. 泰伯网官网
# --------------------------------------------------------------------------
class Taibo:
    """官网抓取。列表/检索用 AJAX 片段（需 X-Requested-With 头）。"""

    def __init__(self):
        self.s = Session()
        self.s.header("X-Requested-With", "XMLHttpRequest")

    def _list(self, path, page, referer):
        sep = "&" if "?" in path else "?"
        url = "%s%s%spage=%d" % (SITE, path, sep, page)
        html = self.s.get_text(url, referer=referer)
        return self._parse_items(html)

    @staticmethod
    def _parse_items(html):
        rows = []
        for block in re.findall(r'(?s)<div class="media article-item">(.*?)</div>\s*</div>\s*</div>',
                                html) or re.findall(r'(?s)<div class="media article-item">(.*?)(?=<div class="media article-item">|$)',
                                                    html):
            href = re.search(r'href="(/p/(\d+))"', block)
            if not href:
                continue
            title = ""
            m = re.search(r'class="item-title"[^>]*>(.*?)</a>', block, re.S)
            if not m:
                m = re.search(r'class="media-img[^"]*"[^>]*>[\s\S]*?</a>\s*<div[^>]*>\s*<a[^>]*>(.*?)</a>', block, re.S)
            if not m:
                m = re.search(r'<a[^>]*>(.*?)</a>', block, re.S)
            if m:
                title = strip_html(m.group(1), keep_breaks=False)
            summary = ""
            m = re.search(r'<p>(.*?)</p>', block, re.S)
            if m:
                summary = strip_html(m.group(1), keep_breaks=False)
            dt = ""
            m = re.search(r'<time[^>]*datetime="([^"]+)"', block)
            if m:
                dt = m.group(1)
            tags = [strip_html(t, keep_breaks=False)
                    for t in re.findall(r'href="/search\?q=[^"]*"[^>]*>(.*?)</a>', block, re.S)]
            rows.append({"id": href.group(2), "title": title, "summary": summary,
                         "publishTime": dt, "tags": tags,
                         "url": SITE + href.group(1)})
        return rows

    def list_info(self, page=1):
        """资讯频道（/info）列表，每页 10 条。"""
        return {"channel": "资讯", "page": page,
                "items": self._list("/info", page, SITE + "/info")}

    def list_zaobao(self, page=1):
        """泰伯早报（/info/zaobao）。"""
        return {"channel": "早报", "page": page,
                "items": self._list("/info/zaobao", page, SITE + "/info/zaobao")}

    def search(self, q, page=1):
        """站内检索（/search?q=）。"""
        qs = urllib.parse.quote(q)
        return {"channel": "检索", "q": q, "page": page,
                "items": self._list("/search?q=%s" % qs, page,
                                    "%s/search?q=%s" % (SITE, qs))}

    def article(self, pid):
        """单篇文章：标题、摘要、发布时间、栏目标签、正文。"""
        url = "%s/p/%s" % (SITE, pid)
        html = self.s.get_text(url, referer=SITE + "/info")
        def meta(prop):
            m = re.search(r'<meta property="%s" content="([^"]*)"' % prop, html)
            if not m:
                m = re.search(r'<meta name="%s" content="([^"]*)"' % prop, html)
            return strip_html(m.group(1), keep_breaks=False) if m else ""
        body = ""
        m = re.search(r'(?s)<div class="article-content"[^>]*>(.*?)</div>\s*</div>', html)
        if not m:
            m = re.search(r'(?s)class="article-content"[^>]*>(.*)', html)
        if m:
            body = m.group(1)
        dt = ""
        m = re.search(r'(?s)class="article-author-date"[^>]*>(.*?)</div>', html)
        if m:
            dm = re.search(r'<time[^>]*datetime="([^"]+)"', m.group(1))
            if dm:
                dt = dm.group(1)
        channel = ""
        m = re.search(r'(?s)class="article-author-date"[^>]*>(.*?)</div>', html)
        if m:
            cm = re.search(r'>([^<>]{2,20})</a>', m.group(1))
            if cm:
                channel = strip_html(cm.group(1), keep_breaks=False)
        text = strip_html(body)
        # 去掉评论区组件残留与模板占位符
        for cut in ("参与评论", "【登录后才能评论", "相关推荐", "热门标签",
                    "该内容属于精选文章系列", "升级PRO会员"):
            idx = text.find(cut)
            if idx > 0:
                text = text[:idx]
        text = re.sub(r"\{\{[^}]*\}\}", "", text)
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()
        return {"id": pid, "url": url,
                "title": meta("og:title"),
                "description": meta("og:description"),
                "keywords": meta("keywords"),
                "channel": channel,
                "publishTime": dt,
                "content": body,
                "contentText": text,
                "memberOnly": "该内容属于精选文章系列" in html or "PRO会员" in html}


# --------------------------------------------------------------------------
# B. 微信公众号（经搜狗微信）
# --------------------------------------------------------------------------
class WeixinSogou:
    """搜狗微信检索 + 链接还原 + 公众号单篇抽取。

    注意：搜狗有反爬，连续请求会触发验证码；建议每页间隔 ≥5 秒、单次会话 ≤10 页。
    """

    def __init__(self):
        self.s = Session()
        self.s.header("Upgrade-Insecure-Requests", "1")

    def _ensure_session(self):
        """搜狗跳转链接需要先建立会话（SNUID/SUID cookie），否则拿不到目标地址。"""
        if "SNUID" in self.s.jar:
            return
        qs = urllib.parse.quote(WX_ACCOUNT)
        self.s.get_text("%s/weixin?type=2&query=%s&ie=utf8" % (SOGOU, qs),
                        referer=SOGOU + "/")

    @staticmethod
    def _check_captcha(html):
        if re.search(r'antispider|请输入验证码|seccodeImage|验证码', html):
            raise RuntimeError("搜狗微信触发反爬验证码，需降速或换 IP 后重试")

    def search(self, q, page=1):
        qs = urllib.parse.quote(q)
        self._ensure_session()
        url = "%s/weixin?type=2&query=%s&ie=utf8&page=%d" % (SOGOU, qs, page)
        html = self.s.get_text(url, referer=SOGOU + "/")
        self._check_captcha(html)
        rows = []
        for block in re.findall(r'(?s)<div class="txt-box">(.*?)</div>\s*</div>', html):
            m = re.search(r'href="(/link\?url=[^"]+)"', block)
            if not m:
                continue
            link = m.group(1).replace("&amp;", "&")
            t = re.search(r'id="sogou_vr_11002601_title_\d+"[^>]*>(.*?)</a>', block, re.S)
            title = strip_html(t.group(1), keep_breaks=False) if t else ""
            a = re.search(r'class="all-time-y2">([^<]*)</span>', block)
            account = a.group(1).strip() if a else ""
            s = re.search(r'class="txt-info"[^>]*>(.*?)</p>', block, re.S)
            summary = strip_html(s.group(1), keep_breaks=False) if s else ""
            ts = re.search(r"timeConvert\('(\d+)'\)", block)
            dt = (time.strftime("%Y-%m-%d", time.localtime(int(ts.group(1))))
                  if ts else "")
            rows.append({"title": title, "account": account, "summary": summary,
                         "date": dt, "sogouLink": SOGOU + link,
                         "isTarget": account == WX_ACCOUNT})
        total = ""
        m = re.search(r'找到约([\d,]+)条结果', html)
        if m:
            total = m.group(1)
        return {"query": q, "page": page, "total": total, "items": rows}

    def resolve(self, link):
        """把 /link?url=... 还原成真实 mp.weixin.qq.com 地址（含时效签名）。"""
        if link.startswith("/"):
            link = SOGOU + link
        for attempt in range(2):
            self._ensure_session()
            html = self.s.get_text(link, referer=SOGOU + "/")
            parts = re.findall(r"url \+= '([^']*)'", html)
            if parts:
                return "".join(parts).replace("@", "")
            m = re.search(r'window\.location\.replace\(["\']([^"\']+)', html)
            if m:
                return m.group(1)
            self.s.jar.pop("SNUID", None)  # 会话失效则重建后重试一次
            time.sleep(2)
        raise RuntimeError("未能从搜狗跳转页解析出目标地址（可能触发反爬，请降速重试）")

    def article(self, url):
        """抓取公众号文章：标题 / 公众号名 / biz / 正文。"""
        html = self.s.get_text(url, referer=SOGOU + "/")
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
            body = m.group(1)
        return {"url": url, "title": title, "account": nick, "biz": biz,
                "content": body, "contentText": strip_html(body)}


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
    ap = argparse.ArgumentParser(description="泰伯网取文工具（官网 + 公众号）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("a-list", help="官网：资讯频道列表")
    p.add_argument("--page", type=int, default=1)

    p = sub.add_parser("a-zaobao", help="官网：泰伯早报")
    p.add_argument("--page", type=int, default=1)

    p = sub.add_parser("a-search", help="官网：站内检索")
    p.add_argument("--q", required=True)
    p.add_argument("--pages", type=int, default=1)

    p = sub.add_parser("a-article", help="官网：单篇正文")
    p.add_argument("--id", required=True)

    p = sub.add_parser("b-search", help="公众号：搜狗微信检索")
    p.add_argument("--q", default=WX_ACCOUNT)
    p.add_argument("--pages", type=int, default=1)
    p.add_argument("--sleep", type=float, default=6.0, help="翻页间隔秒数")

    p = sub.add_parser("b-resolve", help="公众号：还原搜狗链接")
    p.add_argument("--link", required=True)

    p = sub.add_parser("b-article", help="公众号：单篇抽取")
    p.add_argument("--url", required=True)

    args = ap.parse_args(argv)

    if args.cmd == "a-list":
        res = Taibo().list_info(args.page)
        name = _dump(res, "taibo_info_p%d.json" % args.page)
        print("资讯 第%d页 %d条 -> %s" % (args.page, len(res["items"]), name))
        for it in res["items"]:
            print("  %s\t%s\t%s" % (it["publishTime"], it["title"], it["url"]))
        return 0

    if args.cmd == "a-zaobao":
        res = Taibo().list_zaobao(args.page)
        name = _dump(res, "taibo_zaobao_p%d.json" % args.page)
        print("早报 第%d页 %d条 -> %s" % (args.page, len(res["items"]), name))
        for it in res["items"]:
            print("  %s\t%s\t%s" % (it["publishTime"], it["title"], it["url"]))
        return 0

    if args.cmd == "a-search":
        tb, all_items = Taibo(), []
        for page in range(1, args.pages + 1):
            res = tb.search(args.q, page)
            all_items.extend(res["items"])
            if not res["items"]:
                break
            time.sleep(2)
        name = _dump({"q": args.q, "count": len(all_items), "items": all_items},
                     "taibo_search_%s.json" % args.q)
        print("检索“%s” 共%d条 -> %s" % (args.q, len(all_items), name))
        for it in all_items[:20]:
            print("  %s\t%s\t%s" % (it["publishTime"], it["title"], it["url"]))
        return 0

    if args.cmd == "a-article":
        res = Taibo().article(args.id)
        name = _dump(res, "taibo_p%s.json" % args.id)
        print("%s\t%s\t正文%d字 -> %s"
              % (res["publishTime"], res["title"], len(res["contentText"]), name))
        return 0

    if args.cmd == "b-search":
        wx = WeixinSogou()
        all_items = []
        for page in range(1, args.pages + 1):
            res = wx.search(args.q, page)
            all_items.extend(res["items"])
            print("第%d页 %d条（累计%d）" % (page, len(res["items"]), len(all_items)))
            if not res["items"]:
                break
            if page < args.pages:
                time.sleep(args.sleep)
        name = _dump({"query": args.q, "count": len(all_items), "items": all_items},
                     "wx_sogou_%s.json" % args.q)
        print("搜狗微信检索“%s” 共%d条 -> %s" % (args.q, len(all_items), name))
        for it in all_items[:20]:
            print("  %s\t%s\t%s" % (it["date"], it["account"], it["title"]))
        return 0

    if args.cmd == "b-resolve":
        target = WeixinSogou().resolve(args.link)
        print(target)
        return 0

    if args.cmd == "b-article":
        res = WeixinSogou().article(args.url)
        name = _dump(res, "wx_article.json")
        print("%s\t%s\t正文%d字 -> %s"
              % (res["account"], res["title"], len(res["contentText"]), name))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
