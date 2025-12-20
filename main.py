# main.py
from fastapi import FastAPI
from app.api.research import router as research_router
import uvicorn
from app.core.config import settings

app = FastAPI(title="Deep Research Backend")

# 注册路由
app.include_router(research_router, prefix="/api")

if __name__ == "__main__":
    print(f"🚀 Starting server on {settings.API_HOST}:{settings.API_PORT}")
    uvicorn.run(
        "main:app", 
        host=settings.API_HOST, 
        port=settings.API_PORT, 
        reload=True
    )