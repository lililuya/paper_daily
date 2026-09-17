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
        "weight": 2,
        "keywords": [
            "data curation", "data-centric", "data selection", "data quality",
            "data engineering", "data pipeline", "data cleaning", "data filtering",
            "dataset construction", "dataset creation", "synthetic data",
            "pretraining data", "data mixture", "data attribution",
            "benchmark construction", "data annotation",
        ],
    },
}

# 三大核心主题（用于日报配额选取，保证每个主题都有足够曝光）
CORE_DIRECTIONS = ["图像编辑", "视频模型", "Agent"]

# 进入 LLM 增强的最低规则分（低于此分的论文直接丢弃）
SCORE_THRESHOLD = 5

# LLM 深度摘要的推荐指数门槛（rating >= 4 生成详细摘要，其余只生成一句话）
DEEP_SUMMARY_RATING = 4

# 每日 LLM 增强的论文数上限（按规则分从高到低取），可用环境变量覆盖
MAX_LLM_PAPERS = int(os.environ.get("MAX_LLM_PAPERS") or 20)

# papers.cool Kimi 摘要抓取配置（每篇约 1-3 分钟，建议并行）
PAPERS_COOL_FETCH = os.environ.get("PAPERS_COOL_FETCH", "1") not in ("0", "false", "False")
PAPERS_COOL_WORKERS = int(os.environ.get("PAPERS_COOL_WORKERS", "2"))
PAPERS_COOL_TIMEOUT = int(os.environ.get("PAPERS_COOL_TIMEOUT", "240"))  # 单篇请求超时（秒）

# LLM 配置（可用环境变量覆盖）
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com")
MODEL_NAME = os.environ.get("MODEL_NAME", "deepseek-chat")

# 目录（相对仓库根）
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
SEEN_IDS_FILE = os.path.join(DATA_DIR, "seen_ids.json")
FILE_LIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "file-list.txt")
