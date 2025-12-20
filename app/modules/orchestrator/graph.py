# app/modules/orchestrator/graph.py

from langgraph.graph import StateGraph, END
from typing import Literal
import json,sqlite3

# 1. 引入同级或跨级模块 (这是关联的关键)
from app.modules.orchestrator.state import ResearchState
from app.modules.perception.search import search_searxng
from app.modules.perception.crawler import crawl_urls
from app.core.llm import simple_llm_call
from app.modules.knowledge.vector import KnowledgeBase
from langgraph.checkpoint.sqlite import SqliteSaver
from app.modules.insight.prompts import ResearchPrompts
from app.core.config import settings

kb = KnowledgeBase()

def log_step(step_name: str, content: dict):
    """
    格式化打印日志，支持中文显示
    """
    print(f"\n🚀 [Step: {step_name}]")
    # 使用 json.dumps 格式化打印，ensure_ascii=False 让中文正常显示
    print(json.dumps(content, indent=2, ensure_ascii=False, default=str))
    print("-" * 50)

# --- 节点逻辑实现 ---

async def node_planner(state: ResearchState):
    """
    [规划者] 动态规划下一步
    """
    iteration = state["iteration_count"]
    gap = state.get("gap_analysis", "无")
    topic = state["topic"]
    
    print(f"--- [Planner] Iteration {iteration} | Gap: {gap[:50]}... ---")

    # 🟢 修改点：使用统一 Prompt
    if iteration == 0:
        prompt = ResearchPrompts.planner_initial(topic)
    else:
        prompt = ResearchPrompts.planner_gap_driven(topic, gap)

    search_query = await simple_llm_call(prompt, model="deepseek/deepseek-chat")
    
    result = {
        "search_queries": [search_query],
        "iteration_count": iteration + 1
    }
    log_step("Planner", result)
    return result

async def node_search_execute(state: ResearchState):
    """
    [执行者] 搜索 -> 爬取 -> 存入向量库
    """
    current_query = state["search_queries"][-1]
    print(f"--- [Search] Executing: {current_query} ---")
    
    search_results = await search_searxng(current_query, num_results=3)
    urls = [item["url"] for item in search_results]
    web_contents = await crawl_urls(urls)
    
    if not web_contents and search_results:
        for item in search_results:
            web_contents.append({
                "url": item["url"],
                "content": item["snippet"],
                "source": "searxng_snippet"
            })

    if web_contents:
        print(f"💾 [Knowledge] Saving {len(web_contents)} docs...")
        kb.add_documents(web_contents)
            
    return {"web_results": web_contents}

async def node_analyst(state: ResearchState):
    """
    [分析师] RAG 检索 -> 深度思考 -> 发现盲点
    """
    print("--- [Analyst] RAG Retrieval & Thinking ---")
    topic = state["topic"]
    
    query = state.get("gap_analysis") or topic
    context = kb.search(query, limit=10)
    
    if not context:
        context = "暂无相关信息，请尝试新的搜索。"

    # 🟢 修改点：使用统一 Prompt
    prompt = ResearchPrompts.analyst_reasoning(topic, context)
    
    # 使用 DeepSeek R1
    response = await simple_llm_call(prompt, model="deepseek/deepseek-reasoner")
    
    # 简单解析逻辑 (保持不变)
    gap = "无"
    draft = response
    if "缺少" in response or "缺乏" in response or "需要" in response:
        gap = "Need more specific data based on analysis." 
        
    result = {
        "draft_report": draft,
        "gap_analysis": gap
    }
    log_step("Analyst", result)
    return result

async def node_publisher(state: ResearchState):
    """
    [出版者] 生成带引用的最终报告
    """
    print("--- [Publisher] Compiling Final Report ---")
    topic = state["topic"]
    
    context = kb.search(topic, limit=20) 
    
    # 🟢 修改点：使用统一 Prompt
    prompt = ResearchPrompts.publisher_final_report(topic, context)
    
    final_report = await simple_llm_call(prompt, model="deepseek/deepseek-reasoner")
    
    return {"final_report": final_report}

def check_sufficiency(state: ResearchState) -> Literal["continue", "publish"]:
    """
    [决策逻辑] 决定继续还是结束
    """
    if state["iteration_count"] >= state["max_iterations"]:
        print("--- [Decision] Max Limit Reached -> Publish ---")
        return "publish"
    
    # 这里的逻辑可以写复杂点，比如判断 gap_analysis 是否为空
    # 为了演示，我们只跑 1 轮就结束
    if state["iteration_count"] < 1: 
        return "continue"
        
    return "publish"

# --- 图谱构建 ---

def build_graph():

    # 1. 初始化 SQLite 连接作为记忆存储
    conn = sqlite3.connect(settings.CHECKPOINT_DB_PATH,check_same_thread=False)
    memory = SqliteSaver(conn)

    workflow = StateGraph(ResearchState)

    # 注册节点
    workflow.add_node("planner", node_planner)
    workflow.add_node("searcher", node_search_execute)
    workflow.add_node("analyst", node_analyst)
    workflow.add_node("publisher", node_publisher)

    # 编排流程
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "searcher")
    workflow.add_edge("searcher", "analyst")
    
    workflow.add_conditional_edges(
        "analyst",
        check_sufficiency,
        {
            "continue": "planner",
            "publish": "publisher"
        }
    )
    
    workflow.add_edge("publisher", END)

    return workflow.compile(checkpointer=memory)