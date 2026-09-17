# -*- coding: utf-8 -*-
"""正文体例体检：把人工审核版月刊与当期选目里的原文正文逐段比对。

做三件事：
1. 空格体检：汉字与字母/数字之间、中文标点前后、特殊空白字符（\\xa0 \\u200a 等）；
2. 漏字体检：特殊标点（引号、书名号、破折号、冒号）前后的内容是否与原文一致；
3. 段落比对：审核版缺了哪段（原文有、审核版无），审核版多了哪段（原文无、审核版有）。

输出：_备查/文本体例检查.md（人读）＋ _raw/text_qa.json（机读）。

用法：
    python 27_text_qa.py [--doc <人工审核版.docx>] [--sel <catalog_selection_final.json>]
"""
import argparse
import json
import os
import re
import sys

import docx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_utils import RAW, ROOT, save_json  # noqa: E402
from period_config import P  # noqa: E402
import sources_whitelist as WL  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.environ.get("CEHUI_TOOL_ROOT") or os.path.dirname(HERE)   # 工具根（含“编制排版”）
DEFAULT_SEL = os.path.join(P.sel_dir, "catalog_selection_final.json")
OUT_MD = os.path.join(ROOT, "_备查", "文本体例检查.md")
OUT_JSON = os.path.join(RAW, "text_qa.json")

# 审核版里“页面元素”性质的段落，比对时不算缺失
SIGN_OFF_RE = re.compile(r"^(?:[\u4e00-\u9fa5]{2,4}(?:/摄|供图|摄)|[\u4e00-\u9fa5]{2,4}[\s\u3000][\u4e00-\u9fa5]{2,4})$")


def norm(s):
    return re.sub(r"\s+", "", s or "")


def title_key(t):
    return re.sub(r"[\s\W_]+", "", t or "")[:12]


def doc_lines(path):
    d = docx.Document(path)
    return [p.text.strip() for p in d.paragraphs if p.text.strip()]


def split_doc(lines):
    """按【省份】标题切成条目：[(标题行, 正文行列表)]。"""
    idx = [i for i, t in enumerate(lines) if t.startswith("【")]
    out = []
    for k, i in enumerate(idx):
        end = idx[k + 1] if k + 1 < len(idx) else len(lines)
        body = [t for t in lines[i + 1:end]
                if not t.startswith("来源：") and not t.startswith("原文链接")]
        out.append((lines[i], body))
    return out


def match_item(title, items, used):
    key = title_key(title)
    best, score = None, 0
    for it in items:
        if id(it) in used:
            continue
        k2 = title_key(it["title"])
        common = len(set(key) & set(k2))
        s = common / max(1, len(set(key) | set(k2)))
        if s > score:
            best, score = it, s
    return best, score


def space_issues(text):
    """空格类问题：汉字↔字母/数字之间的多余空格、中文标点前后的空格。"""
    out = []
    pats = [
        (r"[\u4e00-\u9fa5][ \t]+[A-Za-z0-9]", "汉字与字母/数字之间有空格"),
        (r"[A-Za-z0-9][ \t]+[\u4e00-\u9fa5]", "字母/数字与汉字之间有空格"),
        (r"[ \t]+[，。、；：！？）》”’】]", "中文标点前有空格"),
        (r"[，。、；：！？《（“‘【][ \t]+", "中文标点后有空格"),
        (r"[\xa0\u200a\u200b\u2004\u3000]", "特殊空白字符"),
    ]
    for pat, label in pats:
        for m in re.finditer(pat, text):
            seg = text[max(0, m.start() - 14):m.end() + 14].replace("\n", " ")
            line = text[:m.start()].split("\n")[-1]
            if WL.HEADING_LINE.match(line.strip()):
                continue
            if re.search(r"[“\"'][^”\"']*[ \t][^”\"']*[”\"']", seg):
                continue
            out.append((label, seg))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", default=os.path.join(
        TOOL, "编制排版", "测绘地理信息月刊第1期2026年9月15日.docx"))
    ap.add_argument("--sel", default=DEFAULT_SEL)
    ap.add_argument("--out", default=OUT_MD)
    a = ap.parse_args()

    items = json.load(open(a.sel, encoding="utf-8"))
    lines = doc_lines(a.doc)
    entries = split_doc(lines)

    report = {"doc": a.doc, "sel": a.sel, "items": [], "summary": {}}
    used = set()
    md = ["# 文本体例检查（空格 / 标点 / 漏字）", "",
          "- 审核版：`%s`" % os.path.relpath(a.doc, ROOT),
          "- 选目：`%s`" % os.path.relpath(a.sel, ROOT),
          "- 判定口径：全文逐行比对原文；汉字与字母/数字、中文标点前后的多余空格一律标出，"
          "法条标题（第X章/第X条）与引号内标语的空格属正常。", ""]
    n_space = n_missing = n_extra = 0
    for title, body in entries:
        it, score = match_item(title, items, used)
        if it is None or score < 0.5:
            md += ["## %s" % title, "", "- 未能在选目中匹配到对应条目。", ""]
            continue
        used.add(id(it))
        pb = [t for t in (it.get("原文正文") or "").split("\n") if t.strip()]
        hs, ps = [norm(t) for t in body], [norm(t) for t in pb]
        missing = [t for t in pb if norm(t) not in hs]          # 原文有、审核版无
        extra = [t for t in body if norm(t) not in ps]          # 审核版有、原文无
        missing = [t for t in missing if not SIGN_OFF_RE.match(t)]
        si = []
        for t in body:
            si += [("%s｜%s" % (kind, seg)) for kind, seg in space_issues(t)]
        qi = ["%s｜%s" % (k, c) for k, c in WL.check_text_quality("\n".join(body), title)]
        n_space += len(si)
        n_missing += len(missing)
        n_extra += len(extra)
        report["items"].append({"doc_title": title, "sel_title": it["title"],
                                "match": round(score, 2), "space": si,
                                "quality": qi, "missing_from_doc": missing,
                                "extra_in_doc": extra})
        md += ["## %s" % title, "",
               "- 选目对应：%s（匹配度 %.2f）｜审核版 %d 段 / 原文 %d 段"
               % (it["title"], score, len(body), len(pb))]
        if si:
            md += ["", "**空格问题（%d）**" % len(si)] + ["- %s" % s for s in si]
        if qi:
            md += ["", "**体例问题（%d）**" % len(qi)] + ["- %s" % s for s in qi]
        if missing:
            md += ["", "**原文有、审核版缺（%d）**" % len(missing)] + \
                  ["- %s" % t[:120] for t in missing]
        if extra:
            md += ["", "**审核版有、原文无（%d）**" % len(extra)] + \
                  ["- %s" % t[:120] for t in extra]
        md += [""]

    report["summary"] = {"条数": len(entries), "空格问题": n_space,
                         "审核版缺段": n_missing, "审核版多段": n_extra}
    md = md[:5] + ["- 汇总：%s" % json.dumps(report["summary"], ensure_ascii=False), ""] + md[5:]
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w", encoding="utf-8").write("\n".join(md))
    save_json(OUT_JSON, report)
    print("条数 %d｜空格问题 %d｜审核版缺段 %d｜审核版多段 %d"
          % (len(entries), n_space, n_missing, n_extra))
    print("输出：%s" % a.out)


if __name__ == "__main__":
    main()
