# Dify API 输出解析逻辑修复

## 问题描述

在批量任务完成后，解析结果生成表格返回时，原有的逻辑无法正确解析 Dify API 返回的 `outputs` 字段内容。

### 原始问题
- Dify API 返回的数据结构如下：
```json
{
  "id": "8f7613d2-47ff-42be-beb3-6c910e4b66a3",
  "workflow_id": "eea3cbd6-154c-431e-8589-5adc5755e2ab",
  "status": "succeeded",
  "outputs": {"text": "`版型词`"},
  "error": null,
  "elapsed_time": 3.310347281396389,
  "total_tokens": 883,
  "total_steps": 3,
  "created_at": 1749820464,
  "finished_at": 1749820468
}
```

- 原有代码只处理了 `output` 字段，无法正确提取 `outputs` 中的内容
- `outputs` 字段中的键名可能是 `text`、`result` 或其他任意名称
- 可能存在多个键值对的情况

## 解决方案

### 修改文件
- `app/services/batch/batch_processor.py` 中的 `_generate_result_file` 方法

### 修改逻辑
1. **优先处理 `outputs` 字段**：检查是否存在 `outputs` 字段，并提取其中所有键值对的内容
2. **支持嵌套结构**：处理 `outputs.outputs` 的嵌套情况
3. **多值处理**：如果有多个键值对，用换行符连接；单个值直接返回
4. **向后兼容**：保持对旧格式 `output` 字段的支持
5. **系统字段过滤**：过滤掉系统字段（如 `id`、`workflow_id` 等）

### 支持的数据格式

#### 1. 标准 Dify API 格式
```json
{
  "outputs": {"text": "`版型词`"}
}
```
**输出**: `版型词`

#### 2. 多个输出字段
```json
{
  "outputs": {
    "title": "标题内容",
    "content": "正文内容", 
    "summary": "摘要内容"
  }
}
```
**输出**: 
```
标题内容
正文内容
摘要内容
```

#### 3. 嵌套 outputs 结构
```json
{
  "outputs": {
    "outputs": {
      "result": "处理结果",
      "confidence": "0.95"
    }
  }
}
```
**输出**:
```
处理结果
0.95
```

#### 4. 旧格式兼容
```json
{
  "output": "直接输出内容"
}
```
**输出**: 直接输出内容

#### 5. 空输出处理
```json
{
  "outputs": {}
}
```
**输出**: 无输出内容

## 测试验证

所有测试用例均已通过验证，确保修改后的逻辑能够正确处理各种 Dify API 返回格式。

## 影响范围

- 批量任务结果文件生成
- Excel 表格中的"执行结果"列内容
- 不影响其他功能模块

## 部署说明

修改已应用到生产代码，服务重启后即可生效。用户在下载批量任务结果时，将看到正确解析的 Dify API 输出内容。 