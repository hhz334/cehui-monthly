# -*- coding: utf-8 -*-
"""按新口径重建本期选目：三个板块 + 10 条业务条线 + 来源白名单核验。

做四件事：
1. 归并三板块（国家公文并入政策法规，会议报告与跨界融合按主题归入技术应用／科技前沿，
   经验做法稿归技术应用类；2026-09-17 起取消“媒体动态类”）；
2. 国际、科普与版图宣传、福建三类条目移入《_备查/未收录条目.md》；
3. 逐条做来源白名单核验，公众号不在白名单或无法回溯原发布方的移入《_备查/周讯回溯待办.md》；
4. 按 10 条业务条线打标，输出 catalog_selection_boards.json 供 07 生成目录。
"""
import importlib.util
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_utils import RAW, ROOT, ensure_dir, load_json, save_json  # noqa: E402
import sources_whitelist as WL  # noqa: E402
from period_config import P  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SEL_PATH = os.path.join(HERE, "catalog_selection.json")
SEL_V2 = os.path.join(RAW, "catalog_selection_base_v2.json")
AUTO_SEL = os.path.join(RAW, "auto_shortlist.json")
MANUAL_SEL = os.path.join(RAW, "manual_includes.json")
OUT_SEL = os.path.join(HERE, "catalog_selection_boards.json")
BACKUP_DIR = os.path.join(ROOT, "_备查")

# v2 里被剥离进《06_国家政策文件附录》的国家公文，新口径下回到政策法规
APPENDIX_TITLES = [
    "关于征求《政务服务平台政务服务地图建设技术规范》",
    "绿色勘查绿色矿山系列国家标准发布",
    "测绘科学与工程自然资源部重点实验室开放基金课题2026年度申请指南",
    "自然资源部印发《非涉密测绘地理信息成果管理办法》",
    "自然资源部发布“车路云一体化”试点地理信息安全防控指南",
    "自然资源部党组：推动地理信息新型基础设施建设",
    "激发地理信息数据要素潜能",
    "激活时空数据 拥抱数智未来",
    "关于开展2026年实景三维数据赋能高质量发展创新应用典型案例征集工作的通知",
]

# 明确不收的模块与层级
EXCLUDED_MODULES = {"国际视野": "国际内容不收", "科普与版图宣传": "科普与版图宣传不收（非经验稿）"}
EXCLUDED_LEVELS = {"福建": "福建本地内容不进目录，留原始语料备查"}

# 标题含物料／评论特征的不收；宣传日与版图意识类按"收录例外"判定（部级与省级可收，地市级与物料不收）
EXCLUDE_TITLE_PAT = __import__("re").compile(
    r"宣传海报|海报|短视频|素材|集锦|评论员|社论|言论|开学第一课")

# 原始来源单位 → 是否官网类（用于周讯条目的回溯判定）
SITE_HINTS = [r"网站", r"官网", r"厅$", r"厅（", r"局$", r"部$", r"部（", r"学会", r"协会",
              r"中心$", r"大学", r"学院", r"研究院", r"实验室", r"出版社", r"报社"]


def load_builder():
    spec = importlib.util.spec_from_file_location(
        "builder", os.path.join(HERE, "07_build_catalog.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def origin_site_like(origin):
    return any(__import__("re").search(p, origin or "") for p in SITE_HINTS)


def norm_title(title):
    """标题归一：去项目符号、序号前缀、空白与标点，用于去重与同一事件判定。"""
    t = re.sub(r"^[·•∙・\-\u2022\s]+", "", title or "")
    t = re.sub(r"^\d{1,3}[\s.、]+(?=[^\d])", "", t)
    t = re.split(r"\s*(?:时间|来源|发布时间|发布日期)\s*[:：]", t)[0]
    return re.sub(r"[\s\W_]+", "", t).lower()


def trace_in_corpus(corpus, title, builder):
    """在已采集语料里找同名条目，且来源为官网的，视为回溯成功。"""
    best, best_score = None, 0.0
    for it in corpus:
        url = it.get("final_url") or it.get("url") or ""
        kind = WL.site_type(url)
        if not kind or kind == "公众号":
            continue
        score = builder.similarity(title, it.get("title"))
        if score > best_score:
            best, best_score = it, score
    if best is not None and best_score >= 0.88:
        return best
    return None


def main():
    builder = load_builder()
    corpus = builder.load_corpus()
    current = load_json(SEL_PATH)
    v2 = load_json(SEL_V2) if os.path.exists(SEL_V2) else []

    # 1) 补回国家公文
    have = {s.get("title", "") for s in current}
    restored = []
    for s in v2:
        t = s.get("title", "")
        if any(a in t for a in APPENDIX_TITLES) and t not in have:
            s = dict(s)
            s["module"] = "政策措施"
            s["restored_from_appendix"] = True
            restored.append(s)
            have.add(t)

    # 2) 合并新来源自动初筛条目（已是四板块口径，按标题去重）
    auto = load_json(AUTO_SEL) if os.path.exists(AUTO_SEL) else []
    have2 = {norm_title(s.get("title", "")) for s in current + restored}
    auto_added = []
    for s in auto:
        key = norm_title(s.get("title", ""))
        if not key or key in have2:
            continue
        have2.add(key)
        auto_added.append(s)
    candidates = current + restored + auto_added

    # 3) 合并人工指定采纳条目（如部级专题、中央媒体地方频道稿件）
    if os.path.exists(MANUAL_SEL):
        manual = load_json(MANUAL_SEL)
        have3 = {norm_title(s.get("title", "")) for s in candidates}
        manual_added = [s for s in manual
                        if s.get("title") and norm_title(s["title"]) not in have3]
        if manual_added:
            print(f"  人工采纳并入 {len(manual_added)} 条")
        candidates = candidates + manual_added
    kept, backup, todo = [], [], []

    for sel in candidates:
        title = sel.get("title", "")
        try:
            item = builder.pick(corpus, sel)
        except SystemExit:
            backup.append((sel, "语料中未匹配到条目，无法核验来源"))
            continue
        url = item.get("final_url") or item.get("url") or ""
        source_name = sel.get("unit") or item.get("source_name") or ""
        note = sel.get("note", "") or ""
        origin = item.get("origin_page") or ""
        module = sel.get("module", "")
        level = sel.get("level") or item.get("level") or ""

        # 2) 排除项
        if module in EXCLUDED_MODULES:
            backup.append((sel, EXCLUDED_MODULES[module]))
            continue
        if level in EXCLUDED_LEVELS:
            backup.append((sel, EXCLUDED_LEVELS[level]))
            continue
        # 人工指定采纳的条目由人判断，不受宣传类自动排除限制
        if not sel.get("manual") and (
                EXCLUDE_TITLE_PAT.search(f"{title} {sel.get('summary','')} {note}")
                or WL.promo_excluded(title, sel.get("summary", ""), sel.get("unit", ""))):
            backup.append((sel, "推广宣传/评论类内容不收"))
            continue
        if WL.title_excluded(title):
            backup.append((sel, "财务决算/采购公告/期次页等非动态内容不收"))
            continue
        if WL.is_non_text(title, sel.get("source_url_checked", "") or "", sel.get("summary", "")):
            backup.append((sel, "视频/音频/图集类非文字稿不收"))
            continue
        if item.get("video_page"):
            backup.append((sel, "视频类页面（详情页含视频播放器）不收"))
            continue

        # 3) 来源核验
        kind = WL.site_type(url)
        trace_note = ""
        if kind and kind != "公众号":
            source_type = kind
        elif kind == "公众号" or "mp.weixin.qq.com" in url:
            account = sel.get("unit") or origin or source_name
            if WL.wechat_ok(account):
                source_type = "白名单公众号"
                trace_note = f"来源为白名单公众号：{account}"
            elif any(a in note for a in ("周讯", "原始来源")):
                hit = trace_in_corpus(corpus, title, builder)
                if hit is not None:
                    url = hit.get("final_url") or hit.get("url") or url
                    source_type = WL.site_type(url) or "主管部门官网"
                    trace_note = "由周讯回溯到官网原文"
                    item = hit
                    sel = dict(sel)
                    sel["match"] = url            # 让 07 成稿时按回溯后的官网链接取正文
                    sel["source_name"] = hit.get("source_name") or sel.get("source_name")
                    sel["carrier"] = hit.get("carrier") or sel.get("carrier")
                    sel["date_override"] = (hit.get("date_page") or hit.get("date_list")
                                            or sel.get("date_override"))
                else:
                    todo.append((sel, f"原始来源：{account}；需回溯到官网原文后入目录"))
                    continue
            else:
                backup.append((sel, f"来源不在白名单：{account}"))
                continue
        else:
            account = sel.get("unit") or origin or source_name
            if WL.wechat_ok(account):
                source_type = "白名单公众号"
            else:
                backup.append((sel, f"来源域名不在白名单：{WL.host_of(url)}（{account}）"))
                continue

        # 4) 三板块 + 业务条线
        resolved_date = (sel.get("date_override") or item.get("date_page")
                         or item.get("date_list") or "")
        if resolved_date and not (P.window_from <= resolved_date <= P.window_to):
            backup.append((sel, f"发布日期 {resolved_date} 不在本期窗口（{P.window_from}~{P.window_to}）"))
            continue
        board = sel.get("board") or WL.board_of(module, title, sel.get("summary", ""), note)
        if sel.get("restored_from_appendix"):
            board = "政策法规"
        hits = WL.business_of(title, sel.get("summary", ""), sel.get("keywords", ""))
        out = dict(sel)
        out.update({
            "board": board,
            "business": sel.get("business") or WL.business_primary(hits),
            "business_all": [h[0] for h in hits],
            "source_type": sel.get("source_type") or source_type,
            "source_url_checked": url,
            "trace": trace_note,
        })
        kept.append(out)

    # ---- 排序：板块 → 层级 → 日期倒序 ----
    level_order = {"部级": 0, "行业与官媒": 1, "外省": 2}
    kept.sort(key=lambda r: (WL.BOARDS.index(r["board"]),
                             level_order.get(r.get("level", ""), 9),
                             r.get("date_override") or "", r.get("title", "")))
    save_json(OUT_SEL, kept)

    # ---- 备查清单 ----
    ensure_dir(BACKUP_DIR)
    lines = ["# 未收录条目（备查）", "",
             "- 口径：只保留政策法规、技术应用类、科技前沿类三个板块（取消“媒体动态类”，经验做法稿归技术应用类）；"
             "国际、科普与版图宣传、福建本地内容不进目录；领导终稿（0917）删除的条目一并列在文末。",
             f"- 条数：{len(backup)}", "", "| 序号 | 标题 | 原模块 | 层级 | 不收录理由 |",
             "| --- | --- | --- | --- | --- |"]
    for i, (sel, why) in enumerate(backup, 1):
        lines.append(f"| {i} | {sel.get('title','')} | {sel.get('module','')} | "
                     f"{sel.get('level','')} | {why} |")
    # 领导终稿（0917）删除的条目：只作备查，不再进入目录
    leader_path = os.path.join(RAW, "leader_%s.json" % (P.leader_label or "0917"))
    if os.path.exists(leader_path):
        leader = load_json(leader_path)
        removed = leader.get("removed", [])
        if removed:
            lines += ["", f"## 领导终稿（{P.leader_label or '0917'}）删除条目（{len(removed)} 条，仅备查）", "",
                      "| # | 原序号 | 原板块 | 标题 | 删除依据 |", "| --- | --- | --- | --- | --- |"]
            for i, x in enumerate(removed, 1):
                lines.append(f"| {i} | {x.get('no','')} | {x.get('sec','')} | "
                             f"{x.get('title','')} | {x.get('reason','')} |")
    with open(os.path.join(BACKUP_DIR, "未收录条目.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    lines = ["# 周讯来源回溯待办", "",
             "- 口径：周讯只作线索，条目须回溯到原发布方官网或白名单公众号原文；未回溯到的不入目录。",
             "- 建议检索入口：中国自然资源报数字报全文检索（`99_脚本/20_zrzyb.py b-search`）、"
             "原发布单位官网站内检索、省厅统一检索（如浙江 `22_zhejiang.py a-search`）。",
             f"- 待回溯条数：{len(todo)}", "", "| 序号 | 标题 | 原始来源 | 处理要求 |",
             "| --- | --- | --- | --- |"]
    for i, (sel, why) in enumerate(todo, 1):
        lines.append(f"| {i} | {sel.get('title','')} | {sel.get('unit','')} | {why} |")
    with open(os.path.join(BACKUP_DIR, "周讯回溯待办.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    import collections
    print(f"入目录 {len(kept)} 条；备查 {len(backup)} 条；回溯待办 {len(todo)} 条")
    print("板块分布：", dict(collections.Counter(r["board"] for r in kept)))
    print("来源类型：", dict(collections.Counter(r["source_type"] for r in kept)))
    print("业务条线：", dict(collections.Counter(r["business"] or "未标注" for r in kept)))
    print(f"输出：{OUT_SEL}")


if __name__ == "__main__":
    main()
