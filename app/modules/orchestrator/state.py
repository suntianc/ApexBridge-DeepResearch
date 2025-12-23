from typing import List, TypedDict, Annotated, Optional, Literal, Union
import operator

# --- 1. 基础数据模型 (Sub-models) ---

class ResearchStep(TypedDict):
    """
    单步研究计划 (DAG 节点)
    用于 Plan-and-Solve 策略，支持任务分解
    """
    id: str                 # 步骤ID (e.g., "step_1")
    description: str        # 步骤描述 (e.g., "搜索2024年全球AI市场规模数据")
    status: Literal["pending", "running", "completed", "failed"] 
    dependencies: List[str] # 依赖的前置步骤ID (支持 DAG)
    result: Optional[str]   # 该步骤的执行结果摘要

class ContextNode(TypedDict):
    """
    知识图谱节点
    比纯文本更结构化，便于后续的引用和冲突消解
    """
    id: str                 # 唯一ID
    content: str            # 核心事实片段
    source_url: str         # 来源
    type: Literal["fact", "data", "opinion", "snippet"] # 知识类型
    confidence: float       # 置信度 (0.0 - 1.0)

class ReflectionLog(TypedDict):
    """
    反思日志
    用于 Reflexion 机制，记录 Critic 的评价
    """
    step_name: str          # 在哪个环节产生的反思
    critique: str           # 批评意见
    score: float            # 评分 (0-10)
    adjustment: str         # 具体的改进措施 (e.g., "下次搜索需要添加'PDF'关键词")

# (保留) 旧的搜索结果结构，用于兼容 crawler.py
class SearchResult(TypedDict):
    url: str
    content: str
    source: str

# --- 2. 核心状态定义 (Main State) ---

class ResearchState(TypedDict):
    """
    Deep Research V2 核心状态 (清理版)
    """
    # --- 核心维度 ---
    task_id: str
    task: str
    clarified_intent: str
    plan: List[ResearchStep]
    knowledge_graph: Annotated[List[ContextNode], operator.add]
    reflection_logs: Annotated[List[ReflectionLog], operator.add]
    iteration_count: int
    max_iterations: int
    
    # --- 必需的中间变量 ---
    topic: str              # TODO: 未来将 graph.py 中的 state["topic"] 替换为 state["task"] 后删除
    draft_report: str
    final_report: str
    
    # --- 这里的 Annotated 列表如果不初始化 inputs，LangGraph 会自动处理为空列表
    # 但为了代码清晰，建议保留定义，但在 api 中可以不传
    web_results: Annotated[List[dict], operator.add] 
    search_queries: Annotated[List[str], operator.add]