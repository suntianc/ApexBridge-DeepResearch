# app/modules/knowledge/file_store.py
import os
import hashlib
import json
from glob import glob
from datetime import datetime
from typing import List, Dict
from app.core.config import settings

class FileKnowledgeStore:
    def __init__(self):
        self.root_dir = settings.TASK_STORAGE_DIR

    def _get_task_dir(self, task_id: str) -> str:
        path = os.path.join(self.root_dir, task_id, "docs")
        os.makedirs(path, exist_ok=True)
        return path

    def _get_filename(self, content: str, url: str) -> str:
        """
        🟢 优化：优先使用内容的 MD5 进行去重。
        如果内容一样，不管 URL 变没变，都视为同一个文件。
        """
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()[:12]
        return f"doc_{content_hash}.md"

    def add_documents(self, documents: List[Dict], task_id: str):
        task_dir = self._get_task_dir(task_id)
        count = 0
        
        for doc in documents:
            content = doc.get("content", "")
            if len(content) < 50: continue

            # 使用内容哈希生成文件名
            filename = self._get_filename(content, doc.get("url", ""))
            filepath = os.path.join(task_dir, filename)

            # 内容级去重
            if os.path.exists(filepath):
                continue

            # 使用当前时间作为保存时间
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            md_content = f"""---
url: {doc.get('url')}
source: {doc.get('source', 'web')}
saved_at: {current_time}
---

{content}
"""
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(md_content)
                count += 1
            except Exception as e:
                print(f"❌ [FileStore] Write error: {e}")

        if count > 0:
            print(f"💾 [FileStore] Saved {count} new documents to {task_dir}")

    # 🟢 补全缺失的方法：获取文件列表
    def list_files(self, task_id: str) -> List[str]:
        task_dir = self._get_task_dir(task_id)
        # 按文件名排序确保顺序一致
        return sorted(glob(os.path.join(task_dir, "*.md")))

    # 🟢 补全缺失的方法：读取单个文件
    def read_file(self, filepath: str) -> str:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"❌ Error reading file {filepath}: {e}")
            return ""

    # 这个方法保留作为备用，或者给 Critic 用
    def get_all_context(self, task_id: str) -> str:
        files = self.list_files(task_id)
        context = []
        for f in files:
            context.append(self.read_file(f))
        return "\n\n".join(context)