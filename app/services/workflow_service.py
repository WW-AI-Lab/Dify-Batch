"""
工作流服务层
"""
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from app.models.workflow import Workflow, WorkflowConfig
from app.core.database import get_db_session
from app.services.dify.client import DifyClient
from app.services.dify.models import WorkflowParameters, WorkflowParameter, WorkflowParameterType
from app.core.exceptions import DifyAPIException, DatabaseException
from app.core.logging import get_logger

logger = get_logger(__name__)


class WorkflowService:
    """工作流服务"""
    
    def __init__(self):
        self.logger = logger
    
    async def get_all_workflows(self) -> List[Dict[str, Any]]:
        """获取所有工作流"""
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(Workflow).where(Workflow.is_active == True).order_by(Workflow.created_at.desc())
                )
                workflows = result.scalars().all()
                return [workflow.to_dict() for workflow in workflows]
        except Exception as e:
            self.logger.error(f"获取工作流列表失败: {str(e)}")
            raise DatabaseException(f"获取工作流列表失败: {str(e)}")
    
    async def get_workflow_by_id(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取工作流"""
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(Workflow).where(Workflow.id == workflow_id)
                )
                workflow = result.scalar_one_or_none()
                return workflow.to_dict() if workflow else None
        except Exception as e:
            self.logger.error(f"获取工作流失败: {str(e)}")
            raise DatabaseException(f"获取工作流失败: {str(e)}")
    
    async def create_workflow(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建新工作流"""
        try:
            # 验证API连接并获取应用信息
            app_info, parameters = await self._validate_and_fetch_workflow_info(
                workflow_data["base_url"], 
                workflow_data["api_key"]
            )
            
            # 创建工作流记录
            workflow = Workflow(
                name=workflow_data["name"],
                description=workflow_data.get("description"),
                base_url=workflow_data["base_url"],
                api_key=workflow_data["api_key"],
                app_name=app_info.get("name"),
                app_description=app_info.get("description"),
                app_tags=app_info.get("tags", []),
                parameters=parameters.dict() if parameters else None,
                last_sync_at=datetime.now()
            )
            
            async with get_db_session() as session:
                session.add(workflow)
                await session.commit()
                await session.refresh(workflow)
                
            self.logger.info(f"工作流创建成功: {workflow.name} ({workflow.id})")
            return workflow.to_dict()
            
        except DifyAPIException as e:
            self.logger.error(f"创建工作流时API验证失败: {e.message}")
            raise e
        except Exception as e:
            self.logger.error(f"创建工作流失败: {str(e)}")
            raise DatabaseException(f"创建工作流失败: {str(e)}")
    
    async def update_workflow(self, workflow_id: str, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新工作流"""
        try:
            async with get_db_session() as session:
                # 获取现有工作流
                result = await session.execute(
                    select(Workflow).where(Workflow.id == workflow_id)
                )
                workflow = result.scalar_one_or_none()
                if not workflow:
                    raise DatabaseException("工作流不存在")
                
                # 如果API配置有变化，重新验证
                if ("base_url" in workflow_data and workflow_data["base_url"] != workflow.base_url) or \
                   ("api_key" in workflow_data and workflow_data["api_key"] != workflow.api_key):
                    app_info, parameters = await self._validate_and_fetch_workflow_info(
                        workflow_data.get("base_url", workflow.base_url),
                        workflow_data.get("api_key", workflow.api_key)
                    )
                    workflow_data["app_name"] = app_info.get("name")
                    workflow_data["app_description"] = app_info.get("description")
                    workflow_data["app_tags"] = app_info.get("tags", [])
                    workflow_data["parameters"] = parameters.dict() if parameters else None
                    workflow_data["last_sync_at"] = datetime.now()
                
                # 更新字段
                for key, value in workflow_data.items():
                    if hasattr(workflow, key):
                        setattr(workflow, key, value)
                
                await session.commit()
                await session.refresh(workflow)
                
            self.logger.info(f"工作流更新成功: {workflow.name} ({workflow.id})")
            return workflow.to_dict()
            
        except DifyAPIException as e:
            self.logger.error(f"更新工作流时API验证失败: {e.message}")
            raise e
        except Exception as e:
            self.logger.error(f"更新工作流失败: {str(e)}")
            raise DatabaseException(f"更新工作流失败: {str(e)}")
    
    async def delete_workflow(self, workflow_id: str) -> bool:
        """删除工作流（软删除）"""
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    update(Workflow)
                    .where(Workflow.id == workflow_id)
                    .values(is_active=False)
                )
                
                if result.rowcount == 0:
                    raise DatabaseException("工作流不存在")
                
                await session.commit()
                
            self.logger.info(f"工作流删除成功: {workflow_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"删除工作流失败: {str(e)}")
            raise DatabaseException(f"删除工作流失败: {str(e)}")
    
    async def sync_workflow_info(self, workflow_id: str) -> Dict[str, Any]:
        """同步工作流信息"""
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(Workflow).where(Workflow.id == workflow_id)
                )
                workflow = result.scalar_one_or_none()
                if not workflow:
                    raise DatabaseException("工作流不存在")
                
                # 重新获取应用信息和参数
                app_info, parameters = await self._validate_and_fetch_workflow_info(
                    workflow.base_url, 
                    workflow.api_key
                )
                
                # 更新信息
                workflow.app_name = app_info.get("name")
                workflow.app_description = app_info.get("description")
                workflow.app_tags = app_info.get("tags", [])
                workflow.parameters = parameters.dict() if parameters else None
                workflow.last_sync_at = datetime.now()
                
                await session.commit()
                await session.refresh(workflow)
                
            self.logger.info(f"工作流信息同步成功: {workflow.name} ({workflow.id})")
            return workflow.to_dict()
            
        except DifyAPIException as e:
            self.logger.error(f"同步工作流信息时API调用失败: {e.message}")
            raise e
        except Exception as e:
            self.logger.error(f"同步工作流信息失败: {str(e)}")
            raise DatabaseException(f"同步工作流信息失败: {str(e)}")
    
    async def get_workflow_parameters(self, workflow_id: str) -> Optional[WorkflowParameters]:
        """获取工作流参数（优先从缓存获取）"""
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(Workflow).where(Workflow.id == workflow_id)
                )
                workflow = result.scalar_one_or_none()
                if not workflow:
                    raise DatabaseException("工作流不存在")
                
                # 如果有缓存的参数且不超过1小时，直接返回
                if workflow.parameters and workflow.last_sync_at:
                    time_diff = datetime.now() - workflow.last_sync_at
                    if time_diff.total_seconds() < 3600:  # 1小时
                        return WorkflowParameters(**workflow.parameters)
                
                # 否则重新获取
                _, parameters = await self._validate_and_fetch_workflow_info(
                    workflow.base_url, 
                    workflow.api_key
                )
                
                # 更新缓存
                workflow.parameters = parameters.dict() if parameters else None
                workflow.last_sync_at = datetime.now()
                await session.commit()
                
                return parameters
                
        except DifyAPIException as e:
            self.logger.error(f"获取工作流参数时API调用失败: {e.message}")
            raise e
        except Exception as e:
            self.logger.error(f"获取工作流参数失败: {str(e)}")
            raise DatabaseException(f"获取工作流参数失败: {str(e)}")
    
    async def _validate_and_fetch_workflow_info(self, base_url: str, api_key: str) -> tuple[Dict[str, Any], WorkflowParameters]:
        """验证API并获取工作流信息"""
        try:
            # 在测试模式下返回模拟数据
            from app.core.config import settings
            if getattr(settings, 'TEST_MODE', False):
                self.logger.info("测试模式：使用模拟工作流信息")
                from app.services.dify.models import WorkflowParameter
                
                mock_app_info = {
                    "name": "测试工作流应用",
                    "description": "用于Phase 4.1测试的模拟工作流",
                    "tags": ["test", "batch"]
                }
                
                mock_parameters = WorkflowParameters(
                    workflow_id="test-workflow-001",
                    workflow_name="测试工作流",
                    parameters=[
                        WorkflowParameter(name="query", type="text", required=True),
                        WorkflowParameter(name="context", type="text", required=False)
                    ]
                )
                
                return mock_app_info, mock_parameters
            
            # 正常模式：创建临时客户端
            client = DifyClient(base_url=base_url, api_key=api_key)
            
            async with client:
                # 获取应用基本信息
                app_info = await client.get_app_info()
                
                # 获取应用参数
                parameters = await client.get_workflow_parameters()
                
                return app_info, parameters
                
        except Exception as e:
            self.logger.error(f"验证API配置失败: {str(e)}")
            raise DifyAPIException(f"API配置验证失败: {str(e)}")


# 创建全局服务实例
workflow_service = WorkflowService() 