# app/modules/knowledge/vector.py
import lancedb
import os
import time
import pyarrow as pa
from typing import List, Dict
from litellm import embedding
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.core.config import settings

# 1. 初始化 LanceDB (本地文件模式)
DB_PATH = settings.LANCEDB_PATH
os.makedirs(DB_PATH, exist_ok=True)
db = lancedb.connect(DB_PATH)

# 定义表结构 (Schema) - 动态向量维度
# 根据 EMBEDDING_MODEL 和 EMBEDDING_DIMENSION 配置
schema = pa.schema([
    pa.field("vector", pa.list_(pa.float32(), settings.EMBEDDING_DIMENSION)),
    pa.field("text", pa.string()),
    pa.field("source", pa.string()),
    pa.field("chunk_id", pa.string()),
    pa.field("model", pa.string()),
    pa.field("task_id", pa.string())
])

def get_embedding(text: str) -> List[float]:
    """
    使用配置的嵌入模型获取向量
    支持多种模型：Ollama本地模型、云端API等
    """
    try:
        response = embedding(
            model=settings.EMBEDDING_MODEL,
            input=[text]
        )
        return response.data[0]['embedding']

    except Exception as e:
        print(f"❌ Embedding Error ({settings.EMBEDDING_MODEL}): {e}")
        return [0.0] * settings.EMBEDDING_DIMENSION

class KnowledgeBase:
    def __init__(self, table_name: str = "research_context"):
        self.table_name = table_name
        
        # 🟢 鲁棒性增强：维度兼容性检查与自动迁移
        try:
            # 尝试打开现有表
            self.table = db.open_table(table_name)
            
            # 检查 schema 中的向量维度
            # PyArrow 的 FixedSizeListType 具有 list_size 属性
            vec_field = self.table.schema.field("vector")
            existing_dim = vec_field.type.list_size
            
            if existing_dim != settings.EMBEDDING_DIMENSION:
                print(f"⚠️ [Knowledge] Dimension mismatch detected! Table: {existing_dim}, Config: {settings.EMBEDDING_DIMENSION}")
                
                # 备份旧表 (重命名)
                backup_name = f"{table_name}_backup_{int(time.time())}"
                try:
                    db.rename_table(table_name, backup_name)
                    print(f"📦 Archived old table to '{backup_name}'.")
                except Exception as rename_err:
                    print(f"⚠️ Failed to rename table: {rename_err}")
                
                # 创建新表
                print("🆕 Creating new table with correct dimension...")
                self.table = db.create_table(table_name, schema=schema)
                
        except Exception:
            # 如果表不存在，直接创建
            # print(f"ℹ️ Table '{table_name}' not found, creating new one.")
            self.table = db.create_table(table_name, schema=schema)

    def add_documents(self, documents: List[Dict], task_id: str):
        """
        接收爬取结果 -> 切片 -> 向量化 -> 存入
        """
        # 根据嵌入模型调整 chunk_size
        if "openai" in settings.EMBEDDING_MODEL:
            chunk_size = 800
        else:
            chunk_size = 1200

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=200
        )

        data_to_insert = []

        print(f"💾 [Knowledge] Processing {len(documents)} docs with {settings.EMBEDDING_MODEL} (Dim: {settings.EMBEDDING_DIMENSION})...")

        for doc in documents:
            clean_content = doc["content"].replace("\n\n\n", "\n")
            chunks = splitter.split_text(clean_content)

            for idx, chunk in enumerate(chunks):
                vec = get_embedding(chunk)
                if len(vec) == settings.EMBEDDING_DIMENSION:
                    data_to_insert.append({
                        "vector": vec,
                        "text": chunk,
                        "source": doc.get("source", "unknown"),
                        "chunk_id": f"{doc.get('url', 'unknown')}_{idx}",
                        "model": settings.EMBEDDING_MODEL,
                        "task_id": task_id
                    })

        if data_to_insert:
            self.table.add(data_to_insert)
            print(f"✅ [Knowledge] Inserted {len(data_to_insert)} chunks (Dim: {settings.EMBEDDING_DIMENSION})")

    def search(self, query: str, task_id: str, limit: int = 5) -> str:
        """
        语义检索
        """
        print(f"🔍 [Retrieval] Searching for: {query[:30]}...")
        try:
            query_vec = get_embedding(query)
            results = self.table.search(query_vec).where(f"task_id = '{task_id}'").limit(limit).to_list()
            
            context = ""
            for item in results:
                context += f"--- Source: {item['source']} ---\n{item['text']}\n\n"
                
            print(f"✅ [Retrieval] Found {len(results)} relevant chunks")
            return context
        except Exception as e:
            print(f"⚠️ Retrieval failed: {e}")
            return ""
        
    def clear_task_data(self, task_id: str):
        try:
            self.table.delete(f"task_id = '{task_id}'")
            print(f"🧹 [Knowledge] Cleared vectors for task: {task_id}")
        except Exception as e:
            print(f"⚠️ Failed to clear task data: {e}")