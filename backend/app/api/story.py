import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from app.models.story import AnalyzeIdeaRequest, GenerateOutlineRequest, GenerateScriptRequest, ChatRequest, RefineRequest
from app.services.llm_service import analyze_idea, generate_outline, generate_script, chat, refine

router = APIRouter(prefix="/api/v1/story")


def get_llm_config(request: Request):
    return {
        "api_key": request.headers.get("X-LLM-API-Key", ""),
        "base_url": request.headers.get("X-LLM-Base-URL", ""),
        "provider": request.headers.get("X-LLM-Provider", ""),
    }


@router.post("/analyze-idea")
async def api_analyze_idea(req: AnalyzeIdeaRequest, request: Request):
    return await analyze_idea(req.idea, req.genre, req.tone, **get_llm_config(request))


@router.post("/generate-outline")
async def api_generate_outline(req: GenerateOutlineRequest, request: Request):
    return await generate_outline(req.story_id, req.selected_setting, **get_llm_config(request))


@router.post("/chat")
async def api_chat(req: ChatRequest, request: Request):
    cfg = get_llm_config(request)

    async def event_stream():
        try:
            async for chunk in chat(req.story_id, req.message, **cfg):
                yield f"data: {chunk}\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/generate-script")
async def api_generate_script(req: GenerateScriptRequest, request: Request):
    cfg = get_llm_config(request)

    async def event_stream():
        try:
            async for scene in generate_script(req.story_id, **cfg):
                yield f"data: {json.dumps(scene, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/refine")
async def api_refine(req: RefineRequest, request: Request):
    return await refine(req.story_id, req.change_type, req.change_summary, **get_llm_config(request))
