"""
数据库配置和连接管理
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# 数据库元数据
metadata = MetaData()


class Base(DeclarativeBase):
    """数据库模型基类"""
    metadata = metadata


# 创建异步数据库引擎
def create_database_engine():
    """创建数据库引擎"""
    database_url = settings.DATABASE_URL
    
    # 处理SQLite异步连接
    if database_url.startswith("sqlite"):
        database_url = database_url.replace("sqlite://", "sqlite+aiosqlite://")
    
    # 处理PostgreSQL异步连接
    elif database_url.startswith("postgresql"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
    
    engine = create_async_engine(
        database_url,
        echo=settings.DEBUG,  # 在调试模式下显示SQL语句
        future=True,
        pool_pre_ping=True,  # 连接池预检查
    )
    
    logger.info(f"数据库引擎创建完成: {database_url}")
    return engine


# 创建数据库引擎实例
engine = create_database_engine()

# 创建会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=True,
    autocommit=False,
)


async def get_db() -> AsyncSession:
    """获取数据库会话依赖"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"数据库会话错误: {e}")
            raise
        finally:
            await session.close()


def get_db_session():
    """获取数据库会话上下文管理器"""
    return AsyncSessionLocal()


async def init_db():
    """初始化数据库"""
    try:
        # 导入所有模型以确保它们被注册
        from app.models.base import Base as ModelBase
        from app.models.workflow import Workflow, WorkflowConfig
        from app.models.batch_task import BatchTask, TaskExecution, ExecutionLog
        
        async with engine.begin() as conn:
            # 创建所有表
            await conn.run_sync(ModelBase.metadata.create_all)
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise


async def close_db():
    """关闭数据库连接"""
    await engine.dispose()
    logger.info("数据库连接已关闭") 