# -*- coding: utf-8 -*-
"""抓取山东省国土测绘院《测绘地理信息周讯》合集索引与 82-87 期整期长图。"""
import html as html_mod
import io as _io
import os
import re
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_utils import RAW, ROOT, ensure_dir, get_text, http_get, save_json  # noqa: E402

WEEKLY_DIR = os.path.join(ROOT, "03_参考_山东周讯")
ALBUM = ("https://mp.weixin.qq.com/mp/appmsgalbum?__biz=MzUyMTczMDQzNg%3D%3D"
         "&action=getalbum&album_id=4149959292101214229")
CN_TZ = timezone(timedelta(hours=8))


def album_index():
    """翻页枚举合集里的全部期次。"""
    items, seen, url = [], set(), ALBUM
    for _ in range(15):
        _, page = get_text(url)
        found = re.findall(r"title:\s*'([^']+)',\s*create_time:\s*'(\d+)'[\s\S]{0,600}?url:\s*'([^']+)'", page)
        fresh = [(t, int(ct), html_mod.unescape(u)) for t, ct, u in found if t not in seen]
        if not fresh:
            break
        for t, ct, u in fresh:
            seen.add(t)
        items += fresh
        m = re.search(r"mid=(\d+).*?idx=(\d+)", html_mod.unescape(found[-1][2]))
        if not m:
            break
        url = f"{ALBUM}&continue_flag=1&begin_msgid={m.group(1)}&begin_itemidx={m.group(2)}"
    out = []
    for title, ct, link in items:
        num = re.search(r"第(\d+)期", title)
        out.append({
            "issue": int(num.group(1)) if num else None,
            "title": title,
            "url": link,
            "date": datetime.fromtimestamp(ct, CN_TZ).strftime("%Y-%m-%d"),
        })
    out.sort(key=lambda x: (x["issue"] or 0))
    return out


def write_index(index):
    rows = ["# 山东省国土测绘院《测绘地理信息周讯》期次索引", "",
            f"- 合计：{len(index)} 期",
            f"- 枚举时间：{datetime.now(CN_TZ).strftime('%Y-%m-%d %H:%M')}",
            "- 来源：公众号合辑页 mp.weixin.qq.com/mp/appmsgalbum", "",
            "| 期号 | 发布日期 | 标题 | 链接 |", "| --- | --- | --- | --- |"]
    for it in index:
        rows.append(f"| {it['issue']} | {it['date']} | {it['title']} | {it['url'].split('&chksm')[0]} |")
    path = os.path.join(WEEKLY_DIR, "期次索引.md")
    ensure_dir(WEEKLY_DIR)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(rows) + "\n")
    return path


def fetch_issue(item):
    """抓取一期：整期长图 + 元数据。"""
    issue_dir = ensure_dir(os.path.join(WEEKLY_DIR, f"第{item['issue']:03d}期"))
    url = item["url"]
    _, page = get_text(url)
    title = re.search(r"var msg_title = '([^']*)'", page)
    ct = re.search(r'var ct = "(\d+)"', page)
    body = re.search(r'id="js_content"[^>]*>(.*?)</div>\s*<div class="rich_media_tool', page, re.S)
    if not body:
        body = re.search(r'id="js_content"[^>]*>(.*)', page, re.S)
    inner = body.group(1) if body else page
    imgs = re.findall(r'<img[^>]+(?:data-src|src)="([^"]+)"', inner)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", inner)).strip()
    meta = {
        "issue": item["issue"],
        "title": title.group(1) if title else item["title"],
        "url": url.split("&chksm")[0],
        "publish": (datetime.fromtimestamp(int(ct.group(1)), CN_TZ).strftime("%Y-%m-%d %H:%M")
                    if ct else item["date"]),
        "lead_text": text,
        "images": [],
    }
    saved = 0
    for src in imgs:
        if not src.startswith("http"):
            continue
        if "wx_fmt=other" in src:
            continue
        try:
            _, data = http_get(src, referer="https://mp.weixin.qq.com/")
        except Exception as exc:  # noqa: BLE001
            print(f"    ! 图片失败 {src[:60]} :: {exc}")
            continue
        try:
            from PIL import Image
            w, h = Image.open(_io.BytesIO(data)).size
        except Exception:  # noqa: BLE001
            continue
        if w < 800 or h < 1200:      # 只留 A4 整期长图，跳过二维码与栏目图
            continue
        saved += 1
        name = f"p{saved:02d}.jpg"
        with open(os.path.join(issue_dir, name), "wb") as fh:
            fh.write(data)
        meta["images"].append({"file": name, "url": src, "size": f"{w}x{h}"})
    save_json(os.path.join(issue_dir, "meta.json"), meta)
    print(f"  第{item['issue']}期 页面图 {saved} 张")
    return meta


def main():
    index = album_index()
    save_json(os.path.join(RAW, "shandong_album.json"), index)
    print("索引：", write_index(index))
    todo = [x for x in index if x["issue"] and 82 <= x["issue"] <= 87]
    print("待抓取：", ", ".join(f"{x['issue']}({x['date']})" for x in todo))
    metas = [fetch_issue(item) for item in todo]
    save_json(os.path.join(WEEKLY_DIR, "周讯元数据.json"), metas)
    print("完成")


if __name__ == "__main__":
    main()
