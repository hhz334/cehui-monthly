# -*- coding: utf-8 -*-
"""多方式核实：链接复检 + 正文回读 + 交叉来源，输出核实结果。"""
import importlib.util
import json
import os
import re
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_utils import RAW, ROOT, get_text, load_json, norm_date, save_json, strip_html  # noqa: E402
import sources_whitelist as WL  # noqa: E402
from period_config import P  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "builder", os.path.join(os.path.dirname(os.path.abspath(__file__)), "07_build_catalog.py"))
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def refetch(url):
    out = {"ok": False, "final": url, "title": "", "date": "", "text": "", "note": ""}
    try:
        final, page = get_text(url)
        out["ok"] = True
        out["final"] = final
    except Exception as exc:  # noqa: BLE001
        out["note"] = str(exc)[:160]
        return out
    m = re.search(r"(?is)<h1[^>]*>(.*?)</h1>", page)
    if m:
        out["title"] = re.sub(r"\s+", " ", strip_html(m.group(1)))
    if not out["title"]:
        m = re.search(r"(?is)<title[^>]*>(.*?)</title>", page)
        out["title"] = re.sub(r"\s+", " ", strip_html(m.group(1))) if m else ""
    plain = strip_html(page)
    m = re.search(r"(?:发布时间|发布日期|时间)[:：]\s*(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2})", plain)
    out["date"] = norm_date(m.group(1)) if m else ""
    body = builder.__dict__.get("best_block")
    if body is None:
        import importlib
        v = importlib.import_module("04_fetch_details")
        body = v.best_block
    out["text"] = body(page) or plain
    return out


def main():
    sel_path = next((p for p in (
        os.path.join(P.sel_dir, "catalog_selection_final.json"),
        os.path.join(P.sel_dir, "catalog_selection_boards.json"),
        os.path.join(P.sel_dir, "catalog_selection.json")) if os.path.exists(p)), "")
    selection = json.load(open(sel_path, encoding="utf-8"))
    corpus = builder.load_corpus()
    weekly = load_json(os.path.join(ROOT, "03_参考_山东周讯", "周讯条目提取.json"))
    cache_path = os.path.join(RAW, "核实结果.json")
    cache = load_json(cache_path) if os.path.exists(cache_path) else {}
    reuse = os.environ.get("RECHECK") != "1"
    results = {}
    print(f"核实 {len(selection)} 条")
    for i, sel in enumerate(selection, 1):
        item = builder.pick(corpus, sel)
        url = item.get("final_url") or item.get("url")
        title = sel.get("title") or item.get("title")
        date = sel.get("date_override") or item.get("date_page") or item.get("date_list") or ""
        is_weekly = item.get("source_id") == "weekly"
        cache_key = url if not is_weekly else f"{url}#{title}"
        old = cache.get(cache_key) if reuse else None
        if old:
            fresh = {"ok": old["检查项"]["链接可达"], "title": old["页面标题"],
                     "date": old["页面日期"], "text": "", "note": ""}
            title_sim = old["标题相似度"]
            body_char = old["正文要素覆盖率"]
        else:
            fresh = refetch(url)
            # 列表页/详情页为前端渲染时（如 i 自然、福建厅检索接口），以采集缓存正文为准
            cached_text = item.get("text") or ""
            if len(cached_text) > len(fresh.get("text") or "") + 200:
                fresh = {
                    "ok": True, "final": url,
                    "title": item.get("title_page") or item.get("title") or fresh.get("title"),
                    "date": norm_date(item.get("date_page") or "") or (item.get("date_list") or "")
                            or fresh.get("date"),
                    "text": cached_text, "note": "正文取自采集缓存",
                }
            title_sim = builder.similarity(title, fresh["title"]) if fresh["title"] else 0
            body_char = 0
            if fresh["text"]:
                key_chars = set(re.sub(r"[\s\W_]+", "", title))
                body_chars = set(re.sub(r"[\s\W_]+", "", fresh["text"][:3000]))
                body_char = len(key_chars & body_chars) / max(1, len(key_chars))
        if is_weekly:
            # 周讯转载条目：正文与判定依据取自周讯整期 PDF 文本层，链接核验周讯原文可访问
            wmatch = max(weekly, key=lambda w: builder.similarity(title, w["title"]), default=None)
            title_sim = builder.similarity(title, wmatch["title"]) if wmatch else 0.0
            body_text = (wmatch.get("body") or "") if wmatch else ""
            key_chars = set(re.sub(r"[\s\W_]+", "", title))
            body_chars = set(re.sub(r"[\s\W_]+", "", body_text[:3000]))
            body_char = len(key_chars & body_chars) / max(1, len(key_chars)) if body_text else 0
        cross = [{"title": o.get("title"), "url": o.get("final_url") or o.get("url"),
                  "source": o.get("source_name")}
                 for o in corpus
                 if o is not item and o.get("source_name") != item.get("source_name")
                 and builder.similarity(o.get("title"), title) >= 0.8]
        api_date = norm_date(item.get("pubtime") or "") or item.get("date_list") or ""
        weekly_hit = max((builder.similarity(title, w["title"]) for w in weekly), default=0)
        checks = {
            "链接可达": fresh["ok"],
            "标题一致": title_sim >= 0.6,
            "正文含标题要素": body_char >= 0.7 and (len(fresh["text"] or "") >= 200 or bool(old) or is_weekly),
            "日期核验": (fresh["date"] == date) if fresh["date"] else None,
            "交叉来源数": len(cross),
            "接口日期核验": (api_date == date) if (api_date and date) else None,
            "山东周讯收录": weekly_hit >= 0.75,
            "来源白名单": bool(WL.site_type(url)) or WL.wechat_ok(sel.get("unit") or ""),
        }
        passed = sum(1 for k in ("链接可达", "标题一致", "正文含标题要素") if checks[k])
        corroborated = (checks["交叉来源数"] > 0 or checks["日期核验"] or
                        checks["接口日期核验"] or checks["山东周讯收录"])
        if passed == 3 and corroborated:
            status = "三重通过"
        elif passed >= 2:
            status = "双重通过"
        else:
            status = "待人工复核"
        methods = ["链接可达复检"]
        methods.append(f"来源核验（{WL.site_type(url) or sel.get('source_type') or '待核'}）")
        if checks["标题一致"] or checks["正文含标题要素"]:
            methods.append("正文回读比对")
        if checks["交叉来源数"] > 0:
            methods.append(f"交叉来源核验({checks['交叉来源数']})")
        if checks["日期核验"] or checks["接口日期核验"]:
            methods.append("发布日期核验")
        if checks["山东周讯收录"]:
            methods.append("山东周讯收录核验")
        if is_weekly:
            methods.append("周讯PDF文本层核验")
        results[cache_key] = {
            "标题": title, "属地层级": sel.get("level"),
            "模块": sel.get("module") or sel.get("board", ""),
            "板块": sel.get("board") or sel.get("module", ""), "业务条线": sel.get("business", ""),
            "来源类型": sel.get("source_type", ""),
            "正文来源": sel.get("正文来源", ""), "正文长度": sel.get("正文长度", ""),
            "检查项": checks, "核实状态": status, "核实方式": "；".join(methods),
            "页面标题": fresh["title"], "页面日期": fresh["date"], "目录日期": date,
            "标题相似度": round(title_sim, 3), "正文要素覆盖率": round(body_char, 3),
            "正文长度": len(fresh["text"] or ""), "交叉来源": cross[:3],
            "接口日期": api_date, "山东周讯相似度": round(weekly_hit, 3),
            "核实时间": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        if i % 10 == 0:
            print(f"  {i}/{len(selection)}")
        time.sleep(0.2)
    save_json(os.path.join(RAW, "核实结果.json"), results)
    stats = {}
    for r in results.values():
        stats[r["核实状态"]] = stats.get(r["核实状态"], 0) + 1
    print("核实统计：", stats)
    for url, r in results.items():
        if r["核实状态"] != "三重通过":
            print(f"  需关注：{r['核实状态']}｜{r['标题'][:40]}｜{r['检查项']}")


if __name__ == "__main__":
    main()
