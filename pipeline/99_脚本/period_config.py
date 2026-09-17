# -*- coding: utf-8 -*-
"""期次配置读取（每期一份 period.json）。

解析顺序（先命中先用）：
1. 环境变量 `CEHUI_PERIOD_DIR` 指向的期次目录；
2. 从当前工作目录向上查找含 `period.json` 的目录；
3. 从本文件向上查找含 `period.json` 的目录；
4. 兜底：本文件所在目录的上级目录（兼容历史期次目录里的脚本副本）。

用法：
    from period_config import P
    P.window_from, P.window_to, P.collect_date, P.title_range, P.issue_label, P.publish_date
    P.issue_dir        # 期次目录（ROOT）
    P.sel_dir          # 该期数据目录（ROOT/99_脚本，存放选目 JSON）
"""
import json
import os
import re


def _candidates():
    env = (os.environ.get("CEHUI_PERIOD_DIR") or "").strip()
    if env:
        yield os.path.abspath(env)
    for start in (os.getcwd(), os.path.dirname(os.path.abspath(__file__))):
        d = os.path.abspath(start)
        while True:
            yield d
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent


def find_period_dir():
    """返回含 period.json 的目录；找不到时返回脚本上级目录（历史布局）。"""
    seen = set()
    for d in _candidates():
        if d in seen:
            continue
        seen.add(d)
        if os.path.isfile(os.path.join(d, "period.json")) or \
                os.path.isfile(os.path.join(d, "99_脚本", "period.json")):
            return d
    env = (os.environ.get("CEHUI_PERIOD_DIR") or "").strip()
    if env:
        return os.path.abspath(env)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(path=None):
    """读取 period.json；文件缺失时返回空配置（由调用方决定报错或沿用默认值）。"""
    if path is None:
        base = find_period_dir()
        for cand in (os.path.join(base, "period.json"),
                     os.path.join(base, "99_脚本", "period.json")):
            if os.path.exists(cand):
                path = cand
                break
        else:
            return {}
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class Period(object):
    """期次配置对象：字段缺失时给出安全默认值，避免脚本直接崩。"""

    def __init__(self, data=None):
        data = dict(data or load())
        self.data = data
        self.issue_dir = data.get("issue_dir") or find_period_dir()
        self.issue_name = data.get("issue_name") or os.path.basename(self.issue_dir.rstrip("\\/"))
        self.window_from = data.get("window_from") or "2026-08-01"
        self.window_to = data.get("window_to") or "2026-09-13"
        self.collect_date = data.get("collect_date") or self.window_to
        self.title_range = data.get("title_range") or "2026年8月1日—9月13日"
        self.issue_label = data.get("issue_label") or "2026年第1期"
        self.publish_date = data.get("publish_date") or "2026年9月15日"
        self.editor_unit = data.get("editor_unit") or "福建省测绘地理信息发展中心"
        self.draft_target = int(data.get("draft_target") or 35)
        self.final_target_low = int(data.get("final_target_low") or 20)
        self.final_target_high = int(data.get("final_target_high") or 25)
        self.leader_label = data.get("leader_label") or ""

    # ---- 派生路径 ----
    @property
    def sel_dir(self):
        """该期数据目录：选目 JSON、脚本产出的中间结果都放这里。"""
        d = os.path.join(self.issue_dir, "99_脚本")
        os.makedirs(d, exist_ok=True)
        return d

    @property
    def issue_file_stem(self):
        return "测绘动态工作_%s" % self.issue_label

    def window_text(self):
        return "%s ~ %s" % (self.window_from, self.window_to)

    def cover_line(self):
        """封面期号行：`2026年9月15日　　第1期　　福建省测绘地理信息发展中心　编制`。"""
        m = re.search(r"第\s*(\d+)\s*期", self.issue_label)
        no_text = "第%s期" % m.group(1) if m else self.issue_label
        return "%s　　%s　　%s　编制" % (self.publish_date, no_text, self.editor_unit)


P = Period()
