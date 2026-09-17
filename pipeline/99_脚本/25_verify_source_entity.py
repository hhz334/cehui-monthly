# -*- coding: utf-8 -*-
"""来源实体校验 + 原文正文复检（汇编成册前置）。

做四件事：
1. 按"链接实体"而不是"名字"校验来源：官网看域名是否属于该单位，公众号看 __biz 是否属于该单位；
2. 不匹配的条目移出目录，写入《_备查/周讯回溯待办.md》；
3. 逐条抓原文正文（官网原站正文 / i自然接口 / 公众号 js_content），校验长度、标题要素与日期；
4. 正文不达标的写入《_备查/待补原文清单.md》；通过的在选目里补"正文来源""正文长度"字段。
"""
import importlib.util
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_utils import RAW, ROOT, ensure_dir, get_text, load_json, norm_date, save_json, strip_html  # noqa: E402
import sources_whitelist as WL  # noqa: E402
from period_config import P  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SEL_IN = os.path.join(P.sel_dir, "catalog_selection_boards.json")
SEL_OUT = os.path.join(P.sel_dir, "catalog_selection_final.json")
# 初版选目（骨架＋补位）优先：31 号脚本产出后即以其为校验对象
SEL_DRAFT = os.path.join(P.sel_dir, "catalog_selection_draft.json")
EXCLUDED = os.path.join(RAW, "excluded_by_entity.json")
BACKUP = os.path.join(ROOT, "_备查")
TODO_MD = os.path.join(BACKUP, "周讯回溯待办.md")
MIN_TEXT, MIN_COVER = 200, 0.7

SLEEP = 0.4
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0",
      "Accept-Language": "zh-CN,zh;q=0.9"}


def load_builder():
    spec = importlib.util.spec_from_file_location(
        "builder", os.path.join(HERE, "07_build_catalog.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_best_block():
    spec = importlib.util.spec_from_file_location(
        "detail", os.path.join(HERE, "04_fetch_details.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.best_block


def http_text(url, referer=None):
    h = dict(UA)
    if referer:
        h["Referer"] = referer
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        if (resp.headers.get("Content-Encoding") or "").lower() == "gzip":
            import gzip
            raw = gzip.decompress(raw)
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "ignore")


def fetch_iziran(url):
    """i 自然官网：走公开接口取正文与标题。"""
    aid = re.search(r"aid=(\d+)", url or "")
    if not aid:
        return "", ""
    data = json.loads(http_text(f"https://api.iziran.net/api/getArticle?aid={aid.group(1)}",
                                referer="https://www.iziran.net/"))
    d = data.get("data") if isinstance(data, dict) else {}
    d = d if isinstance(d, dict) else (data if isinstance(data, dict) else {})
    return strip_html(d.get("content") or ""), (d.get("title") or "")


def fetch_wechat(url):
    """公众号单篇：解析 js_content 正文与发布时间。"""
    page = http_text(url, referer="https://mp.weixin.qq.com/")
    title = ""
    m = re.search(r"var\s+msg_title\s*=\s*['\"]([^'\"]+)", page) or \
        re.search(r'property="og:title"[^>]*content="([^"]+)"', page)
    if m:
        title = m.group(1).strip()
    body = ""
    m = re.search(r'(?s)<div[^>]+id="js_content"[^>]*>(.*?)</div>\s*<script', page)
    if not m:
        m = re.search(r'(?s)<div[^>]+id="js_content"[^>]*>(.*)', page)
    if m:
        body = strip_html(m.group(1))
    date = ""
    m = re.search(r'var\s+ct\s*=\s*"?(\d{10})', page) or re.search(r"createTime\s*[:=]\s*'?(\d{10})", page)
    if m:
        date = time.strftime("%Y-%m-%d", time.localtime(int(m.group(1))))
    if not date:
        m = re.search(r'id="publish_time"[^>]*>([^<]{4,40})<', page)
        if m:
            date = norm_date(m.group(1))
    return body, title, date


def norm_title(t):
    t = re.sub(r"^[·•∙・\-\u2022\s]+", "", t or "")
    return re.sub(r"[\s\W_]+", "", t).lower()


def coverage(title, text):
    key = set(re.sub(r"[\s\W_]+", "", title or ""))
    body = set(re.sub(r"[\s\W_]+", "", (text or "")[:3000]))
    return len(key & body) / max(1, len(key))


def unit_of_domain(url):
    """按域名反查该链接真正属于哪个单位（用于纠正写错的发布单位）。"""
    host = WL.host_of(url)
    for unit, domains in WL.ORG_SITES.items():
        if any(host == d or host.endswith("." + d) for d in domains):
            return unit
    return ""


def similar(a, b):
    from difflib import SequenceMatcher
    return SequenceMatcher(None, norm_title(a), norm_title(b)).ratio()


def main():
    builder = load_builder()
    best_block = load_best_block()
    corpus = builder.load_corpus()
    sel = load_json(SEL_DRAFT if os.path.exists(SEL_DRAFT) else SEL_IN)

    # ---- 0) 同事件去重：优先官网链接、其次正文更长 ----
    def rank(s):
        url = s.get("source_url_checked") or ""
        is_site = 0 if (WL.site_type(url) and WL.site_type(url) != "公众号") else 1
        try:
            item = builder.pick(corpus, s)
            length = len(item.get("text") or "")
        except SystemExit:
            length = 0
        return (is_site, -length)

    # 预解析：链接实体 + 发布单位纠正
    prepared = []
    for s in sel:
        try:
            item = builder.pick(corpus, s)
            url = item.get("final_url") or item.get("url") or s.get("source_url_checked") or ""
        except SystemExit:
            item, url = {}, s.get("source_url_checked") or ""
        publisher = s.get("unit") or s.get("source_name") or ""
        check_url = url
        if "mp.weixin.qq.com" in url and not WL.wechat_biz(url):
            # 短链：抓页面解析账号与 __biz，再按分层白名单校验
            acc, biz = WL.resolve_wechat_account(url)
            if biz:
                check_url = url + ("&" if "?" in url else "?") + "__biz=" + biz
            if acc and not publisher:
                publisher = acc
                s = dict(s)
                s["unit"] = acc
        ok, kind, why = WL.entity_match(check_url, publisher)
        fix_note = ""
        if not ok and kind not in ("公众号", "无链接"):
            unit = unit_of_domain(url)
            if unit:
                publisher = unit
                s = dict(s)
                s["unit"] = unit
                ok, kind, why = WL.entity_match(url, unit)
                fix_note = f"发布单位按链接域名纠正为「{unit}」"
        prepared.append({"sel": s, "item": item, "url": url, "publisher": publisher,
                         "ok": ok, "kind": kind, "why": why, "fix": fix_note,
                         "rank": rank(s)})

    # 同事件合并：标题完全相同或高度相似的，只留一条（优先实体合格、官网链接、正文更长）
    groups = []
    for p in prepared:
        key = norm_title(p["sel"].get("title", ""))
        placed = False
        for g in groups:
            if key and key == g["key"]:
                g["members"].append(p)
                placed = True
                break
            if similar(p["sel"].get("title", ""), g["members"][0]["sel"].get("title", "")) >= 0.85:
                g["members"].append(p)
                placed = True
                break
        if not placed:
            groups.append({"key": key, "members": [p]})

    merged_out, dropped_dup = 0, []
    sel = []
    for g in groups:
        members = sorted(g["members"], key=lambda p: (not p["ok"], p["rank"]))
        head = members[0]
        for extra in members[1:]:
            merged_out += 1
            dropped_dup.append((head, extra))
        head["cross"] = [m for m in members[1:]]
        sel.append(head)
    sel = [p for p in sel]

    kept, todo, pending, report = [], [], [], []
    for i, p in enumerate(sel, 1):
        s, item = p["sel"], p["item"]
        title = s.get("title", "")
        publisher = p["publisher"]
        url = p["url"]
        cached = item.get("text") or ""
        ok, kind, why = p["ok"], p["kind"], p["why"]
        if p["fix"]:
            why = f"{why}；{p['fix']}"
        if p.get("cross"):
            why += "；同事件来源：" + "、".join(
                (c["publisher"] or "") + " " + (c["url"] or "")[:60] for c in p["cross"])
        text, page_title, page_date = "", "", ""
        raw_html = ""
        if ok:
            try:
                if "iziran.net" in url:
                    text, page_title = fetch_iziran(url)
                    page_date = item.get("date_page") or ""
                elif "mp.weixin.qq.com" in url:
                    text, page_title, page_date = fetch_wechat(url)
                else:
                    final, page = get_text(url)
                    raw_html = page
                    text = best_block(page) or ""
                    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", page)
                    page_title = re.sub(r"\s+", " ", strip_html(m.group(1))) if m else ""
                    page_date = norm_date(page)
            except Exception as exc:  # noqa: BLE001
                why += f"；抓取失败：{str(exc)[:60]}"
            if len(text) < len(cached):
                text = cached
                page_title = page_title or item.get("title_page") or title
        cov = coverage(title, text)
        # 去网页元信息与打印/关闭等"页面家具"
        text = WL.clean_body(text, title)
        cov = coverage(title, text)
        date = s.get("date_override") or page_date or item.get("date_page") or ""
        status, reason = "合格", ""
        if not ok:
            status, reason = "实体不匹配", why
        elif WL.is_non_text(title, url, text, raw_html) or item.get("video_page"):
            status, reason = "非文字稿", "视频／音频／图集类，只收文字稿"
        elif WL.is_junk_text(text):
            status, reason = "抓取失败", "正文为整页导航／模板文本，非文章内容"
        elif len(text) < MIN_TEXT:
            status, reason = "待补原文", f"正文仅 {len(text)} 字"
        elif cov < MIN_COVER:
            status, reason = "待补原文", f"标题要素覆盖率 {cov:.2f}"

        rec = {"标题": title, "发布单位": publisher, "链接": url, "载体": kind,
               "核验说明": why, "正文长度": len(text), "标题覆盖率": round(cov, 3),
               "页面标题": page_title, "页面日期": page_date, "状态": status, "说明": reason}
        report.append(rec)
        if status in ("实体不匹配", "抓取失败", "非文字稿"):
            todo.append(rec)
            continue
        if status == "待补原文":
            pending.append(rec)
            s2 = dict(s)
            s2["正文来源"] = "待补（正文不足）"
            s2["正文长度"] = len(text)
            s2["原文核验"] = f"{why}；{reason}"
            s2["原文正文"] = text[:20000]
            kept.append(s2)
            time.sleep(SLEEP)
            continue
        s = dict(s)
        s["正文来源"] = "公众号原文" if kind == "公众号" else "官网原文"
        s["正文长度"] = len(text)
        s["原文核验"] = why
        if s.get("摘要"):
            s["摘要"] = WL.clean_body(s["摘要"], title)
        if p.get("cross"):
            extra = "；".join((c["publisher"] or "") + "：" + (c["url"] or "")
                             for c in p["cross"])
            s["note"] = (s.get("note") or "") + "；同事件来源：" + extra
        if text:
            s["原文正文"] = text[:20000]
        kept.append(s)
        if i % 10 == 0:
            print(f"  {i}/{len(sel)}")
        time.sleep(SLEEP)

    save_json(SEL_OUT, kept)
    save_json(EXCLUDED, todo)
    save_json(os.path.join(RAW, "pending_source.json"), pending)
    save_json(os.path.join(RAW, "source_entity_check.json"), report)

    # ---- 报告 ----
    ensure_dir(BACKUP)
    lines = ["# 来源核验报告（链接实体校验 + 原文正文复检）", "",
             f"- 校验对象：{len(sel)} 条（同事件合并去重后）",
             f"- 合格：{len(kept)} 条；实体不匹配：{len(todo)} 条；正文待补：{len(pending)} 条",
             f"- 同事件合并：{merged_out} 条",
             "", "| # | 发布单位 | 载体 | 正文长度 | 标题覆盖率 | 状态 | 说明 |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for i, r in enumerate(report, 1):
        lines.append(f"| {i} | {r['发布单位'][:16]} | {r['载体']} | {r['正文长度']} | "
                     f"{r['标题覆盖率']} | {r['状态']} | {r['说明'][:46]} |")
    open(os.path.join(BACKUP, "来源核验报告.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")

    lines = ["# 待补原文清单", "",
             "- 规则：正文不足 200 字或标题要素覆盖率低于 0.7 的条目，需补原文后再汇编。",
             f"- 条数：{len(pending)}", "", "| # | 标题 | 发布单位 | 正文长度 | 说明 |",
             "| --- | --- | --- | --- | --- |"]
    for i, r in enumerate(pending, 1):
        lines.append(f"| {i} | {r['标题'][:44]} | {r['发布单位'][:16]} | {r['正文长度']} | {r['说明']} |")
    open(os.path.join(BACKUP, "待补原文清单.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")

    lines = ["# 周讯/来源待回溯清单", "",
             "- 规则：来源链接的实体（域名或公众号 __biz）不属于原发布单位的，一律不入目录，须回溯到原文。",
             "- 名称、备注只作线索；公众号只能证明本账号自己发布的内容。",
             f"- 条数：{len(todo)}", "", "| # | 标题 | 声称发布单位 | 链接实体 | 说明 |",
             "| --- | --- | --- | --- | --- |"]
    for i, r in enumerate(todo, 1):
        lines.append(f"| {i} | {r['标题'][:44]} | {r['发布单位'][:18]} | "
                     f"{WL.host_of(r['链接'])} | {r['说明'][:60]} |")
    open(TODO_MD, "w", encoding="utf-8").write("\n".join(lines) + "\n")

    print(f"实体不匹配 {len(todo)} 条，正文待补 {len(pending)} 条，合格 {len(kept)} 条，合并 {merged_out} 条")
    print(f"输出：{SEL_OUT}")


if __name__ == "__main__":
    main()
