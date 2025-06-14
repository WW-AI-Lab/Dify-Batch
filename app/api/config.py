"""
配置管理API
"""
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


class ConfigResponse(BaseModel):
    """配置响应模型"""
    dify_base_url: str
    app_name: str
    app_version: str


@router.get("/", response_model=ConfigResponse)
async def get_config():
    """
    获取系统配置信息
    
    Returns:
        系统配置信息
    """
    try:
        return ConfigResponse(
            dify_base_url=settings.DIFY_BASE_URL,
            app_name=settings.APP_NAME,
            app_version=settings.APP_VERSION
        )
    except Exception as e:
        logger.exception("获取配置信息时发生错误")
        raise HTTPException(status_code=500, detail="获取配置信息失败") 