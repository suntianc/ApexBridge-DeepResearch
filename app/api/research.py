# app/api/research.py
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from app.modules.orchestrator.graph import build_graph
import asyncio, json, uuid

router = APIRouter()
graph = build_graph()

@router.get("/stream")
async def stream_research(topic: str):
    # 生成唯一会话 ID
    thread_id = str(uuid.uuid4())
    # 配置 config
    config = {"configurable": {"thread_id": thread_id}}
    """流式输出 Agent 的思考过程"""
    async def event_generator():
        # 初始化状态
        inputs = {
            "topic": topic,
            "iteration_count": 0,
            "max_iterations": 3,
            "search_queries": [],
            "web_results": []
        }
        
        # 运行图谱 (astream 会产生每个步骤的事件)
        async for event in graph.astream(inputs, config=config):
            # event 的格式通常是 {"node_name": {updated_state_keys}}
            for node_name, state_update in event.items():
                
                # 构造发送给前端的消息
                payload = {
                    "step": node_name,
                    "data": state_update
                }

                json_str = json.dumps(
                        payload, 
                        default=str, 
                        ensure_ascii=False  # <--- 关键！让中文原样输出
                    )
                
                # SSE 格式: data: ...
                yield {
                    "event": "update",
                    "data": json_str
                }
                
                # 稍微让子弹飞一会儿，方便观察 (生产环境去掉)
                await asyncio.sleep(0.5)

        yield {"event": "finish", "data": "DONE"}

    return EventSourceResponse(event_generator())