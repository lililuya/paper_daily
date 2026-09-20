# 前研追踪配置：抓取类别 + 兴趣方向关键词表

import os

# 抓取的 arXiv 类别
CATEGORIES = ["cs.CL", "cs.LG", "cs.AI", "cs.CV", "cs.DC", "cs.NI", "cs.SE"]

# arXiv 提交日期回看窗口（天）：抓取近 N 天提交的论文，去重模块会过滤历史
ARXIV_LOOKBACK_DAYS = 2

# arXiv API 请求间隔（秒），官方建议 >=3
ARXIV_RATE_LIMIT_SECONDS = 3.0

# 分页大小
ARXIV_PAGE_SIZE = 200

# 兴趣方向 -> 关键词加权表
# 打分规则：关键词命中标题 x3 + 命中摘要 x1，再乘方向权重
INTERESTS = {
    "视频模型": {
        "weight": 5,
        "keywords": [
            "video generation", "video diffusion", "text-to-video", "image-to-video",
            "video synthesis", "video model", "video prediction", "camera control",
            "video editing", "video super-resolution", "world simulator",
            "video tokenizer", "long video generation", "video completion",
        ],
    },
    "图像编辑": {
        "weight": 5,
        "keywords": [
            "image editing", "image edit", "inpainting", "outpainting",
            "image manipulation", "photo editing", "controllable generation",
            "subject-driven", "image composition", "personalized generation",
            "editing direction", "drag-based editing", "reference image",
        ],
    },
    "Agent": {
        "weight": 5,
        "keywords": [
            "LLM agent", "language agent", "multi-agent", "tool use", "tool learning",
            "tool calling", "agentic", "web agent", "GUI agent", "computer use",
            "agent framework", "autonomous agent", "agent training",
            "agent evaluation", "agent memory", "self-improving agent",
        ],
    },
    "大语言模型": {
        "weight": 2,
        "keywords": [
            "LLM", "large language model", "large language models", "reasoning",
            "chain-of-thought", "in-context learning",
            "long context", "instruction tuning", "RLHF", "preference optimization",
            "fine-tuning", "LoRA", "RAG", "retrieval-augmented", "knowledge distillation",
            "mixture-of-experts", "MoE", "test-time", "scaling law",
        ],
    },
    "多模态": {
        "weight": 2,
        "keywords": [
            "multimodal", "multi-modal", "vision-language", "text-to-image",
            "diffusion model", "visual question", "image understanding",
            "video understanding", "visual grounding", "tokenization",
        ],
    },
    "系统与基础设施": {
        "weight": 2,
        "keywords": [
            "distributed training", "inference optimization", "serving system",
            "LLM serving", "GPU", "kernel", "compiler", "scheduler", "scheduling",
            "memory optimization", "parallelism", "datacenter", "cluster",
            "offloading", "speculative decoding", "quantization", "KV cache",
            "long context inference", "network", "RDMA",
        ],
    },
    "数据工程": {
        "weight": 5,
        "keywords": [
            "data curation", "data-centric", "data selection", "data quality",
            "data engineering", "data pipeline", "data cleaning", "data filtering",
            "dataset construction", "dataset creation", "synthetic data",
            "pretraining data", "data mixture", "data attribution",
            "benchmark construction", "data annotation",
        ],
    },
}

# 核心主题（用于日报配额选取，保证每个主题都有足够曝光）
CORE_DIRECTIONS = ["图像编辑", "视频模型", "Agent", "数据工程"]

# 进入 LLM 增强的最低规则分（低于此分的论文直接丢弃）
SCORE_THRESHOLD = 5

# LLM 深度摘要的推荐指数门槛（rating >= 4 生成详细摘要，其余只生成一句话）
DEEP_SUMMARY_RATING = 4

# 每日 LLM 增强的论文数上限（按规则分从高到低取），可用环境变量覆盖
MAX_LLM_PAPERS = int(os.environ.get("MAX_LLM_PAPERS") or 25)

# papers.cool Kimi 摘要抓取配置
# 注意：papers.cool 的 Kimi 生成是串行排队的——未缓存论文要么立刻返回 HTTP 错误
# （服务器忙），要么占住生成位 2-6 分钟。因此需要耐心重试 + 时间预算。
PAPERS_COOL_FETCH = os.environ.get("PAPERS_COOL_FETCH", "1") not in ("0", "false", "False")
PAPERS_COOL_WORKERS = int(os.environ.get("PAPERS_COOL_WORKERS", "2"))
PAPERS_COOL_TIMEOUT = int(os.environ.get("PAPERS_COOL_TIMEOUT", "240"))  # 单篇请求超时（秒）
PAPERS_COOL_RETRIES = int(os.environ.get("PAPERS_COOL_RETRIES", "5"))    # 单篇重试次数（被弹回后等一等再试）
PAPERS_COOL_RETRY_WAIT = int(os.environ.get("PAPERS_COOL_RETRY_WAIT", "20"))  # 重试间隔（秒）
PAPERS_COOL_BUDGET = int(os.environ.get("PAPERS_COOL_BUDGET", "900"))    # 当日抓取时间预算（秒）
PAPERS_COOL_BACKFILL_DAYS = int(os.environ.get("PAPERS_COOL_BACKFILL_DAYS", "2"))  # 每日运行时自动补抓最近 N 天缺失的 Kimi
PAPERS_COOL_BACKFILL_BUDGET = int(os.environ.get("PAPERS_COOL_BACKFILL_BUDGET", "600"))  # 补抓时间预算（秒）

# LLM 配置（可用环境变量覆盖）
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com")
MODEL_NAME = os.environ.get("MODEL_NAME", "deepseek-chat")

# ============ 技术博客 / 大佬文章追踪 ============
# RSS / Atom 源。key 是唯一标识（用于去重与前端筛选），不要随意改动。
BLOG_FEEDS = [
    # ---- 实验室与机构官方博客 ----
    {"key": "openai", "name": "OpenAI", "url": "https://openai.com/blog/rss.xml"},
    {"key": "deepmind", "name": "Google DeepMind", "url": "https://deepmind.google/blog/rss.xml"},
    {"key": "msr", "name": "Microsoft Research", "url": "https://www.microsoft.com/en-us/research/feed/"},
    {"key": "apple", "name": "Apple ML", "url": "https://machinelearning.apple.com/rss.xml"},
    {"key": "hf", "name": "Hugging Face", "url": "https://huggingface.co/blog/feed.xml"},
    {"key": "nvidia", "name": "NVIDIA Developer", "url": "https://developer.nvidia.com/blog/feed"},
    {"key": "bair", "name": "BAIR Berkeley", "url": "https://bair.berkeley.edu/blog/feed.xml"},
    # ---- 个人博客（技术大佬）----
    {"key": "simonwillison", "name": "Simon Willison", "url": "https://simonwillison.net/atom/everything/"},
    {"key": "lilianweng", "name": "Lilian Weng", "url": "https://lilianweng.github.io/index.xml"},
    {"key": "raschka", "name": "Sebastian Raschka", "url": "https://magazine.sebastianraschka.com/feed"},
    {"key": "eugeneyan", "name": "Eugene Yan", "url": "https://eugeneyan.com/rss/"},
    {"key": "sander", "name": "Sander Dieleman", "url": "https://sander.ai/feed.xml"},
    {"key": "interconnects", "name": "Interconnects", "url": "https://www.interconnects.ai/feed"},
    {"key": "latentspace", "name": "Latent Space", "url": "https://www.latent.space/feed"},
    {"key": "dettmers", "name": "Tim Dettmers", "url": "https://timdettmers.com/feed/"},
    {"key": "importai", "name": "Import AI", "url": "https://importai.substack.com/feed"},
    {"key": "karpathy", "name": "Andrej Karpathy", "url": "https://karpathy.github.io/feed.xml"},
]

BLOG_ENABLED = os.environ.get("BLOG_ENABLED", "1") not in ("0", "false", "False")
# 回看窗口：每日运行，7 天足够容错（某天运行失败次日仍能补上），且靠 seen_blogs.json 去重不会重复入选
BLOG_LOOKBACK_DAYS = int(os.environ.get("BLOG_LOOKBACK_DAYS", "7"))
BLOG_MAX_ITEMS = int(os.environ.get("BLOG_MAX_ITEMS", "30"))          # 每日进入 LLM 增强的候选上限
BLOG_MAX_PER_SITE = int(os.environ.get("BLOG_MAX_PER_SITE", "5"))     # 单个源最多入选几篇（防高产博客霸榜）
BLOG_SUMMARY_CHARS = int(os.environ.get("BLOG_SUMMARY_CHARS", "1500"))  # 原文正文截断长度（给 LLM 的输入）
BLOG_FETCH_WORKERS = int(os.environ.get("BLOG_FETCH_WORKERS", "6"))   # 并发抓取源的数量
# 部分源（HuggingFace / DeepMind）的 feed 不带正文，摘要短于此长度时回退抓文章页的 og:description
BLOG_PAGE_SUMMARY_MIN = int(os.environ.get("BLOG_PAGE_SUMMARY_MIN", "80"))
BLOG_PAGE_WORKERS = int(os.environ.get("BLOG_PAGE_WORKERS", "5"))     # 回退抓页面的并发数
BLOG_PAGE_LIMIT = int(os.environ.get("BLOG_PAGE_LIMIT", "25"))        # 单次运行最多回退抓多少篇
# 每源最多读取的条目数（OpenAI 这类全站 feed 有上千条，只取最新的即可）
BLOG_MAX_ENTRIES_PER_FEED = int(os.environ.get("BLOG_MAX_ENTRIES_PER_FEED", "30"))

# 目录（相对仓库根）
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_ROOT, "data")
SEEN_IDS_FILE = os.path.join(DATA_DIR, "seen_ids.json")
FILE_LIST = os.path.join(_ROOT, "assets", "file-list.txt")
SEEN_BLOGS_FILE = os.path.join(DATA_DIR, "seen_blogs.json")
BLOG_LIST = os.path.join(_ROOT, "assets", "blog-list.txt")
