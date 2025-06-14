#!/usr/bin/env python3
"""
检查大文件格式脚本
专门用于检查9.4万条数据的Excel文件格式
"""

import pandas as pd
import os
from pathlib import Path
import sys

def check_large_excel_file(file_path):
    """检查大Excel文件的格式"""
    print(f"🔍 检查文件: {file_path}")
    print("=" * 60)
    
    # 检查文件是否存在
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    # 获取文件信息
    file_size = os.path.getsize(file_path)
    file_size_mb = file_size / 1024 / 1024
    print(f"📁 文件大小: {file_size_mb:.2f} MB")
    
    try:
        # 读取Excel文件信息
        print("📊 正在读取Excel文件...")
        
        # 首先检查工作表
        excel_file = pd.ExcelFile(file_path)
        sheet_names = excel_file.sheet_names
        print(f"📋 工作表列表: {sheet_names}")
        
        # 检查是否有"批量数据"工作表
        if "批量数据" not in sheet_names:
            print("❌ 缺少'批量数据'工作表")
            print("💡 请确保Excel文件包含名为'批量数据'的工作表")
            return False
        
        # 读取批量数据工作表（只读取前几行来检查格式）
        print("🔍 检查'批量数据'工作表格式...")
        df_sample = pd.read_excel(file_path, sheet_name="批量数据", header=0, nrows=10)
        
        print(f"📊 列信息:")
        for i, col in enumerate(df_sample.columns):
            print(f"   {i+1}. {col}")
        
        # 读取完整数据（可能需要一些时间）
        print("⏳ 正在读取完整数据（可能需要一些时间）...")
        df = pd.read_excel(file_path, sheet_name="批量数据", header=0, engine='openpyxl')
        
        print(f"📈 数据统计:")
        print(f"   总行数: {len(df)}")
        print(f"   总列数: {len(df.columns)}")
        
        # 检查列名
        columns = df.columns.tolist()
        print(f"📝 所有列名: {columns}")
        
        # 检查是否有执行结果列
        if "执行结果" in columns:
            print("✅ 发现'执行结果'列")
            columns.remove("执行结果")
        
        # 清理列名
        clean_columns = []
        for col in columns:
            clean_col = col.strip()
            if clean_col.endswith(' *'):
                clean_col = clean_col[:-2].strip()
            clean_columns.append(clean_col)
        
        print(f"🧹 清理后的参数列: {clean_columns}")
        
        # 检查数据完整性
        print("🔍 检查数据完整性...")
        
        # 过滤空行
        df_filtered = df.dropna(how='all')
        print(f"   过滤空行后: {len(df_filtered)} 行")
        
        # 跳过描述行和示例行
        if len(df_filtered) > 2:
            data_df = df_filtered.iloc[2:]  # 从第3行开始
            actual_data_rows = len(data_df.dropna(how='all'))
            print(f"   实际数据行: {actual_data_rows}")
            
            # 检查前几行数据
            print("📋 前5行数据示例:")
            for i, (idx, row) in enumerate(data_df.head().iterrows()):
                if i >= 5:
                    break
                row_data = {}
                for j, clean_col in enumerate(clean_columns):
                    if j < len(columns):
                        original_col = columns[j]
                        value = row[original_col]
                        if pd.isna(value):
                            row_data[clean_col] = None
                        else:
                            row_data[clean_col] = str(value).strip()
                print(f"   行{i+1}: {row_data}")
        
        # 检查常见的工作流参数
        common_params = ['query', 'search_term', 'keyword', 'text', 'input', 'content']
        found_params = []
        for param in common_params:
            if param in clean_columns:
                found_params.append(param)
        
        if found_params:
            print(f"✅ 发现常见参数: {found_params}")
        else:
            print("⚠️ 未发现常见的工作流参数名")
            print("💡 对于'亚马逊搜索词标签提取'工作流，常见参数可能包括:")
            print("   - query (搜索词)")
            print("   - search_term (搜索词)")
            print("   - keyword (关键词)")
            print("   - text (文本内容)")
        
        # 检查数据量是否合理
        if actual_data_rows > 50000:
            print(f"⚠️ 数据量较大({actual_data_rows}行)，建议:")
            print("   1. 分批处理，每批1-2万条数据")
            print("   2. 适当降低并发数(建议2-3)")
            print("   3. 增加超时时间(建议600秒以上)")
        
        print("✅ 文件格式检查完成")
        return True
        
    except Exception as e:
        print(f"❌ 文件检查失败: {str(e)}")
        print(f"错误类型: {type(e).__name__}")
        return False

def main():
    """主函数"""
    if len(sys.argv) != 2:
        print("使用方法: python check_large_file.py <文件路径>")
        print("示例: python check_large_file.py 'data/test11_template copy.xlsx'")
        return
    
    file_path = sys.argv[1]
    
    print("🚀 大文件格式检查工具")
    print("=" * 60)
    print("🎯 专门用于检查大量数据的Excel文件格式")
    print("📊 支持检查9万+条数据的文件")
    print("=" * 60)
    
    success = check_large_excel_file(file_path)
    
    if success:
        print("\n🎉 文件格式检查通过！")
        print("💡 建议:")
        print("   1. 确认工作流参数名称匹配")
        print("   2. 考虑分批处理大量数据")
        print("   3. 调整并发和超时设置")
    else:
        print("\n❌ 文件格式检查失败")
        print("💡 请根据上述提示修复文件格式")

if __name__ == "__main__":
    main() 