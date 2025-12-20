# app/modules/perception/crawler.py
import asyncio
from crawl4ai import AsyncWebCrawler
from typing import List, Dict

async def crawl_urls(urls: List[str]) -> List[Dict]:
    """
    并发抓取多个 URL 并转换为 Markdown (优化版)
    """
    if not urls:
        return []

    print(f"🕷️ [Crawl4AI] Starting concurrent crawl for {len(urls)} URLs...")
    
    # 定义单个 URL 的处理逻辑 (闭包)
    async def process_url(crawler, url: str):
        try:
            # arun 是异步的，这里并发调用同一个 crawler 实例
            result = await crawler.arun(
                url=url,
                bypass_cache=True,       # 总是获取最新内容
                word_count_threshold=50  # 过滤掉内容过少的页面 (如 403/404 页)
            )
            
            if result.success:
                print(f"✅ [Crawl4AI] Scraped: {url[:30]}... ({len(result.markdown)} chars)")
                return {
                    "url": url,
                    "content": result.markdown,
                    "source": url
                }
            else:
                print(f"⚠️ [Crawl4AI] Failed to scrape {url}: {result.error_message}")
                return None
                
        except Exception as e:
            print(f"❌ [Crawl4AI] Exception for {url}: {e}")
            return None

    # 使用上下文管理器启动浏览器实例
    async with AsyncWebCrawler(verbose=True) as crawler:
        # 1. 创建任务列表
        tasks = [process_url(crawler, url) for url in urls]
        
        # 2. 并发执行所有任务 (Gather)
        # 如果 URL 非常多(>10)，建议使用 asyncio.Semaphore 限制并发数
        # 但 Deep Research 每次一般只搜 3-5 个结果，直接 gather 即可
        results_with_none = await asyncio.gather(*tasks)
        
        # 3. 过滤掉失败的结果 (None)
        results = [r for r in results_with_none if r is not None]
                
    return results