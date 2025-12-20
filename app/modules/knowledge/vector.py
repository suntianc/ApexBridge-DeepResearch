import lancedb,os
from typing import List, Dict
from litellm import embedding
from langchain_text_splitters import RecursiveCharacterTextSplitter
import pyarrow as pa
from app.core.config import settings

# 1. 初始化 LanceDB (本地文件模式)
DB_PATH = settings.LANCEDB_PATH
os.makedirs(DB_PATH, exist_ok=True)
db = lancedb.connect(DB_PATH)

# 定义表结构 (Schema)
# vector 维度取决于你使用的模型，OpenAI text-embedding-3-small 是 1536 维
schema = pa.schema([
    pa.field("vector", pa.list_(pa.float32(), 768)),
    pa.field("text", pa.string()),
    pa.field("source", pa.string()),
    pa.field("chunk_id", pa.string())
])

def get_embedding(text: str) -> List[float]:
    """
    使用本地 Ollama 的 nomic-embed-text 获取向量
    针对 Log 结构: response['data'][0]['embedding']
    """
    try:
        response = embedding(
            model="ollama/nomic-embed-text", 
            input=[text]
        )
        return response.data[0]['embedding']

    except Exception as e:
        print(f"❌ Embedding Error (Ollama): {e}")
        return [0.0] * 768

class KnowledgeBase:
    def __init__(self, table_name: str = "research_context"):
        self.table_name = table_name
        # 如果表不存在则创建
        try:
            self.table = db.open_table(table_name)
        except:
            self.table = db.create_table(table_name, schema=schema)

    def add_documents(self, documents: List[Dict]):
        """
        接收爬取结果 -> 切片 -> 向量化 -> 存入
        """
        # nomic-embed-text 支持 8192 context，我们可以稍微把 chunk 切大一点
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1200, 
            chunk_overlap=200
        )
        
        data_to_insert = []
        
        print(f"💾 [Knowledge] Processing {len(documents)} docs with nomic-embed-text...")
        
        for doc in documents:
            # 简单的清洗，去除过多空行
            clean_content = doc["content"].replace("\n\n\n", "\n")
            chunks = splitter.split_text(clean_content)
            
            for idx, chunk in enumerate(chunks):
                vec = get_embedding(chunk)
                # 简单校验维度，防止 Ollama 偶尔返回空
                if len(vec) == 768:
                    data_to_insert.append({
                        "vector": vec,
                        "text": chunk,
                        "source": doc.get("source", "unknown"),
                        "chunk_id": f"{doc.get('url', 'unknown')}_{idx}"
                    })
        
        if data_to_insert:
            # mode="append" 追加模式
            self.table.add(data_to_insert)
            print(f"✅ [Knowledge] Inserted {len(data_to_insert)} chunks (Dim: 768)")

    def search(self, query: str, limit: int = 5) -> str:
        """
        语义检索
        """
        print(f"🔍 [Retrieval] Searching for: {query[:30]}...")
        query_vec = get_embedding(query)
        
        # 向量搜索
        results = self.table.search(query_vec).limit(limit).to_list()
        
        context = ""
        for item in results:
            context += f"--- Source: {item['source']} ---\n{item['text']}\n\n"
            
        print(f"✅ [Retrieval] Found {len(results)} relevant chunks")
        return context