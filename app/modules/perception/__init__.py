"""
感知模块 - 信息感知和收集

负责信息的收集、感知和初步处理。

本模块提供多种信息收集能力：
    - 从互联网抓取网页内容
    - 通过搜索引擎获取相关信息
    - 解析和提取关键信息
    - 对收集的数据进行预处理

子模块:
    - crawler: 网页爬虫
        提供智能网页抓取能力
        支持动态内容加载和反爬虫策略

    - search: 搜索引擎
        集成多种搜索引擎API
        提供智能搜索和结果筛选功能

主要功能:
    1. 多源信息收集
    2. 实时网页内容抓取
    3. 智能搜索和结果优化
    4. 数据清洗和预处理
    5. 支持多种数据格式输出

使用示例:
    from app.modules.perception import crawler, search

作者: ApexBridge Team
版本: 1.0.0
"""

from . import crawler, search

# 明确列出所有公开的子模块
__all__ = [
    "crawler",
    "search",
]
