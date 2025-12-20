"""
核心配置模块

提供系统核心配置和LLM调用接口。

主要组件:
    - simple_llm_call: 通用LLM调用接口
        支持DeepSeek、OpenAI、Claude、Ollama等多种模型
        通过LiteLLM提供统一的调用方式

使用示例:
    from app.core import simple_llm_call

    response = await simple_llm_call("Hello, world!")

作者: ApexBridge Team
版本: 1.0.0
"""

from .llm import simple_llm_call

__all__ = ["simple_llm_call"]
