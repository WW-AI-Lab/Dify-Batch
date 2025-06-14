"""
Web界面路由模块
"""
from fastapi import APIRouter
from .routes import router as web_routes_router

# 创建Web路由器
web_router = APIRouter()

# 注册Web路由
web_router.include_router(web_routes_router) 