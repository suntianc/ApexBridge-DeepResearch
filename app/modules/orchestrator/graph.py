# app/modules/orchestrator/graph.py

from langgraph.graph import StateGraph, END
import sqlite3
import json
import re
import asyncio 
import numpy as np

from app.core.config import settings
from app.modules.orchestrator.state import ResearchState, ReflectionLog
from app.modules.orchestrator.dag import DAGManager, TaskStatus
from app.modules.perception.search import search_generic as search_tool
from app.modules.perception.crawler import crawl_urls
from app.core.llm import simple_llm_call
from app.modules.knowledge.vector import KnowledgeBase, get_embedding
from app.modules.insight.prompts import ResearchPrompts
from app.modules.verification.verification_agent import VerificationAgent
from app.modules.utils.file_utils import save_markdown_report

kb = KnowledgeBase()

def parse_score(score_val) -> float:
    """从 '8', '8.5', '8/10', 'Score: 8' 等格式中提取浮点数"""
    if isinstance(score_val, (int, float)):
        return float(score_val)
    
    s = str(score_val).strip()
    # 尝试匹配数字部分 (例如从 "4.5/10" 提取 "4.5")
    match = re.search(r"(\d+(\.\d+)?)", s)
    if match:
        try:
            val = float(match.group(1))
            # 防止提取到分母 (比如把 10 当成分数)，通常分数不会超过 10
            # 如果提取到的数字 > 10 (例如 90分制)，归一化到 10分制
            if val > 10: 
                return val / 10.0
            return val
        except:
            return 5.0 # 默认中位数
    return 0.0

def log_step(step_name: str, content: dict):
    """格式化打印日志"""
    print(f"\n🚀 [Step: {step_name}]")
    log_content = content.copy()
    if "plan" in log_content:
        log_content["plan"] = f"[DAG with {len(log_content['plan'])} tasks]"
    print(json.dumps(log_content, indent=2, ensure_ascii=False, default=str))
    print("-" * 50)

def parse_critic_json(text: str) -> dict:
    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(text)
    except:
        return {"score": 5, "critique": "解析失败", "adjustment": "请补充数据"}

def parse_dag_json(text: str) -> list:
    try:
        clean_text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except:
        print(f"❌ JSON Parse Error in DAG: {text[:100]}...")
        return []

def cosine_similarity(v1, v2):
    if not v1 or not v2: return 0.0
    vec1 = np.array(v1)
    vec2 = np.array(v2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0: return 0.0
    return np.dot(vec1, vec2) / (norm1 * norm2)

# --- 节点逻辑 ---

async def node_planner(state: ResearchState):
    """[规划者] 集成语义去重熔断机制"""
    print(f"--- [Planner] Scheduling Tasks (Model: {settings.MODEL_PLANNER}) ---")
    dag = DAGManager(state["plan"])
    model_to_use = settings.MODEL_PLANNER
    
    # 1. 准备历史任务向量
    history_descriptions = [
        t.description for t in dag.tasks.values() 
        if t.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED]
    ]
    history_vecs = []
    if history_descriptions:
        print(f"🧠 [Soft Limits] Loading vectors for {len(history_descriptions)} past tasks...")
        history_vecs = [get_embedding(desc) for desc in history_descriptions]

    def filter_duplicate_tasks(new_tasks_list):
        unique_tasks = []
        for task in new_tasks_list:
            desc = task.get("description", "")
            if not desc: continue
            if not history_vecs:
                unique_tasks.append(task)
                continue
            new_vec = get_embedding(desc)
            is_duplicate = False
            for idx, h_vec in enumerate(history_vecs):
                sim = cosine_similarity(new_vec, h_vec)
                if sim > 0.85:
                    print(f"🛑 [Circuit Breaker] Semantic Loop Detected (Sim: {sim:.2f})!")
                    print(f"   Rejected Task: {desc}")
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_tasks.append(task)
        return unique_tasks

    has_feedback = False
    new_tasks_raw = []

    if state["reflection_logs"]:
        last_log = state["reflection_logs"][-1]
        if last_log["score"] < 8.0:
            print(f"🔄 [Planner] Handling Critique: {last_log['critique'][:50]}...")
            has_feedback = True
            feedback_str = f"批评: {last_log['critique']}\n建议: {last_log['adjustment']}"
            existing_plan_str = json.dumps(dag.to_state(), ensure_ascii=False)
            prompt = ResearchPrompts.planner_dag_replanning(state["task"], existing_plan_str, feedback_str)
            response = await simple_llm_call(prompt, model=model_to_use)
            new_tasks_raw = parse_dag_json(response)

    if not dag.tasks and not has_feedback:
        print("📝 [Planner] Generating initial DAG plan...")
        prompt = ResearchPrompts.planner_dag_generation(state["task"])
        response = await simple_llm_call(prompt, model=model_to_use)
        new_tasks_raw = parse_dag_json(response)

    if new_tasks_raw:
        print(f"🔍 [Soft Limits] Checking {len(new_tasks_raw)} new tasks for semantic loops...")
        final_tasks = filter_duplicate_tasks(new_tasks_raw)
        if len(final_tasks) < len(new_tasks_raw):
            print(f"🛡️ [Soft Limits] Filtered out {len(new_tasks_raw) - len(final_tasks)} redundant tasks.")
        for t in final_tasks:
            try:
                dag.add_task(t["id"], t["description"], t.get("dependencies", []))
            except ValueError as e:
                print(f"⚠️ Add task error: {e}")
    else:
        if has_feedback:
            print("⚠️ [Planner] No new valid tasks generated after feedback.")

    ready_tasks = dag.get_ready_tasks()
    current_queries = []
    for t in ready_tasks:
        dag.set_task_running(t.id)
        current_queries.append(t.description)
    
    if current_queries:
        print(f"🚀 [Planner] Dispatching {len(current_queries)} tasks")
    else:
        print(f"💤 [Planner] No ready tasks.")

    result = {"plan": dag.to_state(), "search_queries": current_queries}
    log_step("Planner", result)
    return result

async def node_search_execute(state: ResearchState):
    """[执行者] 鲁棒性增强版"""
    dag = DAGManager(state["plan"])
    running_tasks = [t for t in dag.tasks.values() if t.status == TaskStatus.RUNNING]
    
    if not running_tasks:
        return {}

    print(f"--- [Search] Parallel Execution: {len(running_tasks)} tasks ---")
    
    search_coros = []
    for t in running_tasks:
        async def safe_search(task_id, query):
            try:
                return await search_tool(query, settings.MAX_SEARCH_RESULTS)
            except Exception as e:
                print(f"❌ Task {task_id} hard failed: {e}")
                return e 
        search_coros.append(safe_search(t.id, t.description))

    search_results_list = await asyncio.gather(*search_coros)
    
    crawl_coros = []
    for res in search_results_list:
        if isinstance(res, list) and res:
            urls = [item["url"] for item in res]
            crawl_coros.append(crawl_urls(urls))
        else:
            crawl_coros.append(asyncio.sleep(0))
            
    if crawl_coros:
        crawl_results_list = await asyncio.gather(*crawl_coros)
    else:
        crawl_results_list = [[] for _ in running_tasks]

    all_new_docs = []
    for i, task in enumerate(running_tasks):
        search_res = search_results_list[i]
        if isinstance(search_res, Exception):
            dag.fail_task(task.id, str(search_res))
            continue
            
        crawl_res = crawl_results_list[i] if i < len(crawl_results_list) else []
        if isinstance(crawl_res, int): crawl_res = []

        if crawl_res:
            all_new_docs.extend(crawl_res)
            dag.complete_task(task.id, result=f"Scraped {len(crawl_res)} pages.")
        else:
            dag.complete_task(task.id, result="No content found.")

    if all_new_docs:
        kb.add_documents(all_new_docs, task_id=state["task_id"])
    
    dag.get_ready_tasks() 

    return {"plan": dag.to_state(), "web_results": all_new_docs}

async def node_analyst(state: ResearchState):
    """[分析师] 使用写作模型 (MODEL_WRITER)"""
    print(f"--- [Analyst] Thinking (Model: {settings.MODEL_WRITER}) ---")
    topic = state["topic"]
    model_to_use = settings.MODEL_WRITER
    
    query = topic
    if state["reflection_logs"]:
        query += f" {state['reflection_logs'][-1]['adjustment']}"

    context = kb.search(query, task_id=state["task_id"], limit=15)

    # 🟢 鲁棒性增强：处理空搜索结果
    # 防止 Prompt 接收空字符串导致幻觉
    if not context or len(context.strip()) < 10:
        print("⚠️ [Analyst] No valid context found in KnowledgeBase.")
        context = (
            "【系统警告】：本轮搜索未能获取有效互联网数据（可能是由于反爬虫限制或网络问题）。"
            "请在报告中明确告知用户：'由于无法连接外部数据源，以下分析仅基于常识和逻辑推演，可能缺乏实时数据支撑。'"
        )

    prompt = ResearchPrompts.analyst_reasoning(topic, context)
    
    raw_draft = await simple_llm_call(prompt, model=model_to_use)
    
    print("🛡️ [Analyst] Running Fact Verification...")
    verified_draft = await VerificationAgent.verify_report(raw_draft)
    
    result = {"draft_report": verified_draft}
    log_step("Analyst", result)
    return result

async def node_critic(state: ResearchState):
    """[批评家] 使用批判模型 (MODEL_CRITIC)"""
    print(f"--- [Critic] Reviewing (Model: {settings.MODEL_CRITIC}) ---")
    topic = state["topic"]
    draft = state["draft_report"]
    model_to_use = settings.MODEL_CRITIC
    
    prompt = ResearchPrompts.critic_evaluation(topic, draft)
    response = await simple_llm_call(prompt, model=model_to_use)
    eval_data = parse_critic_json(response)
    score_raw = eval_data.get("score", 0)
    score = parse_score(score_raw)
    
    log: ReflectionLog = {
        "step_name": f"Iter-{state['iteration_count']}",
        "critique": eval_data.get("critique", ""),
        "score": score,
        "adjustment": eval_data.get("adjustment", "")
    }
    
    result = {"reflection_logs": [log]}
    log_step("Critic", result)
    return result

async def node_publisher(state: ResearchState):
    """[出版者] 使用写作模型 (MODEL_WRITER)"""
    print(f"--- [Publisher] (Model: {settings.MODEL_WRITER}) ---")
    topic = state["topic"]
    context = kb.search(topic, task_id=state["task_id"], limit=30) 
    model_to_use = settings.MODEL_WRITER
    
    prompt = ResearchPrompts.publisher_final_report(topic, context)
    final_report = await simple_llm_call(prompt, model=model_to_use)
    save_markdown_report(topic, final_report)
    kb.clear_task_data(state["task_id"])
    return {"final_report": final_report}

# --- 路由逻辑 ---
def route_planner(state: ResearchState) -> str:
    dag = DAGManager(state["plan"])
    running_tasks = [t for t in dag.tasks.values() if t.status == TaskStatus.RUNNING]
    if running_tasks: return "searcher"
    elif dag.is_all_completed(): return "analyst"
    else: 
        print("⚠️ [Router] No tasks running but DAG not complete. Moving to Analyst.")
        return "analyst"

def route_critic(state: ResearchState) -> str:
    if state["iteration_count"] >= state["max_iterations"]: return "publish"
    last_log = state["reflection_logs"][-1]
    if last_log["score"] >= 8.0: return "publish"
    else: return "planner"

def build_graph():
    workflow = StateGraph(ResearchState)
    workflow.add_node("planner", node_planner)
    workflow.add_node("searcher", node_search_execute)
    workflow.add_node("analyst", node_analyst)
    workflow.add_node("critic", node_critic)
    workflow.add_node("publisher", node_publisher)
    
    workflow.set_entry_point("planner")
    workflow.add_conditional_edges("planner", route_planner, {"searcher": "searcher", "analyst": "analyst"})
    workflow.add_edge("searcher", "planner")
    workflow.add_edge("analyst", "critic")
    workflow.add_conditional_edges("critic", route_critic, {"planner": "planner", "publish": "publisher"})
    workflow.add_edge("publisher", END)

    return workflow