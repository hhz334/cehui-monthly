# -*- coding: utf-8 -*-
"""把 docx 里的西文与数字字体设为 Times New Roman（中文东亚字体保持不变）。

做法：改 word/styles.xml、word/document.xml、word/header*.xml、word/footer*.xml 中
w:rFonts 的 w:ascii 与 w:hAnsi 属性；w:eastAsia 一律不动。

注意：页眉页脚默认**不改**（2026-09-17 起）——《测绘动态工作》正文页眉要求中英文统一黑体，
如确需连页眉一起改，调用时传 include_headers=True。
"""
import os
import re
import shutil
import sys
import zipfile

LATIN = "Times New Roman"
TARGETS = ("word/document.xml", "word/styles.xml")


def patch_xml(xml):
    xml = re.sub(r'w:ascii="[^"]*"', 'w:ascii="%s"' % LATIN, xml)
    xml = re.sub(r'w:hAnsi="[^"]*"', 'w:hAnsi="%s"' % LATIN, xml)

    def add_attrs(m):
        attrs = m.group(1)
        add = ""
        if "w:ascii=" not in attrs:
            add += ' w:ascii="%s"' % LATIN
        if "w:hAnsi=" not in attrs:
            add += ' w:hAnsi="%s"' % LATIN
        if not add:
            return m.group(0)
        if m.group(0).endswith("/>"):
            return "<w:rFonts%s%s/>" % (attrs, add)
        return "<w:rFonts%s%s>" % (attrs, add)

    return re.sub(r"<w:rFonts([^>]*?)/?>", add_attrs, xml)


def convert(path, include_headers=False):
    tmp = path + ".tmp"
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            name = item.filename
            hit_header = bool(re.match(r"word/(header|footer)\d*\.xml$", name))
            if name in TARGETS or (include_headers and hit_header):
                data = patch_xml(data.decode("utf-8")).encode("utf-8")
            zout.writestr(item, data)
    shutil.move(tmp, path)
    with zipfile.ZipFile(path) as z:
        doc = z.read("word/document.xml").decode("utf-8")
        sty = z.read("word/styles.xml").decode("utf-8")
    print("  %s: document 西文字体 %d 处，styles %d 处，东亚字体属性保留 %d 处"
          % (os.path.basename(path), doc.count('w:ascii="%s"' % LATIN),
             sty.count('w:ascii="%s"' % LATIN), doc.count("w:eastAsia=")))


def convert_many(paths, include_headers=False):
    for p in paths:
        if os.path.exists(p):
            convert(p, include_headers=include_headers)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        convert(p)
