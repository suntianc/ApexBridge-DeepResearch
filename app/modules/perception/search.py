# app/modules/perception/search.py
import asyncio
import functools
import random
from typing import List, Dict
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# 🟢 引入成熟的开源库
import arxiv
from github import Github, Auth
import wikipedia

from app.core.config import settings

# --- 1. arXiv 搜索 (基于 arxiv 库) ---
def _sync_arxiv_search(query: str, limit: int) -> List[Dict]:
    """[同步] arXiv 搜索逻辑"""
    print(f"📚 [arXiv] Searching: {query}...")
    try:
        # 构造搜索客户端
        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=limit,
            sort_by=arxiv.SortCriterion.Relevance
        )
        
        results = []
        for r in client.results(search):
            results.append({
                "url": r.pdf_url, # 直接给 PDF 链接，配合我们的 PDF 解析器
                "title": f"[arXiv] {r.title}",
                "snippet": f"Published: {r.published.date()}\nAbstract: {r.summary[:500]}...",
                "source": "arxiv"
            })
        return results
    except Exception as e:
        print(f"⚠️ [arXiv] Error: {e}")
        return []

async def _search_arxiv(query: str, limit: int = 3) -> List[Dict]:
    """[异步包装] 放入线程池执行"""
    if not settings.ENABLE_ARXIV: return []
    return await asyncio.to_thread(_sync_arxiv_search, query, limit)


# --- 2. GitHub 搜索 (基于 PyGithub 库) ---
def _sync_github_search(query: str, limit: int) -> List[Dict]:
    """[同步] GitHub 搜索逻辑"""
    print(f"💻 [GitHub] Searching: {query}...")
    try:
        # 鉴权 (强烈建议配置 Token，否则限制极严)
        auth = Auth.Token(settings.GITHUB_TOKEN) if settings.GITHUB_TOKEN else None
        g = Github(auth=auth)
        
        # 搜索仓库
        repos = g.search_repositories(query=query, sort="stars", order="desc")
        
        results = []
        # PyGithub 的分页是懒加载的，只取前 limit 个
        for i, repo in enumerate(repos):
            if i >= limit: break
            
            results.append({
                "url": repo.html_url,
                "title": f"[GitHub] {repo.full_name} ({repo.stargazers_count}⭐)",
                "snippet": f"Language: {repo.language}\nDescription: {repo.description}\n(Readme will be crawled)",
                "source": "github"
            })
        
        g.close()
        return results
    except Exception as e:
        print(f"⚠️ [GitHub] Error: {e}")
        return []

async def _search_github(query: str, limit: int = 3) -> List[Dict]:
    """[异步包装] 放入线程池执行"""
    if not settings.ENABLE_GITHUB: return []
    return await asyncio.to_thread(_sync_github_search, query, limit)


# --- 3. Wikipedia 搜索 (基于 wikipedia 库) ---
def _sync_wiki_search(query: str, limit: int) -> List[Dict]:
    """[同步] Wiki 搜索逻辑"""
    print(f"📖 [Wiki] Searching: {query}...")
    try:
        # 优先尝试中文，若无结果可考虑回退英文 (此处简化为中文)
        wikipedia.set_lang("zh")
        
        # 1. 搜索词条标题
        search_results = wikipedia.search(query, results=limit)
        if not search_results:
            # 回退到英文
            wikipedia.set_lang("en")
            search_results = wikipedia.search(query, results=limit)
            
        final_results = []
        for title in search_results:
            try:
                # 2. 获取词条详情
                # auto_suggest=False 防止自动纠错导致搜到不相关的
                page = wikipedia.page(title, auto_suggest=False)
                
                final_results.append({
                    "url": page.url,
                    "title": f"[Wiki] {page.title}",
                    "snippet": page.summary[:500] + "...",
                    "source": "wiki"
                })
            except wikipedia.DisambiguationError as e:
                # 歧义页面，取第一个选项重试
                try:
                    page = wikipedia.page(e.options[0], auto_suggest=False)
                    final_results.append({
                        "url": page.url,
                        "title": f"[Wiki] {page.title}",
                        "snippet": page.summary[:500] + "...",
                        "source": "wiki"
                    })
                except: pass
            except wikipedia.PageError:
                pass # 页面不存在
                
        return final_results
    except Exception as e:
        print(f"⚠️ [Wiki] Error: {e}")
        return []

async def _search_wiki(query: str, limit: int = 2) -> List[Dict]:
    """[异步包装] 放入线程池执行"""
    if not settings.ENABLE_WIKI: return []
    return await asyncio.to_thread(_sync_wiki_search, query, limit)


# --- 4. Web 搜索 (Tavily) - 支持多 Key 轮询 ---
async def _search_web_tavily(query: str, limit: int) -> List[Dict]:
    from app.core.config import settings
    # 随机选择一个 API Key，实现负载均衡
    api_key = random.choice(settings.TAVILY_API_KEYS) if settings.TAVILY_API_KEYS else None
    if not api_key: return []
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={"api_key": api_key, "query": query, "max_results": limit, "search_depth": "basic"},
                timeout=15.0
            )
            resp.raise_for_status()
            data = resp.json()
            return [{
                "url": r["url"], 
                "title": r["title"], 
                "snippet": r["content"], 
                "source": "web"
            } for r in data.get("results", [])]
    except Exception as e:
        print(f"⚠️ [Web] Error: {e}")
        return []


# --- 5. 聚合入口 ---
async def search_generic(query: str, num_results: int = 5) -> List[Dict[str, str]]:
    """
    [混合搜索 V2] 基于成熟 SDK 的并行搜索
    """
    print(f"🔍 [Hybrid Search] Dispatching: {query}...")
    
    # 定义任务：同时触发 4 路搜索
    tasks = [
        _search_arxiv(query, limit=settings.Result_Count_Arxiv),
        _search_github(query, limit=settings.Result_Count_Github),
        _search_wiki(query, limit=settings.Result_Count_Wiki),
        _search_web_tavily(query, limit=settings.Result_Count_Web)
    ]
    
    # 并发执行 (耗时取决于最慢的那个，通常是 Web 或 GitHub)
    results_list = await asyncio.gather(*tasks)
    
    # 展平与去重
    all_results = []
    seen_urls = set()
    
    for res_group in results_list:
        for r in res_group:
            if r['url'] not in seen_urls:
                seen_urls.add(r['url'])
                all_results.append(r)
            
    print(f"✅ [Hybrid Search] Found {len(all_results)} total results")
    return all_results

# 兼容导出
search_tool = search_generic