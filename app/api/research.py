# app/api/research.py
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from app.modules.orchestrator.graph import build_graph
from app.core.config import settings
# 🟢 必须换回 AsyncSqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver 
import aiosqlite
import asyncio
import json
import uuid
import traceback
from async_timeout import timeout 

router = APIRouter()

# 获取未编译的图谱构建器
workflow_builder = build_graph()

@router.get("/stream")
async def stream_research(topic: str, thread_id: str = None):
    """
    流式深度研究接口

    Args:
        topic: 研究主题
        thread_id: 可选参数，支持断点续传。
                  - 首次请求：不传此参数，系统自动生成新的 thread_id
                  - 续传请求：传入之前返回的 thread_id，可恢复之前的会话状态
    """
    # 如果前端未提供 thread_id，则生成新的 UUID
    thread_id = thread_id or str(uuid.uuid4())
    task_id = thread_id  # task_id 同步使用 thread_id

    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": settings.MAX_RECURSION_LIMIT
    }

    async def event_generator():
        # 初始化状态
        inputs = {
            "task_id": task_id,
            "task": topic,
            "clarified_intent": topic,
            "plan": [],
            "knowledge_graph": [],
            "reflection_logs": [],
            "iteration_count": 0,
            "max_iterations": 3,
            "topic": topic,          
            "draft_report": "",      
            "final_report": "",     
        }
        
        try:
            async with timeout(settings.GLOBAL_TIMEOUT_SEC):
                
                print(f"🚀 [System] Starting research task: {task_id} (Async + WAL Mode)")
                
                # 🟢 1. 使用异步连接
                async with aiosqlite.connect(settings.CHECKPOINT_DB_PATH) as conn:
                    
                    # 🛡️【关键防死锁配置】开启 WAL 模式和超时设置
                    # 这允许读写并发，彻底解决之前的卡死问题
                    await conn.execute("PRAGMA journal_mode=WAL;")
                    await conn.execute("PRAGMA synchronous=NORMAL;")
                    await conn.execute("PRAGMA busy_timeout=30000;") # 等待 30s 而不是立刻报错
                    await conn.commit()
                    
                    # 🩹 兼容性补丁 (防止部分版本的 LangGraph 报错)
                    setattr(conn, "is_alive", lambda: True)
                    
                    # 2. 创建异步 Checkpointer
                    checkpointer = AsyncSqliteSaver(conn)
                    
                    # 3. 编译图谱
                    graph = workflow_builder.compile(checkpointer=checkpointer)
                    
                    # 4. 运行图谱 (astream 必须配对异步 checkpointer)
                    async for event in graph.astream(inputs, config=config):
                        for node_name, state_update in event.items():
                            payload = {
                                "step": node_name,
                                "data": state_update
                            }
                            
                            json_str = json.dumps(
                                payload, 
                                default=str, 
                                ensure_ascii=False
                            )
                            
                            yield {
                                "event": "update",
                                "data": json_str
                            }
                            # 缓冲一下
                            await asyncio.sleep(0.1)

                yield {"event": "finish", "data": "DONE"}

        except asyncio.TimeoutError:
            print(f"⏰ Task timed out after {settings.GLOBAL_TIMEOUT_SEC}s")
            error_payload = json.dumps(
                {"error": f"Global Timeout: Research stopped after {settings.GLOBAL_TIMEOUT_SEC} seconds."}, 
                ensure_ascii=False
            )
            yield {"event": "error", "data": error_payload}
                
        except Exception as e:
            print(f"❌ Error in stream: {e}")
            traceback.print_exc()
            error_payload = json.dumps({"error": str(e)}, ensure_ascii=False)
            yield {"event": "error", "data": error_payload}

    return EventSourceResponse(event_generator())