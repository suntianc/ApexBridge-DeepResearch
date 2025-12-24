import httpx
import json
import os

# 配置目标
API_URL = "http://localhost:23800/api/stream"  # 注意：路由前缀是 /api
TOPIC = "NexaAI和AutoGLM结合在移动端落地可能性"             # 您想搜的题目

def run_test():
    print(f"🚀 [Test] Starting Deep Research on: '{TOPIC}'")
    print("-" * 60)

    try:
        # 发起流式请求 (设置较长的超时时间，因为深度研究很耗时)
        with httpx.stream("GET", API_URL, params={"topic": TOPIC}, timeout=600.0) as response:
            if response.status_code != 200:
                print(f"❌ API Error: {response.status_code}")
                print(response.read().decode())
                return

            for line in response.iter_lines():
                if not line: continue
                
                # SSE 格式通常是以 "data: " 开头
                if line.startswith("data: "):
                    data_str = line[6:] # 去掉 "data: " 前缀
                    
                    if data_str == "[DONE]" or data_str == "DONE":
                        print("\n✅ Research Completed!")
                        break
                    
                    try:
                        # 解析外层 JSON
                        payload = json.loads(data_str)
                        
                        # 处理错误
                        if payload.get("event") == "error":
                            err_data = json.loads(payload["data"])
                            print(f"\n❌ SERVER ERROR: {err_data.get('error')}")
                            break

                        # 处理正常更新
                        if payload.get("event") == "update":
                            # 解析内层数据 (因为 data 字段本身也是个 JSON 字符串)
                            inner_data = json.loads(payload["data"])
                            step = inner_data.get("step")
                            content = inner_data.get("data")
                            
                            # --- 打印美化日志 ---
                            if step == "planner":
                                plan = content.get("plan", [])
                                print(f"\n🧠 [Planner] Generated Plan ({len(plan)} tasks):")
                                for t in plan:
                                    status = t['status']
                                    icon = "✅" if status == 'completed' else "⏳"
                                    if status == 'running': icon = "▶️"
                                    print(f"   {icon} {t['description']}")
                                    
                            elif step == "searcher":
                                results = content.get("web_results", [])
                                if results:
                                    print(f"\n🌍 [Searcher] Scraped {len(results)} pages.")

                            elif step == "analyst":
                                print(f"\n📝 [Analyst] Drafting Report...")

                            elif step == "critic":
                                logs = content.get("reflection_logs", [])
                                if logs:
                                    latest = logs[-1]
                                    print(f"\n⚖️ [Critic] Score: {latest['score']}/10 -> {latest['adjustment']}")

                            elif step == "publisher":
                                print(f"\n📰 [Publisher] Final Report Generated!")
                                # 这里只是为了提示，实际文件已经由后端保存了

                    except json.JSONDecodeError:
                        pass
                        
    except Exception as e:
        print(f"\n❌ Connection Failed: {e}")
        print("Tip: Make sure the server is running (python main.py)")

if __name__ == "__main__":
    run_test()