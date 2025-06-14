#!/usr/bin/env python3
"""
检查Excel文件结构
"""
import pandas as pd

df = pd.read_excel('test_upload_file.xlsx', sheet_name='批量数据', header=0)
print('Excel文件列名:', df.columns.tolist())
print('数据行数:', len(df))
print('前几行数据:')
print(df.head()) 