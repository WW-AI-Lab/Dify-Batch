"""
任务恢复服务 - 处理服务器重启后的任务恢复
"""
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.core.database import get_db_session
from app.models.batch_task import BatchTask, TaskExecution, TaskStatus, ExecutionStatus
from app.models.workflow import Workflow

logger = get_logger(__name__)


class TaskRecoveryService:
    """任务恢复服务"""
    
    def __init__(self):
        self.recovered_tasks: List[str] = []
        self.failed_recoveries: List[str] = []
    
    async def recover_interrupted_tasks(self) -> Dict[str, Any]:
        """
        恢复被中断的任务
        
        Returns:
            恢复结果统计
        """
        logger.info("🔄 开始检查和恢复被中断的批量任务...")
        
        try:
            # 查找需要恢复的任务
            interrupted_tasks = await self._find_interrupted_tasks()
            
            if not interrupted_tasks:
                logger.info("✅ 没有发现需要恢复的任务")
                return {
                    "total_found": 0,
                    "recovered": 0,
                    "failed": 0,
                    "recovered_tasks": [],
                    "failed_tasks": []
                }
            
            logger.info(f"📋 发现 {len(interrupted_tasks)} 个需要恢复的任务")
            
            # 逐个恢复任务
            for task in interrupted_tasks:
                try:
                    await self._recover_single_task(task)
                    self.recovered_tasks.append(task.id)
                    logger.info(f"✅ 任务恢复成功: {task.id} - {task.name}")
                except Exception as e:
                    self.failed_recoveries.append(task.id)
                    logger.error(f"❌ 任务恢复失败: {task.id} - {task.name}, 错误: {e}")
            
            # 返回恢复结果
            result = {
                "total_found": len(interrupted_tasks),
                "recovered": len(self.recovered_tasks),
                "failed": len(self.failed_recoveries),
                "recovered_tasks": self.recovered_tasks,
                "failed_tasks": self.failed_recoveries
            }
            
            logger.info(f"🎯 任务恢复完成: 发现 {result['total_found']} 个，成功恢复 {result['recovered']} 个，失败 {result['failed']} 个")
            
            return result
            
        except Exception as e:
            logger.error(f"💥 任务恢复过程发生异常: {e}")
            raise
    
    async def _find_interrupted_tasks(self) -> List[BatchTask]:
        """
        查找被中断的任务
        
        Returns:
            需要恢复的批量任务列表
        """
        try:
            async with get_db_session() as db:
                # 查找状态为 RUNNING 的批量任务
                result = await db.execute(
                    select(BatchTask)
                    .where(BatchTask.status == TaskStatus.RUNNING)
                    .options(selectinload(BatchTask.executions))
                    .order_by(BatchTask.created_at)
                )
                
                interrupted_tasks = result.scalars().all()
                
                # 过滤出真正需要恢复的任务
                tasks_to_recover = []
                for task in interrupted_tasks:
                    if await self._should_recover_task(task):
                        tasks_to_recover.append(task)
                    else:
                        # 更新已完成但状态错误的任务
                        await self._fix_completed_task_status(task)
                
                return tasks_to_recover
                
        except Exception as e:
            logger.error(f"查找被中断任务失败: {e}")
            raise
    
    async def _should_recover_task(self, task: BatchTask) -> bool:
        """
        判断任务是否需要恢复
        
        Args:
            task: 批量任务
            
        Returns:
            是否需要恢复
        """
        try:
            # 检查是否有未完成的子任务
            async with get_db_session() as db:
                result = await db.execute(
                    select(TaskExecution)
                    .where(
                        TaskExecution.batch_task_id == task.id,
                        TaskExecution.status == ExecutionStatus.PENDING
                    )
                )
                
                pending_executions = result.scalars().all()
                
                # 如果有 PENDING 状态的子任务，则需要恢复
                if pending_executions:
                    logger.info(f"📝 任务 {task.id} 有 {len(pending_executions)} 个待处理的子任务，需要恢复")
                    return True
                
                # 检查是否有 RUNNING 状态的子任务（可能因为服务器重启而中断）
                result = await db.execute(
                    select(TaskExecution)
                    .where(
                        TaskExecution.batch_task_id == task.id,
                        TaskExecution.status == ExecutionStatus.RUNNING
                    )
                )
                
                running_executions = result.scalars().all()
                
                if running_executions:
                    logger.info(f"🔄 任务 {task.id} 有 {len(running_executions)} 个运行中的子任务，需要恢复")
                    # 将 RUNNING 状态的子任务重置为 PENDING
                    await db.execute(
                        update(TaskExecution)
                        .where(
                            TaskExecution.batch_task_id == task.id,
                            TaskExecution.status == ExecutionStatus.RUNNING
                        )
                        .values(status=ExecutionStatus.PENDING)
                    )
                    await db.commit()
                    return True
                
                return False
                
        except Exception as e:
            logger.error(f"检查任务恢复需求失败: {task.id}, 错误: {e}")
            return False
    
    async def _fix_completed_task_status(self, task: BatchTask):
        """
        修复已完成但状态错误的任务
        
        Args:
            task: 批量任务
        """
        try:
            async with get_db_session() as db:
                # 统计子任务状态
                result = await db.execute(
                    select(TaskExecution)
                    .where(TaskExecution.batch_task_id == task.id)
                )
                
                executions = result.scalars().all()
                
                if not executions:
                    return
                
                total_count = len(executions)
                completed_count = sum(1 for e in executions if e.status == ExecutionStatus.SUCCESS)
                failed_count = sum(1 for e in executions if e.status == ExecutionStatus.FAILED)
                pending_count = sum(1 for e in executions if e.status == ExecutionStatus.PENDING)
                running_count = sum(1 for e in executions if e.status == ExecutionStatus.RUNNING)
                
                # 如果所有子任务都已完成，更新批量任务状态
                if pending_count == 0 and running_count == 0:
                    final_status = TaskStatus.COMPLETED if failed_count == 0 else TaskStatus.COMPLETED
                    
                    await db.execute(
                        update(BatchTask)
                        .where(BatchTask.id == task.id)
                        .values(
                            status=final_status,
                            completed_items=completed_count,
                            failed_items=failed_count,
                            progress_percentage=100.0,
                            completed_at=datetime.utcnow()
                        )
                    )
                    await db.commit()
                    
                    logger.info(f"🔧 修复任务状态: {task.id} -> {final_status}")
                
        except Exception as e:
            logger.error(f"修复任务状态失败: {task.id}, 错误: {e}")
    
    async def _recover_single_task(self, task: BatchTask):
        """
        恢复单个批量任务
        
        Args:
            task: 要恢复的批量任务
        """
        try:
            logger.info(f"🔄 开始恢复任务: {task.id} - {task.name}")
            
            # 获取工作流配置
            workflow_config = await self._get_workflow_config(task.workflow_id)
            if not workflow_config:
                raise Exception(f"无法获取工作流配置: {task.workflow_id}")
            
            # 导入批量处理器（避免循环导入）
            from app.services.batch.batch_processor import BatchProcessor
            from app.services.batch.progress_tracker import progress_tracker
            
            # 创建批量处理器实例
            batch_processor = BatchProcessor()
            
            # 启动批量任务恢复
            success = await batch_processor.start_batch_task(
                task.id,
                workflow_config,
                is_recovery=True  # 标记为恢复模式
            )
            
            if not success:
                raise Exception("批量处理器启动失败")
            
            # 开始进度追踪
            progress_tracker.start_tracking(task.id)
            
            logger.info(f"✅ 任务恢复启动成功: {task.id}")
            
        except Exception as e:
            logger.error(f"恢复单个任务失败: {task.id}, 错误: {e}")
            
            # 更新任务状态为失败
            try:
                async with get_db_session() as db:
                    await db.execute(
                        update(BatchTask)
                        .where(BatchTask.id == task.id)
                        .values(
                            status=TaskStatus.FAILED,
                            error_message=f"任务恢复失败: {str(e)}",
                            completed_at=datetime.utcnow()
                        )
                    )
                    await db.commit()
            except Exception as update_error:
                logger.error(f"更新任务状态失败: {task.id}, 错误: {update_error}")
            
            raise
    
    async def _get_workflow_config(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        获取工作流配置
        
        Args:
            workflow_id: 工作流ID
            
        Returns:
            工作流配置字典
        """
        try:
            async with get_db_session() as db:
                result = await db.execute(
                    select(Workflow).where(Workflow.id == workflow_id)
                )
                
                workflow = result.scalar_one_or_none()
                
                if not workflow:
                    logger.error(f"工作流不存在: {workflow_id}")
                    return None
                
                return {
                    "base_url": workflow.base_url,
                    "api_key": workflow.api_key
                }
                
        except Exception as e:
            logger.error(f"获取工作流配置失败: {workflow_id}, 错误: {e}")
            return None
    
    def get_recovery_summary(self) -> Dict[str, Any]:
        """
        获取恢复结果摘要
        
        Returns:
            恢复结果摘要
        """
        return {
            "recovered_count": len(self.recovered_tasks),
            "failed_count": len(self.failed_recoveries),
            "recovered_tasks": self.recovered_tasks.copy(),
            "failed_tasks": self.failed_recoveries.copy()
        }


# 创建全局实例
task_recovery_service = TaskRecoveryService() 