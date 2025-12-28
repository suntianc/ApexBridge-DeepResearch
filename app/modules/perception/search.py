# app/modules/perception/search.py
import asyncio
import random
import re
from typing import List, Dict
import httpx
from app.core.llm import simple_llm_call
from app.core.utils import parse_json_safe
from app.modules.insight.prompts import prompts

# 🟢 引入成熟的开源库
import arxiv
from github import Github, Auth
import wikipedia

from app.core.config import settings

# --- 0. 查询翻译兜底策略 ---
# 中文停用词列表（搜索时移除这些词以提高检索精度）
_QUERY_STOPWORDS = {
    "分析", "研究", "报告", "市场", "全球", "中国", "行业", "趋势",
    "调研", "深度", "全面", "最新", "2023", "2024", "2025"
}

def _fallback_query_translate(query: str) -> str:
    """
    规则化翻译：中文 -> 英文关键词
    当 LLM 重写失败时，使用此规则引擎生成英文搜索词
    """
    # 移除停用词
    words = [w for w in query.split() if w not in _QUERY_STOPWORDS]
    # 简单处理：移除常见的中文修饰词，保留核心名词
    cleaned = " ".join(words)
    # 如果结果仍为中文，尝试简单的关键词提取（取前 5 个词）
    if re.search(r'[\u4e00-\u9fff]', cleaned):
        # 尝试保留技术术语和核心实体
        keywords = []
        for word in words:
            # 跳过纯中文词（可能是通用词）
            if len(word) > 3 and not all('\u4e00' <= c <= '\u9fff' for c in word):
                keywords.append(word)
        cleaned = " ".join(keywords[:5]) if keywords else query
    return cleaned

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
async def search_generic(query: str) -> List[Dict[str, str]]:
    """
    [混合搜索 V2] 智能查询重写 + 并行搜索
    """
    print(f"🤔 [Hybrid Search] Optimizing query: {query}...")

    # --- A. 调用 LLM 进行查询重写 (Query Rewriting) ---
    # 使用 MODEL_CHAT (快速模型) 即可，不需要推理模型
    try:
        rewrite_prompt = prompts.search_query_optimization(query)
        # 这里建议用 MODEL_FAST 或 MODEL_CHAT，追求速度
        resp = await simple_llm_call(rewrite_prompt, model=settings.MODEL_CHAT)
        optimized_queries = parse_json_safe(resp)
    except Exception as e:
        print(f"⚠️ Query optimization failed: {e}, falling back to raw query.")
        optimized_queries = None

    # --- B. 准备各平台的查询词 ---
    # 如果重写失败，使用规则引擎兜底
    if optimized_queries is None:
        print("🔄 [Search] LLM optimization failed, using rule-based fallback...")
        translated_query = _fallback_query_translate(query)
        q_arxiv = translated_query
        q_github = translated_query
        q_wiki = _fallback_query_translate(query)  # Wiki 也尝试翻译
        q_web = query  # Web 搜索保留中文
    else:
        q_arxiv = optimized_queries.get("arxiv", query)
        q_github = optimized_queries.get("github", query)
        q_wiki = optimized_queries.get("wiki", query)
        q_web = optimized_queries.get("web", query)

    print(f"🚀 [Dispatching] \n   - ArXiv: {q_arxiv}\n   - GitHub: {q_github}\n   - Wiki: {q_wiki}\n   - Web: {q_web}")

    # --- C. 并发执行 ---
    tasks = [
        # 传入各自优化后的关键词
        _search_arxiv(q_arxiv, limit=settings.Result_Count_Arxiv),
        _search_github(q_github, limit=settings.Result_Count_Github),
        _search_wiki(q_wiki, limit=settings.Result_Count_Wiki),
        # Web 搜索通常最强，使用优化后的 Web 关键词
        _search_web_tavily(q_web, limit=settings.Result_Count_Web)
    ]
    
    results_list = await asyncio.gather(*tasks)
    
    # ... (后续的展平、去重逻辑保持不变) ...
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