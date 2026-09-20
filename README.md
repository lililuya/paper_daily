# Paper Daily

[![standard-readme compliant](https://img.shields.io/badge/readme%20style-standard-brightgreen.svg?style=flat-square)](https://github.com/RichardLitt/standard-readme)
[![daily pipeline](https://github.com/lililuya/paper_daily/actions/workflows/run.yml/badge.svg)](https://github.com/lililuya/paper_daily/actions/workflows/run.yml)
[![site](https://img.shields.io/badge/site-GitHub%20Pages-blue?style=flat-square)](https://lililuya.github.io/paper_daily/)

A fully automated pipeline that tracks frontier AI research every day: it fetches arXiv and HuggingFace Daily Papers, scores and filters them by interest directions, and publishes a Chinese daily digest with an interactive web page.

English | [简体中文](README.zh-CN.md)

## Table of Contents

- [Background](#background)
- [Usage](#usage)
  - [Read Online](#read-online)
  - [Tracked Directions](#tracked-directions)
  - [Daily Pipeline](#daily-pipeline)
- [Install](#install)
  - [Cloud Deployment (GitHub Actions)](#cloud-deployment-github-actions)
  - [Local Run](#local-run)
- [Configuration](#configuration)
- [Related Repositories](#related-repositories)
- [Maintainers](#maintainers)
- [Contributing](#contributing)
- [License](#license)

## Background

Hundreds of new papers appear on arXiv every day; manually scanning listings is slow and easy to miss important work. Inspired by [daily-arXiv-ai-enhanced](https://github.com/dw-dengwei/daily-arXiv-ai-enhanced), this project builds an end-to-end **fetch → score → LLM enhance → publish** pipeline:

- **Rule-based scoring first**: a weighted keyword table with hit capping and per-direction quotas prevents a single direction from dominating, and decides which papers are worth LLM tokens;
- **Multiple sources**: official arXiv API + HuggingFace Daily Papers (community upvotes as a safety net) + papers.cool Kimi in-depth Q&A;
- **Tech blogs too**: 17 RSS/Atom feeds from frontier labs and well-known practitioners, with LLM-generated Chinese titles and takeaways — arXiv goes quiet on weekends and holidays, blogs keep the digest alive;
- **Zero dependencies**: pure Python standard library (`urllib` + `xml.etree`) — clone and run;
- **Dual output**: Markdown daily archives under `data/` + an interactive GitHub Pages site (search, tag filtering, LaTeX rendering, must-read marking).

## Usage

### Read Online

Site: **<https://lililuya.github.io/paper_daily/>**

- **📄 Papers / 📝 Blogs** tabs at the top switch between the paper digest and the tech-blog digest
- Switch dates, search keywords, and filter by direction tags at the top
- Each paper shows: Chinese title, one-line summary, original abstract, recommendation rating, and the papers.cool Kimi Q&A deep dive
- Each blog post shows: site, publish date, Chinese title, one-line takeaway, key points, and a collapsible original excerpt
- Blog posts unrelated to frontier AI (rating 1-2) are hidden by default; choose "all ratings" to reveal them
- The ☆ button marks an item as must-read (stored in browser localStorage; a "must-read only" toggle filters the list)

### Tracked Directions

| Direction | Weight | Sample keywords |
|---|---|---|
| **Image Editing** | core ×5 | image editing, inpainting, subject-driven, image composition |
| **Video Models** | core ×5 | video generation, video diffusion, text-to-video, video editing |
| **Agent** | core ×5 | LLM agent, tool use, multi-agent, GUI agent, agentic |
| **Data Engineering** | core ×5 | data curation, data selection, synthetic data, data-centric |
| LLMs | 2 | LLM, reasoning, MoE, RLHF, RAG, LoRA |
| Multimodal | 2 | multimodal, vision-language, text-to-image, diffusion |
| Systems & Infra | 2 | distributed training, inference optimization, KV cache, quantization |
| HF Community Picks | safety net | high-upvote HuggingFace Daily Papers included automatically |

The four core directions are selected round-robin with quotas so every direction gets exposure; the daily digest is capped at 25 papers.

### Tracked Blogs

17 feeds, grouped by type. Individual blogs are ordered so prolific authors cannot crowd out the rest (max 5 posts per site per day).

| Type | Sources |
|---|---|
| Labs & institutions | OpenAI, Google DeepMind, Microsoft Research, Apple ML, Hugging Face, NVIDIA Developer, BAIR Berkeley |
| Practitioners | Simon Willison, Lilian Weng, Sebastian Raschka, Eugene Yan, Sander Dieleman, Nathan Lambert (Interconnects), Latent Space, Tim Dettmers, Import AI, Andrej Karpathy |

Adding or removing a source is one line in `BLOG_FEEDS` — see [CONFIG.md](CONFIG.md).

### Daily Pipeline

```
fetch_arxiv → fetch_hf → dedup → score → select_balanced → DeepSeek enhance → Kimi Q&A → Markdown digest → commit to main → Pages update

(feeds) fetch_blog → keyword scoring → DeepSeek Chinese takeaway → blog digest ─┘
```

| Path | Purpose |
|---|---|
| `daily_arxiv/` | Fetchers (arXiv / HF / papers.cool Kimi / blogs) and rule-based scoring |
| `ai/enhance.py` | DeepSeek enhancement (Chinese title / summary / rating) |
| `ai/enhance_blog.py` | DeepSeek Chinese takeaways for blog posts |
| `to_md/convert.py` | Markdown digest generation |
| `index.html` | Web frontend (single file, no external CDN) |
| `data/` | Daily data and digest archive (auto-generated, do not edit) |
| `.github/workflows/run.yml` | Cloud scheduled workflow |

## Install

Clone this repository:

```sh
git clone https://github.com/lililuya/paper_daily.git
```

### Cloud Deployment (GitHub Actions)

1. In **Settings → Secrets and variables → Actions → Secrets**, add:

   | Secret | Description |
   |---|---|
   | `OPENAI_API_KEY` | DeepSeek API key (or any OpenAI-compatible service) |
   | `OPENAI_BASE_URL` | Defaults to `https://api.deepseek.com` |

2. (Optional) Under **Variables**, add:

   | Variable | Default | Description |
   |---|---|---|
   | `MODEL_NAME` | `deepseek-chat` | LLM model name |
   | `MAX_LLM_PAPERS` | `25` | Daily paper cap |

3. Enable Pages: **Settings → Pages → Build and deployment → Source: Deploy from a branch**, choose **main** / `(root)`.

4. The pipeline runs daily at 09:30 Beijing time (01:30 UTC) — right after arXiv publishes the day's new submissions — or trigger it manually via **Actions → Daily Pipeline → Run workflow**.

### Local Run

Requires Python 3.10+, no third-party dependencies:

```sh
python run_pipeline.py --dry-run        # dry run: real fetching + scoring, no LLM calls, no cost
python run_pipeline.py                  # full run: requires the OPENAI_API_KEY env var
python run_pipeline.py --date 2026-09-17 --no-dedup   # re-run a specific date
```

Without an API key it degrades to dry-run mode (rule-based scoring only, no Chinese summaries).

## Configuration

Changing keywords, direction weights, the daily paper cap, or Kimi/DeepSeek parameters is documented in **[CONFIG.md](CONFIG.md)** (in Chinese).

Configuration changes take effect from the next run after being committed to `main`.

## Related Repositories

- [daily-arXiv-ai-enhanced](https://github.com/dw-dengwei/daily-arXiv-ai-enhanced) — the inspiration for this project
- [papers.cool](https://papers.cool/) — source of the Kimi paper deep dives
- [standard-readme](https://github.com/RichardLitt/standard-readme) — the README style this project follows

## Maintainers

[@lililuya](https://github.com/lililuya)

## Contributing

Feel free to open an [issue](https://github.com/lililuya/paper_daily/issues/new) or submit a pull request — e.g. suggesting new keywords, directions, or data sources.

## License

[MIT](LICENSE) © 2026 lililuya
