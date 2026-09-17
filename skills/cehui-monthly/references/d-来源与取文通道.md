# 来源与取文通道

来源白名单与对照表在 `<工作根 ToolRoot>\2026年8-9月测绘动态资讯\01_来源清单与采集方法.md`
（跨期手册）与 `99_脚本\sources_whitelist.py`（代码）；三条专用通道的方法文档在根目录。

## 白名单要点

- **官网类**：自然资源部及直属单位（`mnr.gov.cn`、`drcmnr.cn`、`ngcc.cn`、`casm.ac.cn`）、
  学会协会（`csgpc.org`、`cagis.org.cn`）、原发媒体（`iziran.net`、`szb.iziran.net`、`taibo.cn`、`people.com.cn`）、
  省级主管部门与测绘单位（`snsm.mnr.gov.cn`、`scsm.mnr.gov.cn`、`hlsm.mnr.gov.cn`、`zrzyt.*.gov.cn` 等）。
- **公众号类**：自然资源部、浙江自然资源等部级/省级主管部门公众号可作来源；地市级（如徐州自然资源和规划）仅作线索；
  `MzUyMTczMDQzNg==`（《测绘地理信息周讯》）只作线索。
- **校验方式**：链接域名 vs 单位（`ORG_SITES`）、公众号 `__biz` vs 账号（`ORG_WECHAT`）；名称、备注只作线索。

## 通道与限制

| 通道 | 脚本 | 关键点 | 限制 |
| --- | --- | --- | --- |
| 部委/省厅官网列表 | `03_harvest_sources.py` + `04_fetch_details.py` | 可只跑指定 id；`FORCE=1` 强制重取详情 | 政府站 GBK/UTF-8 混用；JS 列表要换接口 |
| 中国自然资源报（i 自然） | `20_zrzyb.py` | `a-list --cid 测绘`（`cid=29214`）；`b-search` 数字报全文检索 | 数字报须先 `ipLogin` 取匿名会话并带 `myIdentity` 头 |
| 泰伯网 | `21_taibo.py` | 列表需 `X-Requested-With: XMLHttpRequest`；`sitemap.xml` 可回溯 | **深度稿有会员墙，不绕过** |
| 浙江省厅统一检索 | `22_zhejiang.py` | `a-search --q 测绘 --cate 动态信息`（`_cus_eq_webid=1568`） | 列表标题会截断，引用回文章页取完整标题 |
| 黑龙江局官网 | `03_harvest_sources.py`（`hlsm_*`） | 接口 `getDocsByChannel.action` | 列表不按日期排序，需全量翻页后按日期过滤 |
| 周讯对标 | `01/10/11/12/14_*weekly*` | 只作选题线索 | 不作来源，必须回溯原发布方 |
| 人工指定采纳 | `26_add_manual_source.py` | 编辑 `MANUAL` 列表（URL／板块／业务条线／层级／省份／单位／优先级） | 用于部级专题、中央媒体地方频道等 |

## 取文失败时的处置顺序

1. 换入口：官网列表 → 站内检索 → 数字报/接口 → 公众号原文。
2. 仍取不到**原发布方**原文：该条不入目录（移入《_备查/周讯回溯待办.md》）。
3. 页面仅图片/视频：按非文字稿剔除，不留“待补”。
4. **禁止**：绕过会员墙、验证码、登录（泰伯深度稿、搜狗微信验证码一律放弃）。

## 已废弃入口（勿再尝试）

`iziran.com`、`zrzyb.net`、`zrzyb.cn`、`3snews.net`、`www.zjch.org.cn`、`chinacehui.org`。
