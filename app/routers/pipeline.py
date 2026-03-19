from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from app.schemas.pipeline import PipelineStatusResponse, PipelineStatus
from app.schemas.storyboard import Storyboard
from app.services.storyboard import parse_script_to_storyboard

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])

_pipeline: dict = {}


def _get_or_create(project_id: str) -> dict:
    if project_id not in _pipeline:
        _pipeline[project_id] = {
            "status": PipelineStatus.PENDING,
            "progress": 0,
            "current_step": "等待开始",
            "error": None,
        }
    return _pipeline[project_id]


@router.post("/{project_id}/storyboard", response_model=Storyboard)
async def generate_storyboard(
    project_id: str,
    script: str = Query(..., description="Markdown 格式的视听剧本"),
    provider: str = Query(..., description="LLM provider: claude/openai/qwen/zhipu/gemini"),
    model: str = Query(None, description="具体模型名，不填则用 provider 默认值"),
):
    state = _get_or_create(project_id)
    state.update(status=PipelineStatus.STORYBOARD, progress=10, current_step="解析分镜中")

    try:
        shots = await parse_script_to_storyboard(script, provider=provider, model=model)
    except Exception as e:
        state.update(status=PipelineStatus.FAILED, error=str(e))
        raise HTTPException(status_code=500, detail=f"分镜解析失败: {e}")

    state.update(progress=30, current_step="分镜解析完成")
    return Storyboard(shots=shots)


@router.post("/{project_id}/generate-assets")
async def generate_assets(project_id: str, background_tasks: BackgroundTasks):
    state = _get_or_create(project_id)
    state.update(status=PipelineStatus.GENERATING_ASSETS, progress=30, current_step="生成 TTS 和图片")

    async def _mock_task():
        import asyncio
        await asyncio.sleep(2)
        state.update(progress=60, current_step="资产生成完成")

    background_tasks.add_task(_mock_task)
    return {"project_id": project_id, "message": "资产生成任务已启动"}


@router.post("/{project_id}/render-video")
async def render_video(project_id: str, background_tasks: BackgroundTasks):
    state = _get_or_create(project_id)
    state.update(status=PipelineStatus.RENDERING_VIDEO, progress=65, current_step="图生视频中")

    async def _mock_task():
        import asyncio
        await asyncio.sleep(3)
        state.update(progress=85, current_step="视频渲染完成")

    background_tasks.add_task(_mock_task)
    return {"project_id": project_id, "message": "视频渲染任务已启动"}


@router.get("/{project_id}/status", response_model=PipelineStatusResponse)
async def get_status(project_id: str):
    state = _get_or_create(project_id)
    return PipelineStatusResponse(
        project_id=project_id,
        status=state["status"],
        progress=state["progress"],
        current_step=state["current_step"],
        error=state["error"],
    )


@router.post("/{project_id}/stitch")
async def stitch_video(project_id: str, background_tasks: BackgroundTasks):
    state = _get_or_create(project_id)
    state.update(status=PipelineStatus.STITCHING, progress=90, current_step="FFmpeg 合成中")

    async def _mock_task():
        import asyncio
        await asyncio.sleep(2)
        state.update(status=PipelineStatus.COMPLETE, progress=100, current_step="视频合成完成")

    background_tasks.add_task(_mock_task)
    return {"project_id": project_id, "message": "视频合成任务已启动"}
