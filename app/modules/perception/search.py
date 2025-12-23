# app/modules/perception/search.py
import httpx
import random
import asyncio
from typing import List, Dict
from itertools import cycle
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings

# --- Key 管理器 ---
class KeyManager:
    """简单的 Key 轮询管理器"""
    def __init__(self, keys: List[str]):
        self.keys = keys
        self._iterator = cycle(keys) if keys else None

    def get_key(self) -> str:
        if not self._iterator:
            raise ValueError("No Tavily API keys configured!")
        return next(self._iterator)

# 初始化管理器
tavily_key_manager = KeyManager(settings.TAVILY_API_KEYS)

# --- 具体的实现函数 ---

async def _search_searxng(query: str, num_results: int) -> List[Dict[str, str]]:
    """SearXNG 搜索实现"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    params = {
        "q": query,
        "format": "json",
        "engines": "google,bing,duckduckgo,wikipedia",
        "language": "zh-CN",
        "safesearch": "0"
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(settings.SEARXNG_BASE_URL, params=params, headers=headers, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
        
        results = []
        if "results" in data:
            for item in data["results"][:num_results]:
                if item.get("url", "").startswith("http"):
                    results.append({
                        "url": item["url"],
                        "title": item.get("title", ""),
                        "snippet": item.get("content", "")
                    })
        return results

async def _search_tavily(query: str, num_results: int) -> List[Dict[str, str]]:
    """Tavily 搜索实现 (支持多Key切换)"""
    
    # 获取当前 Key
    api_key = tavily_key_manager.get_key()
    
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic", # 或 "advanced" 用于更深度的搜索（更贵）
        "include_answer": False,
        "include_images": False,
        "include_raw_content": False,
        "max_results": num_results
    }
    
    async with httpx.AsyncClient() as client:
        # Tavily REST API
        resp = await client.post("https://api.tavily.com/search", json=payload, timeout=15.0)
        
        # 401/403 通常意味着 Key 额度用完或无效
        if resp.status_code in [401, 403]:
            print(f"⚠️ [Tavily] Key {api_key[:8]}... failed (Quota/Auth). Rotating key.")
            # 抛出特定异常，虽然 Tenacity 会重试，但下次调用 KeyManager 会拿到新 Key
            # (注意：上面的 get_key 是基于 cycle 的，所以下次调用函数时自然会拿到下一个)
            resp.raise_for_status()
            
        resp.raise_for_status()
        data = resp.json()
        
        results = []
        if "results" in data:
            for item in data["results"]:
                results.append({
                    "url": item["url"],
                    "title": item.get("title", ""),
                    "snippet": item.get("content", "") # Tavily 返回的是 content
                })
        return results

# --- 统一入口 ---

# 定义重试策略：只重试网络类异常
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException, ConnectionError)),
    reraise=True
)
async def search_generic(query: str, num_results: int = 5) -> List[Dict[str, str]]:
    """
    通用搜索入口：根据配置分发请求
    """
    provider = settings.SEARCH_PROVIDER.lower()
    
    print(f"🔍 [Search] Requesting ({provider}): {query[:20]}...")

    try:
        if provider == "tavily":
            return await _search_tavily(query, num_results)
        elif provider == "searxng":
            return await _search_searxng(query, num_results)
        else:
            print(f"⚠️ Unknown provider '{provider}', falling back to SearXNG")
            return await _search_searxng(query, num_results)
            
    except Exception as e:
        # 这里由 Tenacity 捕获并重试
        print(f"❌ [Search] Error with {provider}: {e}")
        raise e

# 保持接口兼容性，直接导出别名
search_searxng = search_generic