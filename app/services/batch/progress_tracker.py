"""
进度追踪器 - 实时监控批量任务的执行进度
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass

from sqlalchemy import select, func
from app.core.logging import get_logger
from app.core.database import get_db_session
from app.models.batch_task import BatchTask, TaskExecution, TaskStatus, ExecutionStatus

logger = get_logger(__name__)


@dataclass
class ProgressInfo:
    """进度信息"""
    batch_task_id: str
    total_items: int
    completed_items: int
    failed_items: int
    running_items: int
    pending_items: int
    progress_percentage: float
    estimated_remaining_seconds: Optional[int]
    current_status: TaskStatus
    start_time: Optional[datetime]
    avg_execution_time: Optional[float]


class ProgressTracker:
    """进度追踪器"""
    
    def __init__(self):
        self._tracking_tasks: Dict[str, asyncio.Task] = {}
        self._progress_callbacks: Dict[str, List[Callable]] = {}
        self._progress_cache: Dict[str, ProgressInfo] = {}
    
    def start_tracking(
        self,
        batch_task_id: str,
        progress_callback: Optional[Callable] = None,
        update_interval: int = 2
    ):
        """
        开始追踪批量任务进度
        
        Args:
            batch_task_id: 批量任务ID
            progress_callback: 进度回调函数
            update_interval: 更新间隔（秒）
        """
        if batch_task_id in self._tracking_tasks:
            logger.warning(f"任务已在追踪中: {batch_task_id}")
            return
        
        # 注册回调函数
        if progress_callback:
            if batch_task_id not in self._progress_callbacks:
                self._progress_callbacks[batch_task_id] = []
            self._progress_callbacks[batch_task_id].append(progress_callback)
        
        # 创建追踪任务
        task = asyncio.create_task(
            self._track_progress(batch_task_id, update_interval)
        )
        self._tracking_tasks[batch_task_id] = task
        
        logger.info(f"开始追踪任务进度: {batch_task_id}")
    
    def stop_tracking(self, batch_task_id: str):
        """
        停止追踪批量任务进度
        
        Args:
            batch_task_id: 批量任务ID
        """
        if batch_task_id in self._tracking_tasks:
            task = self._tracking_tasks[batch_task_id]
            task.cancel()
            del self._tracking_tasks[batch_task_id]
        
        if batch_task_id in self._progress_callbacks:
            del self._progress_callbacks[batch_task_id]
        
        if batch_task_id in self._progress_cache:
            del self._progress_cache[batch_task_id]
        
        logger.info(f"停止追踪任务进度: {batch_task_id}")
    
    def add_progress_callback(self, batch_task_id: str, callback: Callable):
        """
        添加进度回调函数
        
        Args:
            batch_task_id: 批量任务ID
            callback: 回调函数
        """
        if batch_task_id not in self._progress_callbacks:
            self._progress_callbacks[batch_task_id] = []
        self._progress_callbacks[batch_task_id].append(callback)
    
    def get_progress(self, batch_task_id: str) -> Optional[ProgressInfo]:
        """
        获取任务进度信息
        
        Args:
            batch_task_id: 批量任务ID
            
        Returns:
            进度信息或None
        """
        return self._progress_cache.get(batch_task_id)
    
    async def _track_progress(self, batch_task_id: str, update_interval: int):
        """
        追踪进度的核心逻辑
        
        Args:
            batch_task_id: 批量任务ID
            update_interval: 更新间隔
        """
        try:
            while True:
                # 获取最新进度信息
                progress_info = await self._calculate_progress(batch_task_id)
                
                if not progress_info:
                    logger.warning(f"无法获取任务进度信息: {batch_task_id}")
                    break
                
                # 更新缓存
                self._progress_cache[batch_task_id] = progress_info
                
                # 调用回调函数
                await self._notify_progress_callbacks(batch_task_id, progress_info)
                
                # 检查任务是否完成
                if progress_info.current_status in [
                    TaskStatus.COMPLETED, 
                    TaskStatus.FAILED, 
                    TaskStatus.CANCELLED
                ]:
                    logger.info(f"任务已完成，停止追踪: {batch_task_id}")
                    break
                
                # 等待下次更新
                await asyncio.sleep(update_interval)
                
        except asyncio.CancelledError:
            logger.info(f"进度追踪被取消: {batch_task_id}")
        except Exception as e:
            logger.error(f"进度追踪异常: {batch_task_id}, 错误: {e}")
        finally:
            # 清理资源
            if batch_task_id in self._tracking_tasks:
                del self._tracking_tasks[batch_task_id]
    
    async def _calculate_progress(self, batch_task_id: str) -> Optional[ProgressInfo]:
        """
        计算任务进度
        
        Args:
            batch_task_id: 批量任务ID
            
        Returns:
            进度信息
        """
        try:
            async with get_db_session() as db:
                # 获取批量任务基本信息
                result = await db.execute(
                    select(BatchTask).where(BatchTask.id == batch_task_id)
                )
                batch_task = result.scalar_one_or_none()
                
                if not batch_task:
                    return None
                
                # 获取执行统计
                result = await db.execute(
                    select(
                        func.count(TaskExecution.id).label("total_executions"),
                        func.sum(func.case((TaskExecution.status == ExecutionStatus.SUCCESS, 1), else_=0)).label("completed_count"),
                        func.sum(func.case((TaskExecution.status == ExecutionStatus.FAILED, 1), else_=0)).label("failed_count"),
                        func.sum(func.case((TaskExecution.status == ExecutionStatus.RUNNING, 1), else_=0)).label("running_count"),
                        func.sum(func.case((TaskExecution.status == ExecutionStatus.PENDING, 1), else_=0)).label("pending_count"),
                        func.avg(TaskExecution.execution_time_seconds).label("avg_execution_time")
                    )
                    .where(TaskExecution.batch_task_id == batch_task_id)
                )
                stats = result.first()
                
                # 计算进度百分比
                total_items = batch_task.total_items or stats.total_executions or 0
                completed_items = stats.completed_count or 0
                failed_items = stats.failed_count or 0
                running_items = stats.running_count or 0
                pending_items = stats.pending_count or 0
                
                if total_items > 0:
                    finished_items = completed_items + failed_items
                    progress_percentage = (finished_items / total_items) * 100
                else:
                    progress_percentage = 0.0
                
                # 估算剩余时间
                estimated_remaining_seconds = None
                avg_execution_time = stats.avg_execution_time
                
                if avg_execution_time and pending_items > 0:
                    # 考虑并发执行
                    max_concurrency = batch_task.max_concurrency or 1
                    remaining_batches = (pending_items + max_concurrency - 1) // max_concurrency
                    estimated_remaining_seconds = int(remaining_batches * avg_execution_time)
                
                return ProgressInfo(
                    batch_task_id=batch_task_id,
                    total_items=total_items,
                    completed_items=completed_items,
                    failed_items=failed_items,
                    running_items=running_items,
                    pending_items=pending_items,
                    progress_percentage=progress_percentage,
                    estimated_remaining_seconds=estimated_remaining_seconds,
                    current_status=TaskStatus(batch_task.status),
                    start_time=batch_task.started_at,
                    avg_execution_time=float(avg_execution_time) if avg_execution_time else None
                )
                
        except Exception as e:
            logger.error(f"计算任务进度失败: {batch_task_id}, 错误: {e}")
            return None
    
    async def _notify_progress_callbacks(self, batch_task_id: str, progress_info: ProgressInfo):
        """
        通知进度回调函数
        
        Args:
            batch_task_id: 批量任务ID
            progress_info: 进度信息
        """
        callbacks = self._progress_callbacks.get(batch_task_id, [])
        
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(progress_info)
                else:
                    callback(progress_info)
            except Exception as e:
                logger.error(f"进度回调函数执行失败: {batch_task_id}, 错误: {e}")
    
    def get_tracking_tasks(self) -> List[str]:
        """获取正在追踪的任务列表"""
        return list(self._tracking_tasks.keys())
    
    def is_tracking(self, batch_task_id: str) -> bool:
        """检查是否正在追踪指定任务"""
        return batch_task_id in self._tracking_tasks
    
    async def get_all_progress(self) -> Dict[str, ProgressInfo]:
        """
        获取所有正在追踪任务的进度信息
        
        Returns:
            任务ID到进度信息的映射
        """
        result = {}
        
        for batch_task_id in self._tracking_tasks.keys():
            progress_info = await self._calculate_progress(batch_task_id)
            if progress_info:
                result[batch_task_id] = progress_info
                self._progress_cache[batch_task_id] = progress_info
        
        return result
    
    def cleanup_completed_tasks(self):
        """清理已完成任务的追踪"""
        completed_tasks = []
        
        for batch_task_id, progress_info in self._progress_cache.items():
            if progress_info.current_status in [
                TaskStatus.COMPLETED, 
                TaskStatus.FAILED, 
                TaskStatus.CANCELLED
            ]:
                completed_tasks.append(batch_task_id)
        
        for batch_task_id in completed_tasks:
            self.stop_tracking(batch_task_id)
        
        if completed_tasks:
            logger.info(f"清理已完成任务的追踪: {completed_tasks}")


# 全局进度追踪器实例
progress_tracker = ProgressTracker() 