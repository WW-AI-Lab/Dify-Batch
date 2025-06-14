#!/usr/bin/env python3
"""
Phase 4.1 测试数据生成脚本
生成测试用的Excel文件和工作流配置
"""

import pandas as pd
import json
from pathlib import Path

def create_test_excel():
    """创建测试用的Excel文件"""
    
    # 创建测试数据
    test_data = [
        {"query": "什么是人工智能？", "context": "AI技术发展"},
        {"query": "机器学习的基本原理", "context": "算法学习"},
        {"query": "深度学习应用场景", "context": "神经网络"},
        {"query": "自然语言处理技术", "context": "文本分析"},
        {"query": "计算机视觉发展", "context": "图像识别"}
    ]
    
    # 创建DataFrame
    df = pd.DataFrame(test_data)
    
    # 确保uploads目录存在
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)
    
    # 保存为Excel文件
    excel_path = uploads_dir / "test_batch_data.xlsx"
    df.to_excel(excel_path, index=False, sheet_name="批量数据")
    
    print(f"✅ 测试Excel文件已创建: {excel_path}")
    print(f"   数据行数: {len(test_data)}")
    print(f"   列名: {list(df.columns)}")
    
    return excel_path

def create_test_workflow_config():
    """创建测试工作流配置"""
    
    # 模拟工作流配置
    test_config = {
        "id": "test-workflow-001",
        "name": "测试工作流",
        "description": "用于Phase 4.1测试的工作流",
        "base_url": "https://api.dify.ai/v1",
        "api_key": "app-your-test-key-here",
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
    
    # 保存配置文件
    config_path = Path("test_workflow_config.json")
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(test_config, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 测试工作流配置已创建: {config_path}")
    print(f"   工作流ID: {test_config['id']}")
    print(f"   参数数量: {len(test_config['parameters'])}")
    
    return test_config

def create_mock_dify_response():
    """创建模拟的Dify API响应"""
    
    mock_responses = [
        {
            "id": "run-001",
            "workflow_id": "test-workflow-001", 
            "status": "succeeded",
            "outputs": {"text": "人工智能是模拟人类智能的技术"},
            "error": None,
            "elapsed_time": 2.5,
            "total_tokens": 150,
            "created_at": 1749820464,
            "finished_at": 1749820467
        },
        {
            "id": "run-002",
            "workflow_id": "test-workflow-001",
            "status": "succeeded", 
            "outputs": {"text": "机器学习通过算法让计算机自动学习"},
            "error": None,
            "elapsed_time": 3.2,
            "total_tokens": 180,
            "created_at": 1749820468,
            "finished_at": 1749820471
        }
    ]
    
    # 保存模拟响应
    mock_path = Path("mock_dify_responses.json")
    with open(mock_path, 'w', encoding='utf-8') as f:
        json.dump(mock_responses, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 模拟Dify响应已创建: {mock_path}")
    print(f"   响应数量: {len(mock_responses)}")
    
    return mock_responses

def main():
    """主函数"""
    print("🚀 开始创建Phase 4.1测试数据...")
    print()
    
    # 创建测试数据
    excel_path = create_test_excel()
    workflow_config = create_test_workflow_config()
    mock_responses = create_mock_dify_response()
    
    print()
    print("📋 测试数据创建完成！")
    print()
    print("🎯 下一步测试计划:")
    print("1. 访问 http://localhost:8000/workflows 添加测试工作流")
    print("2. 访问 http://localhost:8000/batch 上传测试Excel文件")
    print("3. 启动批量执行并监控过程")
    print("4. 验证结果文件和任务控制功能")
    print()
    print("📁 创建的文件:")
    print(f"   - {excel_path}")
    print(f"   - test_workflow_config.json")
    print(f"   - mock_dify_responses.json")

if __name__ == "__main__":
    main() 