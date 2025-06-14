"""
模拟Dify客户端 - 用于Phase 4.1测试
"""

import asyncio
import json
import random
import time
from typing import Dict, Any, Optional
from pathlib import Path

from .models import WorkflowExecutionResponse, WorkflowRunStatus
from ...core.logging import logger


class MockDifyClient:
    """模拟的Dify客户端，用于测试批量处理功能"""
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
        self.session = None
        
        # 加载模拟响应数据
        self._load_mock_responses()
    
    def _load_mock_responses(self):
        """加载模拟响应数据"""
        try:
            mock_file = Path("mock_dify_responses.json")
            if mock_file.exists():
                with open(mock_file, 'r', encoding='utf-8') as f:
                    self.mock_responses = json.load(f)
            else:
                # 默认模拟响应
                self.mock_responses = [
                    {
                        "id": f"run-{i:03d}",
                        "workflow_id": "test-workflow-001",
                        "status": "succeeded",
                        "outputs": {"text": f"这是第{i+1}个测试响应"},
                        "error": None,
                        "elapsed_time": random.uniform(1.0, 5.0),
                        "total_tokens": random.randint(100, 300),
                        "created_at": int(time.time()),
                        "finished_at": int(time.time()) + random.randint(1, 5)
                    }
                    for i in range(10)
                ]
        except Exception as e:
            logger.warning(f"加载模拟响应失败: {e}, 使用默认响应")
            self.mock_responses = []
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        logger.info(f"🔗 模拟Dify客户端连接: {self.base_url}")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        logger.info(f"🔌 模拟Dify客户端断开连接")
        pass
    
    async def execute_workflow(self, inputs: Dict[str, Any]) -> WorkflowExecutionResponse:
        """
        模拟执行工作流
        
        Args:
            inputs: 输入参数
            
        Returns:
            WorkflowExecutionResponse: 执行响应
        """
        logger.info(f"🎭 模拟执行工作流")
        logger.info(f"   输入参数: {json.dumps(inputs, ensure_ascii=False)}")
        
        # 模拟网络延迟
        delay = random.uniform(0.5, 3.0)
        logger.info(f"   模拟延迟: {delay:.2f}秒")
        await asyncio.sleep(delay)
        
        # 模拟偶发错误（10%概率）
        if random.random() < 0.1:
            error_messages = [
                "网络连接超时",
                "API调用限制",
                "工作流执行失败",
                "参数验证错误"
            ]
            error_msg = random.choice(error_messages)
            logger.error(f"   模拟错误: {error_msg}")
            raise Exception(f"模拟Dify API错误: {error_msg}")
        
        # 生成模拟响应
        response_data = self._generate_mock_response(inputs)
        
        logger.info(f"   模拟响应: {json.dumps(response_data, ensure_ascii=False)}")
        
        # 创建响应对象 - 模拟真实Dify API的响应格式
        response = WorkflowExecutionResponse(
            workflow_run_id=response_data["id"],
            task_id=response_data["id"],
            data=response_data
        )
        
        return response
    
    def _generate_mock_response(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """生成模拟响应数据"""
        
        # 基于输入生成个性化响应
        query = inputs.get("query", "默认查询")
        context = inputs.get("context", "")
        
        # 生成模拟输出
        mock_outputs = {
            "text": f"针对查询「{query}」的回答",
            "summary": f"基于上下文「{context}」的总结" if context else "无上下文总结",
            "confidence": random.uniform(0.7, 0.95)
        }
        
        # 随机选择输出格式
        output_formats = [
            {"text": mock_outputs["text"]},
            {"result": mock_outputs["text"], "confidence": mock_outputs["confidence"]},
            {"answer": mock_outputs["text"], "summary": mock_outputs["summary"]},
            mock_outputs  # 完整输出
        ]
        
        selected_output = random.choice(output_formats)
        
        return {
            "id": f"run-{random.randint(1000, 9999)}",
            "workflow_id": "test-workflow-001",
            "status": "succeeded",
            "outputs": selected_output,
            "error": None,
            "elapsed_time": random.uniform(1.0, 5.0),
            "total_tokens": random.randint(100, 500),
            "total_steps": random.randint(2, 6),
            "created_at": int(time.time()),
            "finished_at": int(time.time()) + random.randint(1, 5)
        }
    
    async def get_workflow_parameters(self) -> Dict[str, Any]:
        """模拟获取工作流参数"""
        logger.info(f"🎭 模拟获取工作流参数")
        
        await asyncio.sleep(0.5)  # 模拟网络延迟
        
        return {
            "parameters": [
                {
                    "name": "query",
                    "type": "string",
                    "required": True,
                    "description": "用户查询内容"
                },
                {
                    "name": "context",
                    "type": "string", 
                    "required": False,
                    "description": "上下文信息"
                }
            ]
        }
    
    async def get_application_info(self) -> Dict[str, Any]:
        """模拟获取应用信息"""
        logger.info(f"🎭 模拟获取应用信息")
        
        await asyncio.sleep(0.3)  # 模拟网络延迟
        
        return {
            "name": "测试工作流应用",
            "description": "用于Phase 4.1测试的模拟应用",
            "tags": ["测试", "模拟", "批量处理"],
            "created_at": "2024-06-13T00:00:00Z"
        } 