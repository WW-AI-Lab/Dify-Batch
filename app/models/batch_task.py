"""
批量任务数据库模型
"""
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
from sqlalchemy import Column, String, Text, JSON, Boolean, DateTime, Integer, ForeignKey, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from .base import Base


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"      # 等待执行
    RUNNING = "running"      # 执行中
    PAUSED = "paused"        # 已暂停
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 执行失败
    CANCELLED = "cancelled"  # 已取消


class ExecutionStatus(str, Enum):
    """单个执行状态枚举"""
    PENDING = "pending"      # 等待执行
    RUNNING = "running"      # 执行中
    SUCCESS = "success"      # 执行成功
    FAILED = "failed"        # 执行失败
    SKIPPED = "skipped"      # 已跳过


class LogLevel(str, Enum):
    """日志级别枚举"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class BatchTask(Base):
    """批量任务模型"""
    __tablename__ = "batch_tasks"
    
    # 主键和时间戳
    id = Column(String(50), primary_key=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # 基本信息
    name = Column(String(200), nullable=False, comment="任务名称")
    description = Column(Text, comment="任务描述")
    workflow_id = Column(String(50), nullable=False, comment="关联的工作流ID")
    
    # 任务状态
    status = Column(String(20), nullable=False, default=TaskStatus.PENDING, comment="任务状态")
    
    # 文件信息
    original_filename = Column(String(500), comment="原始文件名")
    file_path = Column(String(500), comment="上传文件路径")
    result_path = Column(String(500), comment="结果文件路径")
    
    # 执行统计
    total_items = Column(Integer, nullable=False, default=0, comment="总项目数")
    completed_items = Column(Integer, nullable=False, default=0, comment="已完成项目数")
    failed_items = Column(Integer, nullable=False, default=0, comment="失败项目数")
    skipped_items = Column(Integer, nullable=False, default=0, comment="跳过项目数")
    
    # 执行配置
    max_concurrency = Column(Integer, default=3, comment="最大并发数")
    retry_count = Column(Integer, default=2, comment="重试次数")
    timeout_seconds = Column(Integer, default=300, comment="超时时间（秒）")
    
    # 时间记录
    started_at = Column(DateTime, comment="开始执行时间")
    completed_at = Column(DateTime, comment="完成时间")
    
    # 进度信息
    progress_percentage = Column(Float, default=0.0, comment="进度百分比")
    estimated_remaining_seconds = Column(Integer, comment="预计剩余时间（秒）")
    
    # 错误信息
    error_message = Column(Text, comment="错误信息")
    error_details = Column(JSON, comment="错误详情")
    
    # 关联关系
    executions = relationship("TaskExecution", back_populates="batch_task", cascade="all, delete-orphan")
    
    def __init__(self, **kwargs):
        if 'id' not in kwargs:
            kwargs['id'] = str(uuid.uuid4())
        super().__init__(**kwargs)
    
    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self.status == TaskStatus.RUNNING
    
    @property
    def is_completed(self) -> bool:
        """是否已完成"""
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_items == 0:
            return 0.0
        return (self.completed_items / self.total_items) * 100
    
    @property
    def duration_seconds(self) -> Optional[int]:
        """执行时长（秒）"""
        if not self.started_at:
            return None
        end_time = self.completed_at or datetime.utcnow()
        return int((end_time - self.started_at).total_seconds())
    
    def update_progress(self):
        """更新进度信息"""
        if self.total_items > 0:
            completed = self.completed_items + self.failed_items + self.skipped_items
            self.progress_percentage = (completed / self.total_items) * 100
        else:
            self.progress_percentage = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "workflow_id": self.workflow_id,
            "status": self.status,
            "original_filename": self.original_filename,
            "file_path": self.file_path,
            "result_path": self.result_path,
            "total_items": self.total_items,
            "completed_items": self.completed_items,
            "failed_items": self.failed_items,
            "skipped_items": self.skipped_items,
            "max_concurrency": self.max_concurrency,
            "retry_count": self.retry_count,
            "timeout_seconds": self.timeout_seconds,
            "progress_percentage": self.progress_percentage,
            "success_rate": self.success_rate,
            "duration_seconds": self.duration_seconds,
            "estimated_remaining_seconds": self.estimated_remaining_seconds,
            "error_message": self.error_message,
            "error_details": self.error_details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class TaskExecution(Base):
    """单个任务执行记录模型"""
    __tablename__ = "task_executions"
    
    # 主键和时间戳
    id = Column(String(50), primary_key=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # 关联信息
    batch_task_id = Column(String(50), ForeignKey("batch_tasks.id"), nullable=False, comment="批量任务ID")
    workflow_run_id = Column(String(100), comment="Dify工作流运行ID")
    task_id = Column(String(100), comment="Dify任务ID")
    
    # 执行信息
    row_index = Column(Integer, nullable=False, comment="Excel行索引")
    status = Column(String(20), nullable=False, default=ExecutionStatus.PENDING, comment="执行状态")
    
    # 输入输出数据
    inputs = Column(JSON, comment="输入参数")
    outputs = Column(JSON, comment="输出结果")
    
    # 执行统计
    retry_count = Column(Integer, default=0, comment="重试次数")
    execution_time_seconds = Column(Float, comment="执行时间（秒）")
    
    # 时间记录
    started_at = Column(DateTime, comment="开始执行时间")
    completed_at = Column(DateTime, comment="完成时间")
    
    # 错误信息
    error_message = Column(Text, comment="错误信息")
    error_details = Column(JSON, comment="错误详情")
    
    # 关联关系
    batch_task = relationship("BatchTask", back_populates="executions")
    logs = relationship("ExecutionLog", back_populates="task_execution", cascade="all, delete-orphan")
    
    def __init__(self, **kwargs):
        if 'id' not in kwargs:
            kwargs['id'] = str(uuid.uuid4())
        super().__init__(**kwargs)
    
    @property
    def is_completed(self) -> bool:
        """是否已完成"""
        return self.status in [ExecutionStatus.SUCCESS, ExecutionStatus.FAILED, ExecutionStatus.SKIPPED]
    
    @property
    def is_success(self) -> bool:
        """是否执行成功"""
        return self.status == ExecutionStatus.SUCCESS
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "batch_task_id": self.batch_task_id,
            "workflow_run_id": self.workflow_run_id,
            "task_id": self.task_id,
            "row_index": self.row_index,
            "status": self.status,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "retry_count": self.retry_count,
            "execution_time_seconds": self.execution_time_seconds,
            "error_message": self.error_message,
            "error_details": self.error_details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class ExecutionLog(Base):
    """执行日志模型"""
    __tablename__ = "execution_logs"
    
    # 主键和时间戳
    id = Column(String(50), primary_key=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # 关联信息
    task_execution_id = Column(String(50), ForeignKey("task_executions.id"), nullable=False, comment="任务执行ID")
    
    # 日志信息
    level = Column(String(10), nullable=False, comment="日志级别")
    message = Column(Text, nullable=False, comment="日志消息")
    details = Column(JSON, comment="详细信息")
    
    # 关联关系
    task_execution = relationship("TaskExecution", back_populates="logs")
    
    def __init__(self, **kwargs):
        if 'id' not in kwargs:
            kwargs['id'] = str(uuid.uuid4())
        super().__init__(**kwargs)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "task_execution_id": self.task_execution_id,
            "level": self.level,
            "message": self.message,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        } 