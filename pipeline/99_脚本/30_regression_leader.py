# -*- coding: utf-8 -*-
"""回归测试：以领导终稿（0917，三板块）为金标准，校验选目与筛选规则。"""
import importlib.util
import os
import re
import sys
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_utils import RAW, ROOT, load_json  # noqa: E402
import sources_whitelist as WL  # noqa: E402
from period_config import P  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
LEADER = os.path.join(RAW, "leader_%s.json" % (P.leader_label or "0917"))
DRAFT = os.path.join(P.sel_dir, "catalog_selection_draft.json")
OUT = os.path.join(ROOT, "_备查", "领导版回归测试.md")
BOARDS = ["政策类", "技术应用类", "科技前沿类"]


def norm(t):
    return re.sub(r"[\s\W_]+", "", t or "")


def sim(a, b):
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def load_m31():
    """读取 31 号脚本的骨架调整表（R8 剔除 / 板块迁移），保证规则与执行同源。"""
    spec = importlib.util.spec_from_file_location(
        "m31", os.path.join(HERE, "31_build_draft_selection.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    leader = load_json(LEADER)
    draft = load_json(DRAFT)
    m31 = load_m31()
    drop_keys = set(m31.DROP_SKELETON)
    move_keys = set(m31.MOVE_BOARD)
    report, failures = [], []

    expected = [x for x in leader["final"] if norm(x["title"]) not in drop_keys]
    missing = [x["title"] for x in expected
               if not any(sim(x["title"], s["title"]) >= 0.85 for s in draft)]
    report += ["## 一、骨架完整性", "",
               "- 领导终稿 %d 条｜按 R8 剔除 %d 条、按板块迁移 %d 条后，应保留 **%d** 条，选目缺失 **%d** 条"
               % (len(leader["final"]), len(drop_keys), len(move_keys), len(expected), len(missing)), ""]
    for m in missing:
        report.append("  - 缺失：" + m)
    if missing:
        failures.append("骨架缺失 %d 条" % len(missing))
    resurrected = [s["title"] for s in draft if norm(s["title"]) in drop_keys]
    report += ["- 剔除条目回流检查：**%d** 条（应为 0）" % len(resurrected)]
    for t in resurrected:
        report.append("  - 回流：" + t)
    if resurrected:
        failures.append("剔除条目回流 %d 条" % len(resurrected))
    report += ["", "| 骨架调整 | 标题 | 依据 |", "| --- | --- | --- |"]
    for key, reason in m31.DROP_SKELETON.items():
        title = next((x["title"] for x in leader["final"] if norm(x["title"]) == key), key)
        report.append("| 剔除 | %s | %s |" % (title[:44], reason))
    for key, board in m31.MOVE_BOARD.items():
        title = next((x["title"] for x in leader["final"] if norm(x["title"]) == key), key)
        report.append("| 迁移 | %s | 移入 %s |" % (title[:44], board))
    report.append("")

    order_issues = []
    for sec in BOARDS:
        want = [x["title"] for x in leader["final"]
                if x["sec"] == sec and norm(x["title"]) not in drop_keys
                and norm(x["title"]) not in move_keys]
        got = [norm(s["title"]) for s in draft if s.get("is_skeleton") and s["board"] == sec]
        idx = []
        for w in want:
            hit = next((i for i, g in enumerate(got)
                        if SequenceMatcher(None, norm(w), g).ratio() >= 0.85), None)
            idx.append(hit)
        if any(i is None for i in idx) or idx != sorted(idx):
            order_issues.append(sec)
    report += ["## 二、顺序一致性", "",
               "- 骨架顺序异常板块：%d" % len(order_issues), ""]
    for sec in order_issues:
        report.append("  - " + sec)
    if order_issues:
        failures.append("顺序不一致 %d 个板块" % len(order_issues))
    # 补充条目须按 R4 排序键非递减插入（层级 → 业务中心度 → 日期倒序）
    key_bad = []
    for idx, sec in enumerate(BOARDS):
        keys = [WL.sort_key(s.get("level") or "", s.get("business") or "",
                            s.get("date_override") or "", idx)
                for s in draft if s["board"] == sec and not s.get("is_skeleton")]
        if keys != sorted(keys):
            key_bad.append(sec)
    report += ["- 补充条目排序键异常板块：%d（应为 0）" % len(key_bad)]
    for sec in key_bad:
        report.append("  - " + sec)
    if key_bad:
        failures.append("补充条目未按 R4 排序键排列 %d 个板块" % len(key_bad))
    report.append("")

    hit_rule, hit_manual = [], []
    for x in leader.get("removed", []):
        ex, why = WL.draft_excluded(x["title"], "", "外省")
        (hit_rule if ex else hit_manual).append((x["title"], why or x.get("reason", "")))
    n_rm = max(1, len(leader.get("removed", [])))
    report += ["## 三、删除条目命中情况", "",
               "- 共删除 %d 条" % len(leader.get("removed", [])),
               "- 命中 R1 自动规则：**%d** 条（%.0f%%）" % (len(hit_rule), 100 * len(hit_rule) / n_rm),
               "- 归入 R2 人工准则：**%d** 条（由人工精选环节处理，不要求规则命中）" % len(hit_manual), ""]
    if hit_manual:
        report += ["| 人工准则条目 | 领导删除原因 |", "| --- | --- |"]
        for t, r in hit_manual:
            report.append("| %s | %s |" % (t[:44], r))
        report.append("")

    added_ok = []
    added_bad = []
    for x in leader.get("added", []):
        target = next((s for s in draft if sim(x["title"], s["title"]) >= 0.85), None)
        if target and target.get("unit"):
            added_ok.append((x["title"], target["unit"]))
        else:
            added_bad.append(x["title"])
    report += ["## 四、新增条目召回", "",
               "- 领导新增 %d 条，召回 %d 条" % (len(leader.get("added", [])), len(added_ok)), ""]
    for t, u in added_ok:
        report.append("  - %s → 来源标注：%s" % (t[:40], u))
    for t in added_bad:
        report.append("  - 未召回：" + t)
    if added_bad:
        failures.append("新增条目未召回 %d 条" % len(added_bad))
    report.append("")

    totals = {b: sum(1 for s in draft if s["board"] == b) for b in BOARDS}
    pol = totals["政策类"] + totals["科技前沿类"]
    tm = totals["技术应用类"]
    n = max(1, len(draft))
    report += ["## 五、规模与比例（三板块）", "",
               "- 选目共 **%d** 条｜板块：%s" % (len(draft), "、".join("%s %d" % (b, totals[b]) for b in BOARDS)),
               "- 政策类＋科技前沿类 %d 条（%.0f%%）｜技术应用类 %d 条（%.0f%%）"
               % (pol, 100 * pol / n, tm, 100 * tm / n),
               "- 本期为领导终稿直出（16 条）；下期起按三板块走两级产出：初版约 35 条、终稿 20—25 条", ""]

    # 六、三板块口径与 R8（前沿类实质内容门槛）
    front = [s for s in draft if s["board"] == "科技前沿类"]
    r6_bad = []
    for s in front:
        ok, why = WL.frontier_substance_ok(
            s["title"], s.get("原文正文") or s.get("summary") or "")
        if not ok:
            r6_bad.append((s["title"], why))
    out_win = [s for s in draft if s.get("date_override") and not WL.in_window(s["date_override"])]
    bad_board = [s["title"] for s in draft if s["board"] not in WL.BOARDS]
    banned = [s["title"] for s in draft if s.get("frontier_kind")]
    report += ["## 六、三板块口径与前沿类门槛", "",
               "- 板块集合：%s（应为 3 个，且不含“媒体动态类”）" % "、".join(WL.BOARDS),
               "- 越界板块条目：**%d** 条（应为 0）" % len(bad_board),
               "- 已停用入口（前沿论文／国际奖项）条目：**%d** 条（应为 0）" % len(banned),
               "- R8 实质内容门槛（科技前沿类 %d 条）：不达标 **%d** 条（应为 0）"
               % (len(front), len(r6_bad)),
               "- 窗口校验：窗口外条目 **%d** 条" % len(out_win), ""]
    for t, why in r6_bad:
        report.append("  - R8 不达标：" + t[:44] + "｜" + why)
    for s in out_win:
        report.append("  - 窗口外：" + s["title"][:44] + "｜" + str(s.get("date_override")))
    for t in bad_board:
        report.append("  - 越界板块：" + t[:44])
    for t in banned:
        report.append("  - 已停用入口条目：" + t[:44])
    if r6_bad:
        failures.append("R8 不达标 %d 条" % len(r6_bad))
    if out_win:
        failures.append("窗口外条目 %d 条" % len(out_win))
    if bad_board:
        failures.append("越界板块 %d 条" % len(bad_board))
    if banned:
        failures.append("已停用入口条目 %d 条" % len(banned))
    report.append("")

    head = ["# 领导版回归测试（0917 金标准，三板块）", "",
            "- 结果：%s" % ("全部通过" if not failures else "**未通过**：" + "；".join(failures)),
            "- 骨架 %d 条（其中 R8 剔除 %d、板块迁移 %d）｜删除 %d 条｜新增 %d 条"
            % (len(leader["final"]), len(drop_keys), len(move_keys),
               len(leader.get("removed", [])), len(leader.get("added", []))), ""]
    open(OUT, "w", encoding="utf-8").write("\n".join(head + report) + "\n")
    print("回归测试：", "全部通过" if not failures else "未通过 -> " + "；".join(failures))
    print("  骨架缺失 %d｜顺序异常 %d｜R1 命中 %d/%d｜新增召回 %d/%d｜选目 %d 条"
          % (len(missing), len(order_issues), len(hit_rule), len(leader.get("removed", [])),
             len(added_ok), len(leader.get("added", [])), len(draft)))
    print("报告：", OUT)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
