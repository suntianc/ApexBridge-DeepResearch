# app/modules/perception/crawler.py
import asyncio
from crawl4ai import AsyncWebCrawler
from typing import List, Dict

async def crawl_urls(urls: List[str]) -> List[Dict]:
    """
    并发抓取多个 URL 并转换为 Markdown (修复导航冲突版)
    """
    if not urls:
        return []

    print(f"🕷️ [Crawl4AI] Starting concurrent crawl for {len(urls)} URLs...")
    
    # 定义单个 URL 的处理逻辑 (闭包)
    async def process_url(crawler, url: str):
        # 🟢 增加重试机制：针对 Navigation 错误重试最多 3 次
        for attempt in range(3):
            try:
                # arun 是异步的，这里并发调用同一个 crawler 实例
                result = await crawler.arun(
                    url=url,
                    bypass_cache=True,       # 总是获取最新内容
                    word_count_threshold=50, # 过滤掉内容过少的页面
                    
                    # 🟢 [关键修复] 增加等待策略
                    # 1. magic=True: 自动处理一些反爬和弹窗 (如果有这个参数建议开启，视版本而定)
                    # 2. delay_before_return_html: 强制等待页面静止 2 秒，防止跳转中读取
                    delay_before_return_html=2.0, 
                    
                    # 3. wait_until: 等待网络空闲，确保重定向完成
                    # 可选: 'domcontentloaded', 'networkidle', 'load'
                    wait_until="domcontentloaded",
                    
                    # 4. timeout: 防止单个页面卡死整个任务
                    timeout=30000 
                )
                
                if result.success:
                    # 限制内容长度，防止 token 爆炸
                    content = result.markdown[:50000]
                    print(f"✅ [Crawl4AI] Scraped: {url[:30]}... ({len(content)} chars)")
                    return {
                        "url": url,
                        "content": content,
                        "source": url
                    }
                else:
                    error_msg = result.error_message or "Unknown error"
                    # 如果是特定错误，可能需要重试
                    if "navigating" in error_msg.lower() or "timeout" in error_msg.lower():
                         print(f"⚠️ [Crawl4AI] Retry {attempt+1}/3 for {url}: {error_msg}")
                         await asyncio.sleep(2) # 避让一下
                         continue
                    
                    print(f"⚠️ [Crawl4AI] Failed to scrape {url}: {error_msg}")
                    return None
                    
            except Exception as e:
                error_str = str(e)
                # 🟢 捕获 Playwright 的特定导航错误并重试
                if "navigating" in error_str.lower() and attempt < 2:
                    print(f"🔄 [Crawl4AI] Navigation conflict, retrying {attempt+1}/3: {url}")
                    await asyncio.sleep(2.0) # 等待 2 秒后重试
                    continue
                
                print(f"❌ [Crawl4AI] Exception for {url}: {e}")
                return None
        
        return None # 重试耗尽

    # 使用上下文管理器启动浏览器实例
    async with AsyncWebCrawler(verbose=True) as crawler:
        # 1. 创建任务列表
        tasks = [process_url(crawler, url) for url in urls]
        
        # 2. 并发执行所有任务
        results_with_none = await asyncio.gather(*tasks)
        
        # 3. 过滤掉失败的结果
        results = [r for r in results_with_none if r is not None]
                
    return results