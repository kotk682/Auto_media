from fastapi import APIRouter, HTTPException
from ulid import ULID
from app.schemas.interview import (
    ProjectInitRequest, ProjectInitResponse,
    ChatRequest, InterviewStateResponse, InterviewStage
)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

# In-memory store for mock
_projects: dict = {}

INTERVIEW_FLOW = [
    (InterviewStage.TOPIC,    "这个视频的核心主题是什么？",         "例如：介绍一款新的咖啡机产品"),
    (InterviewStage.AUDIENCE, "目标受众是谁？",                    "例如：25-35岁的都市白领"),
    (InterviewStage.TONE,     "视频的风格和语气是什么？",           "例如：轻松幽默、专业严肃、温暖感人"),
    (InterviewStage.DURATION, "视频时长大概多少秒？",               "例如：60秒、90秒、120秒"),
]

STAGE_PROGRESS = {
    InterviewStage.TOPIC: 0,
    InterviewStage.AUDIENCE: 25,
    InterviewStage.TONE: 50,
    InterviewStage.DURATION: 75,
    InterviewStage.COMPLETE: 100,
}


@router.post("/init", response_model=ProjectInitResponse)
async def init_project(body: ProjectInitRequest):
    project_id = str(ULID())
    _projects[project_id] = {
        "seed_idea": body.seed_idea,
        "stage": InterviewStage.TOPIC,
        "answers": {},
    }
    return ProjectInitResponse(
        project_id=project_id,
        message="项目已创建，开始访谈",
        first_question=INTERVIEW_FLOW[0][1],
    )


@router.post("/{project_id}/chat", response_model=InterviewStateResponse)
async def chat(project_id: str, body: ChatRequest):
    project = _projects.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    current_stage = project["stage"]
    project["answers"][current_stage] = body.answer

    # Advance state machine
    stages = [s for s, _, _ in INTERVIEW_FLOW]
    current_idx = stages.index(current_stage)
    next_idx = current_idx + 1

    if next_idx >= len(INTERVIEW_FLOW):
        project["stage"] = InterviewStage.COMPLETE
        return InterviewStateResponse(
            project_id=project_id,
            stage=InterviewStage.COMPLETE,
            question="访谈完成！正在生成脚本...",
            progress=100,
            is_complete=True,
        )

    next_stage, next_question, next_hint = INTERVIEW_FLOW[next_idx]
    project["stage"] = next_stage

    return InterviewStateResponse(
        project_id=project_id,
        stage=next_stage,
        question=next_question,
        hint=next_hint,
        progress=STAGE_PROGRESS[next_stage],
        is_complete=False,
    )


@router.get("/{project_id}/script")
async def get_script(project_id: str):
    project = _projects.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project["stage"] != InterviewStage.COMPLETE:
        raise HTTPException(status_code=400, detail="Interview not complete yet")

    # Mock script
    return {
        "project_id": project_id,
        "script": f"# 视频脚本\n\n**主题**: {project['answers'].get(InterviewStage.TOPIC, '')}\n"
                  f"**受众**: {project['answers'].get(InterviewStage.AUDIENCE, '')}\n"
                  f"**风格**: {project['answers'].get(InterviewStage.TONE, '')}\n"
                  f"**时长**: {project['answers'].get(InterviewStage.DURATION, '')}\n\n"
                  f"[AI 生成脚本内容将在此处显示]",
    }
