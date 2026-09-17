# -*- coding: utf-8 -*-
"""来源白名单与分类口径配置（采集、重建、核实脚本共用）。

口径要点：
1. 来源分两类——官网类（原发布单位/主管部门/学会协会/原发媒体官网）与白名单公众号类；
2. 官网优先，官网无原文时才用白名单公众号原文；两处都核不到的不入目录；
3. 目录只保留三个板块：政策法规、技术应用类、科技前沿类（2026-09-17 起取消“媒体动态类”）；
4. 每条动态按 10 条业务条线打标。
"""
import re

# ---------------------------------------------------------------- 官网白名单
# 域名 → 来源类型
SITE_WHITELIST = {
    # 部委及直属单位
    "mnr.gov.cn": "主管部门官网",
    "drcmnr.cn": "主管部门官网",
    "ngcc.cn": "主管部门官网",
    "casm.ac.cn": "主管部门官网",
    "vod.mnr.gov.cn": "主管部门官网",
    # 学会 / 协会
    "csgpc.org": "学会协会官网",
    "cagis.org.cn": "学会协会官网",
    "gim-international.com": "学会协会官网",
    "isprs.org": "学会协会官网",
    "fig.net": "学会协会官网",
    # 原发媒体官网
    "iziran.net": "原发媒体官网",
    "taibo.cn": "原发媒体官网",
    "people.com.cn": "原发媒体官网",
    # 省级主管部门与测绘单位
    "fujian.gov.cn": "主管部门官网",
    "fjch.org.cn": "单位官网",
    "fjchxh.cn": "学会协会官网",
    "shandong.gov.cn": "主管部门官网",
    "shandongcehui.cn": "单位官网",
    "jiangsu.gov.cn": "主管部门官网",
    "zj.gov.cn": "主管部门官网",
    "search.zj.gov.cn": "主管部门官网",
    "gd.gov.cn": "主管部门官网",
    "ah.gov.cn": "主管部门官网",
    "hubei.gov.cn": "主管部门官网",
    "hunan.gov.cn": "主管部门官网",
    "gxzf.gov.cn": "主管部门官网",
    "sc.gov.cn": "主管部门官网",
    "shaanxi.gov.cn": "主管部门官网",
    "hebei.gov.cn": "主管部门官网",
    "henan.gov.cn": "主管部门官网",
    "yn.gov.cn": "主管部门官网",
    "cqism.cn": "单位官网",
    "shaanxich.gov.cn": "主管部门官网",
}

# ------------------------------------------------------------ 公众号白名单
# 点名的公众号（用户明确保留）
WECHAT_EXPLICIT = {
    "自然微论坛", "自然资源部", "自然资源讲堂", "泰伯网",
    "i自然全媒体", "i自然", "浙江省测绘科学技术研究院",
}
# 按主体判定的公众号名称模式：省级测绘院 / 测绘地理信息局 / 测绘中心等测绘事业单位
WECHAT_PATTERNS = [
    r"测绘院", r"测绘地理信息局", r"测绘中心", r"测绘科学技术研究院",
    r"国土地?测绘", r"地理信息中心", r"测绘产品质量",
]
WECHAT_EXCLUDE = [r"招聘", r"培训学校", r"教育", r"广告", r"营销"]


def wechat_ok(name):
    """判断公众号账号名是否在白名单内。"""
    name = (name or "").strip()
    if not name:
        return False
    if any(re.search(p, name) for p in WECHAT_EXCLUDE):
        return False
    if name in WECHAT_EXPLICIT:
        return True
    return any(re.search(p, name) for p in WECHAT_PATTERNS)


def host_of(url):
    m = re.match(r"https?://([^/]+)", url or "")
    return (m.group(1).lower() if m else "")


# ------------------------------------------------- 公众号真实账号（__biz）
# 只有这些 __biz 才能作为"该账号自身发布内容"的来源
ORG_WECHAT = {
    "浙江省测绘科学技术研究院": ["MzkzMTAxOTQyMg=="],
    "泰伯网": ["MjM5NTg1MzcyMQ=="],
    "i自然全媒体": ["MjM5NTk2MjY1Mw=="],
    "中国自然资源报": ["MjM5NTk2MjY1Mw=="],
}
# 明确的"汇编/转载号"：发布内容不等于其原发布方，只能作线索
WECHAT_DIGEST_BIZ = {
    "MzUyMTczMDQzNg==": "《测绘地理信息周讯》（山东省国土测绘院汇编号）——转载汇编，只能作线索",
}

# ------------------------------------------------- 单位 → 允许的官网域名
ORG_SITES = {
    "陕西测绘地理信息局": ["snsm.mnr.gov.cn"],
    "自然资源部测绘标准化研究所": ["snsm.mnr.gov.cn"],
    "黑龙江测绘地理信息局": ["hlsm.mnr.gov.cn"],
    "四川测绘地理信息局": ["scsm.mnr.gov.cn"],
    "海南测绘地理信息局": ["hism.mnr.gov.cn"],
    "中国自然资源报": ["iziran.net", "szb.iziran.net"],
    "中国自然资源报（i自然）": ["iziran.net", "szb.iziran.net"],
    "i自然官网": ["iziran.net", "szb.iziran.net"],
    "自然资源部": ["mnr.gov.cn"],
    "自然资源部测绘发展研究中心": ["drcmnr.cn"],
    "国家基础地理信息中心": ["ngcc.cn"],
    "中国测绘科学研究院": ["casm.ac.cn"],
    "中国测绘学会": ["csgpc.org"],
    "中国地理信息产业协会": ["cagis.org.cn"],
    "山东省自然资源厅": ["dnr.shandong.gov.cn", "shandong.gov.cn"],
    "山东省国土测绘院": ["shandongcehui.cn"],
    "江苏省自然资源厅": ["zrzy.jiangsu.gov.cn", "jiangsu.gov.cn"],
    "浙江省自然资源厅": ["zrzyt.zj.gov.cn", "zj.gov.cn"],
    "广东省自然资源厅": ["nr.gd.gov.cn", "gd.gov.cn"],
    "安徽省自然资源厅": ["zrzyt.ah.gov.cn", "ah.gov.cn"],
    "湖北省自然资源厅": ["zrzyt.hubei.gov.cn", "hubei.gov.cn"],
    "湖南省自然资源厅": ["zrzyt.hunan.gov.cn", "hunan.gov.cn"],
    "广西壮族自治区自然资源厅": ["dnr.gxzf.gov.cn", "gxzf.gov.cn"],
    "四川省自然资源厅": ["dnr.sc.gov.cn", "sc.gov.cn"],
    "陕西省自然资源厅": ["zrzyt.shaanxi.gov.cn", "shaanxi.gov.cn"],
    "福建省自然资源厅": ["zrzyt.fujian.gov.cn", "fujian.gov.cn"],
    # 测绘法宣传日／国家版图意识宣传周 专题（部级）
    "自然资源部（2026年测绘法宣传日专题）": ["mnr.gov.cn"],
    # 中央媒体地方频道（单篇取文为主）
    "人民网": ["people.com.cn"],
    "人民网宁夏频道": ["nx.people.com.cn", "people.com.cn"],
}


def wechat_biz(url):
    """从公众号链接里取出 __biz。"""
    m = re.search(r"[?&]__biz=([A-Za-z0-9=+/]+)", url or "")
    return m.group(1) if m else ""


def resolve_wechat_account(url, timeout=25):
    """短链不带 __biz 时，抓取页面解析 (公众号名, __biz)。"""
    import gzip
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0",
            "Referer": "https://mp.weixin.qq.com/"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            if (resp.headers.get("Content-Encoding") or "").lower() == "gzip":
                raw = gzip.decompress(raw)
        page = raw.decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001
        return "", ""
    name = ""
    m = re.search(r'id="js_name"[^>]*>\s*([^<\s][^<]*)', page) or \
        re.search(r'var nickname\s*=\s*"([^"]+)"', page)
    if m:
        name = m.group(1).strip()
    biz = ""
    m = re.search(r'var biz\s*=\s*"([^"]+)"', page)
    if m:
        biz = m.group(1)
    return name, biz


def clean_title(title):
    """去掉列表页残留：项目符号、尾部"时间：… 来源：…"等元信息、方括号日期。"""
    t = (title or "").strip()
    t = re.sub(r"^[^\w\u4e00-\u9fa5]+", "", t)
    t = re.sub(r"^[·•∙・\-\u2022\s]+", "", t)
    t = re.sub(r"^\d{1,3}[\s.、]+(?=[^\d])", "", t)
    t = re.split(r"\s*(?:时间|来源|发布(?:时间|日期)|日期)\s*[:：]", t)[0]
    t = re.sub(r"\s*\[\s*20\d{2}-\d{2}-\d{2}\s*\]\s*$", "", t)
    return re.sub(r"\s+", " ", t).strip()


# ------------------------------ 宣传类稿件的"收录例外"判定
# 口径：测绘法宣传日／国家版图意识宣传周 只收部级专题与省级（含自治区）做法成效报道；
#      不收宣传海报、短视频素材、各地活动集锦、地市级活动简讯。
PROMO_HARD_EXCLUDE = re.compile(
    r"宣传海报|海报|短视频|素材|集锦|评论员|社论|言论|开学第一课")
PROMO_CITY_EXCLUDE = re.compile(
    r"(?:市|县|区|旗)(?:自然资源和规划局|自然资源局|规划局|局|分局)")
PROMO_KEYS = ("宣传日", "宣传周", "版图意识", "测绘法")


def promo_excluded(title, summary="", publisher=""):
    """判断宣传类稿件是否属于不收的情形。非宣传类返回 False。

    口径（2026-09-15 收紧）：测绘法宣传日／国家版图意识宣传周类**只收自然资源部专题来源**；
    其他渠道（媒体、地市、单位公众号）的宣传简讯一律不收；人工指定采纳（26 脚本）不受此限。
    """
    text = f"{title} {summary}"
    if not any(k in text for k in PROMO_KEYS):
        return False
    if PROMO_HARD_EXCLUDE.search(text):
        return True
    if PROMO_CITY_EXCLUDE.search(title):
        return True
    return "测绘法宣传日专题" not in (publisher or "")


# ------------------------------ 非动态与低价值内容（直接不收）
TITLE_EXCLUDE = re.compile(
    r"决算|预算|采购|招标|中标|成交|询价|比选|废标|"
    r"第\s*\d+\s*期|发展动态第|工作月报|工作年报|通讯录|值班表")


def title_excluded(title):
    """财务、采购、公告程序与期次页等非动态内容。"""
    return bool(TITLE_EXCLUDE.search(title or ""))


# ------------------------------ 正文质量：识别整页导航／前端模板文本
JUNK_TEXT = re.compile(
    r"Powered by JEECMS|热词\s*[:：]|网站地图|京ICP备|京公网安备|"
    r"\{\{content\.|\{\{item\.|无障碍浏览|简体\s*\|\s*繁體|"
    r"首页\s+机构\s+动态\s+研究|中国政府网\s*\|\s*自然资源部|"
    r"登录\s*注册\s*退出|立即注册|忘记登录状态|"
    r"Toggle navigation|系统要闻|&#x[0-9a-fA-F]{4};")


def is_junk_text(text):
    """正文是否为整页导航／前端模板文本（不是文章正文）。"""
    t = text or ""
    if len(t) < 120:
        return False
    hits = len(JUNK_TEXT.findall(t))
    return hits >= 2 or (hits >= 1 and len(t) < 800)


# ------------------------------ 非文字稿：视频／音频／图集类一律不收
VIDEO_URL = re.compile(
    r"vod\.mnr\.gov\.cn|/spxw/|/spts/|/ztp/|/video|v\.qq\.com|bilibili|youtu|\.mp4|\.mp3")
VIDEO_TITLE = re.compile(r"视频|宣传片|微视频|短视频|动新闻|图集|海报|H5|直播")
VIDEO_TEXT = re.compile(r"视频播放|点击播放|观看视频|本视频|视频时长|扫码观看|视频来源|视频加载|视频地址")
# 视频页在原始 HTML 里的特征（山东厅等用 edui 上传的视频 iframe）
VIDEO_HTML = re.compile(
    # 只认"正文里插了视频"的特征；站点模板里引用 video-js.css 之类不算
    r"edui-upload-video|type=vod|vjs-default-skin|<video[\s>]|\.mp4",
    re.I)


def is_non_text(title, url="", text="", html=""):
    """判断是否为视频／音频／图集等非文字稿（口径：只收文字稿）。"""
    if VIDEO_URL.search(url or ""):
        return True
    if VIDEO_TITLE.search(title or ""):
        return True
    if text and VIDEO_TEXT.search(text):
        return True
    if html and VIDEO_HTML.search(html):
        return True
    return False


# ==================== 初版筛选规则（依 0916 领导批注固化） ====================
# R1 自动排除：培训/竞赛/签约/验收/地市级/期次页等
DRAFT_EXCLUDE = re.compile(
    r"培训|讲座|讲堂|竞赛|练兵|比武|大讲堂|"
    r"签约|签署|框架协议|合作框架|调研|座谈|走访|"
    r"验收|预验收|评审|评估|"
    r"市局|县局|区分局|市自然资源|区自然资源|"
    r"第\s*\d+\s*期|工作月报|工作年报|"
    # 程序性/人事/招生类（领导批注口径）
    r"招生|免试|研究生|录取|申请指南|开放基金|征求意见|遴选|招标|评标|聘任|职称评审|"
    # 党建/工会/宣讲类活动（领导批注口径）
    r"工会|劳模|宣讲|职工|妇联|团委|青年|党建|党支部|党总支|党委|党课|理论学习|读书会|"
    r"主题党日|观影|文体|运动会|大讲堂|启动会|"
    # 文体赛事与内部事务（领导批注口径）
    r"越野赛|健步|斩获|佳绩|喜报|表彰|揭榜挂帅|提效赋能|应急预案|工作推进会")
# 会议类：部级/国家级且含技术实质者才可保留（其余按 R1 排除）
MEETING_PAT = re.compile(r"论坛|研讨会|交流会|年会|座谈会|部署会|推进会|工作会")
# 地市级判定：标题以"XX市/县/区/旗"开头，或出现已知地市关键词（可增补）
CITY_PREFIX = re.compile(r"^[\u4e00-\u9fa5]{2,4}(?:市|县|区|旗)(?!人民政府)")
CITY_KEYWORDS = re.compile(
    r"日照|连云港|大连|宣城|亳州|遂宁|益阳|自贡|天水|鸡西|绵竹|鄂州|韶关|惠州|聊城|佛山|东莞|温州|苏州|徐州|"
    r"兴文县|柞水|金华|常州|南通|烟台|潍坊|绵阳")
# 企业/集团发布类（领导批注口径：不收企业发布）
COMPANY_PAT = re.compile(r"集团|有限公司|股份公司|科技公司")
# 非测绘业务（矿业权交易、地热出让等）
OFF_TOPIC_PAT = re.compile(r"采矿权|探矿权|矿业权|挂牌出让|地热")


def draft_excluded(title, unit="", level=""):
    """初版筛选：返回 (是否排除, 原因)。"""
    t = title or ""
    if CITY_PREFIX.search(t) or CITY_KEYWORDS.search(t):
        return True, "R1 自动排除（地市级/县级）"
    if COMPANY_PAT.search(t):
        return True, "R1 自动排除（企业/集团发布）"
    if OFF_TOPIC_PAT.search(t) and "执法" not in t and "违法" not in t:
        return True, "R1 自动排除（非测绘业务）"
    if DRAFT_EXCLUDE.search(t):
        m = DRAFT_EXCLUDE.search(t)
        return True, "R1 自动排除（%s）" % m.group(0)
    if MEETING_PAT.search(t) and level not in ("部级",):
        return True, "R1 自动排除（非部级会议）"
    if title_excluded(t):
        return True, "R1 自动排除（程序性文件/期次页）"
    if is_non_text(t):
        return True, "R1 自动排除（非文字稿）"
    if promo_excluded(t, "", ""):
        return True, "R1 自动排除（宣传类）"
    return False, ""


# R5 来源分层：部级/省级公众号可作来源；地市级仅作线索或延伸链接
WECHAT_TIER = {
    "MzA4MDU2MjQzMg==": ("自然资源部", "部级"),
    "MzAwODEwODcxNA==": ("浙江自然资源", "省级"),
}
WECHAT_CLUE_ONLY_BIZ = {
    "MzAwMjM0NjI0OA==": "徐州自然资源和规划（地市级，仅作线索或延伸链接）",
}


def wechat_source_ok(url):
    """按分层校验公众号链接能否作来源（部级/省级可，地市级及未登记不可）。"""
    biz = wechat_biz(url)
    if not biz:
        # 短链（mp.weixin.qq.com/s/xxxx）不带 __biz，抓页面解析
        _, biz = resolve_wechat_account(url)
        if not biz:
            return False, "取不到 __biz（短链解析失败）"
    if biz in WECHAT_CLUE_ONLY_BIZ:
        return False, WECHAT_CLUE_ONLY_BIZ[biz]
    if biz in WECHAT_TIER:
        return True, "%s（%s）" % WECHAT_TIER[biz]
    if biz in WECHAT_DIGEST_BIZ:
        return False, WECHAT_DIGEST_BIZ[biz]
    return False, "未登记的公众号（__biz=%s）" % biz


# R3 归类修正：国家层面成果发布/服务落地 → 技术应用类
RESULT_PAT = re.compile(r"正式发布|首版|首次|落地|上线|开通|建成|通过验收")


def board_of_v2(module, title, summary="", note="", level=""):
    """在 board_of 基础上应用板级归类修正（部级成果发布归技术应用类）。"""
    b = board_of(module, title, summary, note)
    if b == "科技前沿类" and level == "部级" and RESULT_PAT.search(title or ""):
        return "技术应用类"
    return b


# R4 排序键：板块 → 层级（国家→地方）→ 业务中心度（中心→边缘）→ 日期倒序
_LEVEL_RANK = {"部级": 0, "行业与官媒": 1, "外省": 2}
_PRIORITY_RANK = {"A": 0, "B": 1, "C": 2}
# 业务中心度：来自本中心党组半年工作情况汇报的章节顺序（1 最中心）
BUSINESS_CENTER_RANK = {
    "实景三维建设": 1,
    "测绘基准服务": 2,
    "测绘地理信息公共服务": 3,
    "测绘科技创新与关键技术攻关": 4,
    "应急测绘保障": 5,
    "自然资源调查监测技术支撑": 6,
    "自然资源执法监管技术支撑": 7,
    "测绘行业管理与技术服务": 8,
    "地理信息数据安全与保密": 9,
    "卫星遥感与多源数据融合应用": 10,
}


def date_rank(date):
    """日期倒序权重：新的排前面；缺失日期排最后。"""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", date or "")
    return -int(m.group(1) + m.group(2) + m.group(3)) if m else 0


def sort_key(level, business, date, board_order=0):
    """R4 排序键：板块 → 层级（部级→行业与官媒→外省）→ 业务中心度 → 日期倒序。"""
    return (board_order, _LEVEL_RANK.get(level, 9),
            BUSINESS_CENTER_RANK.get(business, 99), date_rank(date))


# ------------------------------ R8 科技前沿类：实质内容门槛（2026-09 新增）
# 只收有可核验技术实质的条目（方法／指标／模型／成果）；产业评论、市场预测、
# 会议召开、活动总结这类"看似前沿"的内容不收。
FRONTIER_SUBSTANCE = re.compile(
    r"算法|模型|架构|框架|方法|指标|精度|准确率|召回率|误差|数据集|样本库|"
    r"试验|实验|验证|反演|解译|检测|识别|自动化|平台|系统|载荷|卫星|激光雷达|"
    r"论文|学报|期刊|成果|获奖|大奖|专利|标准|技术|研发|研制|攻关|突破")
FRONTIER_COMMENT_ONLY = re.compile(
    r"市场空间|市场规模|产业规模|万亿|前景|展望|评论|述评|寄语")
def frontier_substance_ok(title, body=""):
    """R8：前沿类条目是否有实质内容。返回 (是否合格, 原因)。"""
    text = "%s %s" % (title or "", body or "")
    if FRONTIER_COMMENT_ONLY.search(title or ""):
        return False, "R8 实质内容门槛（产业评论／市场预测，无技术实质）"
    if not FRONTIER_SUBSTANCE.search(text):
        return False, "R8 实质内容门槛（无方法／指标／成果要素）"
    return True, ""


# ------------------------------ 采集窗口（国际内容一律不收，不做任何回溯放宽）
from period_config import P  # noqa: E402

WINDOW_FROM, WINDOW_TO = P.window_from, P.window_to


def in_window(date):
    """日期是否落在采集窗口内（空日期视为待核）。"""
    if not date:
        return True
    return WINDOW_FROM <= date <= WINDOW_TO
# ------------------------------ 正文清洗：去掉网页元信息与打印/关闭之类的"页面家具"
BODY_FURNITURE = [
    r"发布(?:日期|时间)\s*[:：]\s*\d{4}\s*[-/年.]\s*\d{1,2}\s*[-/月.]\s*\d{1,2}\s*日?",
    r"发布(?:日期|时间)\s*[:：]\s*[^\s，。；]{0,20}",
    r"浏览次数\s*[:：]?\s*\d+",
    r"阅读次数\s*[:：]?\s*\d+",
    r"浏览\s*(?:次数|量)?\s*[:：]\s*\d+\s*次?",
    r"-->", r"<!--",
    r"【\s*(?:字号|字体|大\s*中\s*小)[^】]*】",
    r"【\s*(?:打印|关闭|返回|顶部|收藏|分享|纠错|下载)[^】]*】",
    r"(?:打印本页|关闭窗口|返回顶部|打印文章)",
    # 注意：不能贪吃正文。曾用 `扫一扫[^\n。]{0,16}` 把正文
    # “用手机扫一扫随机获取的地图，系统即可自动识别…”整段误删（2026-09-17 修正）。
    r"微信扫一扫\s*(?:关注|二维码|查看|浏览|了解|详情|我们)?\s*[:：]?",
    r"(?:长按|扫描|识别)\s*二维码[^\n。]{0,12}",
    r"分享到\s*[:：]",
    r"新媒体编辑\s*[:：]\s*\S{1,12}",
    r"责任编辑\s*[:：]\s*\S{1,12}",
    r"审核人\s*[:：]\s*\S{1,12}",
    r"标签\s*[:：]\s*$",
    r"时间\s*[:：]\s*\d{4}\s*[-/年.]\s*\d{1,2}\s*[-/月.]\s*\d{1,2}\s*日?",
]
BODY_FURNITURE_RE = re.compile("|".join(BODY_FURNITURE))
# 独立成行的“页面提示”才整行删除（正文里出现的同名字词保留）
FURNITURE_LINE_RE = re.compile(
    r"^(?:扫一扫[^\n]{0,24}|长按[^\n]{0,20}|识别二维码[^\n]{0,24}|点击[^\n]{0,16}(?:查看|阅读|了解)|"
    r"阅读原文|关注(?:我们|公众号)[^\n]{0,12}|转载请注明来源[^\n]{0,12}|稿件来源[:：][^\n]{0,20})$")
# 头部区域内的"来源：单位"属于页面元信息（正文里的"数据来源""资料来源"不受影响）
HEAD_SOURCE_RE = re.compile(r"(?<![数据资料])来源\s*[:：]\s*[^\s，。；【】]{2,24}")


def clean_body(text, title=""):
    """清洗正文：去头部标题重复与页面元信息，去尾部打印/关闭等家具。"""
    t = (text or "").replace("\u3000", " ")
    if not t.strip():
        return ""
    # 去掉开头重复的标题（允许标题内部夹空格/换行）
    title = re.sub(r"\s+", "", title or "")
    if title:
        body_head = re.sub(r"\s+", "", t[:len(title) + 40])
        if body_head.startswith(title[:12]):
            pat = r"\s*".join(re.escape(c) for c in title)
            m = re.match(pat + r"\s*", t)
            if m:
                t = t[m.end():]
    t = BODY_FURNITURE_RE.sub(" ", t)
    # 独立成行的页面提示整行删除（正文中的同名字词不受影响）
    t = "\n".join("" if FURNITURE_LINE_RE.match(line.strip()) else line
                  for line in t.split("\n"))
    head, tail = t[:200], t[200:]
    head = HEAD_SOURCE_RE.sub(" ", head)
    t = head + tail
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return normalize_text(t).strip()


# ---------------------------------------------------------------- 空格与标点规范化
CJK = "\u3400-\u4dbf\u4e00-\u9fff"
CN_PUNCT_OPEN = "，。、；：！？）》”’】"
CN_PUNCT_CLOSE = "，。、；：！？《（“‘【"
HEADING_LINE = re.compile(r"^第\s*[一二三四五六七八九十百零〇\d]+\s*[章条节款项]|^[一二三四五六七八九十]+、\S{0,20}$")


def _fix_line_spaces(line):
    """单行空格规范化：去掉汉字与字母/数字之间、中文标点前后的多余空格。

    保留：章条标题行、“引号内标语”这类汉字之间的空格（如“维护地理信息安全 激发时空数据潜能”）。
    """
    if HEADING_LINE.match(line.strip()):          # 法条/章标题：整体保留空格
        return re.sub(r"[ \t]{2,}", " ", line)
    out = []
    # 引号内的片段先保护起来（标语常以空格分隔）
    protected = []

    def _keep(m):
        protected.append(m.group(0))
        return "\x00%d\x00" % (len(protected) - 1)

    line = re.sub(r"[“\"'][^”\"']{1,40}[”\"']", _keep, line)
    # 汉字 ↔ 字母/数字
    line = re.sub(r"(?<=[%s])[ \t]+(?=[A-Za-z0-9])" % CJK, "", line)
    line = re.sub(r"(?<=[A-Za-z0-9])[ \t]+(?=[%s])" % CJK, "", line)
    # 中文标点前后
    line = re.sub(r"[ \t]+(?=[%s])" % CN_PUNCT_OPEN, "", line)
    line = re.sub(r"(?<=[%s])[ \t]+" % CN_PUNCT_CLOSE, "", line)
    # 行首行尾
    line = re.sub(r"^[ \t]+|[ \t]+$", "", line)
    for i, seg in enumerate(protected):
        line = line.replace("\x00%d\x00" % i, seg)
    return line


def normalize_text(text):
    """统一特殊空白、去掉汉字与字母数字/中文标点之间的多余空格，规范中文里的半角标点。"""
    if not text:
        return ""
    t = (text.replace("\u200a", "").replace("\u200b", "").replace("\u2004", " ")
              .replace("\xa0", " ").replace("\u3000", " "))
    t = "\n".join(_fix_line_spaces(line) for line in t.split("\n"))
    # 中文语境里的半角标点 → 全角（两侧都是汉字时才转，避免影响数字/英文）
    for half, full in ((",", "，"), (";", "；"), ("!", "！"), ("?", "？")):
        t = re.sub(r"(?<=[%s])%s(?=[%s])" % (CJK, re.escape(half), CJK), full, t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t


def check_text_quality(text, title=""):
    """正文体例检查：返回问题列表 [(类型, 上下文)]，供人工复核（不自动改写）。"""
    issues = []
    t = text or ""
    for m in re.finditer(r"[%s][ \t]+[%s]" % (CJK, CJK), t):
        seg = t[max(0, m.start() - 12):m.end() + 12].replace("\n", " ")
        line = t[:m.start()].split("\n")[-1]
        if HEADING_LINE.match(line.strip()) or re.search(r"[“\"'][^”\"']*[ \t][^”\"']*[”\"']", seg):
            continue                              # 法条标题、引号内标语属正常
        issues.append(("汉字间空格（疑漏字）", seg))
    for m in re.finditer(r"[%s][,;:?!][%s]" % (CJK, CJK), t):
        issues.append(("中文里出现半角标点", t[max(0, m.start() - 12):m.end() + 12].replace("\n", " ")))
    for m in re.finditer(r"[，。、；：！？]{2,}", t):
        issues.append(("连续标点", t[max(0, m.start() - 10):m.end() + 10].replace("\n", " ")))
    for m in re.finditer(r"[\xa0\u200a\u2004\u200b]", t):
        issues.append(("特殊空白字符", repr(t[max(0, m.start() - 10):m.end() + 10])))
    for m in re.finditer(r"^(?:扫一扫|长按|识别二维码|点击(?:查看|阅读)|关注我们|阅读原文)[^\n]{0,20}$", t, re.M):
        issues.append(("页面提示残留", m.group(0)[:30]))
    for a, b in (("“", "”"), ("《", "》"), ("（", "）"), ("‘", "’")):
        if t.count(a) != t.count(b):
            issues.append(("引号/括号不成对", "%s=%d %s=%d" % (a, t.count(a), b, t.count(b))))
    for m in re.finditer(r"[\u4e00-\u9fa5]{2,}(?:/摄|供图)", t):
        issues.append(("疑似署名/供图", m.group(0)))
    return issues


def entity_match(url, publisher):
    """校验链接实体是否属于该发布单位。返回 (是否匹配, 载体类型, 说明)。

    名称只作线索：官网看域名是否属于该单位，公众号看 __biz 是否属于该单位。
    """
    pub = (publisher or "").strip()
    host = host_of(url)
    if not host:
        return False, "无链接", "链接缺失"
    if host in ("mp.weixin.qq.com", "weixin.sogou.com"):
        biz = wechat_biz(url)
        if not biz:
            return False, "公众号", "取不到 __biz，无法确认发布账号"
        # R5 来源分层：部级/省级公众号可作来源；地市级与汇编号不可
        ok_tier, why_tier = wechat_source_ok(url)
        if ok_tier:
            return True, "公众号", why_tier
        if biz in WECHAT_CLUE_ONLY_BIZ or biz in WECHAT_DIGEST_BIZ:
            return False, "公众号", why_tier
        if biz in WECHAT_DIGEST_BIZ:
            return False, "公众号", WECHAT_DIGEST_BIZ[biz]
        allowed = ORG_WECHAT.get(pub)
        if allowed and biz in allowed:
            return True, "公众号", f"{pub} 公众号原文（__biz={biz}）"
        if allowed:
            return False, "公众号", f"__biz={biz} 不属于「{pub}」"
        # 单位未建公众号对照：按账号名线索通过，并提示补录
        return True, "公众号", f"未建 ORG_WECHAT 对照，按名称线索通过（__biz={biz}）"
    # 官网
    kinds = site_type(url)
    if not kinds:
        return False, "非白名单域名", f"域名 {host} 不在白名单"
    allowed = ORG_SITES.get(pub)
    if allowed is None:
        return True, kinds, f"未建 ORG_SITES 对照，按域名白名单通过（{host}）"
    if any(host == d or host.endswith("." + d) for d in allowed):
        return True, kinds, f"{pub} 官网原文（{host}）"
    return False, kinds, f"域名 {host} 不属于「{pub}」（允许：{', '.join(allowed)}）"


def site_type(url):
    """官网域名判定，返回来源类型或空串。"""
    host = host_of(url)
    if not host:
        return ""
    if host in ("mp.weixin.qq.com", "weixin.sogou.com"):
        return "公众号"
    for domain, kind in SITE_WHITELIST.items():
        if host == domain or host.endswith("." + domain):
            return kind
    return ""


# ---------------------------------------------------------------- 三个板块
BOARDS = ["政策法规", "技术应用类", "科技前沿类"]
# 旧板块名的兼容映射（历史批注版／历史数据里仍可能写“政策类”）
BOARD_ALIASES = {"政策类": "政策法规", "媒体动态类": "技术应用类"}


def board_name(name):
    """把历史板块名归一成现行板块名。"""
    return BOARD_ALIASES.get((name or "").strip(), name)

# 既有七模块 → 四板块的基础映射（会议报告、跨界融合与产业按内容再判）
MODULE_TO_BOARD = {
    "政策措施": "政策法规",
    "技术应用": "技术应用类",
    "科技前沿": "科技前沿类",
    # 科普与版图宣传、国际视野按“不收”处理（见 23 号脚本 EXCLUDED_MODULES），这里只给中性归属
    "科普与版图宣传": "技术应用类",
    "国际视野": "技术应用类",
    "会议报告": "技术应用类",
    "跨界融合与产业": "技术应用类",
}

# 关键词规则：先命中者优先（政策法规 > 科技前沿类 > 技术应用类）
BOARD_RULES = [
    ("政策法规", [r"印发", r"发布.{0,10}(?:办法|条例|规划|标准|指南|规定|意见)",
                r"(?:条例|办法|规划|标准|指南|规定|意见|通知|细则)$", r"管理办法",
                r"实施意见", r"征求意见", r"修订发布", r"规范性文件", r"顶层设计",
                r"规划(?:印发|发布|实施|通过|获批|编制|评审)", r"“十五五”.{0,12}规划",
                r"(?:基础测绘|测绘地理信息|国土空间|地理空间|地理信息产业).{0,8}规划"]),
    ("科技前沿类", [r"算法", r"大模型", r"人工智能", r"智能解译", r"样本库", r"卫星",
                    r"论文", r"院士", r"学术", r"研究(?:成果|进展)", r"专利", r"高光谱",
                    r"理论", r"技术(?:攻关|突破)", r"质检系统", r"自研系统"]),
]

POLICY_TITLE = re.compile(
    r"印发|发布|条例|办法|规划|标准|指南|规定|通知|意见|细则|实施方案|实施方案|修订|政策|"
    r"部署|举措|方案")


def board_of(module, title, summary="", note=""):
    """三板块归类：模块给底，关键词纠偏。

    政策法规只在标题上判定（避免摘要里"国土规划集团"这类误命中）；
    科技前沿类在标题＋摘要上判定（属内容特征）；经验做法稿归技术应用类。
    """
    text = f"{title} {summary}"
    base = MODULE_TO_BOARD.get(module, "技术应用类")
    for board, pats in BOARD_RULES:
        if base == board:
            continue
        scope = title if board == "政策法规" else text
        if any(re.search(p, scope) for p in pats):
            return board
    # 政策法规兜底校验：标题没有政策特征就不要硬塞进政策法规
    if base == "政策法规" and not POLICY_TITLE.search(title or ""):
        return "技术应用类"
    return base


# ------------------------------------------------------------ 10 条业务条线
BUSINESS_LINES = [
    "实景三维建设",
    "测绘基准服务",
    "测绘地理信息公共服务",
    "自然资源调查监测技术支撑",
    "自然资源执法监管技术支撑",
    "卫星遥感与多源数据融合应用",
    "应急测绘保障",
    "地理信息数据安全与保密",
    "测绘科技创新与关键技术攻关",
    "测绘行业管理与技术服务",
]

BUSINESS_RULES = [
    ("卫星遥感与多源数据融合应用",
     [r"卫星遥感", r"遥感影像", r"影像获取", r"影像统筹", r"数据融合", r"多源", r"解译",
      r"铁塔视频", r"影像云"]),
    ("自然资源执法监管技术支撑",
     [r"执法", r"违法", r"乱占耕地", r"非农化", r"挖湖造景", r"砂石", r"非法采矿",
      r"生态修复", r"损毁土地", r"督察", r"例行督察", r"越界", r"矿山测量", r"采矿"]),
    ("自然资源调查监测技术支撑",
     [r"变更调查", r"国土空间监测", r"调查监测", r"耕地保护", r"国土绿化", r"确权登记",
      r"地籍", r"林权", r"自然资源资产"]),
    ("应急测绘保障",
     [r"应急测绘", r"应急保障", r"抢险", r"救灾", r"地震", r"泥石流", r"防汛", r"演练"]),
    ("地理信息数据安全与保密",
     [r"保密", r"涉密", r"非涉密", r"数据安全", r"成果管理", r"安全监管", r"密码",
      r"重要数据", r"个人信息"]),
    ("测绘基准服务",
     [r"基准站", r"卫星导航定位", r"北斗", r"高程", r"大地基准", r"深度基准", r"GNSS",
      r"坐标系统", r"授时", r"测量标志", r"陆海一体化", r"似大地水准面", r"潮位",
      r"基准(?:建设|维护|服务|体系)"]),
    ("实景三维建设",
     [r"实景三维", r"一张图", r"数智底座", r"时空底座", r"三维模型", r"三维建设",
      r"基础测绘", r"时空数据", r"数字孪生"]),
    ("测绘地理信息公共服务",
     [r"天地图", r"公众版", r"公益性地图", r"地图集", r"政务用图", r"一乡一图", r"挂图",
      r"地图编制", r"地图服务", r"公共服务", r"成果服务", r"地理信息公共服务", r"帮扶"]),
    ("测绘行业管理与技术服务",
     [r"资质", r"注册测绘师", r"职称", r"质量检查", r"双随机", r"计量检定", r"检定",
      r"信用管理", r"行业管理", r"地图审查", r"问题地图", r"地图监管", r"国家版图",
      r"地图审核", r"标准地图", r"标准(?:发布|实施|体系)", r"规范"]),
    ("测绘科技创新与关键技术攻关",
     [r"科技创新", r"科技项目", r"众创", r"竞赛", r"课题", r"智库", r"技术赛", r"成果转化",
      r"学术会议", r"研讨会", r"论坛", r"交流会", r"年会", r"人工智能", r"大模型",
      r"大数据", r"挖掘", r"众源", r"语义化", r"地理实体", r"低空经济", r"实景三维数据更新"]),
    # —— 兜底规则（放最后，不抢占上面的精确匹配）——
    ("测绘行业管理与技术服务",
     [r"国家标准", r"行业标准", r"标准发布", r"管理办法", r"地理信息产业", r"产业",
      r"万亿", r"数据要素", r"新型基础设施", r"信用"]),
    ("测绘地理信息公共服务",
     [r"古地图", r"档案", r"地图文化", r"数字地图"]),
]


def business_of(title, summary="", keywords=""):
    """按 10 条业务条线打标，返回 (条线, 命中关键词) 列表。"""
    text = f"{title} {summary} {keywords}"
    hits = []
    for line, pats in BUSINESS_RULES:
        matched = [p for p in pats if re.search(p, text)]
        if matched:
            hits.append((line, matched[0]))
    return hits


def business_primary(hits):
    """取第一条命中作为主条线（BUSINESS_RULES 已按业务权重排序）。"""
    return hits[0][0] if hits else ""
