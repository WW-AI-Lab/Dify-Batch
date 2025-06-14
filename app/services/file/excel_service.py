"""
Excel文件处理服务
"""
import io
import os
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.worksheet.worksheet import Worksheet

from app.services.dify.models import WorkflowParameters, WorkflowParameter, WorkflowParameterType
from app.core.exceptions import FileProcessingException
from app.core.logging import get_logger
from .template_generator import TemplateGenerator

logger = get_logger(__name__)


class ExcelService:
    """Excel文件处理服务"""
    
    def __init__(self):
        """初始化Excel服务"""
        self.max_file_size = 200 * 1024 * 1024  # 200MB（支持大文件）
        self.supported_extensions = ['.xlsx', '.xls']
        self.template_generator = TemplateGenerator()
        
    def generate_template(self, parameters: WorkflowParameters) -> io.BytesIO:
        """
        生成Excel模板文件
        
        Args:
            parameters: 工作流参数信息
            
        Returns:
            Excel文件的字节流
        """
        try:
            logger.info(f"开始生成Excel模板: {parameters.workflow_name}")
            return self.template_generator.generate_workflow_template(parameters)
        except Exception as e:
            logger.error(f"生成Excel模板失败: {str(e)}")
            raise FileProcessingException(f"生成Excel模板失败: {str(e)}")
    

    
    def parse_excel_file(self, file_path: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        解析Excel文件
        
        Args:
            file_path: Excel文件路径
            
        Returns:
            (数据行列表, 参数名列表)
        """
        try:
            logger.info(f"开始解析Excel文件: {file_path}")
            
            # 验证文件
            self._validate_file(file_path)
            
            # 读取Excel文件（优化大文件处理）
            df = pd.read_excel(file_path, sheet_name="批量数据", header=0, engine='openpyxl')
            
            # 获取参数列名（排除结果列）
            columns = df.columns.tolist()
            if "执行结果" in columns:
                columns.remove("执行结果")
            
            # 清理列名，移除必填标记 *
            clean_columns = []
            for col in columns:
                clean_col = col.strip()
                if clean_col.endswith(' *'):
                    clean_col = clean_col[:-2].strip()
                clean_columns.append(clean_col)
            columns = clean_columns
            
            # 过滤空行和示例行
            df = df.dropna(how='all')  # 删除完全空白的行
            
            # 跳过描述行和示例行（第2、3行）
            # 如果第一行数据看起来像描述行，也要跳过
            if len(df) > 0:
                # 检查第一行是否为描述行（包含参数名称本身或描述性文字）
                first_row = df.iloc[0]
                is_description_row = False
                
                for col_idx, col_name in enumerate(df.columns):
                    if col_idx < len(first_row):
                        cell_value = str(first_row.iloc[col_idx]).strip()
                        clean_col_name = col_name.strip()
                        if clean_col_name.endswith(' *'):
                            clean_col_name = clean_col_name[:-2].strip()
                        
                        # 如果单元格值就是列名本身，或者是常见的描述词，则认为是描述行
                        if (cell_value == clean_col_name or 
                            cell_value in ['搜索词', '参数', '输入', '数据', '内容', '值', '示例']):
                            is_description_row = True
                            break
                
                # 跳过描述行
                if is_description_row:
                    df = df.iloc[1:]
                
                # 如果还有数据且长度大于1，再跳过一行示例行
                if len(df) > 1:
                    # 检查是否有明显的示例数据行
                    if len(df) > 0:
                        second_row = df.iloc[0]
                        # 可以在这里添加更多示例行检测逻辑
                        pass
            
            # 转换为字典列表
            data_rows = []
            original_columns = df.columns.tolist()
            if "执行结果" in original_columns:
                original_columns.remove("执行结果")
            
            for index, row in df.iterrows():
                row_data = {}
                for i, clean_col in enumerate(columns):
                    original_col = original_columns[i]
                    value = row[original_col]
                    # 处理NaN值
                    if pd.isna(value):
                        row_data[clean_col] = None
                    else:
                        # 确保所有值都转换为Python原生类型
                        if hasattr(value, 'item'):  # numpy类型
                            value = value.item()
                        row_data[clean_col] = str(value).strip()
                
                # 跳过空行
                if any(v for v in row_data.values() if v):
                    data_rows.append(row_data)
            
            logger.info(f"Excel文件解析完成: 共{len(data_rows)}行数据")
            return data_rows, columns
            
        except Exception as e:
            logger.error(f"解析Excel文件失败: {str(e)}")
            raise FileProcessingException(f"解析Excel文件失败: {str(e)}")
    
    def _validate_file(self, file_path: str):
        """验证文件"""
        if not os.path.exists(file_path):
            raise FileProcessingException("文件不存在")
        
        # 检查文件大小
        file_size = os.path.getsize(file_path)
        if file_size > self.max_file_size:
            raise FileProcessingException(f"文件大小超过限制({self.max_file_size / 1024 / 1024:.1f}MB)")
        
        # 检查文件扩展名
        file_ext = Path(file_path).suffix.lower()
        if file_ext not in self.supported_extensions:
            raise FileProcessingException(f"不支持的文件格式: {file_ext}")
    
    def validate_data_structure(self, data_rows: List[Dict[str, Any]], parameters: WorkflowParameters) -> List[str]:
        """
        验证数据结构
        
        Args:
            data_rows: 数据行列表
            parameters: 工作流参数
            
        Returns:
            验证错误列表
        """
        errors = []
        
        try:
            # 获取必填参数
            required_params = [p.name for p in parameters.parameters if p.required]
            
            # 验证每行数据
            for row_idx, row_data in enumerate(data_rows, 1):
                # 检查必填参数
                for param_name in required_params:
                    if param_name not in row_data or not row_data[param_name]:
                        errors.append(f"第{row_idx}行: 必填参数'{param_name}'为空")
                
                # 验证参数类型和格式
                for param in parameters.parameters:
                    if param.name in row_data and row_data[param.name]:
                        value = row_data[param.name]
                        error = self._validate_parameter_value(param, value, row_idx)
                        if error:
                            errors.append(error)
            
            logger.info(f"数据结构验证完成: {len(errors)}个错误")
            return errors
            
        except Exception as e:
            logger.error(f"数据结构验证失败: {str(e)}")
            return [f"数据验证失败: {str(e)}"]
    
    def _validate_parameter_value(self, param: WorkflowParameter, value: str, row_idx: int) -> Optional[str]:
        """验证参数值"""
        try:
            if param.type == WorkflowParameterType.NUMBER:
                try:
                    float(value)
                except ValueError:
                    return f"第{row_idx}行: 参数'{param.name}'必须为数字"
            
            elif param.type == WorkflowParameterType.BOOLEAN:
                if value.lower() not in ['true', 'false', '1', '0', 'yes', 'no']:
                    return f"第{row_idx}行: 参数'{param.name}'必须为布尔值(true/false)"
            
            elif param.type == WorkflowParameterType.SELECT:
                if param.options and value not in param.options:
                    return f"第{row_idx}行: 参数'{param.name}'值'{value}'不在可选项中: {param.options}"
            
            elif param.type == WorkflowParameterType.JSON:
                try:
                    import json
                    json.loads(value)
                except json.JSONDecodeError:
                    return f"第{row_idx}行: 参数'{param.name}'不是有效的JSON格式"
            
            # 检查长度限制
            if param.max_length and len(value) > param.max_length:
                return f"第{row_idx}行: 参数'{param.name}'长度超过限制({param.max_length})"
            
            return None
            
        except Exception as e:
            return f"第{row_idx}行: 参数'{param.name}'验证失败: {str(e)}"
    
    def generate_result_file(
        self, 
        original_file_path: str, 
        results: List[Dict[str, Any]], 
        output_path: str
    ) -> str:
        """
        生成结果文件
        
        Args:
            original_file_path: 原始文件路径
            results: 执行结果列表
            output_path: 输出文件路径
            
        Returns:
            生成的结果文件路径
        """
        try:
            logger.info(f"开始生成结果文件: {output_path}")
            
            # 读取原始文件
            df = pd.read_excel(original_file_path, sheet_name="批量数据", header=0)
            
            # 跳过描述行和示例行
            if len(df) > 2:
                df = df.iloc[2:]
            
            # 过滤空行
            df = df.dropna(how='all')
            
            # 添加结果列
            if "执行结果" not in df.columns:
                df["执行结果"] = ""
            
            # 填充结果数据
            for idx, result in enumerate(results):
                if idx < len(df):
                    if result.get("success"):
                        df.iloc[idx, df.columns.get_loc("执行结果")] = result.get("output", "执行成功")
                    else:
                        df.iloc[idx, df.columns.get_loc("执行结果")] = f"执行失败: {result.get('error', '未知错误')}"
            
            # 保存结果文件
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name="执行结果", index=False)
                
                # 设置样式
                workbook = writer.book
                worksheet = writer.sheets["执行结果"]
                
                # 设置表头样式
                header_font = Font(bold=True)
                for cell in worksheet[1]:
                    cell.font = header_font
                
                # 调整列宽
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            logger.info(f"结果文件生成完成: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"生成结果文件失败: {str(e)}")
            raise FileProcessingException(f"生成结果文件失败: {str(e)}") 