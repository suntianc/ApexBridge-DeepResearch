from litellm import completion
import os
from dotenv import load_dotenv

# 加载 .env 环境变量
load_dotenv()

async def simple_llm_call(
    prompt: str, 
    model: str = "deepseek/deepseek-chat", # 默认改为 DeepSeek V3
    temperature: float = 0.7
) -> str:
    """
    通用 LLM 调用接口，支持 DeepSeek, OpenAI, Claude, Ollama 等
    """
    
    # 打印当前使用的模型，方便调试
    print(f"🤖 [LLM Call] Model: {model}")

    try:
        # LiteLLM 会自动根据 model 前缀识别供应商
        # deepseek/deepseek-chat -> 自动映射到 DeepSeek API
        # ollama/deepseek-r1 -> 自动映射到本地 Ollama
        
        response = completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            # 如果是 DeepSeek API，不需要手动设 base_url，LiteLLM 内置了支持
            # 如果是 Ollama，LiteLLM 默认连接 http://localhost:11434
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        print(f"❌ [LLM Error] {model} failed: {str(e)}")
        return f"Error generation response with {model}. Details: {str(e)}"

# --- 使用说明 ---
# 1. DeepSeek API: 
#    model="deepseek/deepseek-chat" (V3)
#    model="deepseek/deepseek-reasoner" (R1)
#
# 2. 本地 DeepSeek (通过 Ollama):
#    model="ollama/deepseek-r1"
#
# 3. OpenAI:
#    model="gpt-4o"