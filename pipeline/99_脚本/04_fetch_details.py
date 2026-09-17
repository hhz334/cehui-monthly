# -*- coding: utf-8 -*-
"""逐条抓详情页并做首轮核实：链接可达、标题一致、发布时间、正文完整性。"""
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_utils import RAW, get_text, load_json, norm_date, save_json, strip_html  # noqa: E402

SLEEP = 0.3


def similarity(a, b):
    a = re.sub(r"[\s\W_]+", "", a or "")
    b = re.sub(r"[\s\W_]+", "", b or "")
    if not a or not b:
        return 0.0
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    hit = sum(1 for ch in set(shorter) if ch in longer)
    return hit / len(set(shorter))


def best_block(raw_html):
    """在页面里挑出最像正文的块：文字多、链接少。"""
    from lxml import html as LH
    try:
        doc = LH.fromstring(raw_html)
    except Exception:  # noqa: BLE001
        return ""
    for bad in doc.xpath("//script|//style|//nav|//header|//footer|//form|//noscript"):
        parent = bad.getparent()
        if parent is not None:
            parent.remove(bad)
    best, best_score = "", -1
    for el in doc.xpath("//div|//article|//section|//td"):
        try:
            frag = LH.tostring(el, encoding="unicode")
        except Exception:  # noqa: BLE001
            continue
        txt = strip_html(frag)
        if len(txt) < 150:
            continue
        links = len(el.findall(".//a"))
        lists = len(el.findall(".//li"))
        score = len(txt) - 40 * links - 20 * lists
        if score > best_score:
            best_score, best = score, txt
    return best


def fetch_detail(url, title=""):
    info = {"url": url, "final_url": url, "title_page": "", "date_page": "", "origin_page": "",
            "text": "", "http_ok": False, "note": ""}
    try:
        final, page = get_text(url)
        info["http_ok"] = True
        info["final_url"] = final
    except Exception as exc:  # noqa: BLE001
        info["note"] = f"抓取失败: {exc}"
        return info
    page_raw = page
    page = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", page)
    m = re.search(r'(?is)<meta[^>]+property="og:title"[^>]+content="([^"]+)"', page)
    if m:
        info["title_page"] = re.sub(r"\s+", " ", m.group(1)).strip()
    if not info["title_page"]:
        m = re.search(r"(?is)<h1[^>]*>(.*?)</h1>", page)
        if m:
            info["title_page"] = re.sub(r"\s+", " ", strip_html(m.group(1)))
    if not info["title_page"]:
        m = re.search(r"(?is)<title[^>]*>(.*?)</title>", page)
        if m:
            info["title_page"] = re.sub(r"\s+", " ", strip_html(m.group(1)))
    plain = strip_html(page)
    for pat in (r"发布时间[:：]\s*(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2})",
                r"发布日期[:：]\s*(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2})",
                r"时间[:：]\s*(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2})",
                r"(20\d{2}年\d{1,2}月\d{1,2}日)"):
        m = re.search(pat, plain) or re.search(pat, page)
        if m:
            info["date_page"] = norm_date(m.group(1))
            break
    m = re.search(r"来源[:：]\s*([^\s，,。;；]{2,30})", plain)
    if m:
        info["origin_page"] = m.group(1)
    text = best_block(page_raw)
    # 记录是否为视频页（供筛选阶段剔除非文字稿）
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from sources_whitelist import VIDEO_HTML  # noqa: E402
        info["video_page"] = bool(VIDEO_HTML.search(page_raw or ""))
    except Exception:  # noqa: BLE001
        info["video_page"] = False
    if len(text) < 150:
        text = plain
    text = re.sub(r"\n{2,}", "\n", text)
    info["text"] = text[:20000]
    info["title_sim"] = round(similarity(title, info["title_page"]), 3)
    info["text_len"] = len(info["text"])
    info["date_ok"] = bool(info["date_page"])
    return info


def main():
    files = [f for f in os.listdir(RAW)
             if f.endswith(".json") and not f.endswith("_detail.json")
             and f not in ("shandong_album.json",)]
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    for name in sorted(files):
        sid = name[:-5]
        if only and sid not in only:
            continue
        items = load_json(os.path.join(RAW, name))
        out_path = os.path.join(RAW, f"{sid}_detail.json")
        done = {}
        if os.path.exists(out_path) and os.environ.get("FORCE") != "1":
            for rec in load_json(out_path):
                done[rec["url"]] = rec
        results = []
        print(f"### {sid}: {len(items)} 条")
        for idx, item in enumerate(items, 1):
            url = item["url"]
            if url in done and done[url].get("http_ok"):
                results.append(done[url])
                continue
            detail = fetch_detail(url, item.get("title", ""))
            detail.update({k: v for k, v in item.items() if k != "content"})
            api_text = item.get("content") or ""
            if len(api_text) > len(detail.get("text") or "") + 200:
                detail["text"] = api_text          # 福建厅检索接口返回的正文更完整
                detail["text_from_api"] = True
            detail["text_len"] = len(detail["text"])
            results.append(detail)
            if idx % 25 == 0:
                print(f"   {idx}/{len(items)}")
                save_json(out_path, results)
            time.sleep(SLEEP)
        save_json(out_path, results)
        ok = sum(1 for r in results if r.get("http_ok"))
        print(f"  => 可达 {ok}/{len(results)}，已存 {out_path}")


if __name__ == "__main__":
    main()
