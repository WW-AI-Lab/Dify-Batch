"""
API路由模块
"""
from fastapi import APIRouter
from .workflows import router as workflows_router
from .batch import router as batch_router
from .tasks import router as tasks_router
from .config import router as config_router

# 创建主API路由器
api_router = APIRouter()

# 注册子路由
api_router.include_router(workflows_router, prefix="/workflows", tags=["workflows"])
api_router.include_router(batch_router, prefix="/batch", tags=["batch"])
api_router.include_router(tasks_router, prefix="/tasks", tags=["tasks"])
api_router.include_router(config_router, prefix="/config", tags=["config"]) 