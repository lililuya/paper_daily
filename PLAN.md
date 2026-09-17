# 前研技术追踪系统 — 项目规划

> 对标项目：[daily-arXiv-ai-enhanced](https://github.com/dw-dengwei/daily-arXiv-ai-enhanced)
> 核心思路：GitHub Actions 每日定时抓取前沿研究内容 → 去重 → DeepSeek 中文摘要与打分 → 生成 Markdown 日报 → 发布 GitHub Pages 网站

---

## 1. 目标与范围

每日自动追踪以下方向的前沿研究，产出一份**中文、可筛选、带推荐指数**的日报：

| 方向 | 数据来源 | 权重 | 说明 |
|---|---|---|---|
| 图像编辑模型（核心） | 关键词过滤（跨类别） | 5 | image editing / inpainting / 可控生成 / 个性化定制 |
| Agent / 智能体（核心） | 关键词过滤（跨类别） | 5 | tool use / agentic / web·GUI agent / 多智能体 |
| 视频模型（核心） | 关键词过滤（跨类别） | 5 | text-to-video / video diffusion / 视频编辑 / 长视频 |
| 大语言模型 | arXiv: cs.CL, cs.LG, cs.AI | 2 | 推理、微调、MoE、长上下文 |
| 多模态 | arXiv: cs.CV | 2 | vision-language、扩散模型、视觉理解 |
| 系统 / 基础设施 | arXiv: cs.DC, cs.NI, cs.SE | 2 | 分布式训练、推理优化、GPU |
| 社区精选 | Hugging Face Daily Papers | - | 量少质高，直接全收 |
| papers.cool Kimi Q&A | https://papers.cool/arxiv/{id}/kimi | 可选 | 7 组 Q&A 深度解读（每篇 ~1-8min，并发=2），失败时回退为链接 |

> 已按需求调整：移除具身智能（cs.RO）与 AI 安全方向，聚焦图像编辑 / Agent / 视频模型三大核心主题。

## 2. 总体架构

```
GitHub Actions (cron: 每日 UTC 21:00 / 北京时间早 5:00)
        │
        ▼
① 抓取  arXiv API（按类别+提交日期） + HF Daily Papers API
        │  → data/YYYY-MM-DD.jsonl（标题/作者/摘要/链接/类别）
        ▼
② 预处理  去重（对比历史 ID 库） + 规则打分（兴趣关键词加权）
        │  → 无新内容则跳过当天
        ▼
③ LLM 增强  DeepSeek-chat（OpenAI 兼容接口）
        │  → 每篇生成：中文一句话摘要 / 详细摘要 / 研究亮点 / 方向标签 / 推荐指数(1-5星)
        │  → 分级处理：3星以下只出一句话摘要（省 token），4星以上做深度摘要
        ▼
④ 生成日报  to_md/convert.py
        │  → data/YYYY-MM-DD.md（含当日总览、Top 10 推荐、分类列表）
        ▼
⑤ 存档与发布
        ├─ 提交到 repo 的 data 分支（JSONL + MD，网站数据源）
        ├─ GitHub Pages 渲染静态网站（复用/改造原项目前端：日期筛选、关键词高亮）
        └─ 本地 git pull 即得 Markdown 日报
```

### 关键技术决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 抓取方式 | arXiv 官方 API（`export.arxiv.org/api/query`），不用 Scrapy | 原项目用 Scrapy 爬列表页较脆弱；官方 API 稳定、支持按类别+日期查询、礼貌限速 3s/次 |
| LLM | DeepSeek-chat（OpenAI 兼容） | 已有 Key，成本低（预估 ¥0.2~0.5/天） |
| 打分策略 | 两级：规则预筛 + LLM 评估 | 先用关键词规则把每日几百篇压到几十篇，再让 LLM 打推荐指数，控制成本 |
| 调度 | GitHub Actions cron（UTC 21:00 ≈ arXiv 当日更新后）+ `workflow_dispatch` 手动触发 | 零服务器、免费、电脑关机不影响 |
| 分支策略 | main 存代码+前端，data 分支只存每日数据 | 仿原项目，data 分支保持轻量 |
| 前端 | fork 后改造原项目 index.html/js/css | 已支持日期筛选、关键词高亮、移动端适配，改数据格式即可 |

## 3. 目录结构

```
前研研究/
├── daily_arxiv/
│   ├── fetch_arxiv.py        # arXiv API 抓取（分类别+关键词）
│   ├── fetch_hf.py           # Hugging Face Daily Papers 抓取
│   ├── dedup.py              # 去重（历史 ID 库 + 当日交叉）
│   └── score.py              # 规则打分（兴趣关键词加权表）
├── ai/
│   └── enhance.py            # DeepSeek 摘要与打分（分级处理）
├── to_md/
│   └── convert.py            # 生成 Markdown 日报
├── data/                     # 每日 JSONL + MD（由 Actions 提交到 data 分支）
├── assets/                   # file-list.txt 等站点资源
├── js/  css/  index.html     # GitHub Pages 前端
├── .github/workflows/run.yml # 每日工作流
├── pyproject.toml            # uv 依赖管理
└── PLAN.md                   # 本文档
```

## 4. 数据格式（JSONL 单行）

```json
{
  "id": "2609.12345",
  "title": "原始英文标题",
  "title_zh": "中文标题",
  "authors": ["A", "B"],
  "abstract": "原文摘要",
  "categories": ["cs.CV"],
  "url": "https://arxiv.org/abs/2609.12345",
  "pdf_url": "https://arxiv.org/pdf/2609.12345",
  "source": "arxiv|hf_daily",
  "oneline_zh": "一句话中文摘要",
  "summary_zh": "详细中文摘要（高分论文）",
  "highlights": ["亮点1", "亮点2"],
  "tags": ["视频生成", "扩散模型"],
  "rating": 4,
  "score": 8.5
}
```

## 5. 日报格式（Markdown）

```markdown
# 前研日报 2026-09-17
> 共 312 篇新论文 · 精选 28 篇 · 推荐 6 篇

## 今日必读（推荐指数 ≥ 4）
### ⭐⭐⭐⭐⭐ 论文中文标题
**方向**：视频生成 | **作者**：A, B 等 | [原文](...) | [PDF](...)
> 一句话摘要
**亮点**：...
**详细摘要**：...

## 具身智能（5 篇）
...

## 图像编辑 / 视频生成（4 篇）
...
```

## 6. 实施计划

| 阶段 | 内容 | 产出 | 预估工作量 |
|---|---|---|---|
| **P1 骨架+抓取** | 项目初始化（uv）、fetch_arxiv.py、fetch_hf.py、dedup.py | 本地能跑出当日 JSONL | 先做 |
| **P2 打分+AI 增强** | score.py 兴趣关键词表、enhance.py 接 DeepSeek | 带中文摘要和评分的 JSONL | 依赖 P1 |
| **P3 日报生成** | convert.py、日报模板 | data/YYYY-MM-DD.md | 依赖 P2 |
| **P4 云端部署** | fork 原项目前端并适配、run.yml、Secrets 配置、Pages 开通 | 每日自动更新的网站 | 依赖 P3 |
| **P5 打磨** | 兴趣关键词调优、失败重试、周报聚合（可选） | 稳定运行 | 持续 |

### 需要的配置（P4 时准备）

- GitHub 仓库（建议私有 + Pages）
- Secrets：`OPENAI_API_KEY`（DeepSeek）、`OPENAI_BASE_URL`（https://api.deepseek.com）
- Variables：`MODEL_NAME=deepseek-chat`、`LANGUAGE=Chinese`、`EMAIL`、`NAME`

## 7. 成本预估

- GitHub Actions / Pages：免费（公开仓库；私有仓库每月 2000 分钟额度，单次约 30~60 分钟，够用）
- DeepSeek API：每日约 50~100 篇精选 × 平均 2K token ≈ ¥0.2~0.5/天，每月 < ¥15

## 8. 风险与对策

| 风险 | 对策 |
|---|---|
| arXiv API 限流 | 请求间隔 ≥3s，失败退避重试；workflow 设 timeout |
| 某日无新内容（周末/节假日） | 去重检查后正常跳过，不产生空提交 |
| DeepSeek 超时/失败 | 单篇失败不阻塞整体，降级为仅规则打分输出 |
| 电脑本地日报同步 | Actions 跑完后本地 `git pull` data 分支即可 |
