# -*- coding: utf-8 -*-
"""生成本期选目：领导终稿骨架 → 目录（三板块，2026-09-17 起取消“媒体动态类”）。

本期为“终稿直出”：领导 0917 批注版 16 条即最终目录，不补位；
下一期起按三板块走两级产出（初版约 35 条 → 领导终稿 20—25 条）。

产出：
- catalog_selection_draft.json（供 25 号来源实体校验 → 07 成稿）
- _备查/终稿16条构成说明.md（骨架、三板块构成、排序与口径说明）
"""
import glob
import importlib.util
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_utils import RAW, ROOT, load_json, save_json  # noqa: E402
import sources_whitelist as WL  # noqa: E402
from period_config import P  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
LEADER = os.path.join(RAW, "leader_%s.json" % (P.leader_label or "0917"))
# 元数据取自保留的全量底稿（68 条），避免上一轮校验结果反向影响骨架元数据
SEL_FINAL = os.path.join(RAW, "full68_selection.json")
OUT = os.path.join(P.sel_dir, "catalog_selection_draft.json")
REPORT = os.path.join(ROOT, "_备查", P.data.get("selection_report") or "终稿16条构成说明.md")

BOARDS = ["政策法规", "技术应用类", "科技前沿类"]
# 产出模式：DIRECT_FINAL=True 为“领导终稿直出”（本期），False 为初版补位（下期起）
DIRECT_FINAL = True
TARGET_TOTAL = 16 if DIRECT_FINAL else 35
# 下期初版目标构成（三板块、35 条时）：政策法规＋科技前沿类约 31%、技术应用类约 69%
TARGET_BOARD = {"政策法规": 6, "技术应用类": 24, "科技前沿类": 5}
# 初版补充按三板块粗筛（不设二级分类）；终稿直出时为空
BOARD_PLAN = [] if DIRECT_FINAL else [("政策法规", 6), ("技术应用类", 24), ("科技前沿类", 5)]
# 论文／国际奖项与“论文摘选”通道已停用：这两类来源不再参与候选
EXCLUDE_SOURCE_IDS = ("frontier", "csgpc_lwzx")
EXPERIENCE = re.compile(r"探索|实践|做法|经验|织密|打造|新范式|新路径|纪实|担当|样本|亮点|走在前")
LEVEL_RANK = {"部级": 0, "行业与官媒": 1, "外省": 2}


def norm(t):
    return re.sub(r"[\s\W_]+", "", t or "")


# 骨架调整表：键为规范化标题。本期领导终稿已压缩为 16 条，无需再剔除或迁移；
# 如需调整（如按 R8 实质内容门槛剔除、按归类修正迁移板块），在此登记并写明理由。
DROP_SKELETON = {}
MOVE_BOARD = {}


def similar(a, b):
    from difflib import SequenceMatcher
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def order_key(s):
    """R4 排序键：层级（国家→地方）→ 业务中心度（中心→边缘）→ 日期倒序。"""
    return (LEVEL_RANK.get(s.get("level") or "", 9),
            WL.BUSINESS_CENTER_RANK.get(s.get("business") or "", 99),
            WL.date_rank(s.get("date_override") or ""))


def order_selection(items):
    """类内排序：骨架条目保持领导版相对顺序，补充条目插入到第一条排序键大于它的条目之前。"""
    out = []
    for board in BOARDS:
        block = [s for s in items if s["board"] == board]
        merged = [s for s in block if s.get("is_skeleton")]
        extras = sorted([s for s in block if not s.get("is_skeleton")], key=order_key)
        for e in extras:
            k = order_key(e)
            pos = len(merged)
            for i, s in enumerate(merged):
                if order_key(s) > k:
                    pos = i
                    break
            merged.insert(pos, e)
        out.extend(merged)
    return out


def dup_of(title, titles):
    """与既有条目是否为同一事件（模糊判重）。"""
    n = norm(title)
    for t in titles:
        m = norm(t)
        if similar(title, t) >= 0.85:
            return True
        # 一条标题包含另一条的主体（如"激发地理信息数据要素潜能…"的长短两版）
        if len(n) >= 10 and len(m) >= 10 and (n[:14] in m or m[:14] in n):
            return True
    return False


def load_corpus():
    items = []
    for p in glob.glob(os.path.join(RAW, "*_detail.json")):
        for it in load_json(p):
            items.append(it)
    return items


def fetch_wechat(url):
    spec = importlib.util.spec_from_file_location(
        "v25", os.path.join(HERE, "25_verify_source_entity.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    text, title, date = mod.fetch_wechat(url)
    return text, title, date


def acceptable_source(url, unit=""):
    """来源可用性：官网白名单，或部级/省级公众号（R5 分层）。"""
    if not url:
        return False
    kind = WL.site_type(url)
    if kind and kind != "公众号":
        return True
    if "mp.weixin.qq.com" in url:
        biz = WL.wechat_biz(url)
        if not biz:
            _, biz = WL.resolve_wechat_account(url)
            if not biz:
                return False
        return biz in WL.WECHAT_TIER
    return False


def wechat_unit(url):
    """公众号条目的来源单位名：按页面实际账号名（或分层白名单登记名）标注。"""
    acc, biz = WL.resolve_wechat_account(url)
    if not acc:
        acc = WL.WECHAT_TIER.get(biz, ("", ""))[0]
    return (acc + "微信公众号") if acc else ""


def main():
    leader = load_json(LEADER)
    final = load_json(SEL_FINAL)
    by_title = {norm(s["title"]): s for s in final}
    corpus = load_corpus()
    corpus_titles = {norm(it.get("title")) for it in corpus}
    extra_details = []      # 语料里没有的骨架条目（如领导新增的公众号稿）写入语料

    frontier = []                      # 论文／国际奖项入口已停用（见 EXCLUDE_SOURCE_IDS）
    selected, used, dropped, moved = [], set(), [], []
    for sec in BOARDS:
        for it in [x for x in leader["final"] if x["sec"] == sec]:
            key = norm(it["title"])
            if key in DROP_SKELETON:
                dropped.append({"title": it["title"], "board": sec, "reason": DROP_SKELETON[key]})
                used.add(key)      # 同时挡掉语料里同题的重采条目，避免"剔除后又从候选池回来"
                continue
            board = MOVE_BOARD.get(key, sec)
            if board != sec:
                moved.append({"title": it["title"], "from": sec, "to": board})
            used.add(key)
            base = by_title.get(key) or {}
            text = base.get("原文正文") or ""
            urls = it.get("urls") or []
            if not text and urls and "mp.weixin.qq.com" in urls[0]:
                text, _, _ = fetch_wechat(urls[0])
            if key not in corpus_titles and text:
                extra_details.append({
                    "url": urls[0] if urls else "", "final_url": urls[0] if urls else "",
                    "title": it["title"], "title_page": it["title"],
                    "date_page": it.get("added_date") or "", "date_list": it.get("added_date") or "",
                    "source_id": "leader_added", "source_name": "公众号",
                    "level": "外省", "carrier": "公众号", "text": text, "text_len": len(text),
                    "http_ok": True,
                })
            entry = {
                "board": board, "title": it["title"],
                # 新增的公众号条目按分层白名单标注来源单位
                "unit": base.get("unit") or (
                    wechat_unit(urls[0]) if (not base and urls and "mp.weixin.qq.com" in urls[0]) else ""),
                "level": base.get("level") or ("外省" if it.get("prov") not in (None, "全国") else "部级"),
                "province": it.get("prov") or base.get("province") or "全国",
                "source_type": base.get("source_type")
                or (WL.site_type(urls[0]) if urls else "") or "主管部门官网",
                "source_url_checked": (urls[0] if (urls and acceptable_source(urls[0]))
                                       else base.get("source_url_checked") or (urls[0] if urls else "")),
                "date_override": base.get("date_override") or it.get("added_date") or "",
                "priority": base.get("priority") or ("A" if board == "政策法规" else "B"),
                "business": base.get("business") or "",
                "summary": it.get("summary") or base.get("摘要") or "",
                "原文正文": text, "is_skeleton": True,
            }
            # 继承原记录的定位与备注，保证 25 号能定位到官网原文而不是转载页
            for k in ("match", "note", "keywords", "sub", "carrier"):
                if base.get(k):
                    entry[k] = base[k]
            if base.get("source_url_checked") and acceptable_source(base["source_url_checked"]):
                entry["source_url_checked"] = base["source_url_checked"]
            if it["title"].startswith("《江苏省") and len(urls) > 1:
                entry["extra_url"] = urls[1]
            elif urls and not acceptable_source(urls[0]):
                entry["extra_url"] = urls[0]      # 领导提供的转载链接保留为延伸链接
            if not entry["unit"] and urls and "mp.weixin.qq.com" in urls[0]:
                unit = wechat_unit(urls[0])
                if unit:
                    entry["unit"] = unit
            if urls and "mp.weixin.qq.com" in urls[0]:
                ok_wx, _ = WL.wechat_source_ok(urls[0])
                entry["source_type"] = "白名单公众号" if ok_wx else entry["source_type"]
            if not entry["business"]:
                hits = WL.business_of(entry["title"], entry.get("summary") or "", "")
                entry["business"] = hits[0][0] if hits else "测绘行业管理与技术服务"
            selected.append(entry)

    if extra_details:
        save_json(os.path.join(RAW, "leader_detail.json"), extra_details)
        for e in extra_details:
            for s in selected:
                if norm(s["title"]) == norm(e["title"]):
                    s.setdefault("match", e["final_url"])

    def usable(it):
        t = it.get("title") or ""
        date = it.get("date_page") or it.get("date_list") or ""
        text = it.get("text") or ""
        url = it.get("final_url") or it.get("url") or ""
        if not t or not text or len(text) < 200:
            return False
        if date and not (P.window_from <= date <= P.window_to):
            return False
        if (it.get("level") or "") == "福建" or "福建" in (it.get("source_name") or ""):
            return False
        if norm(t) in used:
            return False
        if not acceptable_source(url):
            return False
        if not re.search(r"测绘|实景三维|遥感|影像|基准|北斗|导航定位|地图|地理信息|时空|无人机|"
                         r"调查监测|变更调查|确权|地籍|耕地保护|质检|应急|"
                         r"执法|违法|非农化|乱占耕地|挖湖造景|督察|生态修复|砂石|采矿|矿区", t):
            return False
        body = WL.clean_body(text, t)
        if body == "" or WL.is_junk_text(body):
            return False
        ex, _ = WL.draft_excluded(t, it.get("source_name") or "", it.get("level") or "")
        return not ex

    candidates = []
    for it in corpus:
        # 论文摘选、论文／国际奖项入口已停用，其语料不参与候选
        if (it.get("source_id") or "") in EXCLUDE_SOURCE_IDS:
            continue
        if not usable(it):
            continue
        t = it["title"]
        body = WL.clean_body(it.get("text") or "", t)
        hits = WL.business_of(t, body[:400], "")
        board = WL.board_of_v2("", t, body[:400], "", it.get("level") or "")
        if not hits:
            continue
        # 经验做法稿不再单列，统一留在技术应用类（不设二级分类）
        candidates.append({"it": it, "board": board, "business": hits[0][0], "body": body})

    added = []
    skeleton_titles = [s["title"] for s in selected]
    for board, quota in BOARD_PLAN:
        # 板块粗筛：只按板块取候选，板内按层级（部级/行业→外省）与日期倒序择优
        pool = [c for c in candidates if c["board"] == board]
        pool.sort(key=lambda c: (LEVEL_RANK.get(c["it"].get("level") or "外省", 9),
                                 -int((c["it"].get("date_page") or c["it"].get("date_list")
                                       or P.window_from).replace("-", ""))))
        picked = 0
        for c in pool:
            if picked >= quota:
                break
            it = c["it"]
            it = dict(it)
            it["title"] = WL.clean_title(it.get("title"))
            if norm(it["title"]) in used:
                continue
            if dup_of(it["title"], skeleton_titles) or dup_of(it["title"], [s["title"] for s in added]):
                continue
            # 同事件限一条：按事件关键词（灾害/流域/事件名）去重
            EVENT = r"吉隆|泥石流|防汛|台风|暴雨|汛期|地震|柞水|抢险|灾区|救援"
            event_key = re.search(EVENT, it["title"])
            if event_key and any(re.search(EVENT, x["title"])
                                 for x in selected + added):
                continue
            used.add(norm(it["title"]))
            url = it.get("final_url") or it.get("url") or ""
            sel = {
                "board": board, "title": it["title"], "unit": it.get("source_name") or "",
                "level": it.get("level") or "外省", "province": it.get("province") or "全国",
                "source_type": WL.site_type(url) or "主管部门官网",
                "source_url_checked": url, "date_override": it.get("date_page") or it.get("date_list") or "",
                "priority": "A" if it.get("level") == "部级" else "B",
                # 业务条线只作标签与统计，不作补位依据
                "business": c["business"],
                "summary": c["body"][:180],
                "原文正文": c["body"], "is_skeleton": False, "gap_board": board,
            }
            selected.append(sel)
            added.append(sel)
            picked += 1

    save_json(OUT, selected)

    # 若仍不足目标条数，按最大可用条线继续补（并在报告中说明）
    # 终稿直出时 TARGET_TOTAL=16 且骨架即 16 条，shortfall=0（不补位）；
    # 下期起 TARGET_TOTAL=35，按三板块初版目标补位。
    shortfall = TARGET_TOTAL - len(frontier) - len(selected)
    if shortfall > 0:
        backup_pool = sorted([c for c in candidates if not c.get("_used")],
                             key=lambda c: (LEVEL_RANK.get(c["it"].get("level") or "外省", 9),
                                            -int((c["it"].get("date_page") or c["it"].get("date_list")
                                                  or P.window_from).replace("-", ""))))
        for c in backup_pool:
            if shortfall <= 0:
                break
            it = dict(c["it"])
            it["title"] = WL.clean_title(it.get("title"))
            if norm(it["title"]) in used:
                continue
            if dup_of(it["title"], [s["title"] for s in selected]):
                continue
            event_key = re.search(r"吉隆|泥石流|防汛|台风|暴雨|汛期|地震|柞水|抢险|灾区|救援",
                                  it["title"])
            if event_key and any(re.search(r"吉隆|泥石流|防汛|台风|暴雨|汛期|地震|柞水|抢险|灾区|救援",
                                           x["title"]) for x in selected):
                continue
            used.add(norm(it["title"]))
            url = it.get("final_url") or it.get("url") or ""
            sel = {
                "board": c["board"] or "技术应用类",
                "title": it["title"], "unit": it.get("source_name") or "",
                "level": it.get("level") or "外省", "province": it.get("province") or "全国",
                "source_type": WL.site_type(url) or "主管部门官网",
                "source_url_checked": url, "date_override": it.get("date_page") or it.get("date_list") or "",
                "priority": "A" if it.get("level") == "部级" else "B",
                "business": c["business"], "summary": c["body"][:180],
                "原文正文": c["body"], "is_skeleton": False, "gap_line": c["business"] + "（兜底补位）",
            }
            selected.append(sel)
            added.append(sel)
            shortfall -= 1
        save_json(OUT, selected)

    # ---- 论文／国际奖项补位已停用（frontier 恒为空，保留代码位以便日后恢复） ----
    for s in frontier:
        s = dict(s)
        s["is_skeleton"] = False
        selected.append(s)
        added.append(s)

    # ---- 类内排序：板块 → 层级（国家→地方）→ 业务中心度（中心→边缘）→ 日期倒序 ----
    selected = order_selection(selected)
    save_json(OUT, selected)

    totals = {b: sum(1 for s in selected if s["board"] == b) for b in BOARDS}
    pol = totals["政策法规"] + totals["科技前沿类"]
    tm = totals["技术应用类"]
    n = max(1, len(selected))
    n_skel = sum(1 for s in selected if s["is_skeleton"])
    lines = [f"# 选目构成说明（{P.title_range}，三板块）", "",
             "- 产出模式：**领导终稿直出**（本期不补位）；骨架 = 领导 0917 批注版 %d 条（顺序按领导版）" % n_skel,
             "- 骨架调整：剔除 %d 条、板块迁移 %d 条（本期均无）" % (len(dropped), len(moved)),
             "- 合计：**%d 条**｜政策法规＋科技前沿类 %d 条（%.0f%%）｜技术应用类 %d 条（%.0f%%）"
             % (len(selected), pol, 100 * pol / n, tm, 100 * tm / n),
             "- 板块构成：%s" % "、".join("%s %d" % (b, totals[b]) for b in BOARDS), "",
             "> 口径说明：2026-09-17 起取消“媒体动态类”，原该类经验做法稿归技术应用类；"
             "国际内容一律不收，不设前沿论文与国际协会奖项例外；科技前沿类按 R8 实质内容门槛，"
             "只收有方法／指标／模型／成果的内容。下期起按三板块走两级产出（初版约 35 条、终稿 20—25 条）。", "",
             "## 一、目录条目（按板块）", ""]
    for sec in BOARDS:
        lines += ["**%s**" % sec, ""]
        for s in selected:
            if s["board"] == sec and s["is_skeleton"]:
                lines.append("- %s" % s["title"])
        lines.append("")
    lines += ["## 二、骨架调整记录（本期无）", ""]
    lines += ["| 处理 | 标题 | 原板块 | 说明 |", "| --- | --- | --- | --- |"]
    for d in dropped:
        lines.append("| 剔除 | %s | %s | %s |" % (d["title"][:44], d["board"], d["reason"]))
    for m in moved:
        lines.append("| 迁移 | %s | %s | 移入 %s（经验做法稿，本质属行业管理） |"
                     % (m["title"][:44], m["from"], m["to"]))
    lines += ["", "## 三、补充条目（本期终稿直出，无补充）", "",
              "| 板块 | 标题 | 来源 | 日期 |", "| --- | --- | --- | --- |"]
    for s in added:
        lines.append("| %s | %s | %s | %s |" % (s["board"], s["title"][:46], s["unit"][:18], s["date_override"]))
    lines += ["", "## 四、三板块构成（编排只按三个板块，不设二级分类）", "",
              "| 板块 | 骨架 | 补充 | 合计 |", "| --- | --- | --- | --- |"]
    for b in BOARDS:
        a = sum(1 for s in selected if s["is_skeleton"] and s["board"] == b)
        c = sum(1 for s in added if s["board"] == b)
        lines.append("| %s | %d | %d | %d |" % (b, a, c, a + c))
    lines += ["", "## 五、类内排序规则（本期起固定）", "",
              "1. 板块序：政策法规 → 技术应用类 → 科技前沿类。",
              "2. 层级：部级 → 行业与官媒 → 外省（国家到地方）。",
              "3. 业务中心度（依本中心党组半年工作情况汇报章节，中心到边缘）：实景三维建设 → 测绘基准服务 → "
              "测绘地理信息公共服务 → 测绘科技创新与关键技术攻关 → 应急测绘保障 → 自然资源调查监测技术支撑 → "
              "自然资源执法监管技术支撑 → 测绘行业管理与技术服务 → 地理信息数据安全与保密 → 卫星遥感与多源数据融合应用。",
              "4. 发布日期倒序；优先级 A／B／C 保留为字段与筛选条件，不作排序主键。",
              "5. 骨架条目相对顺序不变，补充条目插入到第一条排序键大于它的条目之前。", "",
              "> 业务条线、主题标签仅作数据字段与统计维度，不作为目录或成刊的编排层级。"]
    open(REPORT, "w", encoding="utf-8").write("\n".join(lines) + "\n")

    print("选目 %d 条（骨架 %d ＋ 补充 %d；剔除 %d、迁移 %d）"
          % (len(selected), n_skel, len(added), len(dropped), len(moved)))
    print("板块：", totals, "| 政策+前沿 %d（%.0f%%）｜技术应用类 %d（%.0f%%）"
          % (pol, 100 * pol / n, tm, 100 * tm / n))
    print("补充条线：", dict(Counter(s["business"] for s in added)))
    print("输出：", OUT)
    print("报告：", REPORT)


if __name__ == "__main__":
    main()
