"""
Deep Research Backend - 核心应用包

这是一个基于AI的深度研究系统，提供智能信息收集、分析和洞察能力。
主要功能包括：工作流编排、信息感知、知识管理和洞察生成。

主要模块:
    - api: API路由和接口
    - modules: 核心功能模块集合
        - orchestrator: 工作流编排器
        - perception: 信息感知和收集
        - knowledge: 知识存储和检索
        - insight: 洞察生成

使用说明:
    # 导入API模块
    from app.api import research, history

    # 导入核心功能模块
    from app.modules import orchestrator, perception, knowledge, insight

    # 导入LLM调用接口
    from app.core import simple_llm_call

作者: ApexBridge Team
版本: 1.0.0
许可证: MIT
"""

__version__ = "1.0.0"
__author__ = "ApexBridge Team"
__email__ = "team@apexbridge.ai"
__license__ = "MIT"
__description__ = "基于AI的深度研究系统"


__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    "__description__",
]
