"""
编排器模块 - 工作流编排器

使用LangGraph实现状态机和工作流编排。

本模块负责：
    - 定义和管理复杂的工作流状态
    - 实现任务间的依赖关系和调度
    - 协调各个模块之间的交互
    - 提供可扩展的状态转换逻辑

子模块:
    - graph: 图结构和工作流定义
        包含LangGraph节点和边的定义

    - state: 状态管理
        定义共享状态结构和状态转换逻辑

工作流程:
    1. 初始化工作流状态
    2. 通过graph定义执行路径
    3. 使用state跟踪和管理状态变化
    4. 协调各模块按序执行

使用示例:
    from app.modules.orchestrator import graph, state

作者: ApexBridge Team
版本: 1.0.0
"""

from . import graph, state

# 的子明确列出所有公开模块
__all__ = [
    "graph",
    "state",
]
