# cehui-monthly · 测绘动态月刊工作流

把省级测绘地理信息发展中心的《测绘动态工作（测绘地理信息月刊）》编发流程，做成一套可复用的
**Codex 技能 + 工具链**，分两块：

| 阶段 | 做什么 | 入口 |
| --- | --- | --- |
| **A 初稿目录生成** | 官网/专用通道采集 → 周讯线索 → 自动初筛 → 三板块归类与业务条线打标 → 领导批注回灌 → 来源实体校验与正文复检 → 生成目录（md／xlsx／Word）与 `02_原文` 归档 → 自检 | `skills/cehui-monthly/scripts/run_draft_catalog.ps1` |
| **B 月刊排版** | 校验定稿选目 → 用三栏目模板出刊（封面红字刊名、正文页眉、全文＋文末原文链接、目录页码收敛）→ **文本核校**（空格／半角标点／漏字）→ 渲染 PDF/预览 → 版式体检 | `skills/cehui-monthly/scripts/run_monthly_issue.ps1` |

## 文本核校（2026-09-17 增补）

成稿后必做两道，`run_monthly_issue.ps1` 已内置：

| 脚本 | 作用 | 输出 |
| --- | --- | --- |
| `99_脚本\27_text_qa.py --doc <成稿.docx>` | 体例体检：多余空格、特殊空白、汉字间半角标点、疑漏字，并与原文逐段比对 | `_备查\文本体例检查.md` |
| `99_脚本\33_fix_docx_text.py <成稿.docx>` | 只改 `w:t` 文本节点清空格与半角标点，不动版式 | `<成稿>_核校版.docx`、`_备查\成稿空格核校.md` |

- 清除：汉字与字母/数字之间的空格（“自 2023 年”→ “自2023年”）、中文标点前后的空格、`U+00A0／U+200A／U+2004` 等特殊空白、汉字间半角标点。
- 保留：法条与章标题（`第一章 总 则`）、引号内标语（“维护地理信息安全 激发时空数据潜能”）、页脚“— 1 —”、目录制表位。
- 漏字防控：抓取端的页面家具正则严禁写成 `扫一扫[^\n。]{0,16}` 这类会吞掉正文的写法（曾误删整句），
  详见 `references\c-口径与规则.md`。

## 目录结构

```
cehui-monthly/
├─ skills/cehui-monthly/           # Codex 技能（复制到 ~/.codex/skills/ 即可用）
│   ├─ SKILL.md                    # 触发条件、硬规则、两块流程与路由
│   ├─ agents/openai.yaml
│   ├─ references/                 # A/B 两块流程、口径规则、来源通道、验收清单
│   ├─ scripts/                    # 两个入口脚本 + 版式体检脚本
│   └─ assets/period.template.json # 期次配置模板
├─ pipeline/                       # 工具链（放到“工作根目录”下使用）
│   ├─ 99_脚本/                    # 采集、初筛、重建、核验、成稿、自检等 30+ 脚本
│   └─ 编制排版/                   # 月刊模板与出刊脚本
└─ docs/                           # 采集口径、作业流程 SOP、三条取文通道方法
```

## 快速开始

1. **安装技能**

   ```text
   把 skills/cehui-monthly 整个目录复制到：
     Windows: %USERPROFILE%\.codex\skills\cehui-monthly
     macOS/Linux: ~/.codex/skills/cehui-monthly
   ```

   之后在 Codex 里提到“测绘动态 / 初稿目录 / 月刊排版”时会自动考虑该技能，也可以显式写 `$cehui-monthly`。

2. **部署工具链**（任选一个工作根目录，例如 `D:\cehui-work`）

   ```text
   D:\cehui-work\
   ├─ 99_脚本\        ← 来自 pipeline\99_脚本
   └─ 编制排版\       ← 来自 pipeline\编制排版（含 测绘动态月刊_模板.docx/.dotx）
   ```

   运行脚本时用参数或环境变量指向它：

   ```powershell
   $env:CEHUI_TOOL_ROOT = "D:\cehui-work"
   ```

3. **建期**：新建期次目录（如 `D:\cehui-work\2026年10-11月测绘动态资讯\`），
   复制 `skills/cehui-monthly/assets/period.template.json` 到该目录的 `99_脚本\period.json`，填好采集窗口、期号等。

4. **跑流程**

   ```powershell
   # 阶段A：初稿目录生成（可用 -Only 07,14,32,17 / -From 25 / -SkipWeekly / -LeaderDoc）
   powershell -File "…\skills\cehui-monthly\scripts\run_draft_catalog.ps1" `
     -PeriodDir "D:\cehui-work\2026年10-11月测绘动态资讯" -ToolRoot "D:\cehui-work"

   # 阶段B：月刊排版（-RebuildTemplate 重建模板；-Forward 干跑到 _raw\_forward）
   powershell -File "…\skills\cehui-monthly\scripts\run_monthly_issue.ps1" `
     -PeriodDir "D:\cehui-work\2026年10-11月测绘动态资讯" -ToolRoot "D:\cehui-work"
   ```

## 依赖

- Python 3.10+：`pdfplumber`、`openpyxl`、`python-docx`、`lxml`、`PyYAML`
- LibreOffice（`soffice`）——导出 PDF 与渲染校验
- 可选：Codex `documents` 技能自带的 `render_docx.py`（用于逐页 PNG 预览；缺失时自动降级为只出 PDF）
- 需要外网访问目标官网/接口

> 入口脚本会自动挑一个装了上述依赖的 Python：先看 `-Python` 参数，再看环境变量 `CEHUI_PYTHON`，
> 然后依次探测 `python`／`python3`／`py` 与 Codex 桌面版自带运行时。都不满足时可以显式指定：
> `-Python "D:\Python311\python.exe"`。

## 流程规则摘要

- **三板块**：政策类／技术应用类／科技前沿类（不设“媒体动态类”，经验做法稿归技术应用类），不设二级分类。
- **来源规则**：官网优先、白名单公众号兜底；**校验看链接实体**（域名／公众号 `__biz`）；周讯只作线索。
- **正文**：必须是原发布方原文，**段落换行必须保留**；成刊“一行即一段”，全文＋文末原文链接。
- **排序（R4）**：层级（部级→行业与官媒→外省）→ 业务中心度（按本单位党组半年工作情况汇报章节序）→ 发布日期倒序。
- **产出**：初版约 35 条 → 领导批注后终稿 20—25 条；某期也可“终稿直出”。
- 详细规则见 `docs/00_测绘动态资讯采集口径.md`、`docs/01_作业流程（SOP）.md` 与技能 `references/`。

## 数据与合规

- 只采集**公开网页**内容，抓取内容仅供内部资讯汇编；`README` 与文档中的单位名称、目录路径均已模板化。
- 不绕过会员墙、验证码或登录限制；发现验证码/付费墙即放弃该来源。
- 请遵守目标站点的 robots 与版权要求；对外转载需获得版权方授权。

## 许可

MIT License，见 `LICENSE`。模板中的版式（刊头、页眉等）取自本单位内部刊物，可按需替换。
