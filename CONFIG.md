# 前研日报 · 配置与运维手册

本手册说明系统所有可配置项，以及「想改某个东西时该动哪个文件」。不需要懂代码也能照着改。

## 一、系统全貌

```
每日自动流程（GitHub Actions，默认北京时间 23:00）
  ┌─ 1. 抓取 arXiv（按类别+近2天） + HuggingFace Daily Papers
  ├─ 2. 去重（seen_ids.json 记录历史论文 ID）
  ├─ 3. 规则打分（关键词加权，筛选出候选）
  ├─ 4. DeepSeek 增强（中文标题/摘要/推荐指数，约 25 篇）
  ├─ 5. 抓取 papers.cool 的 Kimi 深度解读（Q&A）
  ├─ 6. 生成 data/日期.md 日报 + data/日期.jsonl 数据
  └─ 7. 自动提交回 GitHub → Pages 网站更新
```

| 文件 | 作用 | 改它的场景 |
|---|---|---|
| `daily_arxiv/config.py` | **核心配置**：类别、方向关键词、篇数、抓取参数 | 想改追踪方向/关键词/每日篇数 |
| `daily_arxiv/fetch_arxiv.py` | arXiv API 抓取（含 curl 回退） | 一般不动 |
| `daily_arxiv/fetch_hf.py` | HF Daily Papers 抓取 | 一般不动 |
| `daily_arxiv/fetch_kimi.py` | papers.cool Kimi 解读抓取 | 调并发/超时 |
| `daily_arxiv/score.py` | 规则打分 + 核心方向配额 | 一般不动 |
| `ai/enhance.py` | DeepSeek 调用与提示词 | 改 AI 摘要的输出格式/口吻 |
| `to_md/convert.py` | Markdown 日报模板 | 改日报的排版结构 |
| `index.html` | 网页前端（单文件，无依赖） | 改网站样式/交互 |
| `.github/workflows/run.yml` | 定时任务与云端执行 | 改运行时间 |
| `data/` | 每日数据与日报存档 | 不手改，自动生成 |

## 二、改关键词 / 方向（最常用）

所有追踪方向都在 `daily_arxiv/config.py` 的 `INTERESTS` 字典里：

```python
INTERESTS = {
    "视频模型": {                        # 方向名（会显示为标签）
        "weight": 5,                    # 权重：5=核心方向，2=次级方向
        "keywords": [                   # 英文关键词（匹配标题+摘要，不分大小写）
            "video generation", "video diffusion", "text-to-video",
            ...
        ],
    },
    ...
}
```

**打分规则**：关键词命中标题 ×3 + 命中摘要 ×1（单关键词在摘要中最多计 2 次），求和后乘方向权重。总分低于 `SCORE_THRESHOLD`(5) 的论文直接丢弃。

### 常见操作

**① 加关键词**：在对应方向的 `keywords` 列表里加一行英文词组，比如给「数据工程」加 `data wrangling`：

```python
    "数据工程": {
        "weight": 5,
        "keywords": [
            "data curation", "data-centric", ..., "data wrangling",  # ← 新加
        ],
    },
```

**② 加新方向**：仿照现有格式加一段（weight 2 为次级、5 为核心）。注意：weight 5 的方向会进入 `CORE_DIRECTIONS` 配额轮询（见下）。

**③ 删方向**：删掉整段即可。

**④ 注意事项**：
- 关键词写**英文小写**短语，不要写单词级的泛词（如 `agent`、`model`、`data`），会造成大量误报
- 一个方向要「成立」需：标题命中过关键词，或摘要累计命中 ≥3 次
- 新方向加了 `tags` 后，日报分组顺序在 `to_md/convert.py` 的 `DIRECTION_ORDER` 里同步加一下

## 三、核心方向配额

```python
CORE_DIRECTIONS = ["图像编辑", "视频模型", "Agent", "数据工程"]
```

选每日精选时，这些核心方向**轮流取**，防止某一个方向（如 Agent 论文量大）霸榜、小众方向（如图像编辑）被挤掉。想把某方向提升为核心，把它加进这个列表并把 `INTERESTS` 里的 weight 改成 5。

## 四、每日篇数与门槛

```python
SCORE_THRESHOLD = 5        # 最低规则分，低于此分丢弃（调高→更挑剔，调低→更全）
MAX_LLM_PAPERS = 25       # 每日精选篇数上限（觉得多/少就改这个）
DEEP_SUMMARY_RATING = 4   # 推荐指数 ≥4 的论文才生成详细中文摘要
```

**同日重跑是合并、不是覆盖**：某天已生成过日报后再次运行（手动 Run workflow、或本地重跑同一天），已有条目会原样保留（沿用其 LLM 增强与 Kimi 解读，不重复花 token），新论文按分数并入，总数不超过 `MAX_LLM_PAPERS`。

## 五、抓取范围

```python
CATEGORIES = ["cs.CL", "cs.LG", "cs.AI", "cs.CV", "cs.DC", "cs.NI", "cs.SE"]
ARXIV_LOOKBACK_DAYS = 2    # 回看窗口，一般不用动
```

常用类别参考：`cs.RO`（机器人）、`cs.IR`（信息检索）、`cs.CR`（安全）、`stat.ML`（统计ML）、`eess.IV`（图像处理）。

## 六、Kimi 深度解读抓取

```python
PAPERS_COOL_FETCH = True        # 设环境变量 PAPERS_COOL_FETCH=0 可关闭
PAPERS_COOL_WORKERS = 2         # 并发数，不要超过 2（papers.cool 会限流）
PAPERS_COOL_TIMEOUT = 240       # 单篇请求超时（秒）
PAPERS_COOL_RETRIES = 5         # 单篇重试次数（被弹回后等 20s 再试）
PAPERS_COOL_BUDGET = 900        # 当日 Kimi 抓取总预算（秒），用尽即止
PAPERS_COOL_BACKFILL_DAYS = 2   # 每日运行后自动补抓最近 N 天缺失的 Kimi
PAPERS_COOL_BACKFILL_BUDGET = 600  # 补抓总预算（秒）
```

**papers.cool 的 Kimi 生成是串行排队的**：未缓存的论文要么立刻被弹回（HTTP 错误，服务器忙），要么占住生成位 2-6 分钟。所以当日抓不完是常态——每日运行会自动回头补最近 2 天缺失的（已缓存的秒回），覆盖率逐步补齐。也可手动补：Actions → Run workflow，参数填 `--backfill-kimi 2026-09-18`（逗号可分隔多天）。

## 七、DeepSeek / LLM 配置

云端在 GitHub 仓库 **Settings → Secrets and variables → Actions** 配置：

| Secret 名 | 值 |
|---|---|
| `OPENAI_API_KEY` | DeepSeek API Key |
| `OPENAI_BASE_URL` | `https://api.deepseek.com` |
| `MODEL_NAME` | `deepseek-chat`（可选，默认即此） |

本地跑完整版：设置环境变量 `OPENAI_API_KEY` 后运行（见下节）。没配 Key 时自动降级为 dry-run（无中文摘要，仅规则打分）。

## 八、运行方式与生效时间

**云端自动**：每天北京时间 23:00（cron 在 `.github/workflows/run.yml`，改 `cron: "0 15 * * *"` 的 UTC 时间，北京时间 = UTC+8）。

**云端手动**：仓库 → Actions → Daily Pipeline → Run workflow，可选填参数（如 `--no-dedup`）。

**本地运行**（项目目录下）：

```bash
# 试跑：真实抓取，不调 LLM、不花钱
python run_pipeline.py --dry-run

# 试跑且忽略去重（重复生成今天的数据）
python run_pipeline.py --dry-run --no-dedup

# 完整版：需要 OPENAI_API_KEY 环境变量
python run_pipeline.py

# 重跑指定日期
python run_pipeline.py --date 2026-09-17 --no-dedup
```

**改了配置后如何生效**：

1. 改 `daily_arxiv/config.py` 等文件
2. 提交并推送到 GitHub `main` 分支（本地项目目录内 `git add -A && git commit -m "..." && git push`）
3. **当天数据不会变**——新配置从下一次运行生效（第二天 23:00，或立刻到 Actions 页面手动 Run workflow）

## 九、网页前端说明

- `index.html` 是无依赖单文件；KaTeX 公式渲染库已打包在 `assets/katex/`（勿删）
- 「重点阅读」标记存在**浏览器本地**（localStorage）：换浏览器/设备不同步，清浏览器缓存会丢失
- 数据文件在 `data/日期.jsonl`，网站按 `assets/file-list.txt` 列出的日期加载

## 十、常见问题

| 问题 | 处理 |
|---|---|
| 今天某篇论文没被选进来 | 看它关键词命中：本地 `python run_pipeline.py --dry-run` 看打分日志；不中就在 config.py 加关键词 |
| 想重看昨天的日报 | 网页顶部日期下拉选择；或仓库 `data/` 目录 |
| Actions 运行失败 | Actions 页面点进失败的 run 看日志；arXiv 偶发限流会自动重试 |
| 想暂时停掉每日任务 | `.github/workflows/run.yml` 里注释掉 `schedule:` 段，或 Settings → Actions 禁用 |
| 网页改了不生效 | Ctrl+F5 强刷（GitHub Pages 有约 10 分钟缓存） |
