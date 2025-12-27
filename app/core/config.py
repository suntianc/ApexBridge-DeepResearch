# app/core/config.py
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Union, Any
import os

class Settings(BaseSettings):
    # --- 基础配置 ---
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 23800
    
    # 🟢 新增：任务文件存储根目录
    TASK_STORAGE_DIR: str = "./data/tasks"
    
    # 状态检查点 (保持 SQLite 以管理状态机)
    CHECKPOINT_DB_PATH: str = "./data/checkpoints.db"
    
    # 报告输出
    SAVE_REPORT_TO_FILE: bool = True
    REPORT_OUTPUT_DIR: str = "./outputs"

    # --- 搜索配置 ---
    SEARCH_PROVIDER: str = "tavily"
    TAVILY_API_KEYS: Union[str, List[str]] = []

    @field_validator("TAVILY_API_KEYS", mode="before")
    @classmethod
    def parse_api_keys(cls, v: Any) -> List[str]:
        if isinstance(v, str) and not v.strip().startswith("["):
            return [k.strip() for k in v.split(",") if k.strip()]
        return v or []

    # 深度研究建议设为 5-10，因为我们有 OCR 了，能处理更多资料
    MAX_SEARCH_RESULTS: int = 6 

    # --- 模型配置 ---
    DEEPSEEK_API_KEY: str | None = None
    GLOBAL_TIMEOUT_SEC: int = 1200

    # 🟢 简化为两类模型配置
    # 用于推理任务 (Planner, Critic, MAD Debate)
    MODEL_REASONING: str = "deepseek/deepseek-reasoner"
    # 用于生成任务 (Writer, Fast, Long context)
    MODEL_CHAT: str = "deepseek/deepseek-chat"

    # --- 高级配置 ---
    MAX_RECURSION_LIMIT: int = 25

    # 🟢 垂直搜索配置
    GITHUB_TOKEN: str | None = None # 强烈建议配置，否则每小时只能调 60 次
    
    ENABLE_ARXIV: bool = True
    ENABLE_GITHUB: bool = True
    ENABLE_WIKI: bool = True
    
    # 混合搜索权重
    Result_Count_Arxiv: int = 3
    Result_Count_Github: int = 3
    Result_Count_Wiki: int = 2
    Result_Count_Web: int = 3

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

os.makedirs(os.path.dirname(settings.CHECKPOINT_DB_PATH), exist_ok=True)
os.makedirs(settings.TASK_STORAGE_DIR, exist_ok=True)
if settings.SAVE_REPORT_TO_FILE:
    os.makedirs(settings.REPORT_OUTPUT_DIR, exist_ok=True)