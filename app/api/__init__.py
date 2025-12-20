"""
API 路由模块

提供RESTful API接口，包括：
    - research: 研究相关API接口
    - history: 历史记录API接口

本模块封装了所有对外暴露的API路由，
通过FastAPI框架实现高效的网络请求处理。

使用示例:
    from app.api import research, history

作者: ApexBridge Team
版本: 1.0.0
"""

from . import research, history

# 明确列出所有公开的子模块
__all__ = [
    "research",
    "history",
]
