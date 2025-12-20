# app/modules/perception/search.py
import httpx, json
from typing import List, Dict
from app.core.config import settings

SEARXNG_URL = settings.SEARXNG_BASE_URL

async def search_searxng(query: str, num_results: int = 5) -> List[Dict[str, str]]:
    """
    调用本地 SearXNG 搜索，返回 URL 列表
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    params = {
        "q": query,
        "format": "json",
        "engines": "quark (ZH),sogou (ZH),360search (ZH),wikimini (FR),yandex,mwmbl,currency,dictzone,libretranslate,lingva,mojeek,naver (KO),crowdview", 
        "language": "zh-CN", # 根据需求调整
        "safesearch": "0"
    }
    print(f"🔍 [Debug] Requesting: {SEARXNG_URL}")
    print(f"🔍 [Debug] Params: {params}")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(SEARXNG_URL, params=params, headers=headers, timeout=15.0)
            
            # 2. 检查 HTTP 状态码
            if resp.status_code != 200:
                print(f"❌ [Error] SearXNG returned status: {resp.status_code}")
                print(f"❌ [Error] Response text: {resp.text[:200]}") # 打印前200字符看看报错信息
                return []

            # 3. 检查是否返回了 JSON
            try:
                data = resp.json()
            except json.JSONDecodeError:
                print("❌ [Error] Returned content is NOT JSON. Maybe HTML?")
                print(f"❌ [Content Preview]: {resp.text[:200]}...")
                return []

            # 4. 检查是否有 results 字段
            if "results" not in data:
                print(f"⚠️ [Warning] JSON parsed but no 'results' field. Keys: {data.keys()}")
                # 有时 SearXNG 报错会返回 {"error": "..."}
                if "error" in data:
                    print(f"⚠️ [SearXNG Error]: {data['error']}")
                return []
            
            raw_results = data["results"]
            print(f"✅ [Debug] Raw results count: {len(raw_results)}")

            # 5. 提取有效链接
            results = []
            for item in raw_results[:num_results]:
                if item.get("url", "").startswith("http"):
                    results.append({
                        "url": item["url"],
                        "title": item.get("title", ""),
                        "snippet": item.get("content", "")
                    })
            
            return results

        except Exception as e:
            print(f"❌ [Exception] Connection failed: {e}")
            return []