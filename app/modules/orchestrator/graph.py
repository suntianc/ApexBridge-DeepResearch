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

def _normalize_title(title: str) -> str:
    """
    标准化标题：去除序号、空格、标点，转小写
    用于解决 Planner 生成的标题与 Searcher 打标签不一致的问题
    """
    import re
    if not title:
        return ""
    # 去除序号 (1., 1.1, 一、, etc.)
    normalized = re.sub(r'^[\d\.\．]+\s*|^\w[、]\s*', '', title)
    # 保留中文、英文、数字，移除所有标点和空格
    normalized = re.sub(r'[^\w\u4e00-\u9fff]+', '', normalized)
    return normalized.lower()

def _match_sections(section_title: str, label: str) -> bool:
    """模糊匹配章节标题"""
    return _normalize_title(section_title) == _normalize_title(label)

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

            # 🟢 新增：处理 Critic 的章节级反馈
            focus_section = last_log.get("focus_section")
            reason = last_log.get("reason", "unknown")

            if focus_section and last_log.get("score", 0) < 7.5:
                print(f"🔧 [Planner] Handling Critic feedback for section: {focus_section}")

                if reason == "insufficient_data":
                    # 🟢 缺数据 -> 生成针对性的搜索任务
                    feedback_str = f"批评: {last_log.get('critique')}\n建议: {last_log.get('adjustment')}"
                    resp = await simple_llm_call(
                        prompts.planner_section_retry(focus_section, feedback_str),
                        model=settings.MODEL_REASONING
                    )
                    new_tasks = parse_json_safe(resp) or []
                    for t in new_tasks:
                        if isinstance(t, dict) and "id" in t:
                            dag.add_task(
                                t["id"],
                                t["description"],
                                t.get("dependencies", []),
                                related_section=focus_section
                            )
                    print(f"   📝 Generated {len(new_tasks)} tasks for section '{focus_section}'")
                # reason 是 "writing_quality" -> 可以跳过搜索直接重写（当前设计回 Planner 即可）
            else:
                # 🟢 通用重规划
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

    # 🟢 初始化映射表（保留之前的映射，支持增量添加）
    file_map = state.get("file_section_map", {}).copy()

    for task in running_tasks:
        print(f"🔍 Task: {task.description}")
        try:
            raw_results = await search_tool(task.description)
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

            # 🟢 修改点：返回保存的文件路径
            saved_paths = kb.add_documents(crawl_results, task_id=state["task_id"])

            # 🟢 根据任务关联的章节打标签
            section = task.related_section

            # 如果是"综合调研"类任务（无特定章节关联），标记为通用
            if not section:
                if any(kw in task.description.lower() for kw in ["overview", "introduction", "背景", "概况"]):
                    section = "__general__"
                else:
                    section = "__uncategorized__"

            for path in saved_paths:
                file_map[path] = section
                print(f"   📎 {os.path.basename(path)} -> {section}")

            dag.complete_task(task.id, f"Scraped {len(crawl_results)} valid pages/files")
        else:
            dag.complete_task(task.id, "No valid content retrieved")

    if collected_docs:
        print(f"💾 [Knowledge] Saved {len(collected_docs)} files.")

    dag.get_ready_tasks()
    # 🟢 返回 file_section_map 字段
    return {"plan": dag.to_state(), "knowledge_stats": [f"Added {len(collected_docs)} docs"], "file_section_map": file_map}

# 🟢 核心修改：Analyst 节点 (分章节报告生成)
async def node_analyst(state: ResearchState):
    print(f"--- [Analyst] Section-based Reporting ---")

    outline = state.get("outline", [])
    file_map = state.get("file_section_map", {})
    all_files = kb.list_files(state["task_id"])

    if not all_files:
        return {"draft_report": "Error: No documents found to analyze."}

    # 🟢 准备章节队列
    # 优先使用 state 中的 pending_sections (来自 Critic 的返工要求)
    # 如果 state["pending_sections"] 为空 (首次运行)，才使用完整 outline
    current_pending = state.get("pending_sections", [])
    if current_pending:
        print(f"🔄 [Analyst] Resuming specific sections: {current_pending}")
        target_sections = current_pending
    else:
        target_sections = outline.copy() if outline else ["__general__"]

    section_drafts = state.get("section_drafts", {}).copy()  # 记得 .copy() 防止原地修改

    # 🟢 核心逻辑：按章节逐个攻破
    for section_title in target_sections:
        print(f"  Writing Section: {section_title}")

        # 1. 筛选属于当前章节的文件 (三层优先级，使用模糊匹配)
        section_files = [f for f in all_files if _match_sections(section_title, file_map.get(f, ""))]
        general_files = [f for f in all_files if file_map.get(f) == "__general__"]
        uncategorized_files = [f for f in all_files if file_map.get(f) in ("__uncategorized__", None)]

        # 2. 合并文件列表（专属在前，通用次之，未分类兜底）
        relevant_files = section_files + general_files + uncategorized_files

        if not relevant_files:
            print(f"   No files for section: {section_title}")
            continue

        # 3. 增量阅读该章节
        section_notes = ""
        for i, file_path in enumerate(relevant_files):
            doc_content = kb.read_file(file_path)
            if not doc_content:
                continue
            if len(doc_content) > 80000:
                doc_content = doc_content[:80000] + "\n...(truncated)..."

            print(f"   [{i+1}/{len(relevant_files)}] {os.path.basename(file_path)}")

            # 调用 LLM 更新该章节的笔记
            prompt = prompts.analyst_section_writing(section_title, section_notes, doc_content)
            section_notes = await simple_llm_call(prompt, model=settings.MODEL_CHAT)

        # 4. 生成该章节的最终文本
        if section_notes:
            section_drafts[section_title] = section_notes

    # 5. 拼装完整报告 (Merger)
    print("  Merging all sections...")
    topic = state.get("clarified_intent", state["task"])

    full_report = await simple_llm_call(
        prompts.analyst_merge_sections(topic, outline, section_drafts),
        model=settings.MODEL_CHAT
    )

    # 6. 统一的事实核查
    print("  Running verification...")
    verified_report = await VerificationAgent.verify_report(full_report)

    return {
        "draft_report": verified_report,
        "section_drafts": section_drafts,
        "pending_sections": []
    }

async def node_critic(state: ResearchState):
    """支持按章节反馈的 Critic"""
    print("--- [Critic] Section-aware Reviewing ---")
    topic = state.get("clarified_intent", state["task"])
    draft = state.get("draft_report", "")
    section_drafts = state.get("section_drafts", {})

    prompt = prompts.critic_evaluation(topic, draft, section_drafts)
    resp = await simple_llm_call(prompt, model=settings.MODEL_REASONING)

    default_eval = {
        "score": 5,
        "critique": "Parsing failed",
        "adjustment": "Retry",
        "focus_section": None,
        "reason": "unknown"
    }
    eval_data = parse_json_safe(resp) or default_eval

    try:
        score = float(eval_data.get("score", 0))
    except:
        score = 5.0

    # 如果 Critic 指出特定章节问题，将该章节放回待办
    focus_section = eval_data.get("focus_section")
    new_pending = [] 
    
    if focus_section and score < 7.5:
        # 只有在分数低且指定了章节时，才标记为待办
        new_pending = [focus_section]
        print(f"🔄 [Critic] Marking section for rework: {focus_section}")

    log = {
        "step_name": f"Iter-{state['iteration_count']}",
        "critique": eval_data.get("critique"),
        "score": score,
        "adjustment": eval_data.get("adjustment"),
        "focus_section": focus_section,
        "reason": eval_data.get("reason", "unknown")
    }
    
    return {
        "reflection_logs": [log],
        "iteration_count": state["iteration_count"] + 1,
        "pending_sections": new_pending  # ✅ 返回新的待办列表，供下一轮 Analyst 使用
    }

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
    """支持章节级重试的路由 - 关键修复：避免死循环"""
    if state["iteration_count"] >= state["max_iterations"]:
        print("🛑 Max iterations reached -> Publisher")
        return "publisher"

    # 防御性检查：防止 reflection_logs 为空
    if not state.get("reflection_logs"):
        print("⚠️ No reflection logs found -> Publisher")
        return "publisher"

    last_log = state["reflection_logs"][-1]
    score = last_log.get("score", 0)

    if score >= 7.5:
        print("✅ Score >= 7.5 -> Publisher")
        return "publisher"

    # 核心修复：无论问题是否在特定章节，都回 Planner
    print(f"🔄 [Router] Score {score} < 7.5 -> Back to Planner for repair")
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