# 🚀 Dify Workflow 批量执行系统

> _AI-accelerated batch processing for Dify Workflows - 让批量任务执行更智能、更可靠_

---

## 🌟 项目概述

**这是一个实验性项目** - 基于 FastAPI 构建的 Dify Workflow 批量执行系统，专为解决 Dify Web 界面批量执行的痛点而生。

### 💡 为什么需要这个项目？

Dify 官方 Web 界面的批量执行功能存在以下问题：
- **前端执行限制**：大数据量时前端解析缓慢，用户等待时间长
- **中断风险**：页面刷新或网络中断导致全部任务失败
- **无状态恢复**：无法从中断点继续执行
- **缺乏监控**：无法实时监控执行进度和错误处理

本项目通过 **后端批量处理 + 智能缓存 + 错误恢复** 机制，彻底解决这些问题。

---

## ✨ 核心特性

| 功能模块 | 特性描述 | 技术亮点 |
|---------|---------|---------|
| 🔄 **智能批量执行** | Excel 模板导入，并发执行工作流 | 异步处理 + 连接池优化 |
| 📊 **实时监控面板** | 任务进度追踪，状态可视化 | WebSocket 实时通信 |
| 🛡️ **容错与恢复** | 中断恢复，失败重试，错误隔离 | 状态持久化 + 智能重试 |
| 🎯 **动态模板生成** | 基于 API 参数自动生成 Excel 模板 | Jinja2 模板引擎 |
| 🔧 **工作流配置管理** | Web 界面管理多个工作流配置 | 本地存储 + 配置验证 |
| 📈 **结果数据导出** | 支持多种格式的结果导出 | pandas + openpyxl |

---

## 🛠️ 技术栈

**后端框架**
- FastAPI + Pydantic (API 框架)
- SQLAlchemy + Alembic (数据库 ORM)
- aiohttp + httpx (异步 HTTP 客户端)

**数据处理**
- pandas + openpyxl (Excel 处理)
- Jinja2 (模板引擎)
- Redis (缓存和任务队列)

**前端界面**
- Alpine.js + Bootstrap 5 (响应式 UI)
- Chart.js (数据可视化)
- 本地化静态资源 (离线可用)

**容器化部署**
- Docker + Docker Compose (一键部署)
- 阿里云镜像源 (国内加速)
- 数据持久化 (挂载卷)

---

## 🚀 快速开始

### 环境要求
- Python 3.10+
- Redis (可选，用于任务队列)
- macOS / Linux / Windows

### 安装部署

#### 🐳 Docker 部署（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/WW-AI-Lab/dify-workflow-batch.git
cd dify-workflow-batch

# 2. 使用 Docker Compose 启动
docker-compose up -d

# 3. 查看服务状态
docker-compose ps
```

#### 🐍 本地部署

```bash
# 1. 克隆项目
git clone https://github.com/WW-AI-Lab/dify-workflow-batch.git
cd dify-workflow-batch

# 2. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env-example .env
# 编辑 .env 文件，配置你的 Dify API 相关参数

# 5. 启动服务
python main.py
```

### 访问服务
- **Web 界面**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

---

## 📋 使用流程

### 1️⃣ 配置工作流
访问 `/workflows` 页面，添加你的 Dify 工作流配置：
- 工作流名称和描述
- Dify API Base URL
- 工作流 API Key
- 结果输出模板 (Jinja2 格式)

### 2️⃣ 下载模板
系统自动获取工作流参数，生成对应的 Excel 输入模板

### 3️⃣ 批量执行
- 填写 Excel 模板数据
- 上传文件到 `/batch` 页面
- 启动批量执行任务
- 实时监控执行进度

### 4️⃣ 结果导出
任务完成后，下载包含所有执行结果的 Excel 文件

---

## 🏗️ 项目架构

```
dify-workflow-batch/
├── app/
│   ├── api/                 # REST API 路由
│   ├── core/               # 核心配置和数据库
│   ├── models/             # SQLAlchemy 数据模型
│   ├── services/           # 业务逻辑服务
│   │   ├── dify/          # Dify API 客户端
│   │   ├── batch/         # 批量执行服务
│   │   └── excel/         # Excel 处理服务
│   ├── tasks/              # 异步任务处理
│   ├── utils/              # 工具函数
│   └── web/               # Web 界面路由
├── static/                 # 前端静态资源
├── templates/              # Jinja2 HTML 模板
├── docs/                   # 项目文档
├── uploads/                # 上传文件目录
├── results/                # 结果文件目录
└── data/                   # SQLite 数据库
```

---

## 🔧 配置说明

### 核心配置项
```env
# Dify API 配置
DIFY_BASE_URL=https://api.dify.ai/v1
DIFY_TIMEOUT=30
DIFY_MAX_RETRIES=3

# 并发控制
MAX_CONCURRENT_TASKS=10
DEFAULT_BATCH_SIZE=100
TASK_TIMEOUT=3600

# 文件处理
MAX_FILE_SIZE=50MB
ALLOWED_EXTENSIONS=xlsx,xls,csv
```

### 数据库配置
```env
# 开发环境 (SQLite)
DATABASE_URL=sqlite:///./data/app.db

# 生产环境 (PostgreSQL)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dify_batch
```

---

## 🧪 AI 辅助开发说明

**本项目完全由 AI 辅助完成**，使用了以下 AI 工具：
- **Cursor IDE**: 代码生成和重构
- **GitHub Copilot**: 函数实现和测试用例
- **Claude/GPT**: 架构设计和文档编写

### 开发过程记录
- `docs/` 目录包含完整的开发过程文档
- `.cursor/rules` 包含 Cursor IDE 的上下文规则
- 每个关键决策都有对应的设计文档
---

## 效果截图

![image-20250614224456212](./assets/image-20250614224456212.png)

![image-20250614224544016](./assets/image-20250614224544016.png)

![image-20250614224618551](./assets/image-20250614224618551.png)

![image-20250614224710297](./assets/image-20250614224710297.png)

![image-20250614224800790](./assets/image-20250614224800790.png)

## ⚠️ 免责声明

**这是一个实验性项目**，主要用于：
- 技术验证和概念演示
- 学习 FastAPI + Dify API 集成
- AI 辅助开发流程探索

**不建议直接用于生产环境**，如需商用请联系获得专业支持。

---

## 🤝 联系方式

| 渠道 | 地址 | 用途 |
|------|------|------|
| 📧 **Email** | [toxingwang@gmail.com](mailto:toxingwang@gmail.com) | 技术交流 / 合作咨询 |
| 🐦 **X (Twitter)** | [@WW_AI_Lab](https://x.com/WW_AI_Lab) | 项目动态 / 技术分享 |
| 💬 **微信** | toxingwang | 深度交流，添加请注明来源 |

---

## 📜 开源协议

MIT License - 详见 [LICENSE](LICENSE) 文件

**使用须知**：
- ✅ 可自由使用、修改、分发
- ✅ 可用于商业项目（需自行承担风险）
- ❌ 不提供任何形式的质量保证
- ❌ 作者不承担使用后果责任

---

## 🙏 致谢

感谢以下开源项目和工具：
- [FastAPI](https://fastapi.tiangolo.com/) - 现代化的 Python Web 框架
- [Dify](https://dify.ai/) - 优秀的 LLM 应用开发平台
- [Alpine.js](https://alpinejs.dev/) - 轻量级前端框架
- [Bootstrap](https://getbootstrap.com/) - 响应式 UI 组件库

---

**⭐ 如果这个项目对你有帮助，欢迎 Star 支持！** 