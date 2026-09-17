# -*- coding: utf-8 -*-
"""下载山东《测绘地理信息周讯》82—87 期整期 PDF 并归档到各期目录。

下载地址由草料活码页面（qr61.cn）经浏览器渲染后解析得到，见
`03_参考_山东周讯/整期文件下载链接.md`。活码页为 JavaScript 渲染，
普通 HTTP 请求无法解析，故此处直接固化已验证的直链。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_utils import ROOT, ensure_dir, http_get  # noqa: E402

WEEKLY_DIR = os.path.join(ROOT, "03_参考_山东周讯")
BASE = "https://ncstatic.clewm.net/rsrc/2026/"

# 期号 -> (直链路径, 活码页)
ISSUES = {
    82: ("0731/17/1950514b77854232b2274c5fb07ed423.pdf", "https://qr61.cn/oYqnzL/qUTpLoo"),
    83: ("0810/14/505c4eaf1b314c62bff3f1f293b24ab5.pdf", "https://qr61.cn/oYqnzL/qY93N5K"),
    84: ("0817/17/a6ebb828a7444d0983028c8a2b2f8f59.pdf", "https://qr61.cn/oYqnzL/qSMvOFm"),
    85: ("0824/17/235a7bfa767149549b35f2e2bef3176c.pdf", "https://qr61.cn/oYqnzL/qtdIFCL"),
    86: ("0901/17/c779a2ae958241198d556fc64e83b0b1.pdf", "https://qr61.cn/oYqnzL/qheAR9v"),
    87: ("0907/15/775ddfbbee5e49ecb6af1626609ed4d8.pdf", "https://qr61.cn/oYqnzL/qjwQXF9"),
}


def main() -> None:
    for issue, (path_part, code_url) in sorted(ISSUES.items()):
        folder = ensure_dir(os.path.join(WEEKLY_DIR, f"第{issue:03d}期"))
        name = f"测绘地理信息周讯第{issue:03d}期.pdf"
        target = os.path.join(folder, name)
        if os.path.exists(target) and os.path.getsize(target) > 10000:
            print(f"第{issue}期 已存在，跳过（{os.path.getsize(target)} 字节）")
            continue
        url = BASE + path_part
        try:
            _, data = http_get(url, referer=code_url)
        except Exception as err:  # noqa: BLE001
            print(f"第{issue}期 下载失败：{err}")
            continue
        if not data.startswith(b"%PDF"):
            print(f"第{issue}期 返回内容不是 PDF（{len(data)} 字节），跳过")
            continue
        with open(target, "wb") as fh:
            fh.write(data)
        print(f"第{issue}期 已保存 {name}（{len(data)} 字节）")


if __name__ == "__main__":
    main()
