"""
任务管理器 - 批量任务的CRUD操作和状态管理
"""
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.core.database import get_db_session
from app.models.batch_task import BatchTask, TaskExecution, ExecutionLog, TaskStatus, ExecutionStatus
from app.models.workflow import Workflow

logger = get_logger(__name__)


class TaskManager:
    """任务管理器"""
    
    async def create_batch_task(
        self,
        workflow_id: str,
        name: str,
        file_path: str,
        original_filename: str,
        description: Optional[str] = None,
        max_concurrency: int = 3,
        retry_count: int = 2,
        timeout_seconds: int = 300
    ) -> BatchTask:
        """
        创建批量任务
        
        Args:
            workflow_id: 工作流ID
            name: 任务名称
            file_path: 文件路径
            original_filename: 原始文件名
            description: 任务描述
            max_concurrency: 最大并发数
            retry_count: 重试次数
            timeout_seconds: 超时时间
            
        Returns:
            创建的批量任务
        """
        try:
            async with get_db_session() as db:
                batch_task = BatchTask(
                    workflow_id=workflow_id,
                    name=name,
                    description=description,
                    file_path=file_path,
                    original_filename=original_filename,
                    max_concurrency=max_concurrency,
                    retry_count=retry_count,
                    timeout_seconds=timeout_seconds,
                    status=TaskStatus.PENDING
                )
                
                db.add(batch_task)
                await db.commit()
                await db.refresh(batch_task)
                
                logger.info(f"批量任务创建成功: {batch_task.id} - {name}")
                return batch_task
                
        except Exception as e:
            logger.error(f"创建批量任务失败: {e}")
            raise
    
    async def get_batch_task(self, batch_task_id: str) -> Optional[BatchTask]:
        """
        获取批量任务
        
        Args:
            batch_task_id: 批量任务ID
            
        Returns:
            批量任务对象或None
        """
        try:
            async with get_db_session() as db:
                result = await db.execute(
                    select(BatchTask)
                    .where(BatchTask.id == batch_task_id)
                    .options(selectinload(BatchTask.executions))
                )
                return result.scalar_one_or_none()
                
        except Exception as e:
            logger.error(f"获取批量任务失败: {batch_task_id}, 错误: {e}")
            return None
    
    async def list_batch_tasks(
        self,
        page: int = 1,
        size: int = 20,
        status: Optional[TaskStatus] = None,
        workflow_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取批量任务列表
        
        Args:
            page: 页码
            size: 每页大小
            status: 状态过滤
            workflow_id: 工作流ID过滤
            
        Returns:
            任务列表和分页信息
        """
        try:
            async with get_db_session() as db:
                # 构建查询条件
                query = select(BatchTask)
                count_query = select(func.count(BatchTask.id))
                
                if status:
                    query = query.where(BatchTask.status == status)
                    count_query = count_query.where(BatchTask.status == status)
                
                if workflow_id:
                    query = query.where(BatchTask.workflow_id == workflow_id)
                    count_query = count_query.where(BatchTask.workflow_id == workflow_id)
                
                # 获取总数
                total_result = await db.execute(count_query)
                total = total_result.scalar()
                
                # 分页查询
                offset = (page - 1) * size
                query = query.order_by(BatchTask.created_at.desc()).offset(offset).limit(size)
                
                result = await db.execute(query)
                tasks = result.scalars().all()
                
                return {
                    "tasks": [task.to_dict() for task in tasks],
                    "total": total,
                    "page": page,
                    "size": size,
                    "pages": (total + size - 1) // size if total > 0 else 0
                }
                
        except Exception as e:
            logger.error(f"获取批量任务列表失败: {e}")
            return {
                "tasks": [],
                "total": 0,
                "page": page,
                "size": size,
                "pages": 0
            }
    
    async def update_batch_task_status(
        self,
        batch_task_id: str,
        status: TaskStatus,
        error_message: Optional[str] = None
    ) -> bool:
        """
        更新批量任务状态
        
        Args:
            batch_task_id: 批量任务ID
            status: 新状态
            error_message: 错误信息
            
        Returns:
            是否更新成功
        """
        try:
            async with get_db_session() as db:
                update_data = {"status": status}
                
                if error_message:
                    update_data["error_message"] = error_message
                
                if status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    update_data["completed_at"] = datetime.utcnow()
                elif status == TaskStatus.RUNNING:
                    update_data["started_at"] = datetime.utcnow()
                
                await db.execute(
                    update(BatchTask)
                    .where(BatchTask.id == batch_task_id)
                    .values(**update_data)
                )
                await db.commit()
                
                logger.info(f"批量任务状态更新成功: {batch_task_id} -> {status}")
                return True
                
        except Exception as e:
            logger.error(f"更新批量任务状态失败: {batch_task_id}, 错误: {e}")
            return False
    
    async def delete_batch_task(self, batch_task_id: str) -> bool:
        """
        删除批量任务
        
        Args:
            batch_task_id: 批量任务ID
            
        Returns:
            是否删除成功
        """
        try:
            async with get_db_session() as db:
                # 获取任务信息
                result = await db.execute(
                    select(BatchTask).where(BatchTask.id == batch_task_id)
                )
                batch_task = result.scalar_one_or_none()
                
                if not batch_task:
                    logger.warning(f"批量任务不存在: {batch_task_id}")
                    return False
                
                # 删除相关文件
                if batch_task.file_path and Path(batch_task.file_path).exists():
                    Path(batch_task.file_path).unlink()
                    logger.info(f"删除上传文件: {batch_task.file_path}")
                
                if batch_task.result_path and Path(batch_task.result_path).exists():
                    Path(batch_task.result_path).unlink()
                    logger.info(f"删除结果文件: {batch_task.result_path}")
                
                # 删除数据库记录（级联删除相关的执行记录和日志）
                await db.execute(
                    delete(BatchTask).where(BatchTask.id == batch_task_id)
                )
                await db.commit()
                
                logger.info(f"批量任务删除成功: {batch_task_id}")
                return True
                
        except Exception as e:
            logger.error(f"删除批量任务失败: {batch_task_id}, 错误: {e}")
            return False
    
    async def get_task_executions(
        self,
        batch_task_id: str,
        status: Optional[ExecutionStatus] = None
    ) -> List[TaskExecution]:
        """
        获取任务执行记录
        
        Args:
            batch_task_id: 批量任务ID
            status: 状态过滤
            
        Returns:
            执行记录列表
        """
        try:
            async with get_db_session() as db:
                query = select(TaskExecution).where(TaskExecution.batch_task_id == batch_task_id)
                
                if status:
                    query = query.where(TaskExecution.status == status)
                
                query = query.order_by(TaskExecution.row_index)
                
                result = await db.execute(query)
                return result.scalars().all()
                
        except Exception as e:
            logger.error(f"获取任务执行记录失败: {batch_task_id}, 错误: {e}")
            return []
    
    async def get_execution_logs(
        self,
        execution_id: str,
        limit: int = 100
    ) -> List[ExecutionLog]:
        """
        获取执行日志
        
        Args:
            execution_id: 执行记录ID
            limit: 日志数量限制
            
        Returns:
            日志列表
        """
        try:
            async with get_db_session() as db:
                result = await db.execute(
                    select(ExecutionLog)
                    .where(ExecutionLog.task_execution_id == execution_id)
                    .order_by(ExecutionLog.created_at.desc())
                    .limit(limit)
                )
                return result.scalars().all()
                
        except Exception as e:
            logger.error(f"获取执行日志失败: {execution_id}, 错误: {e}")
            return []
    
    async def get_batch_task_statistics(self, batch_task_id: str) -> Dict[str, Any]:
        """
        获取批量任务统计信息
        
        Args:
            batch_task_id: 批量任务ID
            
        Returns:
            统计信息
        """
        try:
            async with get_db_session() as db:
                # 获取批量任务基本信息
                result = await db.execute(
                    select(BatchTask).where(BatchTask.id == batch_task_id)
                )
                batch_task = result.scalar_one_or_none()
                
                if not batch_task:
                    return {}
                
                # 获取执行统计
                result = await db.execute(
                    select(
                        func.count(TaskExecution.id).label("total_executions"),
                        func.sum(func.case((TaskExecution.status == ExecutionStatus.SUCCESS, 1), else_=0)).label("success_count"),
                        func.sum(func.case((TaskExecution.status == ExecutionStatus.FAILED, 1), else_=0)).label("failed_count"),
                        func.sum(func.case((TaskExecution.status == ExecutionStatus.PENDING, 1), else_=0)).label("pending_count"),
                        func.sum(func.case((TaskExecution.status == ExecutionStatus.RUNNING, 1), else_=0)).label("running_count"),
                        func.avg(TaskExecution.execution_time_seconds).label("avg_execution_time")
                    )
                    .where(TaskExecution.batch_task_id == batch_task_id)
                )
                stats = result.first()
                
                return {
                    "batch_task": batch_task.to_dict(),
                    "execution_stats": {
                        "total_executions": stats.total_executions or 0,
                        "success_count": stats.success_count or 0,
                        "failed_count": stats.failed_count or 0,
                        "pending_count": stats.pending_count or 0,
                        "running_count": stats.running_count or 0,
                        "avg_execution_time": float(stats.avg_execution_time) if stats.avg_execution_time else 0.0,
                        "success_rate": (stats.success_count / stats.total_executions * 100) if stats.total_executions else 0.0
                    }
                }
                
        except Exception as e:
            logger.error(f"获取批量任务统计失败: {batch_task_id}, 错误: {e}")
            return {}
    
    async def cleanup_old_tasks(self, days: int = 30) -> int:
        """
        清理旧的批量任务
        
        Args:
            days: 保留天数
            
        Returns:
            清理的任务数量
        """
        try:
            from datetime import timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            async with get_db_session() as db:
                # 获取要删除的任务
                result = await db.execute(
                    select(BatchTask)
                    .where(
                        BatchTask.created_at < cutoff_date,
                        BatchTask.status.in_([TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED])
                    )
                )
                old_tasks = result.scalars().all()
                
                cleaned_count = 0
                for task in old_tasks:
                    if await self.delete_batch_task(task.id):
                        cleaned_count += 1
                
                logger.info(f"清理旧任务完成，共清理 {cleaned_count} 个任务")
                return cleaned_count
                
        except Exception as e:
            logger.error(f"清理旧任务失败: {e}")
            return 0
    
    async def get_failed_executions(self, batch_task_id: str) -> List[Dict[str, Any]]:
        """
        获取批量任务中失败的执行记录
        
        Args:
            batch_task_id: 批量任务ID
            
        Returns:
            失败的执行记录列表
        """
        try:
            async with get_db_session() as db:
                result = await db.execute(
                    select(TaskExecution)
                    .where(
                        TaskExecution.batch_task_id == batch_task_id,
                        TaskExecution.status == ExecutionStatus.FAILED
                    )
                    .order_by(TaskExecution.row_index)
                )
                
                failed_executions = result.scalars().all()
                
                return [execution.to_dict() for execution in failed_executions]
                
        except Exception as e:
            logger.error(f"获取失败执行记录失败: {batch_task_id}, 错误: {e}")
            return []
    
    async def retry_failed_execution(self, batch_task_id: str, execution_id: str) -> bool:
        """
        重试单个失败的执行任务
        
        Args:
            batch_task_id: 批量任务ID
            execution_id: 执行记录ID
            
        Returns:
            是否重试成功
        """
        try:
            async with get_db_session() as db:
                # 检查执行记录是否存在且为失败状态
                result = await db.execute(
                    select(TaskExecution)
                    .where(
                        TaskExecution.id == execution_id,
                        TaskExecution.batch_task_id == batch_task_id,
                        TaskExecution.status == ExecutionStatus.FAILED
                    )
                )
                
                execution = result.scalar_one_or_none()
                
                if not execution:
                    logger.warning(f"执行记录不存在或状态不允许重试: {execution_id}")
                    return False
                
                # 重置执行状态
                await db.execute(
                    update(TaskExecution)
                    .where(TaskExecution.id == execution_id)
                    .values(
                        status=ExecutionStatus.PENDING,
                        error_message=None,
                        error_details=None,
                        started_at=None,
                        completed_at=None,
                        execution_time_seconds=None
                    )
                )
                
                # 更新批量任务统计
                await db.execute(
                    update(BatchTask)
                    .where(BatchTask.id == batch_task_id)
                    .values(
                        failed_items=BatchTask.failed_items - 1,
                        progress_percentage=((BatchTask.completed_items + BatchTask.failed_items - 1) / BatchTask.total_items) * 100
                    )
                )
                
                await db.commit()
                
                logger.info(f"执行任务重试成功: {execution_id}")
                
                # 如果批量任务已完成，重新启动它
                await self._restart_batch_task_if_needed(batch_task_id)
                
                return True
                
        except Exception as e:
            logger.error(f"重试失败执行任务失败: {execution_id}, 错误: {e}")
            return False
    
    async def retry_all_failed_executions(self, batch_task_id: str) -> Dict[str, Any]:
        """
        重试批量任务中所有失败的子任务
        
        Args:
            batch_task_id: 批量任务ID
            
        Returns:
            重试结果
        """
        try:
            async with get_db_session() as db:
                # 获取所有失败的执行记录
                result = await db.execute(
                    select(TaskExecution)
                    .where(
                        TaskExecution.batch_task_id == batch_task_id,
                        TaskExecution.status == ExecutionStatus.FAILED
                    )
                )
                
                failed_executions = result.scalars().all()
                
                if not failed_executions:
                    return {
                        "success": False,
                        "message": "没有找到失败的任务",
                        "retried_count": 0,
                        "failed_count": 0
                    }
                
                failed_count = len(failed_executions)
                
                # 批量重置失败任务状态
                await db.execute(
                    update(TaskExecution)
                    .where(
                        TaskExecution.batch_task_id == batch_task_id,
                        TaskExecution.status == ExecutionStatus.FAILED
                    )
                    .values(
                        status=ExecutionStatus.PENDING,
                        error_message=None,
                        error_details=None,
                        started_at=None,
                        completed_at=None,
                        execution_time_seconds=None
                    )
                )
                
                # 更新批量任务统计
                await db.execute(
                    update(BatchTask)
                    .where(BatchTask.id == batch_task_id)
                    .values(
                        failed_items=0,
                        progress_percentage=(BatchTask.completed_items / BatchTask.total_items) * 100
                    )
                )
                
                await db.commit()
                
                logger.info(f"批量重试失败任务成功: {batch_task_id}, 重试数量: {failed_count}")
                
                # 重新启动批量任务
                await self._restart_batch_task_if_needed(batch_task_id)
                
                return {
                    "success": True,
                    "retried_count": failed_count,
                    "failed_count": 0
                }
                
        except Exception as e:
            logger.error(f"批量重试失败任务失败: {batch_task_id}, 错误: {e}")
            return {
                "success": False,
                "message": f"重试失败: {str(e)}",
                "retried_count": 0,
                "failed_count": 0
            }
    
    async def _restart_batch_task_if_needed(self, batch_task_id: str):
        """
        如果需要，重新启动批量任务
        
        Args:
            batch_task_id: 批量任务ID
        """
        try:
            async with get_db_session() as db:
                # 检查批量任务状态
                result = await db.execute(
                    select(BatchTask).where(BatchTask.id == batch_task_id)
                )
                
                batch_task = result.scalar_one_or_none()
                
                if not batch_task:
                    return
                
                # 如果任务已完成但有待处理的子任务，重新启动
                if batch_task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                    # 检查是否有待处理的子任务
                    result = await db.execute(
                        select(TaskExecution)
                        .where(
                            TaskExecution.batch_task_id == batch_task_id,
                            TaskExecution.status == ExecutionStatus.PENDING
                        )
                    )
                    
                    pending_executions = result.scalars().all()
                    
                    if pending_executions:
                        # 获取工作流配置
                        from app.models.workflow import Workflow
                        result = await db.execute(
                            select(Workflow).where(Workflow.id == batch_task.workflow_id)
                        )
                        workflow = result.scalar_one_or_none()
                        
                        if workflow:
                            workflow_config = {
                                "base_url": workflow.base_url,
                                "api_key": workflow.api_key
                            }
                            
                            # 重新启动批量任务
                            from app.services.batch.batch_processor import BatchProcessor
                            from app.services.batch.progress_tracker import progress_tracker
                            
                            # 创建批量处理器实例
                            batch_processor = BatchProcessor()
                            
                            success = await batch_processor.start_batch_task(
                                batch_task_id,
                                workflow_config,
                                is_recovery=True
                            )
                            
                            if success:
                                progress_tracker.start_tracking(batch_task_id)
                                logger.info(f"批量任务重新启动成功: {batch_task_id}")
                            else:
                                logger.error(f"批量任务重新启动失败: {batch_task_id}")
                
        except Exception as e:
            logger.error(f"重新启动批量任务失败: {batch_task_id}, 错误: {e}") 