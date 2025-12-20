# app/core/config.py
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    # --- 基础服务配置 ---
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 23800
    
    # --- 路径配置 (自动转换为绝对路径或保持相对路径) ---
    # 知识库向量数据路径
    LANCEDB_PATH: str = "./data/lancedb"
    # LangGraph 检查点数据库路径
    CHECKPOINT_DB_PATH: str = "./data/checkpoints.db"
    
    # --- 外部依赖配置 ---
    # SearXNG 搜索服务地址
    SEARXNG_BASE_URL: str = "http://localhost:8888/search"
    
    # --- 模型配置 ---
    # 如果 .env 中没有设置，读取系统环境变量；如果都没有，则为 None
    DEEPSEEK_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None

    class Config:
        # 指定加载 .env 文件
        env_file = ".env"
        # 忽略多余的变量
        extra = "ignore"

# 实例化全局配置对象
settings = Settings()

# 自动确保关键数据目录存在 (可选，增强健壮性)
os.makedirs(os.path.dirname(settings.CHECKPOINT_DB_PATH), exist_ok=True)
os.makedirs(settings.LANCEDB_PATH, exist_ok=True)