"""
核心功能模块

包含五大核心模块：
    - orchestrator: 工作流编排器
        使用LangGraph实现状态机和工作流编排
        负责任务调度、流程控制和模块协调

    - perception: 信息感知模块
        负责信息收集和感知
        包括网页抓取(crawler)和搜索引擎(search)能力

    - knowledge: 知识引擎
        负责数据的存储、索引和检索
        包括向量数据库(LanceDB)和关系型数据库(SQLModel)

    - insight: 洞察模块
        负责生成和管理Prompt模板
        为LLM提供结构化的提示词

这些模块协同工作，实现完整的AI驱动研究流程。

使用示例:
    from app.modules import (
        orchestrator,
        perception,
        knowledge,
        insight
    )

作者: ApexBridge Team
版本: 1.0.0
"""

from . import (
    orchestrator,
    perception,
    knowledge,
    insight
)

# 明确列出所有公开的核心模块
__all__ = [
    "orchestrator",
    "perception",
    "knowledge",
    "insight",
]
