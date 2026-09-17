# 阶段A：初稿目录生成（逐步骤）

所有脚本在 `<工作根 ToolRoot>\99_脚本\`（唯一代码副本）。运行前用 `CEHUI_PERIOD_DIR` 指向期次目录，
或用入口脚本 `scripts\run_draft_catalog.ps1 -PeriodDir <期次目录>`（它已设置该环境变量并把日志写进 `_raw\_run_logs\`）。

期次参数来自 `<期次目录>\period.json`：`issue_dir`、`window_from`、`window_to`、`collect_date`、
`title_range`、`issue_label`、`publish_date`。改窗口只改这一处，不要改脚本。

## 步骤与判定

| 步 | 脚本 | 作用 | 判定 |
| --- | --- | --- | --- |
| 0 | 开期校验 | 检查期次目录结构（`_raw/02_原文/Word版/_备查/03_参考_山东周讯`）与 `period.json` | 缺 `period.json` 时用 `assets\period.template.json` 生成并提示补全 |
| 1 | `03_harvest_sources.py` | 官网列表采集（可只跑指定 id） | 列表页日期只作线索；每来源落 `_raw/<id>.json` |
| 2 | `04_fetch_details.py` | 抓详情与正文 | `_raw/<id>_detail.json`；正文按块级标签换行 |
| 3 | `20_zrzyb.py`／`21_taibo.py`／`22_zhejiang.py` | 三条专用通道（i 自然、泰伯网、浙江厅统一检索） | 见 `d-来源与取文通道.md`；泰伯深度稿会员墙不绕过 |
| 4 | `26_add_manual_source.py` | 人工指定采纳（按需，编辑 `MANUAL` 列表） | 写入语料与选目补丁 |
| 5 | `01/10/11/12_*weekly*` | 周讯线索（只作线索，不入来源） | 未回溯到原发布方的条目不进目录 |
| 6 | `24_auto_shortlist.py` | 新来源初筛（每来源上限 6 条） | 排除党建、巡视、招聘、培训、走访等 |
| 7 | `23_rebuild_boards.py` | 三板块归类＋10 条业务条线打标 | 国际/科普/福建/日期越界/宣传类进《_备查/未收录条目.md》 |
| 8 | `29_apply_leader_edits.py --doc <批注版.doc> --label <版本>` | 解析领导批注（w:ins/w:del）→ `_raw/leader_<版本>.json` | 有批注版才跑；报告进《_备查/领导批注规则（<版本>）.md》 |
| 9 | `31_build_draft_selection.py` | 以终稿为骨架出选目；`DIRECT_FINAL=True` 为终稿直出，False 为按三板块补位 | 骨架保序；补充条目按 R4 插入 |
| 10 | `25_verify_source_entity.py` | 链接实体校验＋正文复检 | 实体不匹配剔除；正文 <200 字或覆盖率 <0.7 记“待补” |
| 11 | `08_verify.py` | 多方式核实（链接/正文/日期/交叉来源） | 输出 `_raw/核实结果.json` |
| 12 | `09_make_verify_doc.py` | 生成《04_核实记录.md》 | 板块分布与来源类型统计一致 |
| 13 | `07_build_catalog.py` | 出目录 md／xlsx、写 `02_原文`、清理往期归档 | 归档份数＝目录条数；抬头三行 |
| 14 | `14_weekly_pool.py` | 周讯线索池工作表 | 必须晚于 07（往 xlsx 追加表） |
| 15 | `32_export_backups.py` | 全量底稿与领导终稿备查 + xlsx 工作表 | 条数与选目一致 |
| 16 | `17_make_docx.py` | Word 版交付件（目录、阅读说明、来源清单、核实记录、线索池、口径、SOP） | 文件被占用时脚本会跳过，关闭后重跑 |
| 17 | `28_check_standard_consistency.py`＋`30_regression_leader.py` | 收尾自检 | 28 不一致 0 项；30 骨架缺失 0、顺序异常 0、剔除不回流 |

## 顺序约束（不可调换）

- `14` 必须晚于 `07`（07 会重建 xlsx）。
- `25` 必须早于 `07`（07 读 `catalog_selection_final.json`）。
- `08` 必须早于 `07`（07 写“核实状态/核实方式”）。
- `23` 必须在 `25` 之前，`24` 在 `23` 之前。

## 常见故障

- **正文是整页导航/模板文本**：`is_junk_text()` 判为抓取失败 → 剔除，不要靠“字数够 200”放行。
- **正文被压成一行**：抓取端 `strip_html()` 已把 `</section>` 等块级标签当换行；若仍出现，检查该来源是否把正文放进 `<td>`／图片或用了特殊容器。
- **来源实体不匹配**：按链接域名纠正发布单位，或回溯原发布方；回溯不到就剔到《_备查/周讯回溯待办.md》。
- **条目数对不上**：先看 `_备查/待补原文清单.md`（待补条目仍计入目录）与 `02_原文` 份数。
- **重复条目**：25 会按标题相似度 ≥0.85 合并，主链接取官网。
