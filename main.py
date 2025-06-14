"""
Dify Workflow批量执行系统 - 应用入口
"""
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import init_db
from app.api import api_router
from app.web import web_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化数据库
    await init_db()
    
    # 🆕 恢复被中断的批量任务
    try:
        from app.services.batch.task_recovery import task_recovery_service
        recovery_result = await task_recovery_service.recover_interrupted_tasks()
        
        if recovery_result["total_found"] > 0:
            print(f"🔄 任务恢复完成: 发现 {recovery_result['total_found']} 个中断任务，"
                  f"成功恢复 {recovery_result['recovered']} 个，失败 {recovery_result['failed']} 个")
        else:
            print("✅ 应用启动完成，没有发现需要恢复的任务")
            
    except Exception as e:
        print(f"⚠️ 任务恢复过程出现异常: {e}")
        # 不阻止应用启动，只记录错误
    
    yield
    # 关闭时清理资源
    pass


def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="基于FastAPI的Dify Workflow批量执行系统",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan
    )
    
    # 配置CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 挂载静态文件
    app.mount("/static", StaticFiles(directory="static"), name="static")
    
    # 注册路由
    app.include_router(api_router, prefix="/api")
    app.include_router(web_router)
    
    return app


# 创建应用实例
app = create_app()


@app.get("/")
async def root():
    """根路径重定向到Web界面"""
    return {"message": "Dify Workflow批量执行系统", "version": settings.APP_VERSION}


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "healthy", "version": settings.APP_VERSION}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.WEB_HOST,
        port=settings.WEB_PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    ) 