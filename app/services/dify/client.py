"""
Dify API客户端
"""
import asyncio
import json
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import aiohttp
from aiohttp import ClientTimeout, ClientSession

from app.core.config import settings
from app.core.exceptions import DifyAPIException
from app.core.logging import get_logger
from .models import (
    WorkflowExecutionRequest,
    WorkflowExecutionResponse,
    WorkflowRunStatus,
    WorkflowLogEntry,
    WorkflowParameters,
    WorkflowParameter,
    WorkflowParameterType,
    TaskStatus,
    DifyAPIError
)

logger = get_logger(__name__)


class DifyClient:
    """Dify API客户端"""
    
    def __init__(
        self,
        base_url: str = None,
        api_key: str = None,
        timeout: int = None,
        max_retries: int = None,
        retry_delay: int = None
    ):
        """初始化Dify客户端"""
        self.base_url = base_url or settings.DIFY_BASE_URL
        self.api_key = api_key  # API密钥必须显式提供，不再使用全局配置
        self.timeout = timeout or settings.DIFY_TIMEOUT
        self.max_retries = max_retries or settings.DIFY_MAX_RETRIES
        self.retry_delay = retry_delay or settings.DIFY_RETRY_DELAY
        
        if not self.api_key:
            raise ValueError("API密钥是必需的，请提供api_key参数")
        
        if not self.base_url.endswith('/'):
            self.base_url += '/'
        
        self._session: Optional[ClientSession] = None
    
    async def __aenter__(self):
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def _ensure_session(self):
        """确保HTTP会话存在"""
        if self._session is None or self._session.closed:
            timeout = ClientTimeout(total=self.timeout)
            connector = aiohttp.TCPConnector(
                limit=100,  # 总连接池大小
                limit_per_host=30,  # 每个主机的连接数
                ttl_dns_cache=300,  # DNS缓存时间
                use_dns_cache=True,
            )
            self._session = ClientSession(
                timeout=timeout,
                connector=connector,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "Dify-Batch-Client/1.0.0"
                }
            )
    
    async def close(self):
        """关闭HTTP会话"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """发起HTTP请求"""
        await self._ensure_session()
        
        # 检查session状态
        if self._session is None:
            raise DifyAPIException("HTTP会话未初始化")
        
        if self._session.closed:
            logger.warning("检测到会话已关闭，重新创建会话")
            await self._ensure_session()
        
        url = urljoin(self.base_url, endpoint)
        
        for attempt in range(self.max_retries + 1):
            try:
                # 详细的请求日志
                logger.info(f"🚀 Dify API请求 [尝试 {attempt + 1}/{self.max_retries + 1}]")
                logger.info(f"   方法: {method}")
                logger.info(f"   URL: {url}")
                if params:
                    logger.info(f"   参数: {json.dumps(params, ensure_ascii=False, indent=2)}")
                if data:
                    logger.info(f"   请求体: {json.dumps(data, ensure_ascii=False, indent=2)}")
                
                async with self._session.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params
                ) as response:
                    response_text = await response.text()
                    
                    # 详细的响应日志
                    logger.info(f"📥 Dify API响应")
                    logger.info(f"   状态码: {response.status}")
                    logger.info(f"   响应头: {dict(response.headers)}")
                    logger.info(f"   响应体: {response_text}")
                    
                    if response.status == 200:
                        try:
                            response_json = json.loads(response_text)
                            logger.info(f"✅ API请求成功")
                            return response_json
                        except json.JSONDecodeError as e:
                            logger.error(f"❌ API响应JSON解析失败: {str(e)}")
                            raise DifyAPIException(f"API响应JSON解析失败: {str(e)}")
                    
                    # 处理错误响应
                    try:
                        error_data = json.loads(response_text)
                    except json.JSONDecodeError:
                        error_data = {"message": response_text}
                    
                    error_message = error_data.get("message", f"API请求失败: HTTP {response.status}")
                    logger.error(f"❌ API请求失败: {error_message}")
                    
                    if 400 <= response.status < 500:
                        raise DifyAPIException(error_message, status_code=response.status)
                    
                    if attempt < self.max_retries:
                        logger.warning(f"⚠️ API请求失败，将重试: {error_message}")
                        await asyncio.sleep(self.retry_delay)
                        continue
                    
                    raise DifyAPIException(error_message, status_code=response.status)
                    
            except aiohttp.ClientError as e:
                logger.error(f"❌ 网络请求失败: {str(e)}")
                if attempt < self.max_retries:
                    logger.warning(f"⚠️ 网络请求失败，将重试: {str(e)}")
                    await asyncio.sleep(self.retry_delay)
                    continue
                
                raise DifyAPIException(f"网络请求失败: {str(e)}")
        
        logger.error(f"❌ API请求重试次数已用尽")
        raise DifyAPIException("API请求重试次数已用尽")
    
    async def execute_workflow(
        self,
        inputs: Dict[str, Any],
        response_mode: str = "blocking",
        user: str = "batch-user"
    ) -> WorkflowExecutionResponse:
        """执行工作流"""
        request_data = {
            "inputs": inputs,
            "response_mode": response_mode,
            "user": user
        }
        
        logger.info("执行工作流", extra={"inputs": inputs})
        
        response_data = await self._make_request(
            method="POST",
            endpoint="workflows/run",
            data=request_data
        )
        
        return WorkflowExecutionResponse(**response_data)
    
    async def get_workflow_run_status(self, workflow_run_id: str) -> WorkflowRunStatus:
        """获取工作流运行状态"""
        logger.debug(f"获取工作流运行状态: {workflow_run_id}")
        
        response_data = await self._make_request(
            method="GET",
            endpoint=f"workflows/run/{workflow_run_id}"
        )
        
        return WorkflowRunStatus(**response_data)
    
    async def stop_workflow_run(self, task_id: str) -> Dict[str, Any]:
        """停止工作流运行"""
        logger.info(f"停止工作流运行: {task_id}")
        
        response_data = await self._make_request(
            method="POST",
            endpoint=f"workflows/tasks/{task_id}/stop"
        )
        
        return response_data
    
    async def get_workflow_logs(self, workflow_run_id: str) -> List[WorkflowLogEntry]:
        """获取工作流日志"""
        logger.debug(f"获取工作流日志: {workflow_run_id}")
        
        response_data = await self._make_request(
            method="GET",
            endpoint=f"workflows/run/{workflow_run_id}/logs"
        )
        
        logs = []
        for log_data in response_data.get("logs", []):
            logs.append(WorkflowLogEntry(**log_data))
        
        return logs
    
    async def get_workflow_parameters(self, workflow_id: str = None) -> WorkflowParameters:
        """获取工作流参数"""
        logger.debug(f"获取工作流参数: {workflow_id}")
        
        # 构建端点URL - 根据Dify API文档，应该是 /parameters
        endpoint = "parameters"
        
        response_data = await self._make_request(
            method="GET",
            endpoint=endpoint
        )
        
        logger.info(f"Dify API响应: {response_data}")
        
        # 解析参数数据 - 只处理user_input_form部分
        parameters = []
        user_input_form = response_data.get("user_input_form", [])
        
        for form_item in user_input_form:
            # user_input_form中每个项目可能有不同的结构
            # 例如: {'paragraph': {'variable': 'query', 'label': '搜索词', ...}}
            for input_type, param_data in form_item.items():
                param_type = self._map_parameter_type(input_type)
                
                parameter = WorkflowParameter(
                    name=param_data.get("variable", ""),
                    type=param_type,
                    required=param_data.get("required", False),
                    description=param_data.get("label", ""),
                    default_value=param_data.get("default", None),
                    options=param_data.get("options", []),
                    max_length=param_data.get("max_length", None)
                )
                parameters.append(parameter)
        
        return WorkflowParameters(
            workflow_id=workflow_id or response_data.get("id", "default"),
            workflow_name=response_data.get("name", "Default Workflow"),
            parameters=parameters
        )
    
    def _map_parameter_type(self, dify_type: str) -> WorkflowParameterType:
        """映射Dify参数类型到内部枚举"""
        type_mapping = {
            "text-input": WorkflowParameterType.TEXT,
            "paragraph": WorkflowParameterType.TEXT,
            "number": WorkflowParameterType.NUMBER,
            "select": WorkflowParameterType.SELECT,
            "file": WorkflowParameterType.FILE,
            "boolean": WorkflowParameterType.BOOLEAN,
            "json": WorkflowParameterType.JSON,
        }
        
        return type_mapping.get(dify_type, WorkflowParameterType.TEXT)
    
    async def get_app_info(self) -> Dict[str, Any]:
        """获取应用基本信息"""
        logger.debug("获取应用基本信息")
        
        response_data = await self._make_request(
            method="GET",
            endpoint="info"
        )
        
        logger.info(f"应用信息API响应: {response_data}")
        
        return {
            "name": response_data.get("name", ""),
            "description": response_data.get("description", ""),
            "tags": response_data.get("tags", [])
        }
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            await self.get_workflow_parameters()
            return True
        except Exception as e:
            logger.error(f"Dify API健康检查失败: {str(e)}")
            return False


# 注意：不再创建全局客户端实例，因为API密钥必须显式提供
# 每个工作流都应该创建自己的DifyClient实例 