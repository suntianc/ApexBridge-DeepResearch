# app/modules/orchestrator/state.py
from typing import List, TypedDict, Annotated
import operator

# 定义一个单一的搜索结果结构
class SearchResult(TypedDict):
    url: str
    content: str  # 清洗后的 Markdown
    source: str   # 来源域名

# 定义 Agent 的全局状态
class ResearchState(TypedDict):
    # 1. 用户输入
    topic: str
    
    # 2. 迭代控制
    iteration_count: int  # 当前递归了多少轮
    max_iterations: int   # 最大允许轮数 (防止死循环)
    
    # 3. 知识积累 (使用 operator.add 实现增量更新，而非覆盖)
    # Annotated[List, operator.add] 意味着每次返回这个字段，都会 append 到列表中
    search_queries: Annotated[List[str], operator.add] 
    web_results: Annotated[List[SearchResult], operator.add]
    
    # 4. 思考与产出
    gap_analysis: str    # 当前还缺什么信息
    draft_report: str    # 草稿
    final_report: str    # 最终产出