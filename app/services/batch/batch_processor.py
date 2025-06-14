"""
批量处理器 - 核心批量执行引擎
"""
import asyncio
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.core.database import get_db_session
from app.core.exceptions import DifyAPIException, FileProcessingException
from app.models.batch_task import BatchTask, TaskExecution, ExecutionLog, TaskStatus, ExecutionStatus, LogLevel
from app.services.dify.client import DifyClient
from app.services.dify.mock_client import MockDifyClient  # 导入模拟客户端
from app.services.file import ExcelService
from .progress_tracker import ProgressTracker

logger = get_logger(__name__)

# 测试模式标志 - 从环境变量或配置中获取
import os
TEST_MODE = os.getenv('TEST_MODE', 'false').lower() == 'true'

class BatchProcessor:
    """批量处理器"""
    
    def __init__(self):
        self.excel_service = ExcelService()
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._task_semaphores: Dict[str, asyncio.Semaphore] = {}
    
    async def start_batch_task(
        self,
        batch_task_id: str,
        workflow_config: Dict[str, Any],
        progress_callback: Optional[Callable] = None,
        is_recovery: bool = False
    ) -> bool:
        """
        启动批量任务
        
        Args:
            batch_task_id: 批量任务ID
            workflow_config: 工作流配置（包含base_url和api_key）
            progress_callback: 进度回调函数
            is_recovery: 是否为恢复模式
            
        Returns:
            是否启动成功
        """
        try:
            logger.info(f"开始启动批量任务: {batch_task_id}")
            
            # 检查任务是否已在运行
            if batch_task_id in self._running_tasks:
                logger.warning(f"批量任务已在运行: {batch_task_id}")
                return False
            
            # 创建异步任务
            if is_recovery:
                task = asyncio.create_task(
                    self._resume_batch_task(batch_task_id, workflow_config, progress_callback)
                )
            else:
                task = asyncio.create_task(
                    self._execute_batch_task(batch_task_id, workflow_config, progress_callback)
                )
            self._running_tasks[batch_task_id] = task
            
            logger.info(f"批量任务启动成功: {batch_task_id}")
            return True
            
        except Exception as e:
            logger.error(f"启动批量任务失败: {batch_task_id}, 错误: {e}")
            return False
    
    async def stop_batch_task(self, batch_task_id: str) -> bool:
        """
        停止批量任务
        
        Args:
            batch_task_id: 批量任务ID
            
        Returns:
            是否停止成功
        """
        try:
            if batch_task_id not in self._running_tasks:
                logger.warning(f"批量任务未在运行: {batch_task_id}")
                return False
            
            # 取消任务
            task = self._running_tasks[batch_task_id]
            task.cancel()
            
            try:
                await task
            except asyncio.CancelledError:
                pass
            
            # 清理资源
            del self._running_tasks[batch_task_id]
            if batch_task_id in self._task_semaphores:
                del self._task_semaphores[batch_task_id]
            
            # 更新任务状态
            async with get_db_session() as db:
                await db.execute(
                    update(BatchTask)
                    .where(BatchTask.id == batch_task_id)
                    .values(
                        status=TaskStatus.CANCELLED,
                        completed_at=datetime.utcnow()
                    )
                )
                await db.commit()
            
            logger.info(f"批量任务已停止: {batch_task_id}")
            return True
            
        except Exception as e:
            logger.error(f"停止批量任务失败: {batch_task_id}, 错误: {e}")
            return False
    
    async def pause_batch_task(self, batch_task_id: str) -> bool:
        """
        暂停批量任务
        
        Args:
            batch_task_id: 批量任务ID
            
        Returns:
            是否暂停成功
        """
        try:
            async with get_db_session() as db:
                result = await db.execute(
                    select(BatchTask).where(BatchTask.id == batch_task_id)
                )
                batch_task = result.scalar_one_or_none()
                
                if not batch_task or batch_task.status != TaskStatus.RUNNING:
                    return False
                
                # 更新状态为暂停
                await db.execute(
                    update(BatchTask)
                    .where(BatchTask.id == batch_task_id)
                    .values(status=TaskStatus.PAUSED)
                )
                await db.commit()
            
            logger.info(f"批量任务已暂停: {batch_task_id}")
            return True
            
        except Exception as e:
            logger.error(f"暂停批量任务失败: {batch_task_id}, 错误: {e}")
            return False
    
    async def resume_batch_task(self, batch_task_id: str) -> bool:
        """
        恢复批量任务
        
        Args:
            batch_task_id: 批量任务ID
            
        Returns:
            是否恢复成功
        """
        try:
            async with get_db_session() as db:
                result = await db.execute(
                    select(BatchTask).where(BatchTask.id == batch_task_id)
                )
                batch_task = result.scalar_one_or_none()
                
                if not batch_task or batch_task.status != TaskStatus.PAUSED:
                    return False
                
                # 更新状态为运行中
                await db.execute(
                    update(BatchTask)
                    .where(BatchTask.id == batch_task_id)
                    .values(status=TaskStatus.RUNNING)
                )
                await db.commit()
            
            logger.info(f"批量任务已恢复: {batch_task_id}")
            return True
            
        except Exception as e:
            logger.error(f"恢复批量任务失败: {batch_task_id}, 错误: {e}")
            return False
    
    async def _execute_batch_task(
        self,
        batch_task_id: str,
        workflow_config: Dict[str, Any],
        progress_callback: Optional[Callable] = None
    ):
        """
        执行批量任务的核心逻辑
        """
        start_time = time.time()
        
        try:
            async with get_db_session() as db:
                # 获取批量任务信息
                result = await db.execute(
                    select(BatchTask).where(BatchTask.id == batch_task_id)
                )
                batch_task = result.scalar_one_or_none()
                
                if not batch_task:
                    logger.error(f"批量任务不存在: {batch_task_id}")
                    return
                
                # 更新任务状态为运行中
                batch_task.status = TaskStatus.RUNNING
                batch_task.started_at = datetime.utcnow()
                await db.commit()
                
                logger.info(f"开始执行批量任务: {batch_task.name}")
                
                # 解析Excel文件
                if not batch_task.file_path or not Path(batch_task.file_path).exists():
                    raise FileProcessingException("批量任务文件不存在")
                
                data_rows, columns = self.excel_service.parse_excel_file(batch_task.file_path)
                
                if not data_rows:
                    raise FileProcessingException("Excel文件中没有有效数据")
                
                # 更新总项目数
                batch_task.total_items = len(data_rows)
                await db.commit()
                
                # 创建任务执行记录
                task_executions = []
                for idx, row_data in enumerate(data_rows):
                    execution = TaskExecution(
                        batch_task_id=batch_task_id,
                        row_index=idx,
                        inputs=row_data,
                        status=ExecutionStatus.PENDING
                    )
                    task_executions.append(execution)
                    db.add(execution)
                
                await db.commit()
                
                # 创建并发控制信号量
                semaphore = asyncio.Semaphore(batch_task.max_concurrency)
                self._task_semaphores[batch_task_id] = semaphore
                
                # 并发执行所有任务
                tasks = []
                for execution in task_executions:
                    task = asyncio.create_task(
                        self._execute_single_task(
                            batch_task_id, 
                            execution.id, 
                            execution.inputs,
                            semaphore,
                            batch_task.retry_count,
                            batch_task.timeout_seconds,
                            workflow_config  # 传递配置而不是客户端实例
                        )
                    )
                    tasks.append(task)
                
                # 等待所有任务完成
                await asyncio.gather(*tasks, return_exceptions=True)
                
                # 更新最终状态
                await self._finalize_batch_task(batch_task_id, start_time)
                
                if progress_callback:
                    await progress_callback(batch_task_id, 100, "completed")
                
        except asyncio.CancelledError:
            logger.info(f"批量任务被取消: {batch_task_id}")
            raise
        except Exception as e:
            logger.error(f"批量任务执行失败: {batch_task_id}, 错误: {e}")
            await self._handle_batch_task_error(batch_task_id, str(e))
        finally:
            # 清理资源
            if batch_task_id in self._running_tasks:
                del self._running_tasks[batch_task_id]
            if batch_task_id in self._task_semaphores:
                del self._task_semaphores[batch_task_id]
    
    async def _resume_batch_task(
        self,
        batch_task_id: str,
        workflow_config: Dict[str, Any],
        progress_callback: Optional[Callable] = None
    ):
        """
        恢复批量任务的执行（断点续传）
        """
        start_time = time.time()
        
        try:
            async with get_db_session() as db:
                # 获取批量任务信息
                result = await db.execute(
                    select(BatchTask).where(BatchTask.id == batch_task_id)
                )
                batch_task = result.scalar_one_or_none()
                
                if not batch_task:
                    logger.error(f"批量任务不存在: {batch_task_id}")
                    return
                
                logger.info(f"🔄 开始恢复批量任务: {batch_task.name}")
                
                # 确保任务状态为运行中
                batch_task.status = TaskStatus.RUNNING
                if not batch_task.started_at:
                    batch_task.started_at = datetime.utcnow()
                await db.commit()
                
                # 获取所有待处理的执行记录
                result = await db.execute(
                    select(TaskExecution)
                    .where(
                        TaskExecution.batch_task_id == batch_task_id,
                        TaskExecution.status == ExecutionStatus.PENDING
                    )
                    .order_by(TaskExecution.row_index)
                )
                pending_executions = result.scalars().all()
                
                if not pending_executions:
                    logger.info(f"没有待处理的子任务，检查任务完成状态: {batch_task_id}")
                    await self._finalize_batch_task(batch_task_id, start_time)
                    return
                
                logger.info(f"📋 发现 {len(pending_executions)} 个待处理的子任务")
                
                # 重新计算任务统计
                await self._recalculate_task_stats(batch_task_id)
                
                # 创建并发控制信号量
                semaphore = asyncio.Semaphore(batch_task.max_concurrency)
                self._task_semaphores[batch_task_id] = semaphore
                
                # 并发执行待处理的任务
                tasks = []
                for execution in pending_executions:
                    task = asyncio.create_task(
                        self._execute_single_task(
                            batch_task_id, 
                            execution.id, 
                            execution.inputs,
                            semaphore,
                            batch_task.retry_count,
                            batch_task.timeout_seconds,
                            workflow_config
                        )
                    )
                    tasks.append(task)
                
                # 等待所有任务完成
                await asyncio.gather(*tasks, return_exceptions=True)
                
                # 更新最终状态
                await self._finalize_batch_task(batch_task_id, start_time)
                
                if progress_callback:
                    await progress_callback(batch_task_id, 100, "completed")
                
                logger.info(f"✅ 批量任务恢复完成: {batch_task.name}")
                
        except asyncio.CancelledError:
            logger.info(f"批量任务恢复被取消: {batch_task_id}")
            raise
        except Exception as e:
            logger.error(f"批量任务恢复失败: {batch_task_id}, 错误: {e}")
            await self._handle_batch_task_error(batch_task_id, str(e))
        finally:
            # 清理资源
            if batch_task_id in self._running_tasks:
                del self._running_tasks[batch_task_id]
            if batch_task_id in self._task_semaphores:
                del self._task_semaphores[batch_task_id]
    
    async def _recalculate_task_stats(self, batch_task_id: str):
        """
        重新计算任务统计信息
        
        Args:
            batch_task_id: 批量任务ID
        """
        try:
            async with get_db_session() as db:
                # 统计各状态的子任务数量
                result = await db.execute(
                    select(TaskExecution)
                    .where(TaskExecution.batch_task_id == batch_task_id)
                )
                executions = result.scalars().all()
                
                if not executions:
                    return
                
                total_items = len(executions)
                completed_items = sum(1 for e in executions if e.status == ExecutionStatus.SUCCESS)
                failed_items = sum(1 for e in executions if e.status == ExecutionStatus.FAILED)
                pending_items = sum(1 for e in executions if e.status == ExecutionStatus.PENDING)
                
                # 计算进度
                progress_percentage = ((completed_items + failed_items) / total_items) * 100 if total_items > 0 else 0
                
                # 更新批量任务统计
                await db.execute(
                    update(BatchTask)
                    .where(BatchTask.id == batch_task_id)
                    .values(
                        total_items=total_items,
                        completed_items=completed_items,
                        failed_items=failed_items,
                        progress_percentage=progress_percentage
                    )
                )
                await db.commit()
                
                logger.info(f"📊 重新计算任务统计: {batch_task_id} - 总计:{total_items}, 完成:{completed_items}, 失败:{failed_items}, 待处理:{pending_items}")
                
        except Exception as e:
            logger.error(f"重新计算任务统计失败: {batch_task_id}, 错误: {e}")
    
    async def _execute_single_task(
        self,
        batch_task_id: str,
        execution_id: str,
        inputs: Dict[str, Any],
        semaphore: asyncio.Semaphore,
        max_retries: int,
        timeout_seconds: int,
        workflow_config: Dict[str, Any]
    ):
        """执行单个任务"""
        async with semaphore:
            retry_count = 0
            start_time = time.time()
            
            logger.info(f"🎯 开始执行单个任务")
            logger.info(f"   批量任务ID: {batch_task_id}")
            logger.info(f"   执行ID: {execution_id}")
            logger.info(f"   输入参数: {json.dumps(inputs, ensure_ascii=False, indent=2)}")
            logger.info(f"   最大重试次数: {max_retries}")
            logger.info(f"   超时时间: {timeout_seconds}秒")
            
            # 为每个任务创建独立的Dify客户端实例
            if TEST_MODE:
                logger.info("🎭 使用模拟Dify客户端进行测试")
                dify_client = MockDifyClient(
                    base_url=workflow_config["base_url"],
                    api_key=workflow_config["api_key"]
                )
            else:
                logger.info("🔗 使用真实Dify客户端")
                dify_client = DifyClient(
                    base_url=workflow_config["base_url"],
                    api_key=workflow_config["api_key"]
                )
            
            while retry_count <= max_retries:
                try:
                    logger.info(f"🔄 执行尝试 {retry_count + 1}/{max_retries + 1}")
                    
                    # 更新执行状态
                    await self._update_execution_status(
                        execution_id, 
                        ExecutionStatus.RUNNING,
                        started_at=datetime.utcnow()
                    )
                    
                    # 执行工作流
                    logger.info(f"📡 调用Dify工作流API...")
                    async with dify_client:
                        response = await asyncio.wait_for(
                            dify_client.execute_workflow(inputs),
                            timeout=timeout_seconds
                        )
                    
                    # 处理成功结果
                    execution_time = time.time() - start_time
                    logger.info(f"✅ 工作流执行成功")
                    logger.info(f"   执行时间: {execution_time:.2f}秒")
                    logger.info(f"   响应数据: {json.dumps(response.data, ensure_ascii=False, indent=2)}")
                    
                    await self._update_execution_status(
                        execution_id,
                        ExecutionStatus.SUCCESS,
                        outputs=response.data,
                        execution_time_seconds=execution_time,
                        completed_at=datetime.utcnow()
                    )
                    
                    # 更新批量任务统计
                    await self._update_batch_task_stats(batch_task_id, "completed")
                    logger.info(f"📊 已更新批量任务统计 (completed)")
                    return
                    
                except Exception as e:
                    retry_count += 1
                    execution_time = time.time() - start_time
                    
                    logger.error(f"❌ 工作流执行失败 [尝试 {retry_count}/{max_retries + 1}]")
                    logger.error(f"   错误类型: {type(e).__name__}")
                    logger.error(f"   错误信息: {str(e)}")
                    logger.error(f"   执行时间: {execution_time:.2f}秒")
                    
                    if retry_count <= max_retries:
                        wait_time = 2 ** retry_count
                        logger.warning(f"⏳ 等待 {wait_time} 秒后重试...")
                        await asyncio.sleep(wait_time)  # 指数退避
                    else:
                        # 所有重试都失败了
                        logger.error(f"💀 所有重试都失败，任务最终失败")
                        await self._update_execution_status(
                            execution_id,
                            ExecutionStatus.FAILED,
                            error_message=str(e),
                            execution_time_seconds=execution_time,
                            retry_count=retry_count - 1,
                            completed_at=datetime.utcnow()
                        )
                        await self._update_batch_task_stats(batch_task_id, "failed")
                        logger.info(f"📊 已更新批量任务统计 (failed)")
    
    async def _update_execution_status(self, execution_id: str, status: ExecutionStatus, **kwargs):
        """更新执行状态"""
        async with get_db_session() as db:
            update_data = {"status": status}
            update_data.update(kwargs)
            
            await db.execute(
                update(TaskExecution)
                .where(TaskExecution.id == execution_id)
                .values(**update_data)
            )
            await db.commit()
    
    async def _update_batch_task_stats(self, batch_task_id: str, result_type: str):
        """更新批量任务统计"""
        async with get_db_session() as db:
            if result_type == "completed":
                await db.execute(
                    update(BatchTask)
                    .where(BatchTask.id == batch_task_id)
                    .values(completed_items=BatchTask.completed_items + 1)
                )
            elif result_type == "failed":
                await db.execute(
                    update(BatchTask)
                    .where(BatchTask.id == batch_task_id)
                    .values(failed_items=BatchTask.failed_items + 1)
                )
            
            await db.commit()
    
    async def _finalize_batch_task(self, batch_task_id: str, start_time: float):
        """完成批量任务"""
        async with get_db_session() as db:
            result = await db.execute(
                select(BatchTask).where(BatchTask.id == batch_task_id)
            )
            batch_task = result.scalar_one_or_none()
            
            if not batch_task:
                return
            
            # 计算最终状态
            total_processed = batch_task.completed_items + batch_task.failed_items + batch_task.skipped_items
            
            if total_processed == batch_task.total_items:
                final_status = TaskStatus.COMPLETED
            else:
                final_status = TaskStatus.FAILED
            
            # 更新任务状态
            batch_task.status = final_status
            batch_task.completed_at = datetime.utcnow()
            batch_task.progress_percentage = 100.0
            
            await db.commit()
            
            # 生成结果文件
            await self._generate_result_file(batch_task_id)
    
    async def _handle_batch_task_error(self, batch_task_id: str, error_message: str):
        """处理批量任务错误"""
        async with get_db_session() as db:
            await db.execute(
                update(BatchTask)
                .where(BatchTask.id == batch_task_id)
                .values(
                    status=TaskStatus.FAILED,
                    error_message=error_message,
                    completed_at=datetime.utcnow()
                )
            )
            await db.commit()
    
    async def _generate_result_file(self, batch_task_id: str):
        """生成结果文件"""
        try:
            async with get_db_session() as db:
                # 获取批量任务信息
                result = await db.execute(
                    select(BatchTask).where(BatchTask.id == batch_task_id)
                )
                batch_task = result.scalar_one_or_none()
                
                if not batch_task or not batch_task.file_path:
                    return
                
                # 获取所有执行结果
                result = await db.execute(
                    select(TaskExecution)
                    .where(TaskExecution.batch_task_id == batch_task_id)
                    .order_by(TaskExecution.row_index)
                )
                executions = result.scalars().all()
                
                # 构建结果数据
                results = []
                for execution in executions:
                    if execution.status == ExecutionStatus.SUCCESS:
                        # 提取实际的输出内容
                        output_text = "执行成功"
                        if execution.outputs:
                            if isinstance(execution.outputs, dict):
                                # 检查是否有 outputs 字段（Dify API 返回结构）
                                if 'outputs' in execution.outputs and isinstance(execution.outputs['outputs'], dict):
                                    outputs_dict = execution.outputs['outputs']
                                    # 如果内层还有 outputs 字段，继续递归处理
                                    if 'outputs' in outputs_dict and isinstance(outputs_dict['outputs'], dict):
                                        outputs_dict = outputs_dict['outputs']
                                    
                                    # 提取所有键值对的内容
                                    output_parts = []
                                    for key, value in outputs_dict.items():
                                        if value is not None and str(value).strip():
                                            output_parts.append(str(value))
                                    
                                    if output_parts:
                                        output_text = '\n'.join(output_parts) if len(output_parts) > 1 else output_parts[0]
                                    else:
                                        output_text = "无输出内容"
                                
                                # 兼容旧的直接 output 字段格式
                                elif 'output' in execution.outputs:
                                    output_text = execution.outputs['output']
                                
                                # 如果直接就是 outputs 的内容（没有嵌套的 outputs 字段）
                                else:
                                    # 提取所有非系统字段的内容
                                    system_fields = {'id', 'workflow_id', 'status', 'error', 'elapsed_time', 
                                                   'total_tokens', 'total_steps', 'created_at', 'finished_at'}
                                    output_parts = []
                                    for key, value in execution.outputs.items():
                                        if key not in system_fields and value is not None and str(value).strip():
                                            output_parts.append(str(value))
                                    
                                    if output_parts:
                                        output_text = '\n'.join(output_parts) if len(output_parts) > 1 else output_parts[0]
                                    else:
                                        output_text = str(execution.outputs)
                            else:
                                output_text = str(execution.outputs)
                        
                        results.append({
                            "success": True,
                            "output": output_text
                        })
                    else:
                        results.append({
                            "success": False,
                            "error": execution.error_message or "执行失败"
                        })
                
                # 生成结果文件
                from app.core.config import settings
                result_dir = Path(settings.RESULT_DIR)
                result_dir.mkdir(exist_ok=True)
                
                result_filename = f"result_{batch_task_id}.xlsx"
                result_path = result_dir / result_filename
                
                self.excel_service.generate_result_file(
                    batch_task.file_path,
                    results,
                    str(result_path)
                )
                
                # 更新结果文件路径
                batch_task.result_path = str(result_path)
                await db.commit()
                
                logger.info(f"结果文件生成完成: {result_path}")
                
        except Exception as e:
            logger.error(f"生成结果文件失败: {batch_task_id}, 错误: {e}")
    
    def get_running_tasks(self) -> List[str]:
        """获取正在运行的任务列表"""
        return list(self._running_tasks.keys())
    
    def is_task_running(self, batch_task_id: str) -> bool:
        """检查任务是否正在运行"""
        return batch_task_id in self._running_tasks 