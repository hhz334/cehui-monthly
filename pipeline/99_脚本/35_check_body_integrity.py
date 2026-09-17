# -*- coding: utf-8 -*-
"""独立复检“原文有没有被抽取漏掉”（正文清洗的漏字兜底检查）。

思路：把页面原始 HTML 用与清洗链不同的方式抽成文本，再按句切分，
找出“页面有、我们归档的正文里没有”的句子，人工判断是页面提示（正常删除）
还是被 `BODY_FURNITURE` 之类规则误删（须修规则后重跑 25）。

输出：`<期次目录>/_raw/live_integrity.json`。

用法：
    python 35_check_body_integrity.py
"""
import html as H
import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from period_config import P  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0"}
SEL = os.path.join(P.sel_dir, "catalog_selection_final.json")


def get(url, referer=None):
    h = dict(UA)
    if referer:
        h["Referer"] = referer
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "ignore")


def naive_text(html):
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?s)<br\s*/?>|</p>|</div>|</li>|</h\d>", "\n", html)
    txt = re.sub(r"(?s)<[^>]+>", "", html)
    return H.unescape(txt)


def norm(s):
    return re.sub(r"\s+", "", s or "")


def page_html(url):
    if "mp.weixin.qq.com" in url:
        page = get(url, referer="https://mp.weixin.qq.com/")
        m = re.search(r'(?s)<div[^>]+id="js_content"[^>]*>(.*?)</div>\s*<script', page)
        if not m:
            m = re.search(r'(?s)<div[^>]+id="js_content"[^>]*>(.*)', page)
        return m.group(1) if m else page
    if "iziran.net" in url:
        aid = re.search(r"aid=(\d+)", url).group(1)
        d = json.loads(get("https://api.iziran.net/api/getArticle?aid=%s" % aid,
                           referer="https://www.iziran.net/"))
        d = d.get("data") if isinstance(d.get("data"), dict) else d
        return d.get("content") or ""
    return get(url)


def main():
    items = json.load(open(SEL, encoding="utf-8"))
    report = []
    for it in items:
        url = it.get("source_url_checked") or ""
        body = it.get("原文正文") or ""
        try:
            txt = naive_text(page_html(url))
        except Exception as e:  # noqa: BLE001
            report.append({"title": it["title"], "error": str(e)})
            continue
        nb = norm(body)
        lost = []
        for frag in re.split(r"[。；\n]", txt):
            f = frag.strip()
            if len(re.findall(r"[\u4e00-\u9fa5]", f)) < 12:
                continue
            if norm(f)[:40] not in nb:
                lost.append(f[:160])
        report.append({"title": it["title"], "url": url, "body_len": len(body),
                       "page_len": len(txt), "lost": lost})
    out = os.path.join(P.issue_dir, "_raw", "live_integrity.json")
    json.dump(report, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in report:
        print("=" * 70)
        print(r["title"], "| body", r.get("body_len"), "| page", r.get("page_len"),
              "| 缺句", len(r.get("lost") or []), r.get("error", ""))
        for s in (r.get("lost") or [])[:12]:
            print("    -", s)
    print("输出：", out)


if __name__ == "__main__":
    main()
