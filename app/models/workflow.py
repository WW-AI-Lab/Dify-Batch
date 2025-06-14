"""
工作流数据库模型
"""
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import Column, String, Text, JSON, Boolean, DateTime
from sqlalchemy.sql import func

from .base import Base


class Workflow(Base):
    """工作流模型"""
    __tablename__ = "workflows"
    
    # 主键和时间戳
    id = Column(String(50), primary_key=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # 基本信息
    name = Column(String(200), nullable=False, comment="工作流名称")
    description = Column(Text, comment="工作流描述")
    
    # API配置
    base_url = Column(String(500), nullable=False, comment="Dify API基础URL")
    api_key = Column(String(200), nullable=False, comment="API密钥")
    
    # 应用信息（从Dify API获取）
    app_name = Column(String(200), comment="应用名称")
    app_description = Column(Text, comment="应用描述")
    app_tags = Column(JSON, comment="应用标签")
    
    # 参数信息（从Dify API获取）
    parameters = Column(JSON, comment="工作流参数")
    
    # 状态
    is_active = Column(Boolean, default=True, comment="是否激活")
    last_sync_at = Column(DateTime, comment="最后同步时间")
    
    def __init__(self, **kwargs):
        if 'id' not in kwargs:
            kwargs['id'] = str(uuid.uuid4())
        super().__init__(**kwargs)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "base_url": self.base_url,
            "api_key": self.api_key,
            "app_name": self.app_name,
            "app_description": self.app_description,
            "app_tags": self.app_tags,
            "parameters": self.parameters,
            "is_active": self.is_active,
            "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class WorkflowConfig(Base):
    """工作流配置模型（用于存储用户自定义配置）"""
    __tablename__ = "workflow_configs"
    
    # 主键和时间戳
    id = Column(String(50), primary_key=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    workflow_id = Column(String(50), nullable=False, comment="工作流ID")
    config_key = Column(String(100), nullable=False, comment="配置键")
    config_value = Column(JSON, comment="配置值")
    description = Column(Text, comment="配置描述")
    
    def __init__(self, **kwargs):
        if 'id' not in kwargs:
            kwargs['id'] = str(uuid.uuid4())
        super().__init__(**kwargs)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "config_key": self.config_key,
            "config_value": self.config_value,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        } 