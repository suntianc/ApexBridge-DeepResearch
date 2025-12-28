# app/modules/perception/crawler.py
import asyncio
import httpx
import fitz  # PyMuPDF
import numpy as np
import cv2
import logging
from crawl4ai import AsyncWebCrawler
from typing import List, Dict

# 尝试导入 PaddleOCR
PADDLE_AVAILABLE = False
try:
    from paddleocr import PaddleOCR
    PADDLE_AVAILABLE = True
except ImportError:
    print("⚠️ PaddleOCR not installed. Scanning features disabled.")

# 全局 OCR 引擎单例 (懒加载)
_ocr_engine = None

# 关键词触发器：包含这些关键词的页面即使超过 15 页也需要 OCR
OCR_KEYWORD_TRIGGERS = [
    "财务", "营收", "利润", "收入", "市场份额", "增长", "Table", "Figure",
    "附录", "附注", "资产负债表", "现金流量表", "利润表", "财务数据",
    "analysis", "revenue", "profit", "income", "balance sheet", "cash flow"
]

def get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None and PADDLE_AVAILABLE:
        print("👁️ [System] Loading PaddleOCR Model (This may take time)...")
        # use_angle_cls=True 自动纠正方向, lang="ch" 支持中英文
        _ocr_engine = PaddleOCR(use_angle_cls=True, lang="ch")
    return _ocr_engine

def _page_needs_ocr(text: str) -> bool:
    """判断页面是否可能包含需要 OCR 的关键信息（基于关键词）"""
    if len(text.strip()) >= 50:
        return False
    # 检查是否包含财务关键词
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in OCR_KEYWORD_TRIGGERS)

def process_pdf_sync(pdf_bytes: bytes, url: str) -> str:
    """
    [同步函数] PDF 处理核心逻辑：PyMuPDF + PaddleOCR 混合策略
    将在线程池中运行，避免阻塞 Async 事件循环。
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        print(f"❌ [PDF] Failed to open: {e}")
        return ""

    full_text = []
    ocr = get_ocr_engine()
    total_pages = len(doc)
    
    print(f"📄 [PDF] Processing {total_pages} pages from {url}...")

    # 限制处理页数，防止几百页的财报把 OCR 跑死 (根据需求调整，比如前20页核心内容)
    # 如果您真的"不在乎时间"，可以把这个限制去掉或调大
    MAX_OCR_PAGES = 15 

    for i, page in enumerate(doc):
        # 1. 尝试直接提取文本 (极快)
        text = page.get_text()
        
        # 2. 密度检测：如果文字极少，判定为扫描件/图片
        needs_ocr = len(text.strip()) < 50 and PADDLE_AVAILABLE
        # 关键词触发：即使超过 15 页，包含关键信息的页面仍需 OCR
        keyword_trigger = _page_needs_ocr(text) if not needs_ocr else needs_ocr

        if needs_ocr:
            if i < MAX_OCR_PAGES or keyword_trigger:
                trigger_note = " (keyword triggered)" if keyword_trigger else ""
                print(f"   🔍 [OCR] Page {i+1}/{total_pages} is image-based{trigger_note}. Scanning...")
                try:
                    # 渲染为高分辨率图片 (zoom=2) 提升识别率
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    
                    # 转换 PyMuPDF(Pix) -> Numpy(OpenCV)
                    img_data = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
                    
                    # 颜色空间转换
                    if pix.n == 4:
                        img_data = cv2.cvtColor(img_data, cv2.COLOR_RGBA2RGB)
                    elif pix.n == 3:
                        pass # RGB
                    else:
                        img_data = cv2.cvtColor(img_data, cv2.COLOR_GRAY2RGB)

                    # 执行 OCR
                    result = ocr.ocr(img_data, cls=True)
                    
                    # 解析结果
                    ocr_lines = []
                    if result and result[0]:
                        for line in result[0]:
                            # line 结构: [[box], (text, score)]
                            txt = line[1][0]
                            ocr_lines.append(txt)
                    
                    ocr_text = "\n".join(ocr_lines)
                    text = f"\n--- [Page {i+1} OCR Scan] ---\n{ocr_text}\n"
                    
                except Exception as e:
                    print(f"⚠️ [OCR] Failed on page {i+1}: {e}")
            else:
                # 只有非关键词触发的页面才跳过 OCR
                if not keyword_trigger:
                    text = "\n[OCR Skipped: Page limit reached]\n"
        
        full_text.append(text)
    
    return "\n\n".join(full_text)

async def extract_pdf_content(url: str) -> str:
    """下载并解析 PDF"""
    print(f"⬇️ [PDF] Downloading: {url}")
    try:
        async with httpx.AsyncClient(verify=False, follow_redirects=True, timeout=60.0) as client:
            response = await client.get(url)
            # 处理部分服务器返回 403 的情况，模拟 UA
            if response.status_code != 200:
                response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            
            response.raise_for_status()
            
            # 检查是否真的是 PDF
            if b"%PDF" not in response.content[:10]:
                return None 

            # 🟢 关键：将繁重的 PDF 处理放入线程池
            return await asyncio.to_thread(process_pdf_sync, response.content, url)

    except Exception as e:
        print(f"❌ [PDF] Download error {url}: {e}")
        return None

async def crawl_urls(urls: List[str]) -> List[Dict]:
    """智能混合爬虫入口"""
    if not urls: return []

    print(f"🕷️ [Smart Crawler] Processing {len(urls)} URLs...")
    
    results = []
    pdf_urls = [u for u in urls if u.lower().endswith(".pdf")]
    web_urls = [u for u in urls if not u.lower().endswith(".pdf")]
    
    # 1. 处理 PDF (限制并发，防止 CPU 爆炸)
    if pdf_urls:
        print(f"📄 Found {len(pdf_urls)} PDFs. Queueing OCR...")
        # 信号量控制同时进行的 OCR 任务数 (CPU密集型)
        sem = asyncio.Semaphore(2) 
        
        async def safe_pdf_task(u):
            async with sem:
                content = await extract_pdf_content(u)
                if content:
                    return {"url": u, "content": content, "source": "pdf_document"}
                return None

        pdf_results = await asyncio.gather(*[safe_pdf_task(u) for u in pdf_urls])
        
        for i, res in enumerate(pdf_results):
            if res:
                results.append(res)
            else:
                # 假如解析失败，可能是伪装的 HTML，丢回 Web 队列
                web_urls.append(pdf_urls[i])

    # 2. 处理 Web 页面 (crawl4ai)
    if web_urls:
        print(f"🌐 [Crawl4AI] Crawling {len(web_urls)} web pages...")
        async with AsyncWebCrawler(verbose=True) as crawler:
            async def process_web(url):
                # 简单重试
                for _ in range(2):
                    try:
                        res = await crawler.arun(
                            url=url, 
                            bypass_cache=True, 
                            word_count_threshold=50,
                            delay_before_return_html=1.0, # 给 JS 一点时间
                            timeout=30000
                        )
                        if res.success:
                            # 限制单页长度，防止单个网页 5MB 文本撑爆内存
                            return {"url": url, "content": res.markdown[:200000], "source": "web_page"}
                    except: pass
                return None
            
            web_results = await asyncio.gather(*[process_web(u) for u in web_urls])
            results.extend([r for r in web_results if r])

    return results