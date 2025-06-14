"""
Dify API相关数据模型
"""
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class WorkflowParameterType(str, Enum):
    """工作流参数类型"""
    TEXT = "text"
    NUMBER = "number"
    SELECT = "select"
    FILE = "file"
    BOOLEAN = "boolean"
    JSON = "json"


class WorkflowParameter(BaseModel):
    """工作流参数模型"""
    name: str = Field(description="参数名称")
    type: WorkflowParameterType = Field(description="参数类型")
    required: bool = Field(default=False, description="是否必需")
    description: Optional[str] = Field(default=None, description="参数描述")
    default_value: Optional[Any] = Field(default=None, description="默认值")
    options: Optional[List[str]] = Field(default=None, description="选项列表（用于select类型）")
    min_value: Optional[Union[int, float]] = Field(default=None, description="最小值（用于number类型）")
    max_value: Optional[Union[int, float]] = Field(default=None, description="最大值（用于number类型）")
    max_length: Optional[int] = Field(default=None, description="最大长度（用于text类型）")


class WorkflowInfo(BaseModel):
    """工作流信息模型"""
    id: str = Field(description="工作流ID")
    name: str = Field(description="工作流名称")
    description: Optional[str] = Field(default=None, description="工作流描述")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")


class WorkflowParameters(BaseModel):
    """工作流参数集合"""
    workflow_id: str = Field(description="工作流ID")
    workflow_name: str = Field(description="工作流名称")
    parameters: List[WorkflowParameter] = Field(description="参数列表")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowParameters":
        """从字典创建WorkflowParameters对象"""
        # 转换参数列表
        parameters = []
        if "parameters" in data and isinstance(data["parameters"], list):
            for param_data in data["parameters"]:
                if isinstance(param_data, dict):
                    # 确保type字段是正确的枚举值
                    if "type" in param_data:
                        param_type = param_data["type"]
                        if param_type not in [e.value for e in WorkflowParameterType]:
                            param_type = WorkflowParameterType.TEXT.value
                        param_data["type"] = param_type
                    
                    parameters.append(WorkflowParameter(**param_data))
        
        return cls(
            workflow_id=data.get("workflow_id", ""),
            workflow_name=data.get("workflow_name", ""),
            parameters=parameters
        )


class WorkflowExecutionRequest(BaseModel):
    """工作流执行请求"""
    inputs: Dict[str, Any] = Field(description="输入参数")
    response_mode: str = Field(default="blocking", description="响应模式：blocking或streaming")
    user: Optional[str] = Field(default="batch-user", description="用户标识")


class WorkflowExecutionResponse(BaseModel):
    """工作流执行响应"""
    workflow_run_id: str = Field(description="工作流运行ID")
    task_id: str = Field(description="任务ID")
    data: Dict[str, Any] = Field(description="响应数据")


class WorkflowRunStatus(BaseModel):
    """工作流运行状态"""
    id: str = Field(description="运行ID")
    workflow_id: str = Field(description="工作流ID")
    status: TaskStatus = Field(description="运行状态")
    inputs: Optional[Dict[str, Any]] = Field(default=None, description="输入参数")
    outputs: Optional[Dict[str, Any]] = Field(default=None, description="输出结果")
    error: Optional[str] = Field(default=None, description="错误信息")
    total_steps: Optional[int] = Field(default=None, description="总步骤数")
    total_tokens: Optional[int] = Field(default=None, description="总token数")
    created_at: Optional[int] = Field(default=None, description="创建时间戳")
    finished_at: Optional[int] = Field(default=None, description="完成时间戳")
    elapsed_time: Optional[float] = Field(default=None, description="执行时间（秒）")


class WorkflowLogEntry(BaseModel):
    """工作流日志条目"""
    id: str = Field(description="日志ID")
    workflow_run_id: str = Field(description="工作流运行ID")
    level: str = Field(description="日志级别")
    message: str = Field(description="日志消息")
    timestamp: datetime = Field(description="时间戳")
    details: Optional[Dict[str, Any]] = Field(default=None, description="详细信息")


class DifyAPIError(BaseModel):
    """Dify API错误响应"""
    code: str = Field(description="错误代码")
    message: str = Field(description="错误消息")
    status: int = Field(description="HTTP状态码")
    details: Optional[Dict[str, Any]] = Field(default=None, description="错误详情") 