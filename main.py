from fastapi import FastAPI
from typing import Dict
from app.middreware.exception_handler import register_exception_handlers

def getapp() -> FastAPI:
    app = FastAPI(
        title="简单的 FastAPI 项目",
        description="这是一个使用 FastAPI 构建的示例项目",
        version="1.0.0",
        openapi_tags=[
            {
                "name": "系统",
                "description": "系统相关接口"
            }
        ],
        docs_url="/api/docs", 
        redoc_url="/api/redoc", 
    )
    register_exception_handlers(app)
    return app

app = getapp()
