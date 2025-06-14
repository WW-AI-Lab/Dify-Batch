"""
批量处理API
"""
import os
import uuid
from typing import List, Dict, Any
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import FileResponse, JSONResponse

from app.services.file import ExcelService, FileValidator
from app.services.dify import DifyClient
from app.services.batch import BatchProcessor, TaskManager, ProgressTracker
from app.models.batch_task import TaskStatus
from app.models.workflow import Workflow
from app.core.exceptions import FileProcessingException, DifyAPIException
from app.core.logging import get_logger
from app.core.config import settings
from app.core.database import get_db_session
from sqlalchemy import select

logger = get_logger(__name__)
router = APIRouter()

# 初始化服务
excel_service = ExcelService()
file_validator = FileValidator()
batch_processor = BatchProcessor()
task_manager = TaskManager()
progress_tracker = ProgressTracker()


@router.post("/upload")
async def upload_batch_file(
    file: UploadFile = File(...),
    workflow_id: str = Form(None)
):
    """
    上传批量处理文件
    
    Args:
        file: 上传的Excel文件
        workflow_id: 工作流ID（可选）
        
    Returns:
        上传结果和文件验证信息
    """
    try:
        logger.info(f"开始处理文件上传: {file.filename}")
        
        # 生成唯一文件名
        file_id = str(uuid.uuid4())
        file_extension = Path(file.filename).suffix.lower()
        
        if file_extension not in ['.xlsx', '.xls']:
            raise HTTPException(status_code=400, detail="只支持Excel文件格式(.xlsx, .xls)")
        
        # 保存上传文件
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(exist_ok=True)
        
        file_path = upload_dir / f"{file_id}{file_extension}"
        
        # 写入文件
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        logger.info(f"文件保存成功: {file_path}")
        
        # 验证文件
        validation_result = file_validator.validate_upload_file(str(file_path), file.filename)
        
        if not validation_result["valid"]:
            # 删除无效文件
            os.remove(file_path)
            raise HTTPException(
                status_code=400, 
                detail={
                    "message": "文件验证失败",
                    "errors": validation_result["errors"],
                    "warnings": validation_result["warnings"]
                }
            )
        
        # 解析Excel文件
        try:
            data_rows, columns = excel_service.parse_excel_file(str(file_path))
            
            # 如果提供了workflow_id，验证数据结构
            validation_errors = []
            if workflow_id:
                try:
                    # 在测试模式下跳过API验证
                    if getattr(settings, 'TEST_MODE', False):
                        # 使用模拟参数进行验证
                        from app.services.dify.models import WorkflowParameters, WorkflowParameter
                        mock_parameters = WorkflowParameters(
                            workflow_id="test-workflow-001",
                            workflow_name="测试工作流",
                            parameters=[
                                WorkflowParameter(name="query", type="text", required=True),
                                WorkflowParameter(name="context", type="text", required=False)
                            ]
                        )
                        validation_errors = excel_service.validate_data_structure(data_rows, mock_parameters)
                    else:
                        # 获取工作流配置进行参数验证
                        async with get_db_session() as db:
                            result = await db.execute(
                                select(Workflow).where(Workflow.id == workflow_id)
                            )
                            workflow = result.scalar_one_or_none()
                            
                            if workflow and workflow.parameters:
                                from app.services.dify.models import WorkflowParameters
                                if isinstance(workflow.parameters, dict):
                                    workflow_params = WorkflowParameters.from_dict(workflow.parameters)
                                else:
                                    workflow_params = workflow.parameters
                                validation_errors = excel_service.validate_data_structure(data_rows, workflow_params)
                            else:
                                validation_errors = []
                except Exception as e:
                    logger.warning(f"工作流参数验证失败，跳过验证: {str(e)}")
                    validation_errors = []
            
            return {
                "success": True,
                "file_id": file_id,
                "filename": file.filename,
                "validation": validation_result,
                "data_info": {
                    "rows": len(data_rows),
                    "columns": columns,
                    "validation_errors": validation_errors
                }
            }
            
        except Exception as e:
            # 删除文件
            os.remove(file_path)
            raise HTTPException(status_code=400, detail=f"文件解析失败: {str(e)}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("文件上传处理失败")
        raise HTTPException(status_code=500, detail=f"文件上传处理失败: {str(e)}")


@router.post("/execute")
async def execute_batch_task(
    file_id: str = Form(...),
    workflow_id: str = Form(...),
    task_name: str = Form("批量执行任务"),
    max_concurrency: int = Form(3),
    retry_count: int = Form(2),
    timeout_seconds: int = Form(300)
):
    """
    执行批量任务
    
    Args:
        file_id: 上传文件的ID
        workflow_id: 工作流ID
        task_name: 任务名称
        max_concurrency: 最大并发数
        retry_count: 重试次数
        timeout_seconds: 超时时间
        
    Returns:
        批量任务执行结果
    """
    try:
        logger.info(f"开始执行批量任务: {task_name}, 文件ID: {file_id}, 工作流ID: {workflow_id}")
        
        # 查找上传的文件
        upload_dir = Path(settings.UPLOAD_DIR)
        file_path = None
        original_filename = None
        
        for ext in ['.xlsx', '.xls']:
            potential_path = upload_dir / f"{file_id}{ext}"
            if potential_path.exists():
                file_path = potential_path
                original_filename = f"{file_id}{ext}"
                break
        
        if not file_path:
            raise HTTPException(status_code=404, detail="上传文件不存在")
        
        # 获取工作流配置
        async with get_db_session() as db:
            result = await db.execute(
                select(Workflow).where(Workflow.id == workflow_id)
            )
            workflow = result.scalar_one_or_none()
            
            if not workflow:
                raise HTTPException(status_code=404, detail="工作流不存在")
        
        # 解析文件数据进行验证
        data_rows, columns = excel_service.parse_excel_file(str(file_path))
        
        if not data_rows:
            raise HTTPException(status_code=400, detail="文件中没有有效数据")
        
        # 验证数据结构
        if workflow.parameters:
            # 将JSON参数转换为WorkflowParameters对象
            from app.services.dify.models import WorkflowParameters
            try:
                if isinstance(workflow.parameters, dict):
                    workflow_params = WorkflowParameters.from_dict(workflow.parameters)
                else:
                    workflow_params = workflow.parameters
                
                validation_errors = excel_service.validate_data_structure(data_rows, workflow_params)
                if validation_errors:
                    raise HTTPException(
                        status_code=400, 
                        detail={
                            "message": "数据验证失败",
                            "errors": validation_errors
                        }
                    )
            except Exception as e:
                logger.error(f"参数转换或验证失败: {str(e)}")
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": "数据验证失败", 
                        "errors": [f"参数处理失败: {str(e)}"]
                    }
                )
        
        # 创建批量任务
        batch_task = await task_manager.create_batch_task(
            workflow_id=workflow_id,
            name=task_name,
            file_path=str(file_path),
            original_filename=original_filename,
            max_concurrency=max_concurrency,
            retry_count=retry_count,
            timeout_seconds=timeout_seconds
        )
        
        # 准备工作流配置
        workflow_config = {
            "base_url": workflow.base_url,
            "api_key": workflow.api_key
        }
        
        # 启动批量处理任务
        success = await batch_processor.start_batch_task(
            batch_task.id,
            workflow_config
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="启动批量任务失败")
        
        # 开始进度追踪
        progress_tracker.start_tracking(batch_task.id)
        
        return {
            "success": True,
            "batch_id": batch_task.id,
            "task_name": task_name,
            "status": "running",
            "total_rows": len(data_rows),
            "workflow_id": workflow_id,
            "workflow_name": workflow.name,
            "max_concurrency": max_concurrency,
            "retry_count": retry_count,
            "timeout_seconds": timeout_seconds,
            "download_url": f"/api/batch/{batch_task.id}/download"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("批量任务执行失败")
        raise HTTPException(status_code=500, detail=f"批量任务执行失败: {str(e)}")


@router.get("/{batch_id}/status")
async def get_batch_status(batch_id: str):
    """
    获取批量任务状态
    
    Args:
        batch_id: 批量任务ID
        
    Returns:
        任务状态信息
    """
    try:
        # 获取批量任务信息
        batch_task = await task_manager.get_batch_task(batch_id)
        
        if not batch_task:
            raise HTTPException(status_code=404, detail="批量任务不存在")
        
        # 获取进度信息
        progress_info = progress_tracker.get_progress(batch_id)
        
        # 构建响应数据
        response_data = {
            "id": batch_id,  # 前端期望的字段名
            "batch_id": batch_id,  # 保持向后兼容
            "name": batch_task.name,
            "status": batch_task.status,
            "workflow_id": batch_task.workflow_id,
            "total_items": batch_task.total_items,
            "completed_items": batch_task.completed_items,
            "failed_items": batch_task.failed_items,
            "skipped_items": batch_task.skipped_items,
            "progress_percentage": batch_task.progress_percentage,
            "success_rate": batch_task.success_rate,
            "created_at": batch_task.created_at.isoformat() if batch_task.created_at else None,
            "started_at": batch_task.started_at.isoformat() if batch_task.started_at else None,
            "completed_at": batch_task.completed_at.isoformat() if batch_task.completed_at else None,
            "duration_seconds": batch_task.duration_seconds,
            "error_message": batch_task.error_message
        }
        
        # 添加实时进度信息
        if progress_info:
            response_data.update({
                "running_items": progress_info.running_items,
                "pending_items": progress_info.pending_items,
                "estimated_remaining_seconds": progress_info.estimated_remaining_seconds,
                "avg_execution_time": progress_info.avg_execution_time
            })
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取批量任务状态失败")
        raise HTTPException(status_code=500, detail=f"获取任务状态失败: {str(e)}")


@router.get("/{batch_id}/download")
async def download_batch_result(batch_id: str):
    """
    下载批量任务结果文件
    
    Args:
        batch_id: 批量任务ID
        
    Returns:
        结果文件下载
    """
    try:
        result_dir = Path(settings.RESULT_DIR)
        result_filename = f"result_{batch_id}.xlsx"
        result_path = result_dir / result_filename
        
        if not result_path.exists():
            raise HTTPException(status_code=404, detail="结果文件不存在")
        
        return FileResponse(
            path=str(result_path),
            filename=f"batch_result_{batch_id}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("下载结果文件失败")
        raise HTTPException(status_code=500, detail=f"下载结果文件失败: {str(e)}")


@router.post("/{batch_id}/stop")
async def stop_batch_task(batch_id: str):
    """
    停止批量任务
    
    Args:
        batch_id: 批量任务ID
        
    Returns:
        停止结果
    """
    try:
        success = await batch_processor.stop_batch_task(batch_id)
        
        if success:
            # 停止进度追踪
            progress_tracker.stop_tracking(batch_id)
            
            return {
                "success": True,
                "message": f"批量任务 {batch_id} 已停止"
            }
        else:
            raise HTTPException(status_code=400, detail="任务未在运行或停止失败")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("停止批量任务失败")
        raise HTTPException(status_code=500, detail=f"停止任务失败: {str(e)}")


@router.post("/{batch_id}/pause")
async def pause_batch_task(batch_id: str):
    """
    暂停批量任务
    
    Args:
        batch_id: 批量任务ID
        
    Returns:
        暂停结果
    """
    try:
        success = await batch_processor.pause_batch_task(batch_id)
        
        if success:
            return {
                "success": True,
                "message": f"批量任务 {batch_id} 已暂停"
            }
        else:
            raise HTTPException(status_code=400, detail="任务未在运行或暂停失败")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("暂停批量任务失败")
        raise HTTPException(status_code=500, detail=f"暂停任务失败: {str(e)}")


@router.post("/{batch_id}/resume")
async def resume_batch_task(batch_id: str):
    """
    恢复批量任务
    
    Args:
        batch_id: 批量任务ID
        
    Returns:
        恢复结果
    """
    try:
        success = await batch_processor.resume_batch_task(batch_id)
        
        if success:
            return {
                "success": True,
                "message": f"批量任务 {batch_id} 已恢复"
            }
        else:
            raise HTTPException(status_code=400, detail="任务未暂停或恢复失败")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("恢复批量任务失败")
        raise HTTPException(status_code=500, detail=f"恢复任务失败: {str(e)}")


@router.get("/{batch_id}/failed-executions")
async def get_failed_executions(batch_id: str):
    """
    获取批量任务中失败的执行记录
    
    Args:
        batch_id: 批量任务ID
        
    Returns:
        失败的执行记录列表
    """
    try:
        failed_executions = await task_manager.get_failed_executions(batch_id)
        
        return {
            "success": True,
            "batch_id": batch_id,
            "failed_count": len(failed_executions),
            "failed_executions": failed_executions
        }
        
    except Exception as e:
        logger.exception("获取失败执行记录失败")
        raise HTTPException(status_code=500, detail=f"获取失败执行记录失败: {str(e)}")


@router.post("/{batch_id}/executions/{execution_id}/retry")
async def retry_failed_execution(batch_id: str, execution_id: str):
    """
    重试单个失败的执行任务
    
    Args:
        batch_id: 批量任务ID
        execution_id: 执行记录ID
        
    Returns:
        重试结果
    """
    try:
        success = await task_manager.retry_failed_execution(batch_id, execution_id)
        
        if success:
            return {
                "success": True,
                "message": f"执行任务 {execution_id} 已重新加入执行队列"
            }
        else:
            raise HTTPException(status_code=400, detail="任务不存在或状态不允许重试")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("重试失败执行任务失败")
        raise HTTPException(status_code=500, detail=f"重试失败: {str(e)}")


@router.post("/{batch_id}/retry-failed")
async def retry_all_failed_executions(batch_id: str):
    """
    重试批量任务中所有失败的子任务
    
    Args:
        batch_id: 批量任务ID
        
    Returns:
        重试结果
    """
    try:
        result = await task_manager.retry_all_failed_executions(batch_id)
        
        if result["success"]:
            return {
                "success": True,
                "message": f"已重试 {result['retried_count']} 个失败任务",
                "retried_count": result["retried_count"],
                "failed_count": result["failed_count"]
            }
        else:
            raise HTTPException(status_code=400, detail=result.get("message", "重试失败"))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("批量重试失败任务失败")
        raise HTTPException(status_code=500, detail=f"批量重试失败: {str(e)}")


@router.delete("/{batch_id}")
async def delete_batch_task(batch_id: str):
    """
    删除批量任务及相关文件
    
    Args:
        batch_id: 批量任务ID
        
    Returns:
        删除结果
    """
    try:
        # 先停止任务（如果正在运行）
        if batch_processor.is_task_running(batch_id):
            await batch_processor.stop_batch_task(batch_id)
            progress_tracker.stop_tracking(batch_id)
        
        # 删除任务记录和文件
        success = await task_manager.delete_batch_task(batch_id)
        
        if success:
            return {
                "success": True,
                "message": f"批量任务 {batch_id} 已删除"
            }
        else:
            raise HTTPException(status_code=404, detail="批量任务不存在")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("删除批量任务失败")
        raise HTTPException(status_code=500, detail=f"删除任务失败: {str(e)}")


@router.get("/")
async def list_batch_tasks(
    page: int = 1,
    size: int = 20,
    status: str = None,
    workflow_id: str = None
):
    """
    获取批量任务列表
    
    Args:
        page: 页码
        size: 每页大小
        status: 状态过滤
        workflow_id: 工作流ID过滤
        
    Returns:
        任务列表
    """
    try:
        # 转换状态参数
        status_filter = None
        if status:
            try:
                status_filter = TaskStatus(status)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"无效的状态值: {status}")
        
        # 获取任务列表
        result = await task_manager.list_batch_tasks(
            page=page,
            size=size,
            status=status_filter,
            workflow_id=workflow_id
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取批量任务列表失败")
        raise HTTPException(status_code=500, detail=f"获取任务列表失败: {str(e)}") 