"""
Web界面路由
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")
router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """首页"""
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/workflows", response_class=HTMLResponse)
async def workflows_page(request: Request):
    """工作流列表页面"""
    return templates.TemplateResponse("workflows.html", {"request": request})


@router.get("/batch", response_class=HTMLResponse)
async def batch_page(request: Request):
    """批量执行页面"""
    return templates.TemplateResponse("batch.html", {"request": request})


@router.get("/tasks", response_class=HTMLResponse)
async def tasks_page(request: Request):
    """任务管理页面"""
    return templates.TemplateResponse("tasks.html", {"request": request}) 