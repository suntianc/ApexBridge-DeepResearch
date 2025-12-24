# app/core/config.py
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Literal, Union, Any
import os

class Settings(BaseSettings):
    # --- 基础配置 ---
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 23800
    LANCEDB_PATH: str = "./data/lancedb"
    CHECKPOINT_DB_PATH: str = "./data/checkpoints.db"
    
    # 报告输出配置
    SAVE_REPORT_TO_FILE: bool = True
    REPORT_OUTPUT_DIR: str = "./outputs"

    # --- 搜索配置 ---
    SEARCH_PROVIDER: Literal["tavily", "searxng"] = "tavily"
    
    # 🔴 核心修改：定义为 Union[str, List[str]]
    # 这样 .env 中的 "key1,key2" 会先被作为 str 接收，不会触发 JSON 解析错误
    TAVILY_API_KEYS: Union[str, List[str]] = []

    @field_validator("TAVILY_API_KEYS", mode="before")
    @classmethod
    def parse_api_keys(cls, v: Any) -> List[str]:
        # 1. 如果接收到的是字符串（来自 .env）
        if isinstance(v, str):
            # 如果不是 JSON 格式（不以 [ 开头），则按逗号分割
            if not v.strip().startswith("["):
                return [key.strip() for key in v.split(",") if key.strip()]
        
        # 2. 如果本来就是列表（代码中赋值），或者其他情况，直接返回
        return v or []
    # 搜索深度
    MAX_SEARCH_RESULTS: int = 5

    # --- 模型配置 ---
    DEEPSEEK_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    MAX_RECURSION_LIMIT: int = 100
    GLOBAL_TIMEOUT_SEC: int = 600

    MODEL_PLANNER: str = "deepseek/deepseek-reasoner"
    MODEL_WRITER: str = "deepseek/deepseek-chat"
    MODEL_CRITIC: str = "deepseek/deepseek-reasoner"
    MODEL_FAST: str = "deepseek/deepseek-chat"
    MODEL_LONG: str = "deepseek/deepseek-chat"
    MODEL_SMART: str = "deepseek/deepseek-reasoner"

    EMBEDDING_MODEL: str = "ollama/nomic-embed-text"
    EMBEDDING_DIMENSION: int = 768

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# 目录初始化逻辑
os.makedirs(os.path.dirname(settings.CHECKPOINT_DB_PATH), exist_ok=True)
os.makedirs(settings.LANCEDB_PATH, exist_ok=True)
if settings.SAVE_REPORT_TO_FILE:
    os.makedirs(settings.REPORT_OUTPUT_DIR, exist_ok=True)