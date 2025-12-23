# app/api/research.py
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from app.modules.orchestrator.graph import build_graph
from app.core.config import settings
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
import aiosqlite
import asyncio
import json
import uuid
import traceback
# 🟢 引入超时控制库 (请确保 pip install async_timeout)
from async_timeout import timeout 

router = APIRouter()

# 获取未编译的图谱构建器
workflow_builder = build_graph()

@router.get("/stream")
async def stream_research(topic: str):
    # 生成唯一会话 ID
    thread_id = str(uuid.uuid4())
    task_id = thread_id
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": settings.MAX_RECURSION_LIMIT
    }

    async def event_generator():
        # 初始化状态
        inputs = {
            "task_id": task_id,
            "task": topic,
            "clarified_intent": topic, # 初始时意图等于题目
            "plan": [],
            "knowledge_graph": [],
            "reflection_logs": [],
            "iteration_count": 0,
            "max_iterations": 3,
            
            # 兼容字段
            "topic": topic,          # 暂时保留，graph.py 还在用
            "draft_report": "",      # 暂时保留，Analyst/Critic 交互用
            "final_report": "",      # 暂时保留，Publisher 用
        }
        
        try:
            # 🟢 使用配置化的超时时间
            # async_timeout 上下文管理器会在超时后抛出 asyncio.TimeoutError
            async with timeout(settings.GLOBAL_TIMEOUT_SEC):
                
                # 1. 显式创建连接
                async with aiosqlite.connect(settings.CHECKPOINT_DB_PATH) as conn:
                    
                    # 🩹【系统性修复 / Monkey Patch】
                    # 修复 langgraph 在 aiosqlite 上调用 is_alive 的兼容性问题
                    setattr(conn, "is_alive", lambda: True)
                    
                    # 2. 将修复后的连接传给 Checkpointer
                    checkpointer = AsyncSqliteSaver(conn)
                    
                    # 3. 编译图谱
                    graph = workflow_builder.compile(checkpointer=checkpointer)
                    
                    # 4. 运行图谱 (流式)
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
                            # 缓冲一下，避免前端渲染过快卡顿
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
            
            error_payload = json.dumps(
                {"error": str(e)}, 
                ensure_ascii=False
            )
            yield {"event": "error", "data": error_payload}

    return EventSourceResponse(event_generator())