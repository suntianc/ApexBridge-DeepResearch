# app/modules/orchestrator/graph.py

from langgraph.graph import StateGraph, END
import json,os

from app.core.config import settings
from app.core.utils import parse_json_safe
from app.modules.orchestrator.state import ResearchState
from app.modules.orchestrator.dag import DAGManager, TaskStatus
from app.modules.perception.search import search_generic as search_tool
from app.modules.perception.crawler import crawl_urls
from app.core.llm import simple_llm_call
# 引入新的文件存储
from app.modules.knowledge.file_store import FileKnowledgeStore
from app.modules.insight.prompts import prompts
from app.modules.verification.verification_agent import VerificationAgent
from app.modules.utils.file_utils import save_markdown_report

# 初始化文件存储
kb = FileKnowledgeStore()

# --- 辅助函数 ---

def log_step(step_name: str, content: dict):
    print(f"\n🚀 [Step: {step_name}]")
    try:
        text = json.dumps(content, indent=2, ensure_ascii=False, default=str)
        if len(text) > 2000:
            print(text[:2000] + "\n... (truncated)")
        else:
            print(text)
    except:
        print(str(content)[:2000])
    print("-" * 50)

# --- 节点逻辑 ---

async def node_clarifier(state: ResearchState):
    print("--- [Clarifier] Checking Ambiguity ---")
    if state.get("clarified_intent"): return {}
    prompt = prompts.clarification_check(state["task"])
    response = await simple_llm_call(prompt, model=settings.MODEL_REASONING)
    result = parse_json_safe(response)
    
    if result and not result.get("is_clear", True):
        assumptions = result.get("assumptions", "Default assumptions")
        questions = result.get("questions", [])
        print(f"⚠️ Ambiguity Detected: {questions}")
        print(f"🤖 Auto-resolving: {assumptions}")
        new_intent = f"{state['task']} (Context: {assumptions})"
        return {"needs_clarification": True, "clarified_intent": new_intent, "clarification_history": questions}
    return {"needs_clarification": False, "clarified_intent": state["task"]}

async def node_planner(state: ResearchState):
    print(f"--- [Planner] (Model: {settings.MODEL_REASONING}) ---")
    dag = DAGManager(state["plan"])
    model_to_use = settings.MODEL_REASONING
    intent = state.get("clarified_intent", state["task"])
    
    # 1. 大纲生成
    current_outline = state.get("outline", [])
    if not current_outline:
        print("📝 [Planner] Generating Research Outline...")
        outline_resp = await simple_llm_call(prompts.outline_generation(state["task"], intent), model=model_to_use)
        current_outline = parse_json_safe(outline_resp) or []
        print(f"📑 Outline: {current_outline}")
    
    # 2. 任务生成
    has_feedback = False
    if state["reflection_logs"]:
        last_log = state["reflection_logs"][-1]
        if last_log.get("score", 0) < 8.0:
            print(f"🔄 [Planner] Replanning based on critique...")
            has_feedback = True
            feedback_str = f"批评: {last_log.get('critique')}\n建议: {last_log.get('adjustment')}"
            plan_str = json.dumps(dag.to_state(), ensure_ascii=False)
            resp = await simple_llm_call(prompts.planner_dag_replanning(intent, plan_str, feedback_str), model=model_to_use)
            new_tasks = parse_json_safe(resp) or []
            # 防御性处理
            if isinstance(new_tasks, list):
                for t in new_tasks:
                    if isinstance(t, dict) and "id" in t and "description" in t:
                        dag.add_task(t["id"], t["description"], t.get("dependencies", []))
    
    if not dag.tasks and not has_feedback:
        print("📝 [Planner] Generating Tasks from Outline...")
        plan_str = json.dumps(dag.to_state(), ensure_ascii=False)
        resp = await simple_llm_call(prompts.planner_tasks_from_outline(intent, current_outline, plan_str), model=model_to_use)
        new_tasks = parse_json_safe(resp) or []

        # 防御性处理：确保 new_tasks 是字典列表
        if isinstance(new_tasks, list):
            valid_tasks = []
            for t in new_tasks:
                if isinstance(t, dict) and "id" in t and "description" in t:
                    valid_tasks.append(t)
                else:
                    print(f"⚠️ [Planner] Skipping invalid task format: {t}")
            for t in valid_tasks:
                dag.add_task(t["id"], t["description"], dependencies=t.get("dependencies", []), related_section=t.get("related_section"))
            
    ready_tasks = dag.get_ready_tasks()
    current_queries = [t.description for t in ready_tasks]
    for t in ready_tasks: dag.set_task_running(t.id)
    
    log_step("Planner", {"outline": current_outline, "plan": dag.to_state()})
    return {"outline": current_outline, "plan": dag.to_state(), "search_queries": current_queries}

async def node_search_execute(state: ResearchState):
    print("🔄 [Search Node] Entered...", flush=True)
    dag = DAGManager(state["plan"])
    running_tasks = [t for t in dag.tasks.values() if t.status == TaskStatus.RUNNING]
    
    if not running_tasks:
        print("⚠️ [Search Node] No running tasks found!")
        return {}

    print(f"--- [Search] Processing {len(running_tasks)} tasks ---", flush=True)
    collected_docs = []
    
    for task in running_tasks:
        print(f"🔍 Task: {task.description}")
        try:
            raw_results = await search_tool(task.description, num_results=settings.MAX_SEARCH_RESULTS)
        except Exception as e:
            dag.fail_task(task.id, str(e))
            continue
            
        if not raw_results:
            dag.complete_task(task.id, "No results found")
            continue
            
        snippets = "\n".join([f"[{i}] {r['url']}\n    {r['snippet'][:100]}..." for i, r in enumerate(raw_results)])
        select_resp = await simple_llm_call(prompts.search_result_selection(task.description, snippets, num_select=3), model=settings.MODEL_CHAT)
        selected_urls = parse_json_safe(select_resp) or [r["url"] for r in raw_results[:3]]
        
        print(f"🎯 [Selector] Selected: {selected_urls}")
        crawl_results = await crawl_urls(selected_urls)
        
        if crawl_results:
            collected_docs.extend(crawl_results)
            dag.complete_task(task.id, f"Scraped {len(crawl_results)} valid pages/files")
        else:
            dag.complete_task(task.id, "No valid content retrieved")

    if collected_docs:
        kb.add_documents(collected_docs, task_id=state["task_id"])
        print(f"💾 [Knowledge] Saved {len(collected_docs)} files.")
    
    dag.get_ready_tasks() 
    return {"plan": dag.to_state(), "knowledge_stats": [f"Added {len(collected_docs)} docs"]}

# 🟢 核心修改：Analyst 节点 (一本一本读)
async def node_analyst(state: ResearchState):
    print(f"--- [Analyst] Incremental Reading (Model: {settings.MODEL_CHAT}) ---")
    topic = state.get("clarified_intent", state["task"])
    
    # 1. 获取文件列表
    files = kb.list_files(state["task_id"])
    if not files:
        return {"draft_report": "Error: No documents found to analyze."}

    # 2. 初始化笔记
    running_notes = "（暂无调研笔记，等待阅读第一份文档...）"
    
    print(f"📚 [Analyst] Found {len(files)} documents. Reading sequentially...")
    
    # 3. 逐个阅读 (For Loop)
    for i, file_path in enumerate(files):
        # 读取文件内容
        doc_content = kb.read_file(file_path)
        if not doc_content: continue
        
        # 截断单个文件内容，防止极个别超大文件溢出
        if len(doc_content) > 100000:
            doc_content = doc_content[:100000] + "\n...(file truncated)..."

        print(f"📖 Reading Doc {i+1}/{len(files)}: {os.path.basename(file_path)} ({len(doc_content)} chars)")
        
        # 调用 LLM 更新笔记
        prompt = prompts.analyst_incremental_reading(topic, running_notes, doc_content)
        # 这一步可能会比较慢，但质量极高
        running_notes = await simple_llm_call(prompt, model=settings.MODEL_CHAT)
    
    print("✅ [Analyst] Reading complete. Generating Draft...")
    
    # 4. 基于最终笔记生成草稿
    final_prompt = prompts.analyst_reasoning(topic, running_notes)
    draft = await simple_llm_call(final_prompt, model=settings.MODEL_CHAT)
    
    # 5. 事实核查
    verified = await VerificationAgent.verify_report(draft)
    
    return {"draft_report": verified}

async def node_critic(state: ResearchState):
    print("--- [Critic] Reviewing ---")
    topic = state.get("clarified_intent", state["task"])
    draft = state.get("draft_report", "")
    
    prompt = prompts.critic_evaluation(topic, draft)
    resp = await simple_llm_call(prompt, model=settings.MODEL_REASONING)
    
    default_eval = {"score": 5, "critique": "Parsing failed", "adjustment": "Retry"}
    eval_data = parse_json_safe(resp) or default_eval
    
    try: score = float(eval_data.get("score", 0))
    except: score = 5.0

    log = {
        "step_name": f"Iter-{state['iteration_count']}",
        "critique": eval_data.get("critique"),
        "score": score,
        "adjustment": eval_data.get("adjustment")
    }
    return {"reflection_logs": [log], "iteration_count": state["iteration_count"] + 1}

async def node_publisher(state: ResearchState):
    print("--- [Publisher] Generating Final Report ---")
    topic = state.get("clarified_intent", state["task"])
    
    # 获取 Analyst 生成并经过 Verification 的草稿
    draft = state.get("draft_report", "")
    
    if not draft:
        return {"final_report": "Error: No draft report generated."}

    # Publisher 的工作是：格式化、润色、增加前言/目录
    # 我们将 draft 作为核心上下文传给 LLM
    prompt = prompts.publisher_final_report(topic, draft)
    
    final_report = await simple_llm_call(prompt, model=settings.MODEL_CHAT)
    
    # 保存
    saved_path = save_markdown_report(state["task"], final_report)
    if saved_path: 
        print(f"✅ Report saved to: {saved_path}")
    
    return {"final_report": final_report}

# --- 路由逻辑 ---

def route_planner(state: ResearchState) -> str:
    print("🚦 [Router] Deciding next step after Planner...")
    dag = DAGManager(state["plan"])
    running = [t for t in dag.tasks.values() if t.status == TaskStatus.RUNNING]
    if running:
        print(f"   -> Going to 'searcher' ({len(running)} tasks running)")
        return "searcher"
    if dag.is_all_completed():
        print("   -> Going to 'analyst' (All tasks completed)")
        return "analyst"
    print("   -> Fallback to 'analyst'")
    return "analyst"

def route_critic(state: ResearchState) -> str:
    if state["iteration_count"] >= state["max_iterations"]:
        print("🛑 Max iterations reached -> Publisher")
        return "publisher"

    # 防御性检查：防止 reflection_logs 为空
    if not state.get("reflection_logs"):
        print("⚠️ No reflection logs found -> Publisher")
        return "publisher"

    last_log = state["reflection_logs"][-1]
    if last_log.get("score", 0) >= 7.5:
        print("✅ Score >= 7.5 -> Publisher")
        return "publisher"
    print("🔄 Score low -> Back to Planner")
    return "planner"

# --- 构建图谱 ---

def build_graph():
    workflow = StateGraph(ResearchState)
    workflow.add_node("clarifier", node_clarifier)
    workflow.add_node("planner", node_planner)
    workflow.add_node("searcher", node_search_execute)
    workflow.add_node("analyst", node_analyst)
    workflow.add_node("critic", node_critic)
    workflow.add_node("publisher", node_publisher)
    
    workflow.set_entry_point("clarifier")
    workflow.add_edge("clarifier", "planner")
    workflow.add_conditional_edges("planner", route_planner, {"searcher": "searcher", "analyst": "analyst"})
    workflow.add_edge("searcher", "planner")
    workflow.add_edge("analyst", "critic")
    workflow.add_conditional_edges("critic", route_critic, {"planner": "planner", "publisher": "publisher"})
    workflow.add_edge("publisher", END)
    return workflow