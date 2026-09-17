# 前研技术追踪 · Frontier Research Daily

每日自动追踪 AI 前沿研究的 GitHub Actions 流水线，每日产出中文日报与 GitHub Pages 网站。

## 当前追踪方向

| 方向 | 权重 | 关键词示例 |
|---|---|---|
| **图像编辑** | 核心 ×5 | image editing、inpainting、subject-driven、image composition |
| **视频模型** | 核心 ×5 | video generation、video diffusion、text-to-video、video editing |
| **Agent** | 核心 ×5 | LLM agent、tool use、multi-agent、GUI agent、agentic |
| **数据工程** | 核心 ×5 | data curation、data selection、synthetic data、data-centric |
| 大语言模型 | 2 | LLM、reasoning、MoE、RLHF、RAG、LoRA |
| 多模态 | 2 | multimodal、vision-language、text-to-image、diffusion |
| 系统/基础设施 | 2 | distributed training、inference optimization、KV cache、quantization |
| HF 社区精选 | 保底 | 自动包含 HuggingFace Daily Papers |

> 完整配置说明（改关键词、调方向、改每日篇数、运行参数等）见 **[CONFIG.md](CONFIG.md)**。

## 数据源

- **arXiv** 官方 API：按 `cs.CL / cs.LG / cs.AI / cs.CV / cs.DC / cs.NI / cs.SE` 类别 + 提交日期窗口拉取
- **Hugging Face Daily Papers**：解析 `huggingface.co/papers` 内嵌 JSON

## 流水线

```
fetch_arxiv → fetch_hf → dedup → score → select_balanced → DeepSeek 增强 → Markdown 日报 → 提交到 main 分支
```

防失衡设计：关键词命中封顶 + 单方向贡献封顶 + 核心方向轮询配额。

## 快速上手

### Secrets（必需）

在仓库 Settings → Secrets and variables → Actions 添加：

| Secret | 说明 |
|---|---|
| `OPENAI_API_KEY` | DeepSeek API Key（或其他 OpenAI 兼容服务） |
| `OPENAI_BASE_URL` | 默认 `https://api.deepseek.com`，可换其他厂商 |

### Variables（可选）

| Variable | 默认值 | 说明 |
|---|---|---|
| `MODEL_NAME` | `deepseek-chat` | LLM 模型名 |
| `MAX_LLM_PAPERS` | `25` | 每日精选篇数上限 |

### 启用 Pages

Settings → Pages → Build and deployment → Source: **Deploy from a branch**, Branch: **main** / `(root)`.

## 本地运行

```bash
python run_pipeline.py --dry-run        # 不调用 LLM
python run_pipeline.py                  # 真实 LLM 增强（需 OPENAI_API_KEY）
python run_pipeline.py --date 2026-09-17 --no-dedup
```

零第三方依赖，纯 Python 3.10+ 标准库（`urllib` + `xml.etree`）。