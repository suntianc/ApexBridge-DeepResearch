# app/core/config.py
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Literal
import os

class Settings(BaseSettings):
    # --- 基础配置 ---
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 23800
    LANCEDB_PATH: str = "./data/lancedb"
    CHECKPOINT_DB_PATH: str = "./data/checkpoints.db"
    
    # --- 搜索配置 (Search Configuration) ---
    # 搜索服务提供商: "tavily" 或 "searxng"
    SEARCH_PROVIDER: Literal["tavily", "searxng"] = "tavily"
    
    # SearXNG 配置
    SEARXNG_BASE_URL: str = "http://localhost:8888/search"
    
    # Tavily 配置 (支持多Key轮询)
    # 在 .env 中配置: TAVILY_API_KEYS="tvly-xxx,tvly-yyy,tvly-zzz"
    TAVILY_API_KEYS: List[str] = []

    @field_validator("TAVILY_API_KEYS", mode="before")
    def parse_api_keys(cls, v):
        if isinstance(v, str):
            # 将逗号分隔的字符串转为列表，并去除空格
            return [key.strip() for key in v.split(",") if key.strip()]
        return v or []

    # --- 模型配置 (保持不变) ---
    DEEPSEEK_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    MAX_RECURSION_LIMIT: int = 100
    GLOBAL_TIMEOUT_SEC: int = 600

    # Phase 4: 分层模型策略
    MODEL_PLANNER: str = "deepseek/deepseek-reasoner"
    MODEL_WRITER: str = "deepseek/deepseek-chat"
    MODEL_CRITIC: str = "deepseek/deepseek-reasoner"
    MODEL_FAST: str = "deepseek/deepseek-chat"
    MODEL_LONG: str = "deepseek/deepseek-chat"
    MODEL_SMART: str = "deepseek/deepseek-reasoner"

    # Embedding 配置
    EMBEDDING_MODEL: str = "ollama/nomic-embed-text"
    EMBEDDING_DIMENSION: int = 768

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

os.makedirs(os.path.dirname(settings.CHECKPOINT_DB_PATH), exist_ok=True)
os.makedirs(settings.LANCEDB_PATH, exist_ok=True)