# app/modules/utils/file_utils.py
import os
import re
from datetime import datetime
from app.core.config import settings

def save_markdown_report(topic: str, content: str) -> str:
    """
    独立工具：将 Markdown 报告保存到磁盘
    
    Args:
        topic: 研究主题 (用于生成文件名)
        content: 报告内容
        
    Returns:
        saved_path: 保存的文件绝对路径 (如果未开启或失败则返回空字符串)
    """
    # 1. 检查配置开关
    if not settings.SAVE_REPORT_TO_FILE:
        return ""

    try:
        # 2. 确保目录存在 (双重保险)
        output_dir = settings.REPORT_OUTPUT_DIR
        os.makedirs(output_dir, exist_ok=True)

        # 3. 清洗文件名 (移除非法字符，将空格转为下划线，限制长度)
        safe_topic = re.sub(r'[\\/*?:"<>|]', "", topic)
        safe_topic = safe_topic.strip().replace(" ", "_")[:50]
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_topic}_{timestamp}.md"
        filepath = os.path.join(output_dir, filename)

        # 4. 写入文件
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
            
        print(f"💾 [System] Report auto-saved to: {filepath}")
        return filepath

    except Exception as e:
        print(f"⚠️ [System] Failed to save report file: {e}")
        return ""