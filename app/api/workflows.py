"""
工作流管理API
"""
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.dify import DifyClient
from app.services.dify.models import WorkflowParameters
from app.services.workflow_service import workflow_service
from app.core.exceptions import DifyAPIException, DatabaseException
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


class WorkflowCreateRequest(BaseModel):
    """创建工作流请求"""
    name: str
    description: str = ""
    base_url: str
    api_key: str


class WorkflowUpdateRequest(BaseModel):
    """更新工作流请求"""
    name: str = None
    description: str = None
    base_url: str = None
    api_key: str = None


@router.get("/", response_model=List[Dict[str, Any]])
async def get_workflows():
    """
    获取所有工作流列表
    
    Returns:
        工作流列表
    """
    try:
        workflows = await workflow_service.get_all_workflows()
        return workflows
    except DatabaseException as e:
        logger.error(f"获取工作流列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("获取工作流列表时发生未知错误")
        raise HTTPException(status_code=500, detail="服务器内部错误")


@router.post("/", response_model=Dict[str, Any])
async def create_workflow(request: WorkflowCreateRequest):
    """
    创建新工作流
    
    Args:
        request: 创建工作流请求
        
    Returns:
        创建的工作流信息
    """
    try:
        workflow = await workflow_service.create_workflow(request.dict())
        return workflow
    except DifyAPIException as e:
        logger.error(f"创建工作流时API验证失败: {e.message}")
        raise HTTPException(status_code=400, detail=f"API配置验证失败: {e.message}")
    except DatabaseException as e:
        logger.error(f"创建工作流失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("创建工作流时发生未知错误")
        raise HTTPException(status_code=500, detail="服务器内部错误")


@router.get("/health")
async def workflow_health_check():
    """
    工作流服务健康检查
    
    Returns:
        健康状态
    """
    return {
        "status": "healthy",
        "service": "workflow_api",
        "timestamp": "2024-06-13T21:52:00Z"
    }


@router.get("/parameters", response_model=WorkflowParameters)
async def get_default_workflow_parameters(workflow_id: str = None, base_url: str = None, api_key: str = None):
    """
    获取工作流参数（需要提供API配置）
    
    Args:
        workflow_id: 工作流ID（可选）
        base_url: Dify API基础URL
        api_key: API密钥
        
    Returns:
        工作流参数信息
    """
    if not base_url or not api_key:
        raise HTTPException(status_code=400, detail="需要提供base_url和api_key参数")
    
    try:
        client = DifyClient(base_url=base_url, api_key=api_key)
        async with client:
            parameters = await client.get_workflow_parameters(workflow_id)
            return parameters
    except DifyAPIException as e:
        logger.error(f"获取工作流参数失败: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.exception("获取工作流参数时发生未知错误")
        raise HTTPException(status_code=500, detail="服务器内部错误")


@router.get("/{workflow_id}", response_model=Dict[str, Any])
async def get_workflow(workflow_id: str):
    """
    获取指定工作流信息
    
    Args:
        workflow_id: 工作流ID
        
    Returns:
        工作流信息
    """
    try:
        workflow = await workflow_service.get_workflow_by_id(workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail="工作流不存在")
        return workflow
    except DatabaseException as e:
        logger.error(f"获取工作流失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("获取工作流时发生未知错误")
        raise HTTPException(status_code=500, detail="服务器内部错误")


@router.put("/{workflow_id}", response_model=Dict[str, Any])
async def update_workflow(workflow_id: str, request: WorkflowUpdateRequest):
    """
    更新工作流
    
    Args:
        workflow_id: 工作流ID
        request: 更新工作流请求
        
    Returns:
        更新后的工作流信息
    """
    try:
        # 过滤掉None值
        update_data = {k: v for k, v in request.dict().items() if v is not None}
        workflow = await workflow_service.update_workflow(workflow_id, update_data)
        return workflow
    except DifyAPIException as e:
        logger.error(f"更新工作流时API验证失败: {e.message}")
        raise HTTPException(status_code=400, detail=f"API配置验证失败: {e.message}")
    except DatabaseException as e:
        logger.error(f"更新工作流失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("更新工作流时发生未知错误")
        raise HTTPException(status_code=500, detail="服务器内部错误")


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str):
    """
    删除工作流
    
    Args:
        workflow_id: 工作流ID
        
    Returns:
        删除结果
    """
    try:
        success = await workflow_service.delete_workflow(workflow_id)
        return {"success": success, "message": "工作流删除成功"}
    except DatabaseException as e:
        logger.error(f"删除工作流失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("删除工作流时发生未知错误")
        raise HTTPException(status_code=500, detail="服务器内部错误")


@router.post("/{workflow_id}/sync")
async def sync_workflow(workflow_id: str):
    """
    同步工作流信息
    
    Args:
        workflow_id: 工作流ID
        
    Returns:
        同步后的工作流信息
    """
    try:
        workflow = await workflow_service.sync_workflow_info(workflow_id)
        return workflow
    except DifyAPIException as e:
        logger.error(f"同步工作流时API调用失败: {e.message}")
        raise HTTPException(status_code=400, detail=f"API调用失败: {e.message}")
    except DatabaseException as e:
        logger.error(f"同步工作流失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("同步工作流时发生未知错误")
        raise HTTPException(status_code=500, detail="服务器内部错误")


@router.get("/{workflow_id}/parameters", response_model=WorkflowParameters)
async def get_workflow_parameters(workflow_id: str):
    """
    获取工作流参数（优先从缓存获取）
    
    Args:
        workflow_id: 工作流ID
        
    Returns:
        工作流参数信息
    """
    try:
        parameters = await workflow_service.get_workflow_parameters(workflow_id)
        if not parameters:
            raise HTTPException(status_code=404, detail="工作流参数不存在")
        return parameters
    except DifyAPIException as e:
        logger.error(f"获取工作流参数失败: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except DatabaseException as e:
        logger.error(f"获取工作流参数失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("获取工作流参数时发生未知错误")
        raise HTTPException(status_code=500, detail="服务器内部错误")


@router.get("/{workflow_id}/template")
async def download_workflow_template(workflow_id: str):
    """
    下载工作流Excel模板
    
    Args:
        workflow_id: 工作流ID
        
    Returns:
        Excel模板文件
    """
    try:
        # 获取工作流参数（从数据库缓存获取）
        parameters = await workflow_service.get_workflow_parameters(workflow_id)
        if not parameters:
            raise HTTPException(status_code=404, detail="工作流参数不存在，请先同步工作流")
        
        # 生成Excel模板
        from app.services.file.excel_service import ExcelService
        excel_service = ExcelService()
        
        template_data = excel_service.generate_template(parameters)
        
        # 返回文件流
        return StreamingResponse(
            template_data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={parameters.workflow_name}_template.xlsx"
            }
        )
        
    except DifyAPIException as e:
        logger.error(f"生成工作流模板失败: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.exception("生成工作流模板时发生未知错误")
        raise HTTPException(status_code=500, detail="服务器内部错误") 