"""
应用配置管理
"""
import os
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置类"""
    
    # ======================
    # 应用基础配置
    # ======================
    APP_NAME: str = Field(default="Dify Workflow Batch System", description="应用名称")
    APP_VERSION: str = Field(default="1.0.0", description="应用版本")
    DEBUG: bool = Field(default=False, description="调试模式")
    TEST_MODE: bool = Field(default=False, description="测试模式")
    SECRET_KEY: str = Field(default="dev-secret-key-change-in-production", description="应用密钥")
    
    # ======================
    # Dify API 配置
    # ======================
    DIFY_BASE_URL: str = Field(default="https://api.dify.ai/v1", description="Dify API基础URL")
    DIFY_TIMEOUT: int = Field(default=30, description="API请求超时时间（秒）")
    DIFY_MAX_RETRIES: int = Field(default=3, description="API请求最大重试次数")
    DIFY_RETRY_DELAY: int = Field(default=1, description="API请求重试延迟（秒）")
    
    # ======================
    # 数据库配置
    # ======================
    DATABASE_URL: str = Field(default="sqlite:///./data/app.db", description="数据库连接URL")
    
    # ======================
    # Redis配置
    # ======================
    REDIS_URL: Optional[str] = Field(default=None, description="Redis连接URL")
    REDIS_PASSWORD: Optional[str] = Field(default=None, description="Redis密码")
    REDIS_DB: int = Field(default=0, description="Redis数据库编号")
    
    # ======================
    # 文件存储配置
    # ======================
    UPLOAD_DIR: str = Field(default="./uploads", description="上传文件目录")
    RESULT_DIR: str = Field(default="./results", description="结果文件目录")
    MAX_FILE_SIZE: str = Field(default="50MB", description="最大文件大小")
    ALLOWED_EXTENSIONS: str = Field(default="xlsx,xls,csv", description="允许的文件扩展名")
    
    # ======================
    # 任务执行配置
    # ======================
    MAX_CONCURRENT_TASKS: int = Field(default=10, description="最大并发任务数")
    DEFAULT_BATCH_SIZE: int = Field(default=100, description="默认批处理大小")
    TASK_TIMEOUT: int = Field(default=3600, description="任务超时时间（秒）")
    PROGRESS_UPDATE_INTERVAL: int = Field(default=5, description="进度更新间隔（秒）")
    
    # ======================
    # Web界面配置
    # ======================
    WEB_HOST: str = Field(default="0.0.0.0", description="Web服务主机")
    WEB_PORT: int = Field(default=8000, description="Web服务端口")
    CORS_ORIGINS: str = Field(default="*", description="CORS允许的源")
    
    # ======================
    # 日志配置
    # ======================
    LOG_LEVEL: str = Field(default="INFO", description="日志级别")
    LOG_FILE: str = Field(default="./logs/app.log", description="日志文件路径")
    LOG_MAX_SIZE: str = Field(default="10MB", description="日志文件最大大小")
    LOG_BACKUP_COUNT: int = Field(default=5, description="日志文件备份数量")
    
    # ======================
    # Celery配置
    # ======================
    CELERY_BROKER_URL: Optional[str] = Field(default=None, description="Celery消息代理URL")
    CELERY_RESULT_BACKEND: Optional[str] = Field(default=None, description="Celery结果后端URL")
    
    # ======================
    # 安全配置
    # ======================
    JWT_SECRET_KEY: Optional[str] = Field(default=None, description="JWT密钥")
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT算法")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, description="JWT访问令牌过期时间（分钟）")
    
    # API限流配置
    RATE_LIMIT_PER_MINUTE: int = Field(default=100, description="每分钟API请求限制")
    RATE_LIMIT_BURST: int = Field(default=20, description="API请求突发限制")
    

    
    def get_max_file_size_bytes(self) -> int:
        """获取最大文件大小（字节）"""
        size_str = self.MAX_FILE_SIZE.upper()
        if size_str.endswith("MB"):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith("KB"):
            return int(size_str[:-2]) * 1024
        elif size_str.endswith("GB"):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        else:
            return int(size_str)
    
    def get_allowed_extensions(self) -> List[str]:
        """获取允许的文件扩展名列表"""
        return [ext.strip() for ext in self.ALLOWED_EXTENSIONS.split(",")]
    
    def get_cors_origins(self) -> List[str]:
        """获取CORS允许的源列表"""
        if self.CORS_ORIGINS.startswith("[") and self.CORS_ORIGINS.endswith("]"):
            import json
            try:
                return json.loads(self.CORS_ORIGINS)
            except json.JSONDecodeError:
                pass
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    def ensure_directories(self):
        """确保必要的目录存在"""
        directories = [
            self.UPLOAD_DIR,
            self.RESULT_DIR,
            os.path.dirname(self.LOG_FILE),
            os.path.dirname(self.DATABASE_URL.replace("sqlite:///", "")) if "sqlite" in self.DATABASE_URL else None
        ]
        
        for directory in directories:
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)


# 创建全局配置实例
settings = Settings()

# 确保必要的目录存在
settings.ensure_directories() 