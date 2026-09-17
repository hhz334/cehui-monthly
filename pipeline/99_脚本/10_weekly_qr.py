# -*- coding: utf-8 -*-
"""下载各期周讯文章里的二维码图片，供解码得到整期文件下载链接。"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_utils import RAW, ROOT, ensure_dir, get_text, http_get, load_json, save_json  # noqa: E402

WEEKLY_DIR = os.path.join(ROOT, "03_参考_山东周讯")


def main():
    metas = load_json(os.path.join(WEEKLY_DIR, "周讯元数据.json"))
    album = {x["issue"]: x["url"] for x in load_json(os.path.join(RAW, "shandong_album.json"))}
    out = {}
    for meta in metas:
        issue = meta["issue"]
        folder = ensure_dir(os.path.join(WEEKLY_DIR, f"第{issue:03d}期"))
        _, page = get_text(album.get(issue) or meta["url"])
        body = re.search(r'id="js_content"[^>]*>(.*)', page, re.S)
        inner = body.group(1) if body else page
        urls = re.findall(r'<img[^>]+(?:data-src|src)="([^"]+)"', inner)
        saved = []
        for url in urls:
            if not url.startswith("http"):
                continue
            try:
                _, data = http_get(url, referer="https://mp.weixin.qq.com/")
            except Exception:  # noqa: BLE001
                continue
            try:
                from PIL import Image
                import io
                w, h = Image.open(io.BytesIO(data)).size
            except Exception:  # noqa: BLE001
                continue
            if 300 <= w <= 700 and 300 <= h <= 700:      # 二维码尺寸
                name = f"qr_{len(saved)+1}.png"
                with open(os.path.join(folder, name), "wb") as fh:
                    fh.write(data)
                saved.append({"file": name, "url": url, "size": f"{w}x{h}"})
        out[issue] = saved
        print(f"第{issue}期 二维码候选 {len(saved)} 个")
    save_json(os.path.join(WEEKLY_DIR, "二维码图片.json"), out)


if __name__ == "__main__":
    main()
