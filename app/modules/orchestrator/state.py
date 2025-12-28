# app/modules/orchestrator/state.py
from typing import List, Dict, TypedDict, Annotated, Optional, Literal
import operator

# --- 基础数据模型 ---

class ResearchStep(TypedDict):
    id: str
    description: str
    status: Literal["pending", "running", "completed", "failed", "skipped"]
    dependencies: List[str]
    result: Optional[str]
    # 🟢 新增：关联的大纲章节 (用于追踪进度)
    related_section: Optional[str]

class ReflectionLog(TypedDict):
    step_name: str
    critique: str
    score: float
    adjustment: str

# --- 核心状态定义 ---

class ResearchState(TypedDict):
    """
    Deep Research V3 核心状态
    """
    # --- 基础信息 ---
    task_id: str
    task: str
    
    # 对齐与结构化层
    clarified_intent: str
    needs_clarification: bool
    clarification_history: List[str]
    
    outline: List[str]
    
    # --- 执行层 ---
    plan: List[ResearchStep]
    
    # 🟢 [核心修复] 补上这个缺失的字段！
    search_queries: List[str] 
    
    # --- 记忆与输出 ---
    knowledge_stats: Annotated[List[str], operator.add] 
    reflection_logs: Annotated[List[ReflectionLog], operator.add]
    iteration_count: int
    max_iterations: int
    
    # --- 中间变量 ---
    topic: str
    draft_report: str
    final_report: str

    # --- 分章节报告 (chunked-section-reporting) ---
    # 文件-章节映射表: { "docs/xxx.md": "1. 市场规模分析", "__general__": "综合报告" }
    file_section_map: Dict[str, str]
    # 分章节草稿: { "1. 市场规模分析": "本章节的内容...", "2. 技术架构": "..." }
    section_drafts: Dict[str, str]
    # 待写章节队列
    pending_sections: List[str]