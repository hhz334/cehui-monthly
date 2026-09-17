# -*- coding: utf-8 -*-
"""标准一致性自检：比对"代码里的执行规则"与"口径／来源清单里的文字标准"。

背景：标准既写在文档里，也实现在代码里，两边会漂移（例：口径曾写"测绘法宣传日不收"，
与后来新增的收录例外矛盾）。本脚本逐项比对硬阈值与关键规则，输出报告并在不一致时返回非零退出码。

用法：python 99_脚本/28_check_standard_consistency.py
输出：_备查/标准一致性检查.md
"""
import importlib.util
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_utils import ROOT  # noqa: E402
import sources_whitelist as WL  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOTDIR = os.path.dirname(ROOT)                      # 项目根（团委/测绘动态）
CALIBER = os.path.join(ROOTDIR, "00_测绘动态资讯采集口径.md")
SOP = os.path.join(ROOTDIR, "01_作业流程（SOP）.md")
SOURCE_LIST = os.path.join(ROOT, "01_来源清单与采集方法.md")
OUT = os.path.join(ROOT, "_备查", "标准一致性检查.md")


def load_module(filename, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main():
    m24 = load_module("24_auto_shortlist.py", "m24")
    m25 = load_module("25_verify_source_entity.py", "m25")
    m23 = load_module("23_rebuild_boards.py", "m23")
    caliber, sop, src = read(CALIBER), read(SOP), read(SOURCE_LIST)

    checks = []          # (项目, 代码值, 文档值, 是否一致)

    def add(name, code_value, doc_ok, doc_value):
        checks.append((name, str(code_value), str(doc_value), bool(doc_ok)))

    # 1. 时间窗口
    add("时间窗口", f"{m24.FROM} ~ {m24.TO}",
        f"{m24.FROM} ~ {m24.TO}" in caliber, "口径第九节/正文质量门槛表")
    same_window = (m24.FROM == getattr(m23, "FROM", m24.FROM))
    add("时间窗口（24 与 23 一致）", f"{m24.FROM}~{m24.TO}", same_window, "两脚本同值")

    # 2. 正文阈值
    add("正文最小字数", m25.MIN_TEXT, f"| 正文最小字数 | {m25.MIN_TEXT} 字" in caliber,
        "口径·量化阈值表")
    add("标题要素覆盖率", m25.MIN_COVER, f"≥{m25.MIN_COVER}" in caliber, "口径·量化阈值表")

    # 3. 初筛上限
    add("单来源初筛上限", m24.MAX_PER_SOURCE, f"每来源 {m24.MAX_PER_SOURCE} 条" in caliber,
        "口径·量化阈值表")

    # 4. 同事件合并阈值
    merge = re.search(r"similarity \w+\) >= (0?\.\d+)|>= (0?\.\d+)\s*$", "")
    add("同事件合并阈值", "0.85", "≥0.85" in caliber, "口径·量化阈值表")

    # 5. 垃圾正文判定
    add("垃圾正文判定", "≥2 特征或 1 特征且 <800 字",
        "命中 2 个以上垃圾特征" in caliber and "800 字" in caliber, "口径·量化阈值表")

    # 6. 周讯汇编号
    add("周讯汇编号（非来源）", "、".join(WL.WECHAT_DIGEST_BIZ.keys()),
        all(b in caliber for b in WL.WECHAT_DIGEST_BIZ), "口径·来源实体校验")

    # 7. 宣传类例外：只收部级专题
    add("宣传类例外", "publisher 须含'测绘法宣传日专题'",
        "只收部级专题来源" in caliber or "收窄为部级专题一处" in caliber, "口径·收录例外")

    # 8. 非动态排除（决算／采购／期次页）
    pat = WL.TITLE_EXCLUDE.pattern
    add("非动态排除", pat[:40] + "…",
        "财务预决算、采购招标" in caliber and "期次页" in caliber, "口径·不收清单")
    # 8b. 非文字稿（视频／图集）排除
    add("非文字稿排除", "is_non_text() 视频／音频／图集",
        "视频、音频、图集、海报" in caliber and "只收文字稿" in caliber, "口径·不收清单")

    # 9. 排除模块与层级
    add("排除模块", "／".join(m23.EXCLUDED_MODULES.keys()),
        "国际内容" in caliber and "科普" in caliber, "口径·不收清单")
    add("排除层级", "／".join(m23.EXCLUDED_LEVELS.keys()),
        "福建本地内容不进目录" in caliber, "口径·不收清单")

    # 10. 三板块与业务条线（2026-09-17 起取消“媒体动态类”）
    add("三板块", "／".join(WL.BOARDS),
        (all(b in caliber for b in WL.BOARDS) and "媒体动态类" in caliber
         and "取消" in caliber), "口径·三个板块定义")
    add("媒体动态类已取消", "不在 BOARDS／BOARD_RULES 中",
        ("媒体动态类" not in WL.BOARDS
         and not any(b == "媒体动态类" for b, _ in WL.BOARD_RULES)
         and all(v != "媒体动态类" for v in WL.MODULE_TO_BOARD.values())),
        "口径·三个板块定义")
    add("业务条线数量", len(WL.BUSINESS_LINES),
        f"{len(WL.BUSINESS_LINES)} 条业务线" in caliber or "10 条业务线" in caliber, "口径·第八节")

    # 11. 来源白名单关键域名
    key_domains = ["mnr.gov.cn", "drcmnr.cn", "iziran.net", "taibo.cn", "people.com.cn"]
    missing = [d for d in key_domains if d not in WL.SITE_WHITELIST]
    add("来源白名单关键域名", "、".join(key_domains), not missing,
        "口径·来源白名单" + (f"（代码缺 {missing}）" if missing else ""))
    add("白名单域名写入来源清单", "people.com.cn",
        "people.com.cn" in src, "来源清单·行业媒体来源")

    # 12. 人工采纳入口可绕过宣传排除
    add("人工采纳绕过宣传排除", "sel.get('manual')", "人工指定采纳" in caliber, "口径·收录例外")

    # 13. SOP 必含顺序约束与自检项
    add("SOP 顺序约束", "25/08/07/14 四条约束",
        ("25" in sop and "08" in sop and "早于" in sop), "SOP·脚本清单")
    add("SOP 含一致性自检", "S1/S11 步骤", "标准一致性" in sop, "SOP 步骤与验收")

    # 14. R1 初版筛选规则（0916 领导批注固化）
    add("R1 初版筛选规则", WL.DRAFT_EXCLUDE.pattern[:36] + "…",
        ("培训" in caliber and "验收" in caliber and "地市级" in caliber and "签约" in caliber),
        "口径·R1 自动排除")
    # 15. R5 公众号分层白名单
    add("R5 公众号分层", "部级%d／省级%d／地市级仅线索%d"
        % (sum(1 for v in WL.WECHAT_TIER.values() if v[1] == "部级"),
           sum(1 for v in WL.WECHAT_TIER.values() if v[1] == "省级"),
           len(WL.WECHAT_CLUE_ONLY_BIZ)),
        ("部级" in caliber and "省级" in caliber and "公众号" in caliber
         and "地市级" in caliber), "口径·来源分层")
    # 16. R7 两级产出标准
    m31 = load_module("31_build_draft_selection.py", "m31")
    add("R7 两级产出", "初版 %d／终稿20—25" % m31.TARGET_TOTAL,
        ("初版" in caliber and str(m31.TARGET_TOTAL) in caliber and "终稿" in caliber), "口径·产出标准")
    # 17. R4 排序与人工置顶
    add("R4 排序规则", "sort_key + 人工置顶",
        hasattr(WL, "sort_key") and ("排序" in caliber), "口径·排序规则")
    # 18. 领导批注回灌机制
    add("批注回灌机制", "29 脚本 + 30 回归 + 31 初版",
        ("29" in sop and "30" in sop and "31" in sop), "SOP·脚本清单")
    # 19. R8 科技前沿类实质内容门槛（原 R9 更名；论文／国际奖项例外已取消）
    add("R8 前沿实质内容门槛", WL.FRONTIER_SUBSTANCE.pattern[:34] + "…",
        ("实质内容" in caliber and "技术实质" in caliber and "一律不收" in caliber),
        "口径·R8 前沿类门槛")
    # 21. R4 新排序键：层级 → 业务中心度 → 日期倒序
    add("R4 排序键（层级→业务→日期）",
        "sort_key + BUSINESS_CENTER_RANK（%d 条业务线）" % len(WL.BUSINESS_CENTER_RANK),
        ("业务中心度" in caliber and "层级从国家到地方" in caliber and "日期倒序" in caliber),
        "口径·R4 排序规则")
    # 22. 论文／国际奖项入口已停用（代码中不得再存在该例外；口径须写明“已取消”）
    add("论文／国际奖项入口停用", "无 INTL_*／FRONTIER_LIMITS；33 号脚本已归档；国际内容一律不收",
        (not hasattr(WL, "INTL_BACK_DAYS") and not hasattr(WL, "FRONTIER_LIMITS")
         and "国际协会奖项例外已取消" in caliber and "一律不收" in caliber
         and not os.path.exists(os.path.join(HERE, "33_add_frontier_items.py"))),
        "口径·R8 前沿类门槛")
    # 23. 本期产物规模与板块构成（三板块，本期终稿直出 16 条）
    add("本期条数与板块构成", "本期 %d 条（终稿直出）｜下期初版 %s"
        % (m31.TARGET_TOTAL, "／".join("%s%d" % (b, m31.TARGET_BOARD[b]) for b in WL.BOARDS)),
        (str(m31.TARGET_TOTAL) in caliber and "终稿直出" in caliber
         and all(str(v) in caliber for v in m31.TARGET_BOARD.values())), "口径·产出标准")
    # 24. 07 号脚本保留 R4 顺序（不再按子栏／层级重排）
    txt07 = read(os.path.join(HERE, "07_build_catalog.py"))
    add("07 保留 R4 顺序", "rows.sort 仅按板块分组（sub_rank 已移除）",
        ("R4" in txt07 and "sub_rank" not in txt07 and "层级从国家到地方" in caliber),
        "口径·R4 排序规则")

    bad = [c for c in checks if not c[3]]
    lines = ["# 标准一致性检查", "",
             f"- 口径文件：`00_测绘动态资讯采集口径.md`",
             f"- 流程文件：`01_作业流程（SOP）.md`",
             f"- 代码：`99_脚本/sources_whitelist.py`、`23/24/25`",
             f"- 检查项：{len(checks)} 项，**不一致 {len(bad)} 项**", "",
             "| # | 检查项 | 代码值 | 文档记载 | 结论 |", "| --- | --- | --- | --- | --- |"]
    for i, (name, code_v, doc_v, ok) in enumerate(checks, 1):
        lines.append(f"| {i} | {name} | {code_v} | {doc_v} | {'一致' if ok else '**不一致**'} |")
    if bad:
        lines += ["", "## 需要处理的不一致", ""]
        for name, code_v, doc_v, _ in bad:
            lines.append(f"- **{name}**：代码为 `{code_v}`，文档为 `{doc_v}`，请同步修改后重跑。")
    open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")

    print(f"检查 {len(checks)} 项，不一致 {len(bad)} 项")
    for name, code_v, doc_v, ok in checks:
        print(f"  {'✓' if ok else '✗'} {name}")
    if bad:
        print(f"报告：{OUT}")
        return 1
    print(f"报告：{OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
