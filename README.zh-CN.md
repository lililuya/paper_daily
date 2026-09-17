# Paper Daily

[![standard-readme compliant](https://img.shields.io/badge/readme%20style-standard-brightgreen.svg?style=flat-square)](https://github.com/RichardLitt/standard-readme)
[![daily pipeline](https://github.com/lililuya/paper_daily/actions/workflows/run.yml/badge.svg)](https://github.com/lililuya/paper_daily/actions/workflows/run.yml)
[![site](https://img.shields.io/badge/site-GitHub%20Pages-blue?style=flat-square)](https://lililuya.github.io/paper_daily/)

每日自动追踪 AI 前沿研究的流水线：抓取 arXiv 与 HuggingFace Daily Papers，按兴趣方向打分筛选，生成中文日报与交互式网页。

[English](README.md) | 简体中文

## 内容列表

- [背景](#背景)
- [使用说明](#使用说明)
  - [在线阅读](#在线阅读)
  - [追踪方向](#追踪方向)
  - [每日流水线](#每日流水线)
- [安装](#安装)
  - [云端部署（GitHub Actions）](#云端部署github-actions)
  - [本地运行](#本地运行)
- [配置](#配置)
- [相关仓库](#相关仓库)
- [维护者](#维护者)
- [如何贡献](#如何贡献)
- [使用许可](#使用许可)

## 背景

前沿论文每天更新数百篇，人工刷 arXiv 列表费时费力且容易漏掉重要工作。本项目参考 [daily-arXiv-ai-enhanced](https://github.com/dw-dengwei/daily-arXiv-ai-enhanced) 的思路，做了一套全自动的「抓取 → 打分 → LLM 增强 → 日报发布」流水线：

- **规则打分先行**：关键词加权表 + 命中封顶 + 方向配额，防止单一方向霸榜，再决定哪些论文值得花 LLM token；
- **多源数据**：arXiv 官方 API + HuggingFace Daily Papers（社区热度保底）+ papers.cool Kimi 深度解读；
- **零依赖**：纯 Python 标准库（`urllib` + `xml.etree`），无第三方包，克隆即跑；
- **双输出**：本地 `data/` 下的 Markdown 日报存档 + GitHub Pages 交互式网页（搜索、标签过滤、LaTeX 公式渲染、重点标记）。

## 使用说明

### 在线阅读

站点地址：**<https://lililuya.github.io/paper_daily/>**

- 顶部切换日期、关键词搜索、按方向标签过滤
- 每篇论文展示：中文标题、一句话摘要、abstract 原文、推荐指数、papers.cool Kimi Q&A 深度解读
- 「☆ 标重点」按钮可标记重点阅读（存储在浏览器 localStorage，「只看重点」一键过滤）

### 追踪方向

| 方向 | 权重 | 关键词示例 |
|---|---|---|
| **图像编辑** | 核心 ×5 | image editing、inpainting、subject-driven、image composition |
| **视频模型** | 核心 ×5 | video generation、video diffusion、text-to-video、video editing |
| **Agent** | 核心 ×5 | LLM agent、tool use、multi-agent、GUI agent、agentic |
| **数据工程** | 核心 ×5 | data curation、data selection、synthetic data、data-centric |
| 大语言模型 | 2 | LLM、reasoning、MoE、RLHF、RAG、LoRA |
| 多模态 | 2 | multimodal、vision-language、text-to-image、diffusion |
| 系统/基础设施 | 2 | distributed training、inference optimization、KV cache、quantization |
| HF 社区精选 | 保底 | 自动包含 HuggingFace Daily Papers 高赞论文 |

四个核心方向每日轮询配额选取，保证每个方向都有曝光；每日精选上限 25 篇。

### 每日流水线

```
fetch_arxiv → fetch_hf → dedup → score → select_balanced → DeepSeek 增强 → Kimi 解读 → Markdown 日报 → 提交回 main → Pages 更新
```

| 文件 | 作用 |
|---|---|
| `daily_arxiv/` | 抓取（arXiv / HF / papers.cool Kimi）与规则打分 |
| `ai/enhance.py` | DeepSeek 中文增强（标题 / 摘要 / 推荐指数） |
| `to_md/convert.py` | Markdown 日报生成 |
| `index.html` | 网页前端（单文件，无外部 CDN 依赖） |
| `data/` | 每日数据与日报存档（自动生成，勿手改） |
| `.github/workflows/run.yml` | 云端定时任务 |

## 安装

克隆本仓库：

```sh
git clone https://github.com/lililuya/paper_daily.git
```

### 云端部署（GitHub Actions）

1. 在仓库 **Settings → Secrets and variables → Actions → Secrets** 添加：

   | Secret | 说明 |
   |---|---|
   | `OPENAI_API_KEY` | DeepSeek API Key（或其他 OpenAI 兼容服务） |
   | `OPENAI_BASE_URL` | 默认 `https://api.deepseek.com`，可换其他厂商 |

2. （可选）在 **Variables** 添加：

   | Variable | 默认值 | 说明 |
   |---|---|---|
   | `MODEL_NAME` | `deepseek-chat` | LLM 模型名 |
   | `MAX_LLM_PAPERS` | `25` | 每日精选篇数上限 |

3. 启用 Pages：**Settings → Pages → Build and deployment → Source: Deploy from a branch**，Branch 选 **main** / `(root)`。

4. 流水线每天北京时间 23:00 自动运行，也可在 **Actions → Daily Pipeline → Run workflow** 手动触发。

### 本地运行

要求 Python 3.10+，无第三方依赖：

```sh
python run_pipeline.py --dry-run        # 试跑：真实抓取 + 打分，不调 LLM、不花钱
python run_pipeline.py                  # 完整版：需设置 OPENAI_API_KEY 环境变量
python run_pipeline.py --date 2026-09-17 --no-dedup   # 重跑指定日期
```

未配置 API Key 时自动降级为 dry-run（无中文摘要，仅规则打分）。

## 配置

改关键词、调整方向权重、修改每日篇数、Kimi/DeepSeek 参数等，完整说明见 **[CONFIG.md](CONFIG.md)**。

配置修改需提交到 `main` 分支后，从下一次运行生效（当天已生成的数据不变）。

## 相关仓库

- [daily-arXiv-ai-enhanced](https://github.com/dw-dengwei/daily-arXiv-ai-enhanced) — 本项目的灵感来源
- [papers.cool](https://papers.cool/) — Kimi 论文深度解读数据源
- [standard-readme](https://github.com/RichardLitt/standard-readme) — 本 README 遵循的规范

## 维护者

[@lililuya](https://github.com/lililuya)

## 如何贡献

欢迎提 [Issue](https://github.com/lililuya/paper_daily/issues/new) 或 Pull Request——比如推荐新的追踪关键词、方向或数据源。

## 使用许可

[MIT](LICENSE) © 2026 lililuya
